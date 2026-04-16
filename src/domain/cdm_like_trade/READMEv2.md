# README 追補: `cdm_contract_model_v2.py` と Scheduled TARF の表現

この文書は、`cdm_contract_model_v2.py` の **拡張点** と、  
その拡張を使って **定期的にストライクと notional がステップアップするレシオフォワード形式の TARF** をどう表すかを説明するための追補です。

元の README では、CDM 的な契約表現の骨格として

- `Trade`
- `TradableProduct`
- `Product`
- `EconomicTerms`
- `Payout`

の流れを説明しました。

この追補では、その上にさらに次の 3 点を足します。

1. **`SettlementPayout` を period ごとに分割せず、共通 mechanics + period schedule で持つ**
2. **`FeatureEffect` の作用対象を文字列ではなく参照で持つ**
3. **TARF の target redemption 条件を `TargetAccrualTerms` で契約的に持つ**

---

# 1. なぜ v2 が必要だったのか

前の版では、TARF を表すときに

- fixing / settlement ごとに
- 1 個ずつ `SettlementPayout` を作る

という例を出しました。

これは単純で分かりやすい反面、少し不満がありました。

たとえば TARF では、period ごとに違うのは主に

- fixing date
- settlement date
- strike
- notional

であって、商品全体としての mechanics はかなり共通です。

つまり、

- これは毎月の FX ratio forward 系 settlement である
- 同じ target redemption 条項がかかる
- 同じストリームに属している

という本質は共通なのに、period ごとに payout をバラしてしまうと、
**共通性が見えにくい**という問題がありました。

そこで v2 では、TARF のような商品に対して

> **1つの scheduled `SettlementPayout` の中に、共通 mechanics と period ごとの差分を分けて持つ**

という方向に拡張しています。

これはかなり重要な変更です。

---

# 2. v2 の設計上の追加点

`cdm_contract_model_v2.py` の大きな追加点は次です。

- `SettlementFormula`
- `FxRatioForwardFormula`
- `SettlementPeriod`
- `FeatureTargetReference`
- `TargetAccrualTerms`

---

# 3. 一番大事な変更: Scheduled `SettlementPayout`

## 3.1 旧版の考え方

旧版では、`SettlementPayout` は基本的に

- 単発の受渡し
- 1個の `PriceQuantity`

というイメージでした。

つまり 1 payout = 1 settlement event にかなり近かったです。

---

## 3.2 v2 の考え方

v2 では `SettlementPayout` は、2通りの持ち方ができます。

### 直接型
- `price_quantity` を 1 個持つ
- 単発 settlement 的に使う

### スケジュール型
- `settlement_formula`
- `settlement_periods`

を持つ

つまり、

> **1 payout が、共通の受渡しロジックを持つ settlement stream 全体を表せる**

ようになりました。

コード上はこうなっています。

```python
@dataclass(frozen=True)
class SettlementPayout(PayoutBase):
    settlement_terms: Optional[SettlementTerms] = None
    price_quantity: Optional[PriceQuantity] = None
    settlement_formula: Optional[SettlementFormula] = None
    settlement_periods: Tuple[SettlementPeriod, ...] = ()
    target_accrual_terms: Optional[TargetAccrualTerms] = None
```

ここで

- `price_quantity` があるなら旧来の単発型
- `settlement_formula + settlement_periods` があるなら scheduled 型

です。

---

## 3.3 何が嬉しいのか

これによって、TARF のように

- 同じ種類の settlement が繰り返される
- ただし strike や notional は period ごとに違う

という商品を、

**「同じ payout stream の period ごとの差分」**

として持てるようになります。

これはかなり自然です。

---

# 4. `SettlementFormula` とは何か

## 4.1 役割

`SettlementFormula` は、

> **この settlement payout の共通 mechanics は何か**

を持つクラスです。

たとえば FX ratio forward なら、

- reference observable は何か
- strike はどういう意味か
- bought leg は何通貨か
- sold leg は何通貨か
- ratio multiplier はいくつか

といった、**期間をまたいで共通な構造**を持ちます。

---

## 4.2 具体型 `FxRatioForwardFormula`

v2 ではその具体例として

```python
@dataclass(frozen=True)
class FxRatioForwardFormula(SettlementFormula):
```

を入れています。

このクラスが持っているのは、ざっくり言うと

- これは FX ratio forward である
- strike は JPY per USD 型の価格である
- bought leg は USD
- sold leg は JPY
- ratio は 2.0
- 基本 bought quantity はいくら

という **共通の契約メカニクス** です。

つまり period ごとに全部を書き直すのではなく、
「この TARF はそもそもどういうフォーマットの取引か」をここに置きます。

