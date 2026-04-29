# Contract Model v2.1 README

## 1. 変更の目的

v2.1 は、v2 レビューで出た `coupon_rule` の曖昧さを解消した版です。

v2 では `CouponStreamLeg` が `coupon_rule_id` を持っていましたが、この名前だと次の区別が曖昧でした。

- coupon rate を決める rule
- coupon amount を直接決める rule
- notional / accrual factor / rate を組み合わせる calculation rule

v2.1 では、`CouponStreamLeg` から `coupon_rule_id` を削除し、代わりに `CouponCalculationSpec` を持たせます。

```text
CouponStreamLeg
  └─ calculation: CouponCalculationSpec
        ├─ RateBasedCouponCalculation
        └─ AmountBasedCouponCalculation
```

## 2. CouponStreamLeg の新しい意味

`CouponStreamLeg` は、coupon stream という economic action の container です。

```python
@dataclass(frozen=True)
class CouponStreamLeg(Component):
    component_id: str
    payer_party_id: str
    receiver_party_id: str
    reference: ReferenceRef
    payment_schedule: ScheduleRefLike
    calculation: CouponCalculationType
    currency: Currency
```

ここでは、fixed / floating / PRDC / ratio-forward などの coupon の決まり方を leg 自身に押し込みません。

## 3. RateBasedCouponCalculation

通常の coupon は rate-based です。

```text
coupon_amount = notional * rate * accrual_factor
```

対応する型は次です。

```python
@dataclass(frozen=True)
class RateBasedCouponCalculation(CouponCalculationSpec):
    notional_rule_id: str
    rate_rule_id: str
    accrual_start_schedule: ScheduleRefLike
    accrual_end_schedule: ScheduleRefLike
    day_count: DayCount = DayCount.ACT_365F
```

ここで重要なのは、`RateRule` は必ず rate だけを返すことです。

```text
RateRule は amount を返さない
RateRule は notional を含まない
RateRule は accrual factor を含まない
```

## 4. RateRule の分割

`StructuredRateRule` のような万能箱は置かず、具体的な rate rule に分けました。

```text
RateRule
  ├─ FixedRateRule
  ├─ FloatingRateRule
  ├─ FxLinkedRateRule
  ├─ RangeAccrualRateRule
  └─ PRDCRateRule
```

代表的な配置は次です。

```text
Fixed coupon
  RateBasedCouponCalculation + FixedRateRule

Floating coupon
  RateBasedCouponCalculation + FloatingRateRule

FX-linked coupon
  RateBasedCouponCalculation + FxLinkedRateRule

Range accrual coupon
  RateBasedCouponCalculation + RangeAccrualRateRule

PRDC coupon
  RateBasedCouponCalculation + PRDCRateRule
```

## 5. AmountBasedCouponCalculation

rate decomposition が不自然な coupon-like cashflow は amount-based にします。

```python
@dataclass(frozen=True)
class AmountBasedCouponCalculation(CouponCalculationSpec):
    amount_rule_id: str
```

対応する `AmountRule` は amount を直接返します。

```text
AmountRule
  ├─ FixedAmountRule
  ├─ FxForwardAmountRule
  ├─ ConditionalAmountRule
  └─ RatioForwardCouponAmountRule
```

代表的な配置は次です。

```text
Ratio-forward coupon swap leg
  AmountBasedCouponCalculation + RatioForwardCouponAmountRule

TARF-like FX window cashflow
  AmountBasedCouponCalculation + FxForwardAmountRule / ConditionalAmountRule

Digital amount coupon
  AmountBasedCouponCalculation + ConditionalAmountRule
```

## 6. Ratio-forward v2.1 の変更

`ratio_forward_product_grammars_v2_1_full.py` では、Coupon Swap form の 2 本の coupon leg が amount-based になりました。

```text
Coupon Swap form
  CouponStreamLeg("coupon_swap_pay_leg")
    AmountBasedCouponCalculation("amt_coupon_swap_pay")

  CouponStreamLeg("coupon_swap_receive_leg")
    AmountBasedCouponCalculation("amt_coupon_swap_receive")
```

その amount rule は `RatioForwardCouponAmountRule` です。

```text
RatioForwardCouponAmountRule
  pair
  scheme
  side_role
  bought_side_quantity_rule_id
  sold_side_quantity_rule_id
  sold_option_selector
  sold_side_condition_id
```

これにより、ratio-forward coupon exchange は無理に rate として表されず、amount-based coupon-like cashflow として表されます。

## 7. sold-side KI の扱い

Coupon Swap form では、sold-side KI は explicit `KnockInMechanism` ではありません。

ただし v2.1 では、coupon determination の依存関係として、sold-side condition を残せるようにしました。

```text
Coupon Swap form
  sold-side KI = RatioForwardCouponAmountRule.sold_side_condition_id

FX Option Package form
  sold-side KI = ObservationRule + BarrierCondition + EventLifecycleRule(ActivateComponentsEffect)
```

つまり、form-first の思想は維持しています。

## 8. MtM reset の微修正

v2.1 では `MtMResetQuantityRule` から `observation_rule_id` を外しました。

観測は lifecycle event 側の責務です。

```text
NotionalResetLifecycleRule
  reset_observation_rule_id
  reset_schedule
  quantity_rule_id
```

`MtMResetQuantityRule` は、観測値を受け取って新しい quantity を返す純粋な quantity rule になりました。

## 9. Target hit CF policy

`HitCashflowPolicyEffect` は削除しました。

hit CF policy は `TargetLifecycleRule.hit_cashflow_action` に一本化しています。

理由は、hit CF policy は単なる effect ではなく、target hit period の economic action を zero / partial / full にする execution policy だからです。

## 10. 実行確認

代表例は以下の結果で実行確認済みです。

```text
COUPON_SWAP_RATIO_FORWARD_V2_1 True 2
FX_OPTION_PACKAGE_RATIO_FORWARD_V2_1 True 2
```

## 11. 今後のレビュー論点

次に見るべき論点は以下です。

```text
1. AmountRule と PayoffRule を今後どこまで分けるか
2. RatioForwardCouponAmountRule の period metadata をどこに持つか
3. RateRule の具体型、特に PRDCRateRule をどこまで型で表すか
4. ObservationStyle と schedule の validation をどこまで厳しくするか
5. 汎用 event engine で TargetLifecycleRule を処理できるようにするか
```
