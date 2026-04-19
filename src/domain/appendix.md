# APPENDIX: Semantic Schedule Graph 版 具体例集

この appendix は、`README_semantic_schedule_graph.md` と  
`contract_model_schedule_semantic_graph.py` を補うための  
**具体例中心のドキュメント** である。

目的は次の 5 点である。

1. semantic schedule graph を持つと、実際の契約をどう書くかが見えること
2. `DateRole` / `ScheduleOwner` / `ScheduleMeaning` の使い分けが見えること
3. patch / override をどこで使い分けるかが見えること
4. `materialize()` をいつ呼ぶべきかが見えること
5. KO の効力スコープを component 分割で表す感覚が身につくこと

この appendix では、特に次を重視している。

- `DateRole`
- `ScheduleOwner`
- `ScheduleMeaning`
- `ScheduleNode`
- `ScheduleRef`
- `PatternScheduleSource`
- `ExplicitDateScheduleSource`
- `RelativeDateScheduleSource`
- `ScheduleNodeDatePatch` / `ScheduleNodeIndexPatch`
- `CashflowOverride`
- `materialize()`
- Coupon Swap vs FX Option Package
- MtM Notional CCS
- KO の効力スコープを leg 分割で表す設計

---

# 目次

1. Semantic Schedule Graph の最小例
2. Rule-based Quarterly Coupon Swap
3. Coupon Swap with Payment Date Patch
4. Coupon Swap with Coupon Override
5. Coupon Swap with KO Effective Only After 5th CF
6. Coupon Swap with KO Effective on Odd Coupons Only
7. FX Option with Form / Meaning Separation
8. FX Option Package with EKI
9. Coupon Swap vs FX Option Package
10. MtM Notional CCS with Semantic Schedule Graph
11. Comparison Table: rule / patch / override / mechanism / runtime

---

## 共通 import

```python
from datetime import date
from decimal import Decimal

from contract_model_schedule_semantic_graph import *
```

---

# 1. Semantic Schedule Graph の最小例

まずは schedule graph だけを最小で見る。

## 例の意図

- coupon leg の payment dates を quarterly で作る
- fixing dates は payment dates の 2 business days prior
- 同じ coupon leg に属する payment / fixing の意味を first-class に持つ

## コード

```python
coupon_owner = ScheduleOwner(
    owner_type=ScheduleOwnerType.LEG,
    owner_id="coupon_leg",
)

payment_meaning = ScheduleMeaning(
    roles=frozenset({DateRole.PAYMENT}),
    owner=coupon_owner,
)

fixing_meaning = ScheduleMeaning(
    roles=frozenset({DateRole.FIXING}),
    owner=coupon_owner,
)

payment_node = ScheduleNode(
    node_id=ScheduleNodeId("coupon_payment_dates"),
    meaning=payment_meaning,
    source=PatternScheduleSource(
        pattern=SchedulePattern(
            start_date=date(2026, 3, 31),
            end_date=date(2027, 12, 31),
            frequency="QUARTERLY",
            end_of_month=True,
        )
    ),
    description="Quarterly coupon payment dates",
)

fixing_node = ScheduleNode(
    node_id=ScheduleNodeId("coupon_fixing_dates"),
    meaning=fixing_meaning,
    source=RelativeDateScheduleSource(
        base_schedule_id=payment_node.node_id,
        offset=-2,
        unit=OffsetUnit.BUSINESS_DAYS,
        business_day_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
    ),
    description="Fixing = payment - 2 business days",
)
```

## どう読むか

### payment node
- 何の日付か: `PAYMENT`
- 誰のものか: `coupon_leg`
- どう決まるか: `PatternScheduleSource`

### fixing node
- 何の日付か: `FIXING`
- 誰のものか: `coupon_leg`
- どう決まるか: `RelativeDateScheduleSource(base=payment, offset=-2bd)`

## ポイント

- 日付の意味は node id ではなく `ScheduleMeaning` にある
- 依存関係は arbitrary string ではなく、`base_schedule_id` で張る
- component 側は node 実体を持たず、`ScheduleRef` を持つ

---

