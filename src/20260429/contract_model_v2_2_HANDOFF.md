# 次チャット引き継ぎ: contract_model v2.2 / Target 表現 / Period 導入

## 0. 現在の成果物

このチャットでは v2.1 成果物を土台に、Target / TARF 表現を再設計して v2.2 を作成した。

成果物:

- `contract_model_v2_2_full.py`
- `ratio_forward_product_grammars_v2_2_full.py`
- `contract_model_v2_2_README.md`

v2.2 は v2.1 の以下を引き継ぐ。

- `Formula` 中心設計をやめる
- `RateRule`, `AmountRule`, `QuantityRule`, `PayoffRule` を分離
- `CouponStreamLeg` から曖昧な `coupon_rule_id` を廃止
- `RateBasedCouponCalculation` / `AmountBasedCouponCalculation` を分離
- `AmountRule` は Target 外でも使う汎用 determination として残す

---

## 1. 今回の主題: Target 表現

ユーザーの問題意識:

1. Amount TARF と Point TARF は固定 notional なら変換できても、notional が途中で変わると互換でなくなる。
2. Count TARF もある。
3. 実際の交換金額と累積対象が一致するとは限らない。
4. `ClientGain / ClientLoss` は主観的なので避けたい。
5. 損失側 target も独立に累積して KO する TARF がある。
6. KO する対象 CF は全部とは限らず、period range / package range で指定したい。

これを踏まえて、v2.2 では `TargetMetric = AMOUNT | POINTS` と `TargetAccumulationSide = CLIENT_GAIN | CLIENT_LOSS` を廃止した。

---

## 2. 新しい Target の基本構造

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

### AccumulationValueRule

Target に積む 1 period / 1 event 分の値を表す。

```text
AccumulationValueRule
  AmountAccumulationValueRule
  FxPipSpreadAccumulationValueRule
  CountAccumulationValueRule
  PackageNetAmountAccumulationValueRule
```

### MetricSelection

`AccumulationValueRule` が返す符号付き値 `x` に対してどの部分を積むか。

```text
POSITIVE_PART = max(x, 0)
NEGATIVE_PART = max(-x, 0)
SIGNED        = x
ABSOLUTE      = abs(x)
```

旧 `CLIENT_GAIN` は、たとえば `SignedByParty(party_id) + POSITIVE_PART` に相当する。  
旧 `CLIENT_LOSS` は、同じ符号規約に対する `NEGATIVE_PART` に相当する。

---

## 3. AmountRule と AccumulationValueRule の関係

重要な合意:

```text
AmountRule は Target 外でも使う汎用 determination として残す。
Target では AccumulationValueRule を導入する。
Amount target は AmountAccumulationValueRule として内部で AmountRule を参照する。
Point target は FxPipSpreadAccumulationValueRule として直接 observation / reference / direction / pip_size を持つ。
Count target は CountAccumulationValueRule とする。
```

つまり、

```text
AmountRule =
  実際に支払う amount / settlement amount を決める汎用 rule

AccumulationValueRule =
  Target に積む値を決める target 専用 rule
```

実際の payoff amount と target accumulation amount が一致するなら同じ AmountRule を再利用できる。  
異なるなら別の AccumulationValueRule を定義すればよい。

---

## 4. Point / pips target の方向

`raw_value` というだけでは、`spot - strike` なのか `strike - spot` なのかが曖昧になる。

そこで `SpreadDirection` を導入した。

```text
LEFT_MINUS_RIGHT
RIGHT_MINUS_LEFT
```

`FxPipSpreadAccumulationValueRule` は以下を持つ。

```python
observed_fx
reference
direction
pip_size
```

意味:

```text
LEFT_MINUS_RIGHT:
  (observed_fx - reference) / pip_size

RIGHT_MINUS_LEFT:
  (reference - observed_fx) / pip_size
```

この結果に `MetricSelection` をかける。

---

