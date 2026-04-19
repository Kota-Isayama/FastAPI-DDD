# README: Ratio-Forward 系 Product Grammar
## Coupon Swap 形態 / FX Option Package 形態

この文書は `ratio_forward_product_grammars.py` の設計説明である。

目的は 1 つである。  
**同一の経済効果を、異なる契約形態にきちんと落とし分けること。**

今回扱うのは、各期の経済効果を Quote Currency で見たときに
**ratio-forward-like payoff** になる商品群である。  
それを次の 2 つの contract form に落とす。

- **Coupon Swap form**
- **FX Option Package form**

同じ economics でも、form は潰さない。  
この考え方は、このプロジェクト全体の中核原則と一致している。

---

## 1. 何をモデル化したいか

今回の対象は、各 CF ごとに ratio-forward-like payoff を持つシリーズ商品である。  
スキームは次の 5 種類。

- **NORMAL**
- **GAP**
- **RANGE_GAP**
- **COLLAR**
- **TWO_STAGE**

また、各シリーズには

- call amount
- put amount

を independently 持たせられる。  
ユーザー入力では `call_level` / `put_level` として与えられるが、  
Product Grammar / ContractForm 側では

- `call_amount_base`
- `put_amount_base`

に落とした後の値を使う方針にしている。

---

## 2. スキーム定義

### 2.1 NORMAL
- `K_call = K_put`
- call / put amount は独立に決められる
- amount ratio が実質レシオになる

### 2.2 GAP
- `K_call < K_put`
- **売りオプション側にのみ European KI**

### 2.3 RANGE_GAP
- `K_call = K_put`
- **売りオプション側にのみ European KI**

### 2.4 COLLAR
- `K_put < K_call`
- KI なし

### 2.5 TWO_STAGE
- 各 CF では `K_call = K_put`
- 途中の一回だけ strike が変化する
- call / put の level は変わらない

---

## 3. 売りオプション側 KI の汎用定義

最初の議論では「put のみに KI」としていたが、より汎用な Product Grammar にするため、
このモジュールでは

- **売っているオプション側にのみ European KI が付く**

という定義を採用している。

そのため `SoldOptionSelector` を持ち、

- `PUT`
- `CALL`

のどちらが sold side かを明示できる。

これにより「契約を通じて同じ側のオプションに KI が付く」という要件を素直に扱える。

---

## 4. KO 条項

今回サポートする KO は次の 3 種類。

- なし
- **WKO**
- **TARGET**

### 4.1 WKO
WKO はここでは

- American KO
- 観測開始をずらせる
- 効力対象開始もずらせる
- hit 後は **以後の未発生 CF / option を消す**

というものとして持つ。

`WKOConfig` の主要情報は次である。

- barrier
- direction
- observation schedule
- monitoring start index
- affected start index

### 4.2 TARGET
TARGET は

- **AMOUNT**
- **POINTS**

の 2 つの metric を持つ。

さらに累積対象は、一般的な TARF の考え方に寄せて

- client gain
- client loss

を区別する。

hit 時の効果は 3 パターン。

- hit CF を含めて消滅
- hit CF では target に達する分だけ交換して、その後消滅
- hit CF は full exchange、その後消滅

---

## 5. Coupon Swap form と FX Option Package form の違い

ここが最重要である。

### 5.1 Coupon Swap form
Coupon Swap form では、各期の payoff は
**本当に通貨を交換する 2 本の coupon leg**
として持つ。

つまり、オプションを内部に意識した package としては持たない。  
むしろ

- base currency side の coupon leg
- quote currency side の coupon leg

として持ち、Quote Currency に直してみたときに
ratio-forward-like economics になる。

したがって、この form では
**KI を option package として表さず、デジタル / range coupon 的 payoff rule に吸収する**
方針を取る。

### 5.2 FX Option Package form
FX Option Package form では、各期ごとに

- long call
- short put
- 必要なら sold side KI

の package を並べる。

こちらは明示的に option legs を持つ。  
したがって KI は option package 側でそのまま表現する。

### 5.3 同じ economics、違う form
- economics は同じでも
- Coupon Swap と FX Option Package は別 form

である。  
この違いを Product Grammar に残すことが重要である。

---

## 6. モジュールの中核 dataclass

### 6.1 Shared economics
- `OptionAmountSpec`
- `TwoStageStrikeSpec`
- `EuropeanKnockInSpec`
- `RatioForwardSeriesEconomicTerms`
- `RatioForwardPeriodProfile`

### 6.2 KO / TARGET
- `WKOConfig`
- `TargetConfig`