---

# 5. `SettlementPeriod` とは何か

## 5.1 役割

`SettlementPeriod` は、

> **共通 mechanics の中で、この期だけ何が違うか**

を表します。

コードではこうです。

```python
@dataclass(frozen=True)
class SettlementPeriod:
    period_id: str
    fixing_date: Optional[AdjustableOrRelativeDate] = None
    settlement_date: Optional[AdjustableOrRelativeDate] = None
    strike_override: Optional[PriceSchedule] = None
    bought_quantity_override: Optional[NonNegativeQuantitySchedule] = None
    sold_quantity_override: Optional[NonNegativeQuantitySchedule] = None
```

重要なのは `override` という考え方です。

---

## 5.2 override の意味

たとえば TARF 全体としては

- 基本 strike = 150
- 基本 bought quantity = 1,000,000 USD

という mechanics を持っているとしても、各期で

- 第2期だけ strike = 151
- 第3期だけ strike = 152.5
- 第4期だけ bought quantity = 1,600,000

のように変えたくなります。

そのとき、

- 共通部分は `FxRatioForwardFormula`
- 差分だけは `SettlementPeriod`

に置くわけです。

これにより、**step-up 商品がかなり自然に表現できます。**

---

# 6. `FeatureEffect.applies_to` を参照化した理由

旧版では、feature effect の対象を

```python
applies_to="remaining_tarf_payouts"
```

のような文字列で置いていました。

これは説明用には十分ですが、モデルとしては弱いです。

なぜなら、

- どの payout に効くのか
- 同じグループとは何か
- 残りとは何を指すのか

が、構造的には分からないからです。

---

## 6.1 v2 の `FeatureTargetReference`

そこで v2 では

```python
@dataclass(frozen=True)
class FeatureTargetReference:
    scope: FeatureTargetScope
    payout_ids: Tuple[str, ...] = ()
    payout_group: Optional[str] = None
    description: Optional[str] = None
```

を導入しました。

これで effect の対象を

- `THIS_PAYOUT`
- `NAMED_PAYOUTS`
- `PAYOUT_GROUP`
- `REMAINING_PAYOUTS_IN_GROUP`

のように、少し構造化して指定できます。

---

## 6.2 payout group の意味

`PayoutBase` 側にも

```python
payout_group: Optional[str] = None
```

を足しています。

これは、たとえば TARF のストリーム全体に

```python
payout_group="tarf_stream"
```

というラベルを付けておき、

feature effect 側で

- この group 全体に効く
- この group の残りに効く

と表すためです。

これにより、「target 到達後に残りの TARF stream を止める」という表現が
旧版よりかなりましになります。

---

# 7. `TargetAccrualTerms` とは何か

これは TARF のためにかなり重要です。

TARF は単なる barrier ではなく、普通は

- 各 fixing の payoff を累積して
- その累積がある target に達したら
- 残りが extinguish / terminate される

という構造を持っています。

つまり「target」は本来、

- spot だけ見れば決まるものではない
- 契約期間中の蓄積ロジックが必要

です。

---

## 7.1 それでも契約モデルには置きたい

ただしこのモジュールは event/state 管理をしません。  
だから target の達成判定そのものはしません。

それでも、契約としては

- target amount はいくらか
- 何通貨で積み上げるか
- どういう accrual method か
- negative amount を含めるか

は持っておきたいです。

そのために入れたのが

```python
@dataclass(frozen=True)
class TargetAccrualTerms:
```

です。

---

## 7.2 中身

```python
target_amount
accrual_currency
accrual_method
observation_terms
include_negative_amounts
```

を持っています。

つまり、これは

> **target redemption ロジックの「契約上の定義」**

です。

まだ評価エンジンではありません。  
でも、契約モデルとしてはこれがあるだけで TARF らしさがかなり増します。

---

# 8. `example_scheduled_tarf_trade()` の読み方

この関数が、v2 の全体例です。

---

## 8.1 Party / Counterparty は従来通り

```python
party1
party2
cp1 = Counterparty(...)
cp2 = Counterparty(...)
```

ここは変わりません。

---

## 8.2 `Observable` を作る

```python
usd_jpy = Observable(...)
```

TARF の reference observable です。

---

## 8.3 共通 mechanics を `FxRatioForwardFormula` に入れる

```python
formula = FxRatioForwardFormula(...)
```

ここで

- 基本 strike
- bought currency
- sold currency
- bought quantity
- ratio multiplier

を共通定義として置いています。

この時点で「この payout stream は FX ratio forward 系です」という骨格が定まります。

---

