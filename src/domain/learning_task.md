# 演習課題集: Semantic Schedule Graph 版 Contract Model に慣れる

この演習集は、`contract_model_schedule_semantic_graph.py` に慣れるための  
**段階的なハンズオン課題集** である。

目的は次の 6 点である。

1. モジュール全体の責務分離を理解する
2. `ContractForm` を source of truth として扱う感覚を身につける
3. `ScheduleMeaning` / `ScheduleNode` / `ScheduleRef` を自然に使えるようになる
4. **schedule の rule / patch / override / materialize** を切り分けられるようになる
5. **同じ経済効果を異なる契約形態で表し分ける** 感覚を身につける
6. 特に **Coupon Swap と FX Option Package** を通じて、form と meaning の違いを理解する

---

# 進め方

この演習集は、次の順序で進める。

1. 全体構造を読む
2. 小さな schedule graph を自分で作る
3. Leg / Formula / Mechanism を足す
4. Patch / Override を使う
5. Coupon Swap を作る
6. FX Option Package を作る
7. 同一経済効果を 2 form で表す
8. Runtime / materialize の流れを整理する

> 重要:  
> 各ステップで「何が source of truth か」「何が派生物か」を必ず言葉で説明すること。

---

# Step 0: 全体像を言葉で整理する

## 課題 0-1
このモジュールに出てくる次の層の役割を、各 3〜5 行で説明してください。

- `InputTemplate`
- `ContractForm`
- `RuntimeState`
- `NormalizedView`

## 課題 0-2
次の 4 つを、それぞれ「契約条項」「途中経過」「比較用派生表現」「入力補助」のどれに近いか分類してください。

- `ScheduleMeaning`
- `CashflowOverride`
- `RuntimeState.numeric_state`
- `InputTemplate`

## 課題 0-3
次を説明してください。

> なぜ `NormalizedView` を source of truth にしないのか。

---

# Step 1: Semantic Schedule Graph の最小例を作る

## 課題 1-1
`coupon_leg` に属する次の 2 つの schedule meaning を作ってください。

- payment
- fixing

必要なもの:

- `ScheduleOwner`
- `ScheduleMeaning`

## 課題 1-2
次の 2 つの node を作ってください。

- quarterly payment dates
- fixing = payment - 2 business days

必要なもの:

- `ScheduleNodeId`
- `ScheduleNode`
- `PatternScheduleSource`
- `RelativeDateScheduleSource`

## 課題 1-3
Step 1-2 の fixing node が、payment node に依存していることを説明してください。  
単にコードを書くのではなく、

- root はどれか
- derived はどれか
- 依存方向はどうか

を文章で書いてください。

## 課題 1-4
同じ日が `PAYMENT` かつ `FIXING` でもあるような `ScheduleMeaning` を作ってください。  
そのうえで、role を単数で持つ設計より何が良いか説明してください。

---

# Step 2: ContractForm に schedule graph を載せる

## 課題 2-1
Step 1 で作った payment / fixing node を `ContractForm` に入れてください。

条件:

- parties は book / client の 2 名
- underlier は `USDJPY`
- まだ leg はなくてよい

## 課題 2-2
`CouponLeg` を 1 本追加し、payment schedule として `ScheduleRef(payment_node.node_id)` を使ってください。

## 課題 2-3
`materialize()` を呼んで、何が起きるかを文章で説明してください。

必ず触れること:

- `ScheduleRef`
- `DateListSchedule`
- runtime との関係

---

# Step 3: Coupon Swap の基本形を作る

## 課題 3-1
次の条件の Coupon Swap を作ってください。

- quarterly coupon payment
- fixing = payment - 2 business days
- coupon は JPY 支払い
- underlying は USDJPY
- coupon formula は fixed 8%

必要なもの:

- payment node
- fixing node
- `CouponLeg`
- `FixedRateFormula`

## 課題 3-2
Step 3-1 の構築結果について、契約条項とオブジェクトの対応表を作ってください。

最低限書くこと:

- payment rule
- fixing rule
- coupon stream
- formula
- parties

## 課題 3-3
payment node と fixing node の owner を同じ `coupon_leg` にする理由を説明してください。

---

# Step 4: Schedule patch と override を使う

## 課題 4-1
Step 3 の Coupon Swap に対して、  
**第 5 回 payment だけ 2027-04-02 に変更** する patch を入れてください。

使うもの:

- `ScheduleNodeIndexPatch`

## 課題 4-2
Step 4-1 の patch を payment node ではなく fixing node に入れると、意味がどう変わるか説明してください。

## 課題 4-3
Step 3 の Coupon Swap に対して、  
**第 3 回 coupon だけ 12% に変更** する override を入れてください。

使うもの:

- `CashflowOverride`

## 課題 4-4
次を分類してください。

- quarterly → monthly に変更
- 第 5 回 payment を変更
- 第 3 回 coupon 率だけ変更

分類先:

- rule 編集
- schedule patch
- override

---

# Step 5: KO を入れる

