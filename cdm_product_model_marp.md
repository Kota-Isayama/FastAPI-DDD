---
marp: true
theme: default
class: lead
paginate: true
backgroundColor: white
header: "**CDM**"
footer: "CDM Product Model"
style: |
  section {
    font-family: 'Helvetica', 'Arial', sans-serif;
  }
  h1, h2 {
    color: #0078D7;
  }
  table {
    font-size: 0.72em;
  }
  code {
    font-size: 0.82em;
  }
---

# CDMについて

## 基本的なモチベーションとProductモデルの考え方

---

## CDMとは何か

CDMは、金融商品の取引・管理・ライフサイクルイベントを、共通のデータモデルと**ロジック**で表現するための標準。

ただし、**取引管理システムそのものではない。**

CDMは、次のような課題を解決するために考えられた。

- 各社が取引データを異なる形式で保持している
- 同じライフサイクルイベントでも、システムごとに表現や処理結果が異なる
- ブッキングモデルの差により、同じ実世界のイベントが異なる結果を生む
- 照合差異、評価差異、報告不一致、決済失敗、自動化阻害が起きる
- 任意の時点で「本当の正本」は何か、という課題が残る

---

## CDMは何を目指しているか

CDMは、金融取引を表すための

> 正規化された、機械可読かつ機械実行可能なblueprint

として設計されている。

```text
machine-readable
  データ構造として標準化されている

machine-executable
  検証・分類・状態遷移などのロジックも定義されている
```

CDMは単なる項目定義ではなく、
**データモデル + ロジック**として理解するのが重要。

---

## CDMは何ではないか

CDMは、取引管理システムそのものではない。

| 誤解 | 実際 |
|---|---|
| CDMを入れれば取引管理できる | CDMは標準モデルであり、アプリではない |
| CDM JSONがそのままDB設計になる | CDMは論理モデルであり、物理DB設計ではない |
| CDMは商品分類マスタである | Productは経済条件を表すモデル |
| CDMはデータ項目表である | データ構造だけでなくロジックも含む |

---

## CDMの6つの構成要素

CDMは、主に6つの観点のモデル・ロジックから構成される。

| 構成要素 | 役割 |
|---|---|
| Product | 取引可能な金融商品の経済効果を定義する |
| Event | 金融取引のライフサイクルイベントを表す |
| Legal Agreement | 契約内容をデジタルに表現する |
| Process | 業界プロセスを機械可読・実行可能な形式に翻訳する |
| Reference Data | 他のモデルで使う参照データを表す |
| Mapping | FIX、FpML、ISO 20022などとの対応を定義する |

---

## CDMの基本設計思想

CDMは、単なるデータ項目集ではなく、金融取引を標準化・自動化するための設計思想を持つ。

| 設計思想 | 意味 |
|---|---|
| Normalisation | 共通概念を抽象化して再利用する |
| Composability | 小さな部品を組み合わせて対象を表す |
| Mapping | FpML、FIX、ISO 20022など既存形式と対応づける |
| Embedded logic | 検証・分類・状態遷移などのロジックも持つ |
| Modularisation | 名前空間・レイヤーでモデルを整理する |

---

## 設計思想はProductモデルにも現れる

Productモデルは、CDMの設計思想を強く反映している。

| 設計思想 | Productモデルでの現れ方 |
|---|---|
| Normalisation | price、quantity、party、settlementなどを共通化する |
| Composability | PayoutやUnderlierを組み合わせて商品を作る |
| Mapping | FpMLなど外部形式との対応を持てる |
| Embedded logic | Product Qualificationで商品分類を推論する |
| Modularisation | product、base、observableなどの領域に分かれる |

> Productモデルが複雑に見えるのは、商品ごとの個別実装ではなく、共通部品で表そうとしているから。

---

## この資料の焦点

この資料では、CDMのうち特に次の2つに焦点を当てる。

```text
Product Model
  「何を取引するか」
  金融商品の経済効果を、再利用可能な部品を用いて表す

Event Model
  「何が起きたか」
  新規約定、決済、変更、終了など取引の変化を表す
```

ただし、中心的に扱うのは **Product Model**。

---

# Product Model

## 商品名ではなく「経済条件の構造」として読む

---

## CDMのProductモデルとは

CDMのProductモデルは、金融商品を