## 8.4 period ごとの差分を `SettlementPeriod` に入れる

```python
periods = (
    SettlementPeriod(...),
    SettlementPeriod(...),
    ...
)
```

各 period に

- fixing_date
- settlement_date
- strike_override
- bought_quantity_override

を入れています。

この構造によって、

- strike step-up
- bought notional step-up

が period override として表現されています。

ここが、あなたが特に欲しいとおっしゃっていたポイントです。

---

## 8.5 target 条件を `TargetAccrualTerms` で置く

```python
target_terms = TargetAccrualTerms(...)
```

ここで TARF の target redemption の契約条件を置いています。

重要なのは、これは **判定処理ではなく契約条件** だということです。

---

## 8.6 effect の対象を payout group 参照で置く

```python
FeatureEffect(
    target=FeatureTargetReference(
        scope=FeatureTargetScope.REMAINING_PAYOUTS_IN_GROUP,
        payout_group="tarf_stream",
    )
)
```

ここで「残りの TARF ストリームに効く」という意図を、
旧版より構造的に持たせています。

---

## 8.7 全部を 1 個の `SettlementPayout` に束ねる

```python
tarf_payout = SettlementPayout(
    payout_id="tarf_ratio_forward_stream",
    payout_group="tarf_stream",
    settlement_formula=formula,
    settlement_periods=periods,
    target_accrual_terms=target_terms,
    features=(target_feature,),
)
```

ここが v2 の中心です。

つまり、TARF 全体を

- 1 個の scheduled settlement payout
- 共通 formula
- period override
- target accrual terms
- target feature

で持っています。

この構造によって、period ごとに payout を乱立させずに、
**1 つの stream として自然に表現**できます。

---

# 9. どういう時に period ごとに分け、どういう時に 1 payout にまとめるか

この追補の一番実務的なポイントはここです。

## 1 payout にまとめやすいケース
- 共通の settlement mechanics がある
- 違うのは fixing / settlement date や strike / notional の override 程度
- 同じ contingent feature が全 stream にかかる
- target や KO の作用対象が stream 全体として自然

TARF はまさにこのケースです。

---

## period ごとに別 payout に分けた方がよいケース
- period ごとに formula 自体が違う
- party direction が変わる
- settlement type が変わる
- target/KO の作用先が各 period で独立すぎる
- stream としての一貫性が薄い

その場合は、旧版の「period ごとに payout」方式の方が自然です。

---

# 10. v2 を使う時のおすすめの読み順

1. `SettlementPayout`
2. `SettlementFormula`
3. `FxRatioForwardFormula`
4. `SettlementPeriod`
5. `TargetAccrualTerms`
6. `FeatureTargetReference`
7. `example_scheduled_tarf_trade()`

この順で読むと分かりやすいです。

---

# 11. この設計の限界

v2 でも、まだやっていないことがあります。

## 11.1 target 到達の実判定
していません。

`TargetAccrualTerms` は「契約条件」です。  
累積損益を計算し、target 到達を state として管理するのは別エンジンです。

---

## 11.2 override の適用計算
していません。

このモジュールは、
「この period では strike は override を使う」
という契約表現を持つだけです。

実際に formula に override をマージして payout amount を作る engine は別です。

---

## 11.3 path-dependent lifecycle
していません。

TARF は path-dependent なので、本物の評価や実務運用には

- fixing 実績
- 累積 amount
- knockout / target state
- remaining schedule

が必要です。

でもそれは contract model ではなく、別の state / event / evaluation layer の仕事です。

---

# 12. 一言でまとめる

`cdm_contract_model_v2.py` の TARF 拡張は、

> **scheduled `SettlementPayout` を導入することで、  
> TARF のような共通 mechanics を持つ period stream を 1 つの payout として自然に表現する**

ためのものです。

その上で、

- `SettlementPeriod` で period ごとの差分を表す
- `FeatureTargetReference` で effect の対象を参照化する
- `TargetAccrualTerms` で target redemption の契約条件を持つ

ことで、旧版よりかなり TARF 向きになっています。

---

# 13. 次にやると良いこと

この v2 をさらに育てるなら、次の順がおすすめです。

## ステップ1
`SettlementFormula + SettlementPeriod` から
**「実効 strike / 実効 notional を period ごとに展開する helper」**
を作る

## ステップ2
`TargetAccrualTerms` を受け取り、
**累積 amount を外部 state で管理する evaluator**
を作る

## ステップ3
`FeatureTargetReference` を使って、
**どの payout / period が止まるかを解釈する engine**
を作る

この 3 つを別レイヤで作ると、contract model を汚さずに育てられます。