## 5. 損失側 target

損失側 target は特別な enum ではなく、別 accumulator として表す。

```text
gain_accumulator:
  value_rule = AmountAccumulationValueRule(...)
  selection = POSITIVE_PART

loss_accumulator:
  value_rule = AmountAccumulationValueRule(...)
  selection = NEGATIVE_PART
```

これにより、利益側・損失側を独立に累積し、それぞれ target 到達時に KO できる。

partial hit CF を扱う場合は、どちらの accumulator が hit したかが重要なので、単純に OR condition にまとめすぎない方がよい。将来的には `TargetHitResult` / priority / lifecycle group が必要。

---

## 6. KO 対象範囲

Target の累積対象と KO 対象は分ける。

```text
累積対象:
  AccumulationValueRule + AccumulationTiming

KO 対象:
  DeactivateComponentsEffect + ComponentSelector
```

v2.2 で入れた selector:

```text
ExplicitComponentSelector
PeriodTagComponentSelector
TriggerRelativePeriodSelector
GroupComponentSelector
TriggerRelativeGroupComponentSelector
```

これで以下を表せる。

- 明示 component list を止める
- period i 以降を止める
- period i から j までを止める
- hit period の次期以降を止める
- FX_OPTION_PACKAGE group だけ止める

---

## 7. Period を first-class にした理由

議論中に、複数 option leg からなる package に TARF をつける例が出た。

例:

```text
period i:
  short put
  long call K1
  long call K2 with KI
```

OptionPackage form では 3 本の `FxOptionExerciseLeg` を作るのは自然。  
ただし Target は 3 本それぞれではなく、period i の package net payoff を累積したい。

そのため v2.2 では以下を first-class にした。

```text
ContractPeriod
PeriodDateBinding
PeriodComponentGroup
```

---

## 8. Period の定義に関する重要な合意

Period は「単一 fixing date を共有する単位」ではない。

```text
Period =
  契約上・商品設計上、同じ economic episode として束ねたい単位
```

同一 period に複数 fixing / observation / payment / determination date があってよい。

日付は `PeriodDateBinding` で owner ごとに持つ。

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

Period は grouping axis。  
Date は schedule / observation / rule / component 側で owner-specific に持つ。

---

## 9. Package / Group

複数 component を 1 period package として束ねるために `PeriodComponentGroup` を入れた。

```python
PeriodComponentGroup(
    group_id="period_1_option_package",
    period_id="period_1",
    group_kind="FX_OPTION_PACKAGE",
    component_ids=("period_1_short_put", "period_1_call_k1", "period_1_call_k2"),
    role_by_component_id={...},
)
```

Target は `PackageNetAmountAccumulationValueRule` で group net payoff を累積できる。  
KO は `GroupComponentSelector` / `TriggerRelativeGroupComponentSelector` で group 単位に作用できる。

---

## 10. v2.2 で作った Product Grammar

`ratio_forward_product_grammars_v2_2_full.py` には代表例を 3 つ入れた。

1. `build_example_coupon_swap_gap_wko_v2_2()`

- Coupon Swap form
- GAP
- sold-side KI
- Point / pips target

2. `build_example_fx_option_package_two_stage_target_v2_2()`

- FX Option Package form
- TWO_STAGE
- package net amount target

3. `build_example_fx_option_package_count_tarf_v2_2()`

- FX Option Package form
- Count TARF

いずれも `form.validate()` を通過済み。

---

## 11. 次に自然な論点

1. `PackageNetAmountAccumulationValueRule` の generic valuation / netting をどう作るか
2. target hit 時の partial CF scale を package 単位でどう適用するか
3. 複数 target が同時 hit したときの priority / conflict policy
4. `ComponentTemplate` / `PeriodRuleBinding` を導入し、period から components を展開する authoring layer
5. direct dependency と id registry の hybrid 化
6. generic event engine で ComponentSelector に hit_period_index を渡す設計