# 2. Rule-based Quarterly Coupon Swap

次に、actual product として coupon swap に載せる。

## 契約イメージ

- quarterly coupon payment
- fixing = payment の 2 営業日前
- KO observation = payment の 5 営業日前
- coupon は USDJPY に連動する JPY coupon
- patch も override もまだない

## コード

```python
cp = CounterpartySpec(
    book_party=PartyRef("BANK", "Bank"),
    counterparty=PartyRef("CLIENT", "Client"),
)
usd_jpy = UnderlierRef("USDJPY", "FX")

coupon_owner = ScheduleOwner(ScheduleOwnerType.LEG, "coupon_leg")
ko_owner = ScheduleOwner(ScheduleOwnerType.MECHANISM, "ko_mech")

payment_node = ScheduleNode(
    node_id=ScheduleNodeId("coupon_payment_dates"),
    meaning=ScheduleMeaning(
        roles=frozenset({DateRole.PAYMENT}),
        owner=coupon_owner,
    ),
    source=PatternScheduleSource(
        pattern=SchedulePattern(
            start_date=date(2026, 3, 31),
            end_date=date(2027, 12, 31),
            frequency="QUARTERLY",
            end_of_month=True,
        )
    ),
)

fixing_node = ScheduleNode(
    node_id=ScheduleNodeId("coupon_fixing_dates"),
    meaning=ScheduleMeaning(
        roles=frozenset({DateRole.FIXING}),
        owner=coupon_owner,
    ),
    source=RelativeDateScheduleSource(
        base_schedule_id=payment_node.node_id,
        offset=-2,
        unit=OffsetUnit.BUSINESS_DAYS,
    ),
)

ko_obs_node = ScheduleNode(
    node_id=ScheduleNodeId("ko_observation_dates"),
    meaning=ScheduleMeaning(
        roles=frozenset({DateRole.OBSERVATION}),
        owner=ko_owner,
    ),
    source=RelativeDateScheduleSource(
        base_schedule_id=payment_node.node_id,
        offset=-5,
        unit=OffsetUnit.BUSINESS_DAYS,
    ),
)

form = ContractForm(
    form_id="FORM-RULE-BASED-COUPON-SWAP",
    form_kind="COUPON_SWAP_RATIO_FORWARD",
    parties=cp.both(),
    party_roles=(
        PartyRoleAssignment("party_1", cp.book_party.party_id),
        PartyRoleAssignment("party_2", cp.counterparty.party_id),
    ),
    references=(usd_jpy,),
    transfers=(),
    legs=(
        CouponLeg(
            component_id="coupon_leg",
            payer_party_id=cp.counterparty.party_id,
            receiver_party_id=cp.book_party.party_id,
            reference=usd_jpy,
            notional=SteppedDecimal(Decimal("1000000")),
            payment_schedule=ScheduleRef(payment_node.node_id),
            rate_formula_name="coupon_formula",
            currency=Currency.JPY,
        ),
    ),
    formulas=(
        FormulaBinding("coupon_formula", FixedRateFormula(SteppedDecimal(Decimal("0.08")))),
    ),
    mechanisms=(
        KnockOutMechanism(
            component_id="ko_mech",
            predicate=BarrierPredicate(
                underlier=usd_jpy,
                direction=BarrierDirection.UP,
                level=Decimal("160"),
                observation_schedule=ScheduleRef(ko_obs_node.node_id),
            ),
            deactivate_components=("coupon_leg",),
        ),
    ),
    schedule_nodes=(payment_node, fixing_node, ko_obs_node),
)
```

## どう読むか

### 条項
> Payment is quarterly.

→ `payment_node.source = PatternScheduleSource(...)`

### 条項
> Fixing is two business days prior to each payment date.

→ `fixing_node.source = RelativeDateScheduleSource(base=payment_node, offset=-2bd)`

### 条項
> KO observation is five business days prior to each payment date.

→ `ko_obs_node.source = RelativeDateScheduleSource(base=payment_node, offset=-5bd)`

### leg / mechanism 側
- coupon leg は `ScheduleRef(payment_node.node_id)` を参照
- KO mechanism は `ScheduleRef(ko_obs_node.node_id)` を参照

