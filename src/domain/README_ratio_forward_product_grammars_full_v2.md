# README: Ratio-Forward 系 Product Grammar 完全版
## Coupon Swap 形態 / FX Option Package 形態 / WKO / TARGET

この文書は `ratio_forward_product_grammars_full.py` のための、  
**説明強化版 README** である。

今回の主題は一貫している。

> **同一の経済効果を、異なる契約形態として落とし分けること**

対象は、各期の payoff を Quote Currency で見たときに  
**ratio-forward-like** な経済効果を持つシリーズ商品である。  
ただし、それを 1 つの canonical form に潰すのではなく、次の 2 つの form に分けて持つ。

- **Coupon Swap form**
- **FX Option Package form**

この README では、次を順に説明する。

1. 何をモデル化したいのか
2. なぜ 2 つの form に分けるのか
3. Product Grammar では何を保持するのか
4. WKO / TARGET をどう扱うのか
5. 実装上どこまで完了しているのか
6. 実際にどう使うのか

---

# 1. このモジュールが解決したいこと

このモジュールの目的は、単に「レシオフォワードっぽい payoff を計算する」ことではない。  
本当にやりたいのは、次の両立である。

- **同じ economics を持つ商品を、異なる契約形態として保持する**
- **その form の違いを保ったまま authoring / editing / simulation できるようにする**

ここでいう「同じ economics」とは、たとえば各期について Quote Currency ベースで見た payoff が同じ、という意味である。  
しかしそれでも、契約としては

- coupon の交換契約として書く
- option package の集合として書く

の違いがありうる。  
この違いは、単なる見た目の違いではなく、

- 契約条項の書き方
- ユーザーが編集したい粒度
- 何を第一情報とみなすか
- README / 監査 / 説明責任

に影響する。

そのため、このモジュールでは

> **same economics でも same form に潰さない**

という方針を採っている。

---

# 2. 2 つの form

## 2.1 Coupon Swap form

Coupon Swap form では、各期において  
**本当に 2 通貨の coupon exchange が起きる**  
という契約形態を保つ。

つまり、option を明示的に exercise する package としては持たない。  
代わりに、各期の coupon exchange を 2 本の leg として持ち、  
その結果を Quote Currency で見たときに ratio-forward-like な経済効果になるようにする。

この form では中心になるのは

- `AccrualCouponLeg("coupon_swap_pay_leg")`
- `AccrualCouponLeg("coupon_swap_receive_leg")`

である。

ここで大事なのは、

- **form 上は coupon exchange**
- economics を option decomposition に還元するのは二次的

という点である。

## 2.2 FX Option Package form

FX Option Package form では、各期ごとに

- long call
- short put
- 必要なら sold-side KI

を持つ。

つまり、1 期 = 1 option package であり、  
シリーズ全体としてはその per-period package の列になる。

この form では中心になるのは

- `FxOptionExerciseLeg(period_i_call)`
- `FxOptionExerciseLeg(period_i_put)`
- `KnockInMechanism(period_i_sold_option_ki)`（必要なら）

である。

ここでは逆に、

- **form 上も option package**
- KI も option の有効化条件として素直に表す

というのが自然になる。

---

# 3. 今回扱うスキーム

このモジュールで扱うスキームは次の 5 種類である。

## NORMAL
- `K_call = K_put`
- call / put amount は independently 決められる
- amount ratio がレシオを作る

## GAP
- `K_call < K_put`
- 売りオプション側にのみ European KI

## RANGE_GAP
- `K_call = K_put`
- 売りオプション側にのみ European KI

## COLLAR
- `K_put < K_call`
- KI なし

## TWO_STAGE
- 各期では `K_call = K_put`
- 途中で strike が一度だけ変わる
- call / put level は変わらない

---

# 4. Input と Product Grammar の分離

ユーザー入力の自然さと、契約構造の自然さは一致しないことがある。  
このモジュールでは、その違いを明示的に分けている。

## 4.1 入力で自然なもの
ユーザーは通常、次のように考える。

- base notional
- `call_level`
- `put_level`

これは入力として自然である。  
たとえば「put を 2 倍レバにする」といった表現がしやすい。

## 4.2 Product Grammar で自然なもの
一方で ContractForm 側で持ちたいのは、最終的には

- `call_amount_base`
- `put_amount_base`

である。  
なぜならこちらの方が、契約 substance に近いからである。

したがって、このモジュールでは

- `OptionAmountSpec` は input-layer 的な object
- Product Grammar / period spec 側では actual amount を使う

という整理にしている。

---

# 5. 売りオプション側 KI の一般化

もともとの問題設定では「put のみに KI」という説明があった。  
ただし Product Grammar としては、それをもう少し一般化した方が自然である。

そこでこのモジュールでは、

> **売りオプション側にのみ European KI が付く**

という定義を採用している。

これを表すのが `SoldOptionSelector` である。

