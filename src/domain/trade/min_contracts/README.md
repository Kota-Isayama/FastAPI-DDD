# min_contracts README

この README は、今回のスコープに絞った **最小限の契約モデル** を説明します。

目的は次です。

- インディケーション後の約定データを表現する
- ユーザー承認フローに載せる
- 確定後に外部システムへ送れるようにする
- 必要に応じてキャッシュフロー単位で個別修正できるようにする
- ただし、修正後も **元の圧縮契約情報** や **元の PeriodicSchedule** を保持する

このため、設計は pricing engine や汎用 payoff compiler を目指さず、**canonical contract + trade representation + editable cashflow snapshot** に寄せています。

---

## 目次

1. 何を表現するか
2. 設計原則
3. パッケージ構成
4. ドメインモデル
5. 商品モデル
6. representation の考え方
7. キャッシュフロー修正の考え方
8. ワークフロー
9. 典型コード例
10. 今後の拡張ポイント

---

## 1. 何を表現するか

このパッケージは、主に次の契約を対象にしています。

- TARF
- AKO Coupon Swap
- 普通の Coupon Swap

また、同じ経済条件でも、業務上の取扱いとして次の 2 通りを持てます。

- `coupon_swap`
- `option_bundle`

たとえば TARF や AKOCS を、

- クーポンスワップとして扱う
- 通貨オプションの束として扱う

の両方をサポートします。

さらに、生成済みキャッシュフローについては、

- 個別の金額説明を修正する
- 個別の支払日を修正する
- 個別に無効化する

ことをサポートします。

ただし、キャッシュフローを修正しても、元の

- `PeriodicScheduleSpec`
- `EventSchedule`
- 圧縮された契約情報

は消さずに保持します。

---

## 2. 設計原則

### 2.1 商品ごとの typed spec を主役にする

今回は `ProductSpec(payoff, barrier, accrual, redemption, ...)` のような一般化は採らず、商品ごとの dataclass を主役にしています。

- `TARFSpec`
- `CouponSwapSpec`
- `AKOCouponSwapSpec`

これにより、承認対象として見たときに、商品ごとの意味が見えやすくなります。

### 2.2 共通化は本当に必要なところだけ

共通化しているのは次だけです。

- `ProductIdentity`
- `Term`
- `ScheduleLike`
- `ObservationWindow`
- `TradeRepresentation`
- `CashflowRecord`

### 2.3 representation を contract とは別軸で持つ

`coupon_swap` と `option_bundle` は product family ではなく、**取扱表現** として持ちます。

つまり、

- TARF という契約
- それを coupon_swap として扱う

を分離します。

### 2.4 個別修正後の cashflow と元の schedule を両方持つ

これは今回の最重要要件です。

`TradeDraft` は

- `schedule_archives`
- `cashflows`

を両方持ちます。

`schedule_archives` には元の圧縮 schedule を保存し、`cashflows` には現在有効なキャッシュフロー列を保持します。

---

## 3. パッケージ構成

```text
min_contracts/
  common/
    identity.py
    terms.py
    schedules.py
    representations.py
    cashflows.py

  products/
    tarf.py
    coupon_swap.py

  workflow/
    trade.py

  services/
    instantiate.py

  examples.py
  README.md
```

---

## 4. ドメインモデル

大まかなモデルは次です。

```text
Contract
  ├─ TARFSpec
  ├─ CouponSwapSpec
  └─ AKOCouponSwapSpec

TradeDraft
  ├─ contract
  ├─ representation
  ├─ indication_snapshot
  ├─ schedule_archives
  └─ cashflows
```

### Contract
契約の経済条件そのものです。

### Representation
業務上どう扱うかです。

- `CouponSwapRepresentation`
- `OptionBundleRepresentation`

### ScheduleArchive
元のスケジュール定義を保持します。

### CashflowRecord
編集可能なキャッシュフローです。元の説明と現在値の両方を持ちます。

---

## 5. 商品モデル

### 5.1 TARFSpec

主な属性:

- `underlying`
- `settlement_currency`
- `base_notional`
- `payoff_style`
- `payoff_schedule`
- `main_leg`
- `target`
- `final_fixing_treatment`
- optional barrier fields

ポイント:

- TARF に固有の `target` を直接持つ
- redemption を別 component に切らない
- payoff schedule は `PeriodicScheduleSpec` または `EventSchedule` のまま保持できる

### 5.2 CouponSwapSpec

主な属性:

- `underlying`
- `coupon_currency`
- `notional`
- `coupon_schedule`
- `coupon_formula`
- `pay_receive`

### 5.3 AKOCouponSwapSpec

`CouponSwapSpec` に対して、さらに