## materialize

runtime の前に materialize する。

```python
materialized = form.materialize()
timeline = build_event_timeline(materialized)
```

---

# 3. Coupon Swap with Payment Date Patch

次は、一般則はそのまま残しつつ、**第 5 回 payment だけ個別に日付変更** する例である。

## 契約イメージ

- 基本は quarterly payment
- ただし第 5 回だけ payment date を後ろ倒し

## コード

```python
form_with_patch = replace(
    form,
    schedule_node_patches=(
        ScheduleNodeIndexPatch(
            node_id=payment_node.node_id,
            occurrence_index=4,   # 0-based index
            new_date=date(2027, 4, 2),
            reason="Special holiday arrangement",
        ),
    ),
)
```

## どう読むか

### 条項
> Payment is quarterly, except that the 5th payment date is postponed to 2027-04-02.

- 一般則 → `payment_node.source`
- 例外 → `ScheduleNodeIndexPatch(node_id=payment_node.node_id, ...)`

## ポイント

ここで重要なのは、patch の付け先である。

- payment に patch  
  → それを基準にする downstream schedule にも影響しうる
- fixing に patch  
  → fixing だけローカルに変える

つまり、**どの node に patch するか自体が意味を持つ**。

---

# 4. Coupon Swap with Coupon Override

次は、日付ではなく **値だけ例外修正** する例である。

## 契約イメージ

- 基本 coupon は 8%
- ただし第 3 回だけ coupon 率を 12% に変更

## コード

```python
form_with_override = replace(
    form,
    overrides=(
        CashflowOverride(
            component_id="coupon_leg",
            payment_date=date(2026, 9, 30),
            field_name="coupon_rate",
            value=Decimal("0.12"),
            reason="Special step-up for 3rd coupon only",
        ),
    ),
)
```

## ポイント

これは **schedule patch ではない**。  
変えているのは日付ではなく値だからである。

- 日付修正 → node patch
- 値修正 → override

の切り分けが重要である。

---

# 5. Coupon Swap with KO Effective Only After 5th CF

ここからが、このモデルの特徴がよく出る例である。

## 契約イメージ

- KO の観察自体は最初から行う
- しかし KO の効力対象は **5 回目以降の coupon** のみ

## 方針

このモデルでは、mechanism に「5回目以降だけ効く」という特殊パラメータを増やさない。  
その代わり、

- `coupon_leg_first_4`
- `coupon_leg_post_4`

に **leg を分割** する。

## コード

```python
form_ko_scoped = ContractForm(
    form_id="FORM-COUPON-SWAP-KO-AFTER-5TH",
    form_kind="COUPON_SWAP_RATIO_FORWARD",
    parties=cp.both(),
    party_roles=(
        PartyRoleAssignment("party_1", cp.book_party.party_id),
        PartyRoleAssignment("party_2", cp.counterparty.party_id),
    ),
    references=(usd_jpy,),
    transfers=(),
    legs=(
        CouponLeg(
            component_id="coupon_leg_first_4",
            payer_party_id=cp.counterparty.party_id,
            receiver_party_id=cp.book_party.party_id,
            reference=usd_jpy,
            notional=SteppedDecimal(Decimal("1000000")),
            payment_schedule=DateListSchedule((
                date(2026, 3, 31),
                date(2026, 6, 30),
                date(2026, 9, 30),
                date(2026, 12, 31),
            )),
            rate_formula_name="coupon_formula",
            currency=Currency.JPY,
        ),
        CouponLeg(
            component_id="coupon_leg_post_4",
            payer_party_id=cp.counterparty.party_id,
            receiver_party_id=cp.book_party.party_id,
            reference=usd_jpy,
            notional=SteppedDecimal(Decimal("1000000")),
            payment_schedule=ScheduleRef(payment_node.node_id),
            rate_formula_name="coupon_formula",
            currency=Currency.JPY,
        ),
    ),
    formulas=(
        FormulaBinding("coupon_formula", FixedRateFormula(SteppedDecimal(Decimal("0.08")))),
    ),
    mechanisms=(
        KnockOutMechanism(
            component_id="ko_mech",
            predicate=BarrierPredicate(
                underlier=usd_jpy,
                direction=BarrierDirection.UP,
                level=Decimal("160"),
                observation_schedule=ScheduleRef(ko_obs_node.node_id),
            ),
            deactivate_components=("coupon_leg_post_4",),
        ),
    ),
    schedule_nodes=(payment_node, fixing_node, ko_obs_node),
)
```