> 商品名ではなく、将来発生する支払・受渡・観測・決済のルール

として表現するモデル。

**商品名が先に来ない。**

例：

```text
金利スワップ
= 固定金利レグ
+ 変動金利レグ
+ Notional
+ 支払日
+ 日数計算
+ 金利インデックス
```

---

## Productモデルを読むための基本姿勢

CDMでProductを読むときは、最初に

```text
これはIRSか？
これはRepoか？
これはSwaptionか？
```

と考えるよりも、まず

```text
どんなPayoutがあるか？
どちら向きに発生するか？
何を参照して金額が決まるか？
どのように決済されるか？
```

を見る。

---

## Productの前に：Asset / Observable / Product

CDMでは、参照されるもの・観測されるもの・取引されるものを分けて考える。

| 概念 | ざっくり意味 | 例 |
|---|---|---|
| Asset | 識別可能な資産 | 株式、債券、ローン、通貨 |
| Observable | 価格・レートなどを観測する対象 | 株価、金利指数、FXレート、株価指数 |
| Product | 経済条件を持つ金融商品 | IRS、CDS、Repo、Swaption |

重要な違い：

> Productは `economicTerms` を持つ。  
> つまり、将来の支払・受渡の条件を持つ。

---

## Productには2種類ある

CDMのProductは、大きく2種類に分かれる。

```text
choice Product:
  TransferableProduct
  NonTransferableProduct
```

| 種類 | 意味 | 例 |
|---|---|---|
| TransferableProduct | 移転可能な資産にEconomicTermsを付けたもの | 債券、ローンなど |
| NonTransferableProduct | 二者間で合意される契約型の商品 | IRS、CDS、Repo、Swaptionなど |

この資料では、主に **NonTransferableProduct** を中心に見る。

---

## 設計思想①：商品は部品の合成

CDMでは、商品を巨大な専用クラスとして表すのではなく、共通部品を組み合わせて表す。

```text
Product
  └─ EconomicTerms
       ├─ effectiveDate
       ├─ terminationDate
       └─ payout[]
```

重要な見方：

> Product = EconomicTermsを持つもの

---

## 設計思想②：商品名は後から推論する

CDMでは最初から

```text
productType = Interest Rate Swap
```

と書くのではない。代わりに、

```text
固定レグがある
変動レグがある
支払条件がある
```

という経済条件を書く。

その結果として、Product Qualificationにより、`InterestRate_IRSwap_FixedFloat` のような分類が付く。

---

## Product Qualificationの注意点

Product Qualificationは、CDMによって定義される分類ロジック。

```text
Economic Terms
  ↓
Product Qualification Function
  ↓
Product Taxonomy / Product Qualifier
```

注意点：

- 商品名は、経済条件から推論される
- 同じ経済効果から複数の分類名が推論されることがあり得る
- したがって、商品名は入力というより、構造から導かれる結果に近い

---

## 設計思想③：ProductとTradeを分ける

商品そのものと、実際の取引条件は分けて考える。

```text
Product
= 商品の経済条件

TradableProduct
= Product + 価格 + 数量 + 当事者

Trade
= TradableProduct + 約定情報 + ライフサイクル情報
```

Productは「何を取引するか」。  
Tradeは「誰と、いつ、どの条件で取引したか」。

---

## Productモデルの中心：EconomicTerms

`EconomicTerms` は商品の心臓部。

```text
EconomicTerms
  ├─ effectiveDate
  ├─ terminationDate
  ├─ dateAdjustments
  ├─ payout[]
  ├─ terminationProvision
  ├─ calculationAgent
  └─ collateral
```

特に重要なのは `payout[]`。

---

## Payout：支払・受渡の部品

Payoutは、将来発生する金融上の義務を表す。

Payoutは8つの具体的なタイプに分類される。

```text
choice Payout:  ← choiceはUnion型だと思ってよい
  AssetPayout
  CommodityPayout
  CreditDefaultPayout
  FixedPricePayout
  InterestRatePayout
  OptionPayout
  PerformancePayout
  SettlementPayout
```

商品はPayoutの組み合わせとして読める。

---

## 商品をPayoutで見る

