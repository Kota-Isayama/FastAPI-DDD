<!-- ---
marp: true
theme: default
class: lead
paginate: true
backgroundColor: white
header: "**CDM**"
footer: "CDM"
style: |
  section {
    font-family: 'Helvetica', 'Arial', sans-serif;
  }
  h1 {
    color: #0078D7;
  }
--- -->

# CDMついて

---

## CDMとは何か

- CDMは、金融商品の取引・管理・ライフサイクルイベントを共通のデータモデルと**ロジック**で表現するための標準データモデル(+ロジック)のこと。**取引管理システムではない。** 以下の課題を解決するために考えられた。
    - 各社が取引データを異なる形式で保持し、ライフサイクル変更も一貫していない。
    - ブッキングモデルの差により、同じ実世界のイベントが異なる結果を生む。
    - 照合差異、評価差異、報告不一致、オペレーションコスト低下、決済失敗、自動化阻害などが発生する。
    - 任意の時点で「本当の正本」は何か、という課題が残る。

- CDMは正規化された機械可読性(machine-readable)と機械実行性(machine-executable)のあるblueprintらしい。

---
## CDMの基本概念

CDMは6つの観点の概念から構成される
- Product: 取引可能な金融商品の経済効果の定義
- Event: 金融取引のライフサイクルイベントのデータ構造
- Legal Agreement: 取引をの契約内容？のデジタル表現
- Process: 業界プロセスを機械可読・実行可能な形式に翻訳（実体は関数と同じ）
- Reference Data: 他の次元をモデル化するために必要な参照データ
- Mapping: FIX, FpML, ISO 20022などの他形式へのマッピングロジック

--- 

## CDMの基本設計思想

CDMは、単なるデータ項目集ではなく、  
金融取引を標準化・自動化するための設計思想を持つ。

| 設計思想 | 意味 |
|---|---|
| Normalisation | 共通概念を抽象化して再利用する |
| Composability | 小さな部品を組み合わせて対象を表す |
| Mapping | FpML、FIX、ISO 20022など既存形式と対応づける |
| Embedded logic | 検証・分類・状態遷移などのロジックも持つ |
| Modularisation | 名前空間・レイヤーでモデルを整理する |

---

## この資料の焦点

- Product Model: 「何を取引するか」
    - 金融商品の経済効果を、再利用可能な部品を用いて表す
- Event Model: 「何が起きたか」
    - 新規約定、決済、変更、終了など取引の変化を表す

---

## CDMのProductモデルとは

CDMのProductモデルは、金融商品を  
**商品名ではなく、将来発生する支払・受渡・観測・決済のルール**  
として表現するモデル。**商品名が先に来ない。**

例：

```text
金利スワップ
= 固定金利レグ
+ 変動金利レグ
+ Notional
+ 支払日
+ 日数計算
+ 金利インデックス
````

---

## 基本設計思想はProductモデルにも現れる

Productモデルは、CDMの設計思想をかなり強く反映している。

| 設計思想 | Productモデルでの現れ方 |
|---|---|
| Normalisation | price、quantity、party、settlementなどを共通化 |
| Composability | PayoutやUnderlierを組み合わせて商品を作る |
| Mapping | FpMLなど外部分類・外部項目との対応を持てる |
| Embedded logic | Product Qualificationで商品分類を推論する |
| Modularisation | product、base、observableなどの領域に分かれる |

ポイント：

> Productモデルが複雑に見えるのは、  
> 商品ごとの個別実装ではなく、共通部品で表そうとしているから。

---

## 設計思想①：商品は部品の合成

CDMでは、商品を巨大な専用クラスとして表すのではなく、
共通部品を組み合わせて表す。

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

その結果として、Product Qualification（これもCDMによって定義されている分類ロジック）により
`InterestRate_IRSwap_FixedFloat` のような分類が付く。 **同じ経済効果から複数の分類名が推論されることがあり得る**

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

Payoutは、将来発生する金融上の義務を表す。Payoutは8つの具体的なタイプに分類される。

```text
choice Payout:  ← choiceはUnion型だと思って良い。
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

PayoutBaseは、どのPayoutにも共通する  
「支払・受渡の基本情報」を持つ。

```text
PayoutBase
  ├─ payerReceiver
  ├─ priceQuantity
  ├─ principalPayment
  └─ settlementTerms
```

Payoutの種類が変わっても、見る観点は同じ

```text
支払方向
金額・数量の決め方
元本交換の有無
決済方法
```

### 例: 固定金利レグならこう読む

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

PayoutBaseを見ると、**このPayoutがどちら向きに、どの条件で、どう決済されるか**がわかる。

---

## Underlier：商品を商品の中に入れる

`Underlier` は、ある商品や資産を別の商品から参照する仕組み。

例：

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

# 初見の人向けの読み方

1. まず `Product → EconomicTerms → payout[]` を見る
2. 商品名ではなくPayoutの組み合わせで考える
3. `PayoutBase` で支払方向・数量・決済を見る
4. 金利商品なら日付・スケジュール系を見る
5. Product Qualificationは最後に確認する

---

# まとめ

CDMのProductモデルは、金融商品を
**商品名のマスタ**としてではなく、
**将来の経済的な義務の部品表**として表すモデル。

> 誰が、何を、いつ、どの条件で支払う・受け渡すかを、
> 機械が読める形で組み立てるためのモデルである。