## どう読むか

### 条項
> KO is monitored from inception.

→ `BarrierPredicate(observation_schedule=ScheduleRef(ko_obs_node.node_id))`

### 条項
> KO affects only coupons from the 5th payment onward.

→ **component 分割**
- `coupon_leg_first_4`
- `coupon_leg_post_4`

and

→ `KnockOutMechanism(deactivate_components=("coupon_leg_post_4",))`

## ポイント

このモデルの基本方針は、

- KO の trigger は mechanism が持つ
- KO の効力スコープは component の切り方が持つ

である。

---

# 6. Coupon Swap with KO Effective on Odd Coupons Only

同じ考え方で、  
「KO の効力が 1 個飛ばし、つまり奇数回 coupon にだけ及ぶ」  
という条件も自然に表現できる。

## 契約イメージ

- KO の観察は最初から
- ただし KO の効力対象は odd coupons のみ

## ポイント

「1個飛ばし」や「奇数回だけ」といった effect scope を  
mechanism 側に賢く持たせる必要はない。

**leg を分割することで自然に書ける**  
というのが、このモデルの大きな特徴である。

---

# 7. FX Option with Form / Meaning Separation

次は FX option の form / meaning 分離である。

## 契約イメージ

- 市場慣行としては USD call / JPY put
- しかし意味としては receive USD / pay JPY の交換権

## コード

```python
fx_tpl = FxOptionInputTemplate(
    pair=FxPair(Currency.USD, Currency.JPY),
    side=Side.BUY,
    option_type=OptionType.CALL,
    base_notional=Decimal("1000000"),
    strike=Decimal("150.25"),
    expiry_date=date(2026, 12, 18),
    settlement_style=SettlementStyle.PHYSICAL,
)
form = build_contract_form(fx_tpl)
fx_leg = form.legs[0]
exchange_leg = fx_option_to_exchange_right(fx_leg)
```

## どう読むか

### form-facing
- `FxOptionExerciseLeg`
- `CALL` は **base currency = USD に対する call**

### meaning-facing
- `FxExchangeRightLeg`
- receive USD / pay JPY を直接持つ

## ポイント

- form と meaning を分ける
- same economics でも form を潰さない
- internal meaning を一意にする

---

# 8. FX Option Package with EKI

次は、FX option package を form として持ち、各 leg に EKI を付ける例である。

## 契約イメージ

- long call + short put の package
- 各 FX option 自体に EKI が付く
- package 全体ではなく、各 option が barrier で activate される

## コードイメージ

```python
cp = CounterpartySpec(
    book_party=PartyRef("BANK", "Bank"),
    counterparty=PartyRef("CLIENT", "Client"),
)

usd_jpy_ref = UnderlierRef("USDJPY", "FX")

long_call = FxOptionExerciseLeg(
    component_id="long_call",
    buyer_party_id=cp.book_party.party_id,
    seller_party_id=cp.counterparty.party_id,
    pair=FxPair(Currency.USD, Currency.JPY),
    side=Side.BUY,
    option_type=OptionType.CALL,
    base_notional=Decimal("1000000"),
    strike=Decimal("150.0"),
    expiry_date=date(2026, 12, 18),
    settlement_style=SettlementStyle.CASH,
    settlement_currency=Currency.JPY,
)

short_put = FxOptionExerciseLeg(
    component_id="short_put",
    buyer_party_id=cp.counterparty.party_id,
    seller_party_id=cp.book_party.party_id,
    pair=FxPair(Currency.USD, Currency.JPY),
    side=Side.SELL,
    option_type=OptionType.PUT,
    base_notional=Decimal("1000000"),
    strike=Decimal("150.0"),
    expiry_date=date(2026, 12, 18),
    settlement_style=SettlementStyle.CASH,
    settlement_currency=Currency.JPY,
)
```