```text
金利スワップ
= InterestRatePayout
+ InterestRatePayout

CDS
= プレミアム支払
+ CreditDefaultPayout

Equity Swap
= InterestRatePayout
+ PerformancePayout

Swaption
= OptionPayout
  └─ underlier = Interest Rate Swap
```

商品名ではなく、Payoutの組み合わせを見る。

---

## PayoutBaseを見ると「支払の型」がわかる

PayoutBaseは、どのPayoutにも共通する「支払・受渡の基本情報」を持つ。

```text
PayoutBase
  ├─ payerReceiver
  ├─ priceQuantity
  ├─ principalPayment
  └─ settlementTerms
```

Payoutの種類が変わっても、まず見る観点は同じ。

```text
支払方向
金額・数量の決め方
元本交換の有無
決済方法
```

---

## 例：固定金利レグならこう読む

```text
payerReceiver
  Party1がParty2に支払う

priceQuantity
  Notional = 100億円
  Fixed Rate = 1.0%

principalPayment
  元本交換なし

settlementTerms
  JPYで現金決済
```

PayoutBaseを見ると、

> このPayoutがどちら向きに、どの条件で、どう決済されるか

がわかる。

---

## Underlier：商品を商品の中に入れる

`Underlier` は、ある商品や資産を別の商品から参照する仕組み。

```text
株式オプション
= OptionPayout
  └─ underlier = Equity

スワップション
= OptionPayout
  └─ underlier = Interest Rate Swap

インデックス連動商品
= PerformancePayout
  └─ underlier = Index
```

この仕組みにより、CDMは複雑な商品も合成的に表せる。

---

# 具体例

## Fixed-Float IRSを段階的にCDMへ近づける

---

## 例：Fixed-Float IRSを自然言語で表す

まずは自然言語で商品を表す。

```text
Party1は固定金利を支払う
Party2は変動金利を支払う

Notionalは100億円
固定金利は1.0%
変動金利はTONA 6M
年2回支払う
満期は5年
元本交換はない
JPYで現金決済
```

ここではまだCDMの型は意識しない。

---

## Step 1：Payoutに分解する

Fixed-Float IRSは、2本の金利Payoutとして見る。

```text
Fixed Leg
= InterestRatePayout
  - payerReceiver: Party1 pays Party2
  - rateSpecification: fixed rate 1.0%
  - notional: 100億円
  - payment frequency: semi-annual

Floating Leg
= InterestRatePayout
  - payerReceiver: Party2 pays Party1
  - rateSpecification: TONA 6M
  - notional: 100億円
  - payment frequency: semi-annual
```

商品名ではなく、**2つのInterestRatePayoutの組み合わせ**として表す。

---

## Step 2：EconomicTermsに入れる

2つのPayoutを、ProductのEconomicTermsに格納する。

```text
NonTransferableProduct
  └─ economicTerms
       ├─ effectiveDate
       ├─ terminationDate
       └─ payout
            ├─ InterestRatePayout  fixed leg
            └─ InterestRatePayout  floating leg
```

この時点で、CDM的には

> 将来の支払義務を持つ契約型Product

として表現される。

---

## Step 3：日付・スケジュールを足す

金利商品では、Payoutだけでなく日付・スケジュールが重要。

固定レグ・変動レグには、それぞれ次のような条件が必要になる。

```text
calculationPeriodDates
  計算期間をどう作るか

paymentDates
  支払日をどう作るか

resetDates
  変動金利をいつ観測するか

dayCountFraction
  日数計算をどう行うか

businessDayAdjustments
  休日の場合にどう調整するか
```

---

## Step 4：Product Qualificationで分類される

CDMでは、最初から

```text
productType = Fixed-Float IRS
```

とは書かない。

代わりに、

```text
InterestRatePayoutが2本ある
片方がFixed
片方がFloating
元本交換なし
金利系の商品条件を満たす
```

という構造から、Product Qualification関数が `InterestRate_IRSwap_FixedFloat` のような分類を推論する。

---

## IRSを擬似JSONで見る

実際のCDM JSONはもっと深いが、考え方は次のようになる。

