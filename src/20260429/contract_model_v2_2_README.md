# contract_model v2.2 / ratio_forward_product_grammars v2.2 README

## 1. 今回の主題

v2.2 の主題は **Target / TARF の表現方法の一般化** です。

v2.1 では Target を概ね次のように表していました。

```text
TargetMetric = AMOUNT | POINTS
TargetAccumulationSide = CLIENT_GAIN | CLIENT_LOSS
```

これは代表的な ratio-forward TARF には便利ですが、次のケースでは弱くなります。

- Amount TARF
- Point / pips TARF
- Count TARF
- 損失側 target も独立に累積する TARF
- 実際の payoff amount と累積対象が異なる商品
- 複数 option leg を 1 period package として束ね、その package net payoff を累積する商品
- hit 後に全部の future CF ではなく、特定 period range / group だけを KO する商品

そこで v2.2 では、Target を以下のように分解しました。

```text
TargetLifecycleRule
  TargetReachedCondition
    AccumulatorSpec
      AccumulationValueRule
      MetricSelection
      AccumulationUnit
  effects
    DeactivateComponentsEffect(ComponentSelector)
```

---

## 2. AccumulationValueRule

v2.2 では、Target に積む 1 period / 1 event 分の値を `AccumulationValueRule` として first-class にしました。

```text
AccumulationValueRule
  AmountAccumulationValueRule
  FxPipSpreadAccumulationValueRule
  CountAccumulationValueRule
  PackageNetAmountAccumulationValueRule
```

### AmountAccumulationValueRule

`AmountRule` は Target 外でも使う汎用 determination rule です。

たとえば以下に使えます。

- AmountBasedCouponCalculation
- FX window cashflow
- option cash settlement
- digital amount
- redemption amount

Target が amount を累積したい場合は、その汎用 `AmountRule` を `AmountAccumulationValueRule` で包みます。

```python
AmountAccumulationValueRule(
    amount_rule=some_amount_rule,
    sign_convention=SignedByParty("CLIENT"),
)
```

つまり、

```text
AmountRule = 支払い金額を決める汎用 rule
AmountAccumulationValueRule = その amount を target 累積値として読む adapter
```

です。

### FxPipSpreadAccumulationValueRule

Point / pips target は amount ではありません。

```python
FxPipSpreadAccumulationValueRule(
    observed_fx=usd_jpy_observation,
    reference=Decimal("150.00"),
    direction=SpreadDirection.LEFT_MINUS_RIGHT,
    pip_size=Decimal("0.01"),
)
```

この場合、

```text
LEFT_MINUS_RIGHT:
  (observed_fx - reference) / pip_size

RIGHT_MINUS_LEFT:
  (reference - observed_fx) / pip_size
```

を返します。

重要なのは、`raw_value` と曖昧にせず、差分の向きを `SpreadDirection` で明示することです。

### CountAccumulationValueRule

Count TARF は、条件 hit を数えます。

```python
CountAccumulationValueRule(
    condition=spot_above_strike_condition,
    count_value=Decimal("1"),
)
```

### PackageNetAmountAccumulationValueRule

複数 option leg を 1 period package として束ね、その net amount を累積するための rule です。

```python
PackageNetAmountAccumulationValueRule(
    group_selector=GroupComponentSelector(group_kind="FX_OPTION_PACKAGE"),
    sign_convention=SignedByParty("CLIENT"),
    currency=Currency.JPY,
)
```

これは、たとえば次のような商品に対応するためです。

```text
period i:
  short put
  long call K1
  long call K2 with KI

Target:
  period i の package net payoff を累積
```

---

## 3. MetricSelection

`ClientGain / ClientLoss` は廃止しました。

代わりに、`AccumulationValueRule` が返す符号付き値 `x` に対して、どの部分を累積するかを指定します。

```text
POSITIVE_PART = max(x, 0)
NEGATIVE_PART = max(-x, 0)
SIGNED        = x
ABSOLUTE      = abs(x)
```