### 6.3 Shared schedules
- `RatioForwardSeriesSchedule`

### 6.4 Product grammar
- `CouponSwapRatioForwardGrammar`
- `FxOptionPackageRatioForwardGrammar`

---

## 7. Coupon Swap form の設計方針

`CouponSwapRatioForwardGrammar` は次を持つ。

- counterparties
- schedule
- economic terms
- quote/base currency
- pay leg orientation
- optional WKO
- optional TARGET

Builder は `build_coupon_swap_ratio_forward_grammar_contract(...)`。

生成する ContractForm の中心は

- `AccrualCouponLeg("coupon_swap_pay_leg")`
- `AccrualCouponLeg("coupon_swap_receive_leg")`

の 2 本である。

Formula は `CouponSwapExchangeFormula` を使う。  
これは executable pricing formula ではなく、**contract-grammar level の declarative formula** である。

### 7.1 なぜ `AccrualCouponLeg` を使うか
Coupon Swap では

- payment
- fixing
- accrual_start
- accrual_end

を持つのが自然だからである。  
単純な `CouponLeg` では不十分。

### 7.2 KI をどう扱うか
Coupon Swap form では KI を option mechanism として持たず、  
sold side KI の経済効果が埋め込まれた coupon formula として扱う。

---

## 8. FX Option Package form の設計方針

`FxOptionPackageRatioForwardGrammar` は次を持つ。

- counterparties
- schedule
- economic terms
- settlement style / settlement currency
- optional premium
- optional WKO
- optional TARGET

Builder は `build_fx_option_package_ratio_forward_grammar_contract(...)`。

生成する ContractForm の中心は、各期ごとの

- `FxOptionExerciseLeg(period_i_call)`
- `FxOptionExerciseLeg(period_i_put)`

である。

### 8.1 1 期 = 1 option package
この設計では、各 CF ごとに 1 つの option package を作る。  
ContractForm 全体としては、その per-period package の列を持つ。

### 8.2 KI をどう扱うか
sold side KI がある場合は

- `KnockInMechanism(period_i_sold_option_ki)`

を option leg に対して張る。

### 8.3 payment schedule はどう持つか
core の `FxOptionExerciseLeg` には settlement date / payment schedule が直接ないため、
この grammar layer では

- exercise/expiry = fixing schedule
- payment schedule = grammar / tags 側で保持

という整理を採っている。

これは core module を拡張するとより綺麗になるが、今回は grammar 設計を優先している。

---

## 9. Schedule の考え方

今回の grammar layer では、period expansion のため
builder が explicit `DateListSchedule` を前提としている。

理由は、

- per-period option legs を立てるためには
- period count を具体的に知る必要がある

からである。

ただし conceptually には、これは core module の semantic schedule graph と両立する。  
つまり、

1. core 側で semantic schedule graph を持つ
2. `materialize()` して explicit date list を得る
3. その materialized schedules を grammar builder に渡す

という流れを想定している。

---

## 10. 代表例

### 10.1 Coupon Swap + GAP + WKO
`build_example_coupon_swap_gap_wko()`

- GAP
- sold put KI
- WKO
- coupon swap form

### 10.2 FX Option Package + TWO_STAGE + TARGET
`build_example_fx_option_package_two_stage_target()`

- two-stage strike
- call/put levels
- TARGET amount
- option package form

---

## 11. 限界と今後の拡張

このモジュールは **Product Grammar / ContractForm authoring** に重点を置いている。  
したがって次は未完成である。

- full payoff evaluator
- TARGET partial-hit-CF exact runtime logic
- WKO runtime pruning
- option package settlement schedule の first-class support
- Coupon Swap form における richer coupon formula evaluation
- TARGET points exact convention library

それでも、今回の成果として重要なのは

- **同一 economics を 2 form に落とし分ける Product Grammar**
- **コード化可能な dataclass-level definitions**
- **代表 builder**
- **README / appendix / 学習課題**

が揃ったことにある。

---

## 12. まとめ

このモジュールは、同一の ratio-forward-like economics を

- Coupon Swap form
- FX Option Package form

に落とし分けるための grammar layer である。

ここで守っている原則は一貫している。

- same economics でも same form に潰さない
- Coupon Swap は本当に currency exchange coupon として持つ
- FX Option Package は option package として持つ
- KO / TARGET は grammar-level mechanism として持つ
- sold-side KI は generic に持つ
- schedule は materialized explicit series で period expansion する

これにより、構造商品としての authoring / editing / explanation をかなり自然に行える。