```json
{
  "nonTransferableProduct": {
    "economicTerms": {
      "effectiveDate": "2026-06-01",
      "terminationDate": "2031-06-01",
      "payout": [
        {
          "interestRatePayout": {
            "payerReceiver": {
              "payer": "Party1",
              "receiver": "Party2"
            },
            "priceQuantity": {
              "quantity": "JPY 10,000,000,000",
              "price": "Fixed Rate 1.0%"
            },
            "settlementTerms": {
              "settlementType": "Cash",
              "settlementCurrency": "JPY"
            }
          }
        }
      ]
    }
  }
}
```

---

## IRSを擬似JSONで見る：2本目のレグ

Floating Legも、もう1本の `InterestRatePayout` として表す。

```json
{
  "interestRatePayout": {
    "payerReceiver": {
      "payer": "Party2",
      "receiver": "Party1"
    },
    "priceQuantity": {
      "quantity": "JPY 10,000,000,000",
      "price": "Floating Rate TONA 6M"
    },
    "settlementTerms": {
      "settlementType": "Cash",
      "settlementCurrency": "JPY"
    }
  }
}
```

ポイント：

> JSONの形を覚えるより、`economicTerms.payout[]` に何が入るかを見る。

---

## 実際のCDM JSONはなぜ深くなるのか

固定金利レグだけでも、実務上は多くのルールを持つ。

```text
誰が払うか
Notionalはいくらか
固定金利はいくらか
計算期間はいつからいつまでか
支払日はいつか
休日ならどう調整するか
日数計算は何か
端数処理はどうするか
決済通貨は何か
```

CDMはこれらを、曖昧な文字列ではなく、機械可読な部品として持つ。

---

## 擬似JSONと正式JSONの違い

ここまでのJSONは理解用に簡略化したもの。

実際のCDM JSONでは、例えば以下のような情報がより細かい型で表現される。

```text
rateSpecification
calculationPeriodDates
paymentDates
resetDates
notionalSchedule
priceSchedule
dayCountFraction
businessDayAdjustments
settlementTerms
```

> まずは大きな構造を理解し、その後で細かい型を追う方が読みやすい。

---

## もう一つの例：Swaption

Swaptionは、OptionPayoutの中に、原資産として金利スワップを持つと考えられる。

```text
Swaption
= OptionPayout
  ├─ option terms
  │    ├─ exercise style
  │    ├─ expiration date
  │    └─ settlement terms
  └─ underlier
       └─ Interest Rate Swap
            ├─ InterestRatePayout fixed leg
            └─ InterestRatePayout floating leg
```

このように、Productを別のProductの中に入れられる。

---

## もう一つの例：Equity Swap

Equity Swapは、金利レグと株式リターンレグの組み合わせとして読める。

```text
Equity Swap
= InterestRatePayout
  + PerformancePayout

InterestRatePayout
  - funding leg
  - floating rateなど

PerformancePayout
  - underlier: equity or equity index
  - return: price return / total return
  - settlement: cash settlement
```

ここでも、商品名ではなくPayoutの組み合わせを見る。

---

# Event Modelとの接続

## Productは「何を」、Eventは「何が起きたか」

---

## ProductとEventの関係

Productは「契約上の経済条件」を表す。

一方、Eventは取引状態の変化を表す。

```text
新規約定
変更
解約
決済
権利行使
リセット
```

重要な考え方：

> Productはライフサイクルイベントのたびに雑に上書きされるものではない。  
> Eventによって、取引状態がどう変化したかを表す。

---

## 初見の人向けの読み方

1. まず `Product → EconomicTerms → payout[]` を見る
2. 商品名ではなくPayoutの組み合わせで考える
3. `PayoutBase` で支払方向・数量・決済を見る
4. 金利商品なら日付・スケジュール系を見る
5. Product Qualificationは最後に確認する

---

## 読むときの合言葉

CDMでProductを読むときは、

> これは何の商品か？

より先に、

> どんなPayoutが、どちら向きに、どの条件で発生するか？

を見る。

---

## まとめ

CDMのProductモデルは、金融商品を

> 商品名のマスタ

としてではなく、

> 将来の経済的な義務の部品表

として表すモデル。

誰が、何を、いつ、どの条件で支払う・受け渡すかを、機械が読める形で組み立てるためのモデルである。

---

## 最後に

CDMのProductモデルは、商品名をデータとして保存するためのモデルではない。

> 商品名を推論できるだけの経済条件を、共通部品で表現するためのモデル

である。

この見方を持つと、CDMのProductドキュメントはかなり読みやすくなる。