これにより、損失側 target も別 accumulator として自然に表現できます。

```python
gain_accumulator:
  value_rule = AmountAccumulationValueRule(...)
  selection = POSITIVE_PART

loss_accumulator:
  value_rule = AmountAccumulationValueRule(...)
  selection = NEGATIVE_PART
```

---

## 4. ComponentSelector

Target hit 後に何を KO / deactivate するかは、`ComponentSelector` で表します。

```text
ComponentSelector
  ExplicitComponentSelector
  PeriodTagComponentSelector
  TriggerRelativePeriodSelector
  GroupComponentSelector
  TriggerRelativeGroupComponentSelector
```

これにより、以下が表せます。

```text
全 component を止める
period 3 以降だけ止める
period 3 から 8 だけ止める
hit period の次期以降を止める
FX_OPTION_PACKAGE group だけ止める
coupon leg だけ止める
```

Target の「累積対象」と「KO 対象」は分離しています。

```text
累積対象:
  AccumulationValueRule + AccumulationTiming

KO 対象:
  DeactivateComponentsEffect + ComponentSelector
```

---

## 5. Period / PeriodDateBinding / PeriodComponentGroup

v2.2 では `ContractPeriod` を first-class に導入しました。

ただし、Period は「単一 fixing date を共有する単位」ではありません。

```text
Period =
  契約上・商品設計上、同じ economic episode として束ねたい単位
```

したがって、同じ period 内に複数の fixing / observation があってよいです。

```text
period_1:
  short_put fixing
  long_call fixing
  KI observation
  target accumulation date
  package payment date
```

それぞれの日付は `PeriodDateBinding` で owner ごとに持ちます。

```python
PeriodDateBinding(
    period_id="period_1",
    owner_id="period_1_long_call_k2_ki_rule",
    owner_type="RULE",
    date_role=DateRole.OBSERVATION,
    purpose="long_call_k2_knock_in_observation",
    date_value=date(2026, 1, 25),
)
```

複数 component を 1 period package として束ねる場合は `PeriodComponentGroup` を使います。

```python
PeriodComponentGroup(
    group_id="period_1_option_package",
    period_id="period_1",
    group_kind="FX_OPTION_PACKAGE",
    component_ids=("period_1_short_put", "period_1_call_k1", "period_1_call_k2"),
)
```

---

## 6. ratio_forward_product_grammars_v2_2_full.py

代表例を 3 つ入れています。

### Coupon Swap + GAP + Point Target

```python
build_example_coupon_swap_gap_wko_v2_2()
```

- Coupon Swap form
- GAP
- sold-side KI
- point / pips target

### FX Option Package + TWO_STAGE + Amount Target

```python
build_example_fx_option_package_two_stage_target_v2_2()
```

- FX Option Package form
- per-period option package
- package net amount target
- target hit 後に affected period range を KO

### FX Option Package + Count TARF

```python
build_example_fx_option_package_count_tarf_v2_2()
```

- CountAccumulationValueRule
- condition hit を count
- count が target に達したら KO

---

## 7. 実行確認

以下を確認済みです。

```python
import ratio_forward_product_grammars_v2_2_full as rf

b1 = rf.build_example_coupon_swap_gap_wko_v2_2()
b2 = rf.build_example_fx_option_package_two_stage_target_v2_2()
b3 = rf.build_example_fx_option_package_count_tarf_v2_2()
```

それぞれ `form.validate()` を通過しています。

---

## 8. 注意

v2.2 はあくまで「設計の筋」を優先した prototype です。

特に以下はまだ今後の発展余地があります。

- `PackageNetAmountAccumulationValueRule` の実際の generic valuation
- trigger-relative selector に runtime の hit period を渡す generic event engine
- period template から component group を生成する authoring layer
- direct dependency と registry/id reference の hybrid 化