- `PUT`
- `CALL`

のどちらが sold side かを指定できる。

この設計にしておくと、

- いまの主用途では sold put KI を素直に表せる
- 将来的に sold call 側に KI を持つ変種も同じ grammar で扱える

という利点がある。

---

# 6. Schedule の考え方

このモジュールは、既存の core module にある
semantic schedule graph の上に乗る grammar layer として設計されている。  
ただし、per-period builder を正確に動かすために、ここでは **explicit な date list** を前提としている。

## 6.1 なぜ explicit schedule が必要か
このモジュールでは period expansion を行う。  
つまり、

- 何期あるか
- 各期の fixing date はどれか
- 各期の payment date はどれか
- 各期の KI observation date はどれか

を builder の時点で具体的に知る必要がある。

そのため、full builder は `DateListSchedule` を前提にしている。

## 6.2 core module との接続
これは semantic schedule graph と矛盾しない。  
むしろ自然な接続は次の流れである。

1. core module 側で semantic schedule graph を持つ
2. `materialize()` して explicit date list を得る
3. その materialized schedule を、この full grammar builder に渡す

つまり、このモジュールは
**semantic schedule graph の materialized downstream**
として位置づけられる。

---

# 7. Coupon Swap form の設計

## 7.1 なぜ `AccrualCouponLeg` なのか
Coupon Swap form をちゃんと表すなら、各 leg には少なくとも

- payment
- fixing
- accrual start
- accrual end

が必要になる。  
そのため、このモジュールでは simple `CouponLeg` ではなく  
**`AccrualCouponLeg`** を使っている。

## 7.2 何を leg に持つか
Coupon Swap form の中心は

- `coupon_swap_pay_leg`
- `coupon_swap_receive_leg`

の 2 本である。

これらは本当に通貨交換として存在する。  
したがって、「オプション package を見えないところで持っていて、それを coupon に見せかけている」のではない。  
form としてはあくまで coupon exchange である。

## 7.3 KI をどう扱うか
ここが FX Option Package form との大きな違いである。

Coupon Swap form では、KI を option activation として前面に出さない。  
むしろ、売りオプション側 KI の経済効果は
**coupon payoff rule の側に吸収する**。

これを contract grammar レベルで表すための object が
`CouponSwapExchangeFormula` である。

これは executable pricing formula ではなく、
**「この coupon exchange はどういう経済意味を持っているか」を残す declarative formula**
として設計している。

---

# 8. FX Option Package form の設計

## 8.1 1 期 = 1 option package
この form では、各期ごとに

- long call
- short put
- optional sold-side KI

を作る。

そのため builder は、period expansion 後の各 period spec に対して
option legs を 2 本ずつ作る。

## 8.2 KI をどう表すか
FX Option Package form では、KI はそのまま option package の構造として持つ。  
したがって sold-side KI がある場合は、その sold option に対して

- `KnockInMechanism(period_i_sold_option_ki)`

を張る。

つまり、

- Coupon Swap form: KI は formula に吸収
- FX Option Package form: KI は explicit mechanism

である。

## 8.3 payment date の扱い
core の `FxOptionExerciseLeg` は payment date を first-class に持たない。  
しかし今回のシリーズ商品では payment date が重要である。

そこで full 実装では `BuiltRatioForwardContract` に

- `payment_dates_by_component`

を持たせている。  
これにより、

- ContractForm 側は core の option leg を保ちつつ
- downstream では各 option component の payment date を扱える

ようにしている。

---

# 9. WKO

WKO はここでは次の意味で実装している。

- American KO
- 観測開始をずらせる
- 効力対象開始をずらせる
- hit 後は future components を消す

## 9.1 monitoring start
KO barrier を **どこから観測するか** を表す。

## 9.2 affected start
KO hit の効力が **どこから将来 component に及ぶか** を表す。

この 2 つを分けることで、以前議論した

- 観測は最初から
- 効力対象は後ろから

のような条項も自然に表せる。

## 9.3 form ごとの作用対象
- Coupon Swap form では future coupon legs
- FX Option Package form では future option components

が deactivate 対象になる。

つまり、ここでも

- trigger は mechanism
- effect scope は component 集合

という原則を守っている。

---

# 10. TARGET

TARGET は今回かなり重要な論点だったので、フル実装では hit-CF 挙動まで含めて具体化している。

## 10.1 metric
- `AMOUNT`
- `POINTS`

### AMOUNT
Quote Currency ベースの実際の payoff 金額を累積する。

### POINTS
notional-free だが level-sensitive な payoff strength を累積する。  
ユーザーの
> `(FXSpot - Strike)^+` のような、notional に依らない尺度
という意図に沿うようにしている。

## 10.2 accumulation side
- `CLIENT_GAIN`
- `CLIENT_LOSS`

これは TARF 的な実務感覚に合わせている。  
つまり、顧客利益側を累積停止条件にする場合もあれば、顧客損失側を累積停止条件にする場合もある。

