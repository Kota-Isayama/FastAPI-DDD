# README: Ratio-Forward 系 Product Grammar 完全版
## Coupon Swap 形態 / FX Option Package 形態 / WKO / TARGET

この文書は `ratio_forward_product_grammars_full.py` の設計説明である。

今回の目的は、同一の ratio-forward-like economics を

- **Coupon Swap form**
- **FX Option Package form**

の 2 つの契約形態へ **完全に落とし分けること** である。

ここでいう「完全」は、単に dataclass を置くだけではない。  
少なくとも次まで含む。

- Product Grammar の設計方針
- Python dataclass レベルの型定義
- 대표 builder
- 具体コード例
- WKO / TARGET の hit-CF semantics
- FX Option Package の payment date 管理
- README / appendix / 学習課題

---

## 1. 問題設定

各期の payoff を Quote Currency で見たときに  
**ratio-forward-like** になるシリーズ商品を考える。

ただし、同じ economics であっても、契約形態は 2 通りありうる。

### 1.1 Coupon Swap form
同一利払日に、実際に 2 通貨の coupon exchange が起きる。  
Quote Currency に換算して見たときに ratio-forward-like economics になる。

### 1.2 FX Option Package form
同一利払日に、call / put option の exercise 結果から payoff が起きる。  
Quote Currency に換算して見たときに ratio-forward-like economics になる。

重要なのは、

> same economics でも same form に潰さない

ことである。  
これがこの設計の根本原則である。

---

## 2. スキーム

今回のスキームは 5 種類。

### NORMAL
- `K_call = K_put`
- call / put amount は independently 決められる
- レシオは amount ratio で表現される

### GAP
- `K_call < K_put`
- 売りオプション側にのみ European KI

### RANGE_GAP
- `K_call = K_put`
- 売りオプション側にのみ European KI

### COLLAR
- `K_put < K_call`
- KI なし

### TWO_STAGE
- 各 CF 内では `K_call = K_put`
- 途中の一回だけ strike が変化する
- call / put level は変わらない

---

## 3. Input level と Product Grammar level の違い

ユーザー入力では

- base notional
- `call_level`
- `put_level`

を持つのが自然である。  
しかし Product Grammar / ContractForm 側では

- `call_amount_base`
- `put_amount_base`

に落とした値を使う方が contract substance に近い。

このため `OptionAmountSpec` は input-side dataclass とし、
period expansion 後の period spec では actual amounts を使う。

---

## 4. 売りオプション側 KI の一般化

元の問題設定では「put にのみ KI」という説明だったが、
より汎用な Product Grammar にするため、本モジュールでは

- **売りオプション側にのみ European KI**

という定義を採用している。

そのため `SoldOptionSelector` を持つ。

- `PUT`
- `CALL`

どちらが sold side かを指定できる。  
これにより「契約を通じて同じ側の option に KI が付く」という一般化を素直に扱える。

---

## 5. Schedule

共通の per-series schedule として次を持つ。

- fixing schedule
- payment schedule
- accrual start schedule（Coupon Swap form で必須）
- accrual end schedule（Coupon Swap form で必須）
- KI observation schedule（optional; absent なら fixing にフォールバック）

この full module では、period expansion を正確に行うため
**materialized explicit `DateListSchedule`** を前提としている。

つまり、core の semantic schedule graph と組み合わせる場合は

1. core で schedule graph を持つ
2. `materialize()` する
3. 得られた explicit schedule を grammar builder に渡す

という流れになる。

---

## 6. Core dataclass

### Shared economics
- `OptionAmountSpec`
- `TwoStageStrikeSpec`
- `EuropeanKnockInSpec`
- `RatioForwardSeriesEconomicTerms`

### Expanded period-level representation
- `RatioForwardPeriodSpec`

### KO / TARGET
- `WKOConfig`
- `TargetConfig`

### Product grammar
- `CouponSwapRatioForwardGrammar`
- `FxOptionPackageRatioForwardGrammar`

### Built output
- `BuiltRatioForwardContract`

`BuiltRatioForwardContract` が重要である。  
今回は単に `ContractForm` を返すだけでなく、

- `ContractForm`
- period specs
- component-to-payment mapping
- WKO / TARGET config

をまとめて返す。  
これにより authoring と downstream simulation の橋渡しができる。

---

## 7. Coupon Swap form

### 7.1 何を form として持つか
Coupon Swap form では、実際に通貨 exchange が起きるので、

- `AccrualCouponLeg("coupon_swap_pay_leg")`
- `AccrualCouponLeg("coupon_swap_receive_leg")`

の 2 本で持つ。

### 7.2 なぜ `AccrualCouponLeg` か
Coupon Swap では coupon determination の中心情報として

- payment
- fixing
- accrual start
- accrual end

が必要である。  
単純な `CouponLeg` では不十分なので、本実装では `AccrualCouponLeg` を使う。

### 7.3 KI をどう表すか
Coupon Swap form では、option package を form にしない。  
したがって sold-side KI は

- option leg
- option KI mechanism

として前面化せず、**coupon payoff rule に吸収** する。

これを grammar-level に表すために `CouponSwapExchangeFormula` を置いている。  
これは executable pricer ではなく、contract semantics を残す declarative formula である。

---

## 8. FX Option Package form

### 8.1 何を form として持つか
FX Option Package form では、各期ごとに

- long call
- short put
- optional sold-side KI

を持つ。  
つまり **1 期 = 1 option package** である。

### 8.2 period expansion
builder は period spec ごとに

