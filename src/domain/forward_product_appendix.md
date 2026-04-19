# APPENDIX: Ratio-Forward 系 Product Grammar 具体例集

この appendix は `ratio_forward_product_grammars.py` の具体例集である。

目的は次の 4 点。

1. 各スキームを Product Grammar にどう落とすかを見る
2. 同じ economics を Coupon Swap / FX Option Package の 2 form にどう分けるかを見る
3. WKO / TARGET / sold-side KI の位置づけを見る
4. schedule / strikes / amounts の責務分離を確認する

---

## 1. NORMAL

### economics
- `K_call = K_put`
- call / put amount は別々に持てる

### Coupon Swap form
- 2 本の `AccrualCouponLeg`
- formula は `CouponSwapExchangeFormula`
- KI なし

### FX Option Package form
- per-period call / put package
- call strike = put strike
- KI なし

---

## 2. GAP

### economics
- `K_call < K_put`
- sold side option only gets European KI

### Product Grammar point
このモジュールでは「put 固定」ではなく  
**sold side option に KI** という汎用定義を採用している。

### Coupon Swap form
- KI を option mechanism としては持たない
- sold-side KI を内包した coupon formula として表す

### FX Option Package form
- sold side option leg に `KnockInMechanism`

---

## 3. RANGE_GAP

### economics
- `K_call = K_put`
- sold side option only gets European KI

### point
GAP と違うのは strike gap がないことだけ。  
KI の扱いは同じ。

---

## 4. COLLAR

### economics
- `K_put < K_call`
- KI なし

### point
純粋に strike asymmetry のみ。  
KI logic は不要。

---

## 5. TWO_STAGE

### economics
- 各 CF 内では `K_call = K_put`
- stage switch の前後で strike が変わる
- call / put levels は変わらない

### Product Grammar point
`TwoStageStrikeSpec` によって

- switch index
- stage1 strike
- stage2 strike

を表す。

---

## 6. WKO

### 契約解釈
- monitoring start をずらせる
- effect start をずらせる
- hit 後は future CF / option を消す

### Coupon Swap form
WKO hit 後は future coupon components を deactivate

### FX Option Package form
WKO hit 後は future option components を deactivate

### point
以前の議論通り

- trigger は mechanism
- effect scope は component set

で表す。

---

## 7. TARGET

### metric
- amount
- points

### accumulation side
- client gain
- client loss

### hit action
- including hit CF stop
- partial hit CF to target then stop
- full hit CF then stop

### point
今回は `TargetTerminationMechanism` を declarative に置いている。  
exact runtime evaluator は今後の課題。

---

## 8. Coupon Swap form の意味

Coupon Swap form では、同じ economics でも
**本当に coupon exchange として持つ**。

したがって、

- option exercise
- option KI activation

を表現の中心にしない。

これが FX Option Package form との最大の違いである。

---

## 9. FX Option Package form の意味

FX Option Package form では、各期に

- long call
- short put
- optional sold-side KI

の package を置く。

こちらは option structure がそのまま contract form になる。

---

## 10. 代表コード

### Coupon Swap + GAP + WKO
```python
from ratio_forward_product_grammars import build_example_coupon_swap_gap_wko

form = build_example_coupon_swap_gap_wko()
```

### FX Option Package + TWO_STAGE + TARGET
```python
from ratio_forward_product_grammars import build_example_fx_option_package_two_stage_target

form = build_example_fx_option_package_two_stage_target()
```

---

## 11. 最後に

この grammar layer の本質は、  
**同じ payoff を 1 つの canonical form に潰すことではない。**

むしろ

- economics は共通でも
- contract form は分ける

ことで、

- authoring
- editing
- explanation
- legal correspondence

を保つことにある。