## 10.3 hit action
TARGET 到達時の挙動は 3 種類ある。

### `KNOCK_OUT_INCLUDING_HIT_CF`
hit した CF 自体も交換しない。  
最も強い stop。

### `PARTIAL_HIT_CF_TO_TARGET_THEN_STOP`
hit した CF では、target に達する分だけ交換する。  
その後は stop。

### `FULL_HIT_CF_THEN_STOP`
hit した CF は full exchange し、その後だけ止める。

---

# 11. Period economics と full simulation

今回の full 実装で、単なる authoring を超えて入れた重要な部分がここである。

## 11.1 `evaluate_period_economics(...)`
各 period について、少なくとも次を計算する。

- client net quote amount
- client gain amount
- client loss amount
- client gain points
- client loss points

つまり、period 単位で「顧客にとってどういう経済結果だったか」を整理する関数である。

## 11.2 `simulate_ratio_forward_series(...)`
シリーズ全体について、

- fixing spot
- KI observation
- WKO observation

を与えると、各期について

- KI hit
- WKO hit
- TARGET accumulation
- exchange scale
- termination point

まで含めて計算する。

特に TARGET については、hit-CF の 3 パターンをここで具体的に処理している。

---

# 12. `BuiltRatioForwardContract`

builder の返り値を `ContractForm` だけにせず、
`BuiltRatioForwardContract` にしたのには明確な理由がある。

## 12.1 `ContractForm` だけでは足りないもの
今回の full 実装では、ContractForm だけでは

- period specs
- option component ごとの payment date
- builder 時に解釈した per-period strike/amount structure
- WKO / TARGET config

が downstream simulation に足りない。

## 12.2 何を持つか
`BuiltRatioForwardContract` は次をまとめて返す。

- `form`
- `form_variant`
- `pair`
- `client_party_id`
- `bank_party_id`
- `period_specs`
- `payment_dates_by_component`
- `wko`
- `target`

これにより、authoring と simulation の橋渡しができる。

---

# 13. 代表例

このモジュールには 2 つの代表 builder を用意している。

## 13.1 Coupon Swap + GAP + WKO
`build_example_coupon_swap_gap_wko()`

- GAP
- sold-side KI
- WKO
- Coupon Swap form

## 13.2 FX Option Package + TWO_STAGE + TARGET
`build_example_fx_option_package_two_stage_target()`

- TWO_STAGE
- TARGET
- premium
- FX Option Package form

README を読むだけではなく、この 2 つを実際に呼び出して `BuiltRatioForwardContract` を眺めるとかなり理解しやすい。

---

# 14. どこまで完成しているか

このモジュールは、以前の「設計方針だけ」「宣言だけ」の段階から進めて、  
少なくとも次までは完成している。

- Product Grammar dataclasses
- builders
- period expansion
- WKO semantics
- TARGET semantics
- hit-CF 3 パターン
- payment-date metadata for option package
- examples
- README / appendix / tasks / answers

つまり、
**authoring + form separation + series-level simulation**
までは一通り揃っている。

---

# 15. まだ残しているもの

一方で、次はまだ外部に残している。

- full pricing / valuation engine
- market data integration
- legal clause round-trip
- core generic runtime への完全統合
- TARGET points の市場慣行差の完全吸収

ただし今回のゴールはそこではなく、  
**Product Grammar と ContractForm への落とし込みを完結させること** だったので、スコープとしては適切に収まっている。

---

# 16. この README の要点

かなり長いので、最後に要点だけまとめる。

## 16.1 一番大事なこと
- same economics でも same form に潰さない

## 16.2 Coupon Swap form
- coupon exchange を本当に form として持つ
- 2 本の `AccrualCouponLeg`
- KI は formula に吸収

## 16.3 FX Option Package form
- per-period option package
- KI は explicit mechanism
- payment date は built metadata 側で管理

## 16.4 WKO / TARGET
- declarative config だけでなく
- series simulation で hit-CF semantics まで持つ

## 16.5 full module の位置づけ
- core semantic schedule graph の downstream
- materialized schedules を受けて
- authoring / build / simulation を担う

---

# 17. まとめ

`ratio_forward_product_grammars_full.py` は、  
ratio-forward-like economics を

- Coupon Swap form
- FX Option Package form

に落とし分けるための
**完全版 Product Grammar / build / simulation モジュール**
である。

今回この README をブラッシュアップした目的は、単に説明を増やすことではない。  
本当にやりたかったのは、

- なぜ 2 form に分けるのか
- それぞれで何を第一情報として持つのか
- KI / WKO / TARGET をどこに置くのか
- full 実装で何ができるのか

を、流れとして自然に読めるようにすることだった。

その意味では、この README は
**コードの API 一覧ではなく、設計判断の理由まで含めた設計文書**
として読むのがよい。
