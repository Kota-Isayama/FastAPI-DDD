# APPENDIX: Ratio-Forward 系 Product Grammar 完全版 具体例

この appendix は `ratio_forward_product_grammars_full.py` の具体例集である。

---

## 1. Coupon Swap form と FX Option Package form の対比

### Coupon Swap form
- 2 本の `AccrualCouponLeg`
- 実際に base / quote currency exchange が起きる
- sold-side KI economics は coupon formula に吸収
- WKO / TARGET は coupon streams に作用

### FX Option Package form
- 各期ごとの call / put package
- sold-side KI は explicit `KnockInMechanism`
- payment date は build metadata 側で管理
- WKO / TARGET は option components に作用

---

## 2. GAP + WKO を Coupon Swap form で作る

```python
from ratio_forward_product_grammars_full import build_example_coupon_swap_gap_wko

built = build_example_coupon_swap_gap_wko()
form = built.form
```

### 何が入るか
- `CouponSwapRatioForwardGrammar`
- `GAP`
- sold-side KI
- `WKOConfig`
- 2-leg `AccrualCouponLeg`

### simulation 例
```python
from decimal import Decimal
from ratio_forward_product_grammars_full import simulate_ratio_forward_series

result = simulate_ratio_forward_series(
    built,
    spot_by_fixing_date={
        built.period_specs[0].fixing_date: Decimal("149"),
        built.period_specs[1].fixing_date: Decimal("161"),
        built.period_specs[2].fixing_date: Decimal("155"),
        built.period_specs[3].fixing_date: Decimal("150"),
    },
    ki_observation_by_date={
        built.period_specs[0].ki_observation_date: Decimal("149"),
        built.period_specs[1].ki_observation_date: Decimal("161"),
        built.period_specs[2].ki_observation_date: Decimal("155"),
        built.period_specs[3].ki_observation_date: Decimal("150"),
    },
    wko_observation_by_date={
        built.period_specs[1].fixing_date: Decimal("161"),
    },
)
```

この例では、2 期目で WKO barrier を超えた場合、
affected start 以降の future coupon exchange が止まる。

---

## 3. TWO_STAGE + TARGET を FX Option Package form で作る

```python
from ratio_forward_product_grammars_full import build_example_fx_option_package_two_stage_target

built = build_example_fx_option_package_two_stage_target()
form = built.form
```

### 何が入るか
- `FxOptionPackageRatioForwardGrammar`
- `TWO_STAGE`
- per-period option package
- `TargetConfig`
- premium transfer

### simulation 例
```python
from decimal import Decimal
from ratio_forward_product_grammars_full import simulate_ratio_forward_series

result = simulate_ratio_forward_series(
    built,
    spot_by_fixing_date={
        built.period_specs[0].fixing_date: Decimal("153"),
        built.period_specs[1].fixing_date: Decimal("154"),
        built.period_specs[2].fixing_date: Decimal("156"),
        built.period_specs[3].fixing_date: Decimal("158"),
    },
)
```

この例では client gain accumulation が target に達した period で
設定された `TargetHitAction` に応じて
- hit CF も消える
- partial exchange
- full exchange then stop
が分かれる。

---

## 4. TARGET 3 パターンの意味

### including hit CF
hit した CF そのものも交換しない。  
最も強い stop。

### partial hit CF
hit した CF では target 到達分だけ交換し、それ以降は止める。  
最も TARF 的。

### full hit CF then stop
hit した CF は満額交換し、その後だけ止める。

---

## 5. Points と Amount

### Amount
Quote Currency で見た実際の payoff amount を累積。

### Points
notional-free な payoff strength を累積。  
level は効くが base notional そのものには依らない。

---

## 6. 最後に

この full implementation の重要点は、
同じ economics を 1 つの canonical object に潰すことではなく、
**2 つの契約形態をそのまま別建てで authoring / simulation 可能にしたこと**
にある。