## ポイント

- barrier は package という抽象物ではなく、**各 option leg に対する activation** として持つ
- これにより、契約形態としての option package を保ったまま EKI を表現できる

---

# 9. Coupon Swap vs FX Option Package

ここは学習上かなり重要な比較である。

## 同じ economic meaning
たとえば ratio forward 形状の payoff を考える。

これは

- Coupon Swap form
- FX Option Package form

の両方で持ちうる。

## しかし form は違う

### Coupon Swap form
- coupon の列として持つ
- KO の効力スコープは coupon leg 分割で表しやすい
- payment / fixing / observation の schedule dependency が自然

### FX Option Package form
- option legs の package として持つ
- EKI や barrier activation が自然
- meaning は `FxExchangeRightLeg` に展開しやすい

## 設計上の結論

- **same economics だから同じ form に潰す** のではない
- **same economics だが異なる form を並列に持つ** のが自然
- 比較したいときだけ normalized / meaning に写す

---

# 10. MtM Notional CCS with Semantic Schedule Graph

次は MtM notional CCS の schedule を semantic graph として見る。

## 契約イメージ

- coupon payment は quarterly
- reset = coupon - 2bd
- principal exchange = effective / maturity
- runtime では reset 観測に応じて current notional が更新される

## schedule meaning の例

- `PAYMENT` of `pay_leg`
- `PAYMENT` of `receive_leg`
- `RESET` of `mtm_notional_reset`
- `PRINCIPAL_EXCHANGE` of `form`

## ポイント

- coupon schedule
- reset schedule
- principal exchange schedule

の 3 種類の schedule meaning を分けて持てる。

そして、current notional 更新そのものは schedule graph ではなく

- `NotionalResetMechanism`
- `RuntimeState`

の責務である。

つまり、

- いつ reset するか → schedule graph
- reset で何が起きるか → mechanism + runtime

で責務を分ける。

---

# 11. Comparison Table

最後に、どの層が何を持つかを表で整理する。

| 項目 | 例 | どこで持つか |
|---|---|---|
| 一般的な payment 規則 | quarterly payment | `PatternScheduleSource` |
| fixing の相対規則 | payment - 2bd | `RelativeDateScheduleSource` |
| observation の相対規則 | payment - 5bd | `RelativeDateScheduleSource` |
| その日付の意味 | PAYMENT / FIXING / OBSERVATION | `ScheduleMeaning.roles` |
| どの component に属するか | coupon leg / KO mech | `ScheduleMeaning.owner` |
| 第5回だけ日付変更 | payment #5 → 2027-04-02 | `ScheduleNodeIndexPatch` |
| 特定日だけ日付変更 | 2027-12-31 → 2028-01-04 | `ScheduleNodeDatePatch` |
| 第3回だけ coupon 12% | coupon rate override | `CashflowOverride` |
| KO trigger | barrier hit | `KnockOutMechanism` |
| KO 効力スコープ | 5回目以降だけ / 奇数回だけ | **component 分割** |
| TARGET 累積 | accumulated payout | `AccumulateUntilTargetMechanism` + `RuntimeState` |
| MtM reset | current notional update | `NotionalResetMechanism` + `RuntimeState` |
| FX option meaning | receive/pay exchange right | `FxExchangeRightLeg` |
| 共通比較 | forward-like / fx-option | `NormalizedView` |

---

# 最後に

この appendix の狙いは、単に「こういうクラスがあります」と並べることではない。  
本当に見てほしいのは、各商品の中で

- どこが schedule meaning か
- どこが schedule relation か
- どこが patch か
- どこが override か
- どこが mechanism か
- どこが runtime state か

が、**商品例ベースで見えること** である。

特に今回の版では、

- semantic schedule graph
- role の複数集合
- patch / override
- KO 効力スコープの component 分割

の 4 つが重要なので、その 4 つが自然に見えるように例を選んでいる。