- `ako_level`
- `ako_window`
- `ako_condition`
- `action_on_breach`

を持ちます。

---

## 6. representation の考え方

representation は、**同じ契約を業務上どう扱うか** を表します。

### 6.1 CouponSwapRepresentation

クーポンスワップとして取り扱うケースです。

この場合、1イベントごとに

- `coupon_leg`

のキャッシュフローを作ります。

### 6.2 OptionBundleRepresentation

通貨オプションの束として取り扱うケースです。

この場合、1イベントごとに

- `call_option_leg`
- `put_option_leg`

のような view を作ります。

ここで重要なのは、**representation は canonical contract そのものではなく、業務上の見せ方・送信の仕方** だということです。

---

## 7. キャッシュフロー修正の考え方

今回の要件の中心です。

### 7.1 何を保持するか

`TradeDraft` は次を持ちます。

- `schedule_archives`: 元の schedule 定義
- `cashflows`: 現在使うキャッシュフロー列

### 7.2 CashflowRecord

各キャッシュフローは次を持ちます。

- `source_schedule_id`
- `source_event_index`
- `view_kind`
- `leg_label`
- `currency`
- `original_amount_description`
- `current_amount_description`
- `original_payment_date`
- `current_payment_date`
- `active`
- `overrides`

つまり、元の値と現在値を両方持ちます。

### 7.3 override

`CashflowOverride` には次を持たせています。

- 誰が修正したか
- いつ修正したか
- なぜ修正したか
- 新しい amount description
- 新しい payment date
- active の変更

### 7.4 元の schedule を消さない

たとえ特定イベントの payment date を手で変えても、`ScheduleArchive` には元の `PeriodicScheduleSpec` が残ります。

つまり、

- 圧縮定義の正本
- 展開後の編集対象 cashflow

を分離しています。

---

## 8. ワークフロー

`TradeDraft` が承認前の状態を表します。

主な status:

- `DRAFT`
- `PENDING_APPROVAL`
- `APPROVED`
- `CONFIRMED`

今のサンプルでは、`TradeDraft` に簡単な state transition を持たせています。

---

## 9. 典型コード例

### 9.1 TARF を coupon swap として draft 化

```python
from datetime import datetime

from min_contracts.common.representations import CouponSwapRepresentation
from min_contracts.examples import make_tarf_coupon_swap_view
from min_contracts.services.instantiate import instantiate_trade_draft

contract = make_tarf_coupon_swap_view()

draft = instantiate_trade_draft(
    draft_id="DRAFT-001",
    contract=contract,
    representation=CouponSwapRepresentation(),
    indication_payload={"quote_id": "Q-1001"},
    captured_at=datetime(2026, 4, 9, 9, 0, 0),
)
```

### 9.2 キャッシュフローを個別修正

```python
from datetime import datetime

from min_contracts.common.cashflows import CashflowOverride

draft.apply_cashflow_override(
    draft.cashflows[0].cashflow_id,
    CashflowOverride(
        edited_by="alice",
        edited_at=datetime(2026, 4, 9, 9, 30, 0),
        reason="negotiated first coupon adjustment",
        new_amount_description="manually fixed coupon amount = 1,250,000 JPY",
    ),
)
```

この後も `draft.schedule_archives` を見れば、元の schedule spec を確認できます。

---

## 10. 今後の拡張ポイント

### 10.1 実際の schedule expander

今の `services.instantiate.expand_schedule()` はデモ用です。
本番では

- business day adjustment
- holiday calendar
- roll convention

を正しく処理する expander に差し替える必要があります。

### 10.2 amount description の構造化

今は pricing をしない前提なので `amount_description` を文字列で持っています。
将来的には

- formula object
- formula AST
- booking-ready field set

などに置き換えられます。

### 10.3 承認履歴の拡張

現状は `TradeDraft` に最低限の状態遷移だけあります。
将来的には

- approver list
- action history
- reject / resubmit
- versioned snapshot

を独立モジュールに切り出せます。

### 10.4 外部連携 mapper

今回のコードには含めていませんが、次のような mapper を追加しやすい構成です。

- booking mapper
- document payload mapper
- downstream publication mapper

---

## まとめ

この `min_contracts/` は、今回のスコープに合わせて次を重視した最小設計です。

- 商品ごとの typed contract を主役にする
- `coupon_swap` / `option_bundle` を representation として別軸で持つ
- 元の圧縮 schedule を保持したまま、編集可能な cashflow 列を持つ
- 承認フローに載せやすい `TradeDraft` を中心にする

特に今回の重要点は、**キャッシュフローを修正しても元の PeriodicSchedule を失わない** ことです。
そのために

- `ScheduleArchive`
- `CashflowRecord`
- `CashflowOverride`

を分けています。