## 課題 5-1
Coupon Swap に次を追加してください。

- KO observation = payment - 5 business days
- barrier = 160
- KO hit で coupon leg を deactivate

必要なもの:

- observation node
- `BarrierPredicate`
- `KnockOutMechanism`

## 課題 5-2
このとき、KO observation node の owner を `coupon_leg` にするか `ko_mech` にするかを考え、理由を書いてください。

## 課題 5-3
`materialize()` 後に、KO mechanism がどの schedule を参照する状態になるか説明してください。

---

# Step 6: KO の効力スコープを component 分割で表す

## 課題 6-1
次の条件を表してください。

- KO の観察は最初から行う
- ただし KO の効力対象は **5 回目以降の coupon** のみ

ヒント:

- `coupon_leg_first_4`
- `coupon_leg_post_4`

## 課題 6-2
次の条件を表してください。

- KO の観察は最初から行う
- ただし KO の効力対象は **奇数回 coupon のみ**

ヒント:

- `coupon_leg_odd`
- `coupon_leg_even`

## 課題 6-3
次を説明してください。

> なぜ mechanism に「odd only」や「from 5th onward」のような特殊フラグを増やすより、component 分割で表す方がよいのか。

---

# Step 7: FX Option の form / meaning を理解する

## 課題 7-1
次の FX option を作ってください。

- USD call / JPY put
- base notional = 1,000,000
- strike = 150.25
- expiry = 2026-12-18
- physical settlement

使うもの:

- `FxPair`
- `FxOptionInputTemplate`
- `build_contract_form(...)`

## 課題 7-2
Step 7-1 で作った `FxOptionExerciseLeg` を `FxExchangeRightLeg` に変換し、  
何が receive / pay になるか文章で説明してください。

## 課題 7-3
次を説明してください。

> なぜ FX option では form-facing な表現と meaning-facing な表現を分けた方がよいのか。

---

# Step 8: FX Option Package を作る

## 課題 8-1
次の FX Option Package を表してください。

- long call
- short put
- same pair / same strike / same expiry
- package として一括契約

## 課題 8-2
各 option leg に EKI を付ける形で、次を表してください。

- barrier down 135
- knock-in 後にそれぞれ activate

使うもの:

- `KnockInMechanism`
- `BarrierPredicate`

## 課題 8-3
Barrier の owner は package 全体より各 option leg / mechanism 側に寄せた方がよい理由を説明してください。

---

# Step 9: Coupon Swap と FX Option Package を比較する

## 課題 9-1
ratio forward 的な payoff を、次の 2 つの契約形態で表す設計方針を書いてください。

- Coupon Swap
- FX Option Package

## 課題 9-2
両者について、それぞれ次を整理してください。

- form の違い
- schedule の自然さ
- KO / KI の自然さ
- internal meaning への展開しやすさ

## 課題 9-3
次を説明してください。

> same economics でも same form に潰さない方がよい理由は何か。

---

# Step 10: MtM Notional CCS を見る

## 課題 10-1
MtM Notional CCS について、次の 3 つを分けて説明してください。

- schedule
- mechanism
- runtime state

## 課題 10-2
次の schedule meaning を考えてください。

- payment of pay_leg
- payment of receive_leg
- reset of mtm_reset_mech
- principal exchange of form

それぞれ owner をどう置くのが自然か書いてください。

## 課題 10-3
次を説明してください。

> current notional の更新は schedule graph ではなく mechanism + runtime state の責務である

---

# Step 11: 自分で小さな grammar を設計する

## 課題 11-1
Coupon Swap product grammar を、自分の言葉で定義してください。

最低限含めるもの:

- 必須 references
- 必須 schedule meanings
- 許される legs
- 許される formulas
- 許される mechanisms
- 許される patch / override

## 課題 11-2
FX Option Package product grammar を、自分の言葉で定義してください。

最低限含めるもの:

- 必須 references
- legs
- premium
- exercise / barrier
- form / meaning の分離

## 課題 11-3
次を説明してください。

> product grammar は単なる UI 入力定義ではなく、authoring schema である

---

# Step 12: まとめの総合課題

## 課題 12-1
次の条件を満たす ContractForm を作る設計方針を、文章でまとめてください。

- Coupon Swap
- payment quarterly
- fixing = payment - 2bd
- KO observation = payment - 5bd
- KO applies only after 5th coupon
- 5th payment date patched
- 3rd coupon rate overridden

## 課題 12-2
次の条件を満たす ContractForm を作る設計方針を、文章でまとめてください。

- FX Option Package
- long call + short put
- EKI on each option
- premium transfer
- internal meaning can be unfolded to exchange-right legs

## 課題 12-3
最後に、次の問いに答えてください。

1. `ScheduleMeaning` を持つことの利点は何か
2. role を複数集合にする利点は何か
3. `ScheduleRef` を使う利点は何か
4. `materialize()` を分ける利点は何か
5. Coupon Swap と FX Option Package を両方やる意味は何か
