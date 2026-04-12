# unified_contracts_v2 README

この版は、**プライシングはしない**前提で、契約条件を正確に表現し、snapshot で履歴管理し、representation と外部連携IDまで扱うためのモデルです。

## この版で強化した点

前版では `payoff_style: str` と単一 formula 的な表現に寄っていたため、次を厳密には表現しきれませんでした。

- normal
- gap
- range_gap
- collar
- two_stage
- 途中で scheme が切り替わる mixed trade

この版では、payoff を **event ごとの leg の束** として表します。

---

## 1. 主要な考え方

モデルの中心は次の 4 つです。

- **Contract**: TARF / CouponSwap / AKOCouponSwap の経済条件
- **Representation**: coupon_swap として扱うか option_bundle として扱うか
- **TradeSnapshot**: 承認対象となるその時点の契約全体像
- **External linkage**: 外部システム向けの trade ID / option leg ID

特に payoff については、

- `ForwardPayoffLeg`
- `OptionPayoffLeg`
- `EuropeanKnockInBarrier`
- `EventPayoffSpec`
- `PayoffProgram`

で表します。

---

## 2. 表現できる payoff scheme

### normal
各 event が単一の ratio forward です。

### gap
各 event が
- buy call
- sell put
- call strike < put strike
- put にのみ European KI

を満たします。

### range_gap
各 event が
- buy call
- sell put
- call strike == put strike
- put にのみ European KI

を満たします。

### collar
各 event が
- buy call
- sell put
- put strike < call strike
- barrier なし

を満たします。

### two_stage
各 event は normal ですが、strike が期中で一度だけ変化します。
これは通常 `StepByIndexTerm` で表します。

### mixed
event ごとに scheme が切り替わる場合です。
たとえば前半 gap、後半 collar のようなものです。

---

## 3. trade 全体の payoff scheme 名

`PayoffProgram.classify_trade_scheme()` により、trade 全体の payoff scheme 名を導出できます。

- 全 event が normal → `normal`
- 全 event が gap → `gap`
- 全 event が two_stage → `two_stage`
- event によって切替あり → `mixed`

この値は `TradeSnapshot.trade_payoff_scheme` に入るので、

- UI の表示分岐
- UI の編集画面分岐
- 外部システムへの送信分岐

に使えます。

---

## 4. representation

同じ経済条件でも、業務上の取扱いを次の 2 つで分けられます。

- `CouponSwapRepresentation`
- `OptionBundleRepresentation`

### coupon_swap
1 event ごとに coupon cashflow を 1 本持ちます。

### option_bundle
1 event ごとに option legs に分解した cashflow を持ちます。

normal / two_stage の場合は、forward を **synthetic な call + put** に分解して option bundle view を生成します。

---

## 5. snapshot 履歴

修正は override ではなく snapshot を積みます。

- 契約条件の修正
- schedule の修正
- cashflow の個別修正
- representation の変更

のいずれも、新しい `TradeSnapshot` を作ります。

ただし元の `PeriodicScheduleSpec` / `EventSchedule` は `ScheduleArchive` に保持し続けます。

---

## 6. 外部ID

外部IDは contract 本体には持たせません。
`TradeDraft` 側に次を持ちます。

- `ExternalTradeRef`
- `ExternalComponentRef`

`option_bundle` の場合は、各 option component にも ID を割り振れます。
`CashflowRecord.metadata.component_key` を使って外部IDとの紐付けを保持します。

---

## 7. ディレクトリ

```text
unified_contracts_v2/
  common/
    identity.py
    terms.py
    schedules.py
    representations.py
    cashflows.py
    payoffs.py
  products/
    tarf.py
    coupon_swap.py
    __init__.py
  workflow/
    trade.py
  services/
    instantiate.py
  outbound/
    id_allocator.py
  examples.py
  README.md
```

---

## 8. 要件との対応

- TARF / AKOCS / plain coupon swap を表現できる
- coupon swap / option bundle の両 representation を持てる
- normal / gap / range_gap / collar / two_stage / mixed を表現できる
- trade 全体の payoff scheme 名を持てる
- cashflow 個別修正も snapshot 管理できる
- 元の periodic schedule を archive として保持できる
- 外部システムの trade ID と option leg ID を保持できる