- `FxOptionExerciseLeg(period_i_call)`
- `FxOptionExerciseLeg(period_i_put)`

を生成する。

### 8.3 KI をどう表すか
sold-side KI がある場合は、その sold option に対して

- `KnockInMechanism(period_i_sold_option_ki)`

を張る。

### 8.4 payment date をどう扱うか
core の `FxOptionExerciseLeg` は payment date を直接持たない。  
そこで本 full module では `BuiltRatioForwardContract.payment_dates_by_component`
として、component ごとの payment date mapping を保持している。

これにより

- ContractForm としては option leg をそのまま使い
- grammar/full-implementation layer では payment 管理もできる

ようにしている。

---

## 9. WKO

WKO はここでは

- American KO
- monitoring start index をずらせる
- affected start index をずらせる
- hit 後は future components を消す

として定義している。

### 9.1 monitoring start
観測自体をどこから始めるか

### 9.2 affected start
効力対象をどこから始めるか

これは以前議論した通り、

- trigger は mechanism
- effect scope は component 集合

という整理に沿っている。

### 9.3 hit 時の効果
今回のフル実装では、WKO hit 時は
**以後の未発生 CF / option を消す** として扱っている。

シミュレーション上は、

- hit 期が affected range に入っていれば、その hit 期も含めて exchange scale = 0
- 以後も停止

という形にしている。

---

## 10. TARGET

TARGET は次の 2 軸を持つ。

### 10.1 Metric
- `AMOUNT`
- `POINTS`

### 10.2 Accumulation side
- `CLIENT_GAIN`
- `CLIENT_LOSS`

### 10.3 Hit action
- `KNOCK_OUT_INCLUDING_HIT_CF`
- `PARTIAL_HIT_CF_TO_TARGET_THEN_STOP`
- `FULL_HIT_CF_THEN_STOP`

---

## 11. Period economics

本 full module では `evaluate_period_economics(...)` を持つ。

これは各 period について、Quote Currency ベースで少なくとも次を計算する。

- client net quote amount
- client gain amount
- client loss amount
- client gain points
- client loss points

### 11.1 Amount
Quote Currency ベースの actual payoff amount。

### 11.2 Points
notional-free だが level-sensitive な payoff strength。  
実装上は

- positive intrinsic terms
- sold-side KI activation
- levels

を反映しつつ、base notional そのものには依らない指標として扱っている。

これはユーザーの
> `(FXSpot - Strike)^+` 的で notional によらない
という期待に沿うようにしている。

---

## 12. TARGET hit-CF の完全実装

今回の full module では `simulate_ratio_forward_series(...)` により
TARGET の 3 パターンを明示的に扱う。

### 12.1 KNOCK_OUT_INCLUDING_HIT_CF
- hit した CF 自体も交換しない
- 以後停止

### 12.2 PARTIAL_HIT_CF_TO_TARGET_THEN_STOP
- hit CF では target 到達分だけ交換
- 以後停止
- 実装上は `exchange_scale = remaining / hit_increment`

### 12.3 FULL_HIT_CF_THEN_STOP
- hit CF は full exchange
- その後停止

これで、以前「宣言だけで exact runtime が未実装」だった部分を埋めている。

---

## 13. Build output と simulation

builder は `BuiltRatioForwardContract` を返す。

これに対して `simulate_ratio_forward_series(...)` を呼ぶと、

- fixing spot
- optional KI observation values
- optional WKO observation values

から、各期について

- KI hit
- WKO hit
- target accumulation
- exchange scale
- client exchanged amount

を計算できる。

---

## 14. 代表 builder

### Coupon Swap + GAP + WKO
`build_example_coupon_swap_gap_wko()`

### FX Option Package + TWO_STAGE + TARGET
`build_example_fx_option_package_two_stage_target()`

これらは単なるスケッチではなく、
そのまま `BuiltRatioForwardContract` を返す代表例である。

---

## 15. 設計上の立場

この full module の立場は一貫している。

### 15.1 same economics, different form
同じ economics でも ContractForm は潰さない。

### 15.2 Coupon Swap は coupon exchange
Coupon Swap form では、実際の通貨交換 coupon として持つ。

### 15.3 FX Option Package は option package
FX Option Package form では、option legs の列として持つ。

### 15.4 schedule は explicit period expansion
core の semantic schedule graph と両立しつつ、grammar/full layer では explicit date lists を使う。

### 15.5 WKO / TARGET は grammar + full simulation で完結
今回の full module では、宣言だけでなく hit-CF semantics まで持たせている。

---

## 16. 限界

この module でも、なお次は外部に残している。

- 市場データの取得
- 汎用 valuation engine
- generic runtime engine への完全統合
- legal text round-trip
- TARGET points の市場慣行差の完全吸収

ただし、今回のスコープとしては
**authoring + form separation + hit-CF semantics**
までは十分カバーできている。

---

## 17. まとめ

`ratio_forward_product_grammars_full.py` は、
ratio-forward-like economics を

- Coupon Swap form
- FX Option Package form

に落とし分けるための **完全版 Product Grammar / build / simulation module** である。

今回ここで完成させたのは、

- Product Grammar dataclasses
- builders
- period expansion
- WKO semantics
- TARGET semantics
- examples
- README

である。

これにより、ユーザーが求めていた

- 契約形態の違いを保つこと
- same economics を 2 form で持つこと
- WKO / TARGET を細かく扱うこと
- README に設計を落とすこと

を一通り満たしている。
