# Contract Model V2 / Ratio-Forward Grammar V2 成果物

## 目的

この成果物は、従来の `Formula` 中心設計をやめ、金融契約を次の軸で再構成したものです。

1. Reference / Observable
2. Event / Schedule
3. Economic Action / Component
4. Determination Rule
5. Lifecycle / State Rule
6. Overlay / Modifier
7. Condition / Trigger / Effect

特に重要なのは、`Formula` を万能箱として扱わないことです。

- coupon rate は `RateRule`
- coupon の決定方法は `CouponDeterminationRule`
- payoff は `PayoffRule`
- notional / amount は `QuantityRule`
- MtM reset は `MtMResetQuantityRule` + `NotionalResetLifecycleRule`
- TARGET は `AccumulatorSpec` + `TargetReachedCondition` + `TargetLifecycleRule`
- KI / KO / WKO は `ObservationRule` + `BarrierCondition` + `EventLifecycleRule`

として分けています。

---

## ファイル

### `contract_model_v2_full.py`

共通モデルです。以下を含みます。

- `ContractFormV2`
- `ObservableRef`
- `ObservationRule`
- `BarrierCondition`
- `TargetReachedCondition`
- `FixedQuantityRule`
- `MtMResetQuantityRule`
- `FixedRateRule`
- `FloatingRateRule`
- `VanillaOptionPayoffRule`
- `FxForwardPayoffRule`
- `CouponSwapExchangePayoffRule`
- `CouponStreamLeg`
- `FxOptionExerciseLeg`
- `AccumulatorSpec`
- `EventLifecycleRule`
- `TargetLifecycleRule`
- `NotionalResetLifecycleRule`
- `RuntimeStateV2`

### `ratio_forward_product_grammars_v2_full.py`

Ratio-forward 系の Product Grammar v2 です。

- Coupon Swap form
- FX Option Package form
- GAP / RANGE_GAP / COLLAR / TWO_STAGE / NORMAL
- sold-side KI
- WKO
- TARGET
- period expansion
- series simulation
- representative examples

---

## 設計上の大きな変更

### 1. Observation を first-class にした

旧設計では `BarrierPredicate` の中に観測対象・観測日・判定条件が混在していました。

v2 では次のように分けています。

```text
ObservableRef
  何を見るか

ObservationRule
  いつ・どの様式で見るか

BarrierCondition
  見た値をどう判定するか
```

これにより、floating fixing、FX fixing、barrier、WKO、MtM reset、autocall 判定を共通の観測モデルに乗せられます。

### 2. Formula を廃止気味にし、Rule に分けた

旧 `Formula` は以下をまとめて背負っていました。

- coupon rate
- payoff
- MtM reset
- digital condition
- memory wrapper
- ratio-forward coupon exchange semantics

v2 では、それぞれを意味に応じて分けています。

```text
DeterminationRule
  ├─ QuantityRule
  ├─ RateRule
  ├─ PayoffRule
  └─ CouponDeterminationRule

LifecycleRule
  ├─ EventLifecycleRule
  ├─ TargetLifecycleRule
  └─ NotionalResetLifecycleRule

OverlayRule
  ├─ CapFloorOverlay
  ├─ LeverageOverlay
  ├─ MemoryOverlay
  └─ StepOverlay
```

### 3. Leg は action container とした

`CouponStreamLeg` は fixed / floating / structured に分裂させず、action container として維持しています。

```text
CouponStreamLeg
  coupon payment stream という action を表す

CouponDeterminationRule
  その coupon amount/rate/payoff をどう決めるかを表す
```

これにより、fixed coupon、floating coupon、range accrual、PRDC、ratio-forward coupon swap leg を leg class 爆発なしに扱えます。

### 4. TARGET は Formula ではなく Accumulator + Lifecycle

TARGET は以下に分解しました。

```text
AccumulatorSpec
  何を累積するか

TargetReachedCondition
  閾値到達判定

TargetLifecycleRule
  到達時に何を止めるか、hit CF をどう扱うか
```

### 5. MtM は Formula ではなく Quantity + Lifecycle

MtM notional reset は以下に分解しました。

```text
ObservationRule
  FX や index を見る

MtMResetQuantityRule
  新 notional を決める

NotionalResetLifecycleRule
  state を更新する
```

---

## Ratio-forward v2 の使い方

```python
from decimal import Decimal
from ratio_forward_product_grammars_v2_full import (
    build_example_coupon_swap_gap_wko_v2,
    build_example_fx_option_package_two_stage_target_v2,
    simulate_ratio_forward_series_v2,
    D,
)

built = build_example_coupon_swap_gap_wko_v2()
result = simulate_ratio_forward_series_v2(
    built,
    spot_by_fixing_date={
        built.period_specs[0].fixing_date: D("149"),
        built.period_specs[1].fixing_date: D("161"),
        built.period_specs[2].fixing_date: D("155"),
        built.period_specs[3].fixing_date: D("150"),
    },
    ki_observation_by_date={
        built.period_specs[0].ki_observation_date: D("149"),
        built.period_specs[1].ki_observation_date: D("161"),
        built.period_specs[2].ki_observation_date: D("155"),
        built.period_specs[3].ki_observation_date: D("150"),
    },
    wko_observation_by_date={
        built.period_specs[1].fixing_date: D("161"),
    },
)

print(result.terminated)
print(result.termination_period_index)
```

---

## 代表例の意味

### Coupon Swap + GAP + WKO

`build_example_coupon_swap_gap_wko_v2()` は以下を作ります。

- `ContractFormV2(form_kind="COUPON_SWAP_RATIO_FORWARD_V2")`
- 2 本の `CouponStreamLeg`
- `CouponSwapExchangePayoffRule`
- `ObservableRef("obs_fx")`
- fixing observation rule
- WKO observation rule
- WKO barrier condition
- WKO lifecycle rule

Coupon Swap form では sold-side KI は explicit option mechanism ではなく、coupon determination 側の意味に吸収されます。

### FX Option Package + TWO_STAGE + TARGET

`build_example_fx_option_package_two_stage_target_v2()` は以下を作ります。

- `ContractFormV2(form_kind="FX_OPTION_PACKAGE_RATIO_FORWARD_V2")`
- per-period `FxOptionExerciseLeg`
- per-period quantity rules
- premium transfer
- `AccumulatorSpec`
- `TargetReachedCondition`
- `TargetLifecycleRule`

FX Option Package form では sold-side KI がある場合、per-period `ObservationRule` + `BarrierCondition` + `EventLifecycleRule` として explicit に表現されます。

---

## 検証済み事項

作成時に以下を確認しています。

```bash
PYTHONPATH=/mnt/data python -S -m py_compile /mnt/data/contract_model_v2_full.py
PYTHONPATH=/mnt/data python -S -m py_compile /mnt/data/ratio_forward_product_grammars_v2_full.py
PYTHONPATH=/mnt/data python -S /mnt/data/ratio_forward_product_grammars_v2_full.py
```

実行例では以下になります。

```text
COUPON_SWAP_RATIO_FORWARD_V2 True 2
FX_OPTION_PACKAGE_RATIO_FORWARD_V2 True 2
```

---

## 注意

この成果物は v1 互換性より、v2 の意味論の筋を優先しています。

特に、旧 `FormulaBinding` との完全な backward compatibility adapter はまだ入れていません。必要なら次段階で、

```python
def upgrade_contract_form_v1_to_v2(...): ...
```

または、旧 ratio-forward grammar から v2 builder への adapter を追加できます。
