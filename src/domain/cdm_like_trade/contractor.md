
# README: `definition_to_contract_generator.py`

この README は、`typical_product_definitions.py` と `cdm_contract_model_v2.py` の間をつなぐ  
**generator 層**である `definition_to_contract_generator.py` の意図と使い方を説明します。

---

# 1. このモジュールの役割

この generator は、次の 2 層の間を橋渡しします。

## 上位層: Typical Product Definition
クライアントが編集・作成する商品定義です。

例:
- `FxTarfDefinition`
- `CouponSwapDefinition`
- `DigitalCouponSwapDefinition`

この層は

- 商品ごとに必要十分な項目を持つ
- rule-based / explicit / mixed の意図を保持する
- CDM-like model の自由度を直接露出しない

ことを目的としています。

## 下位層: CDM-like Contract Model
正規化された契約表現です。

例:
- `Trade`
- `TradableProduct`
- `EconomicTerms`
- `InterestRatePayout`
- `SettlementPayout`
- `ContingentFeature`

この generator は、**上位の definition を下位の contract model に落とす**役割を持ちます。

---

# 2. 何をして、何をしないか

## この generator がすること
- rule-based schedule を explicit period 群に展開する
- explicit schedule をそのまま period 群として扱う
- rule-based / explicit / mixed の step 定義を period ごとの値へ展開する
- `FxTarfDefinition` を scheduled `SettlementPayout` に変換する
- `CouponSwapDefinition` / `DigitalCouponSwapDefinition` を `InterestRatePayout` 群に変換する
- KO や digital 条件を contract-model feature に写像する
- target redemption を `TargetAccrualTerms` に写像する
- 生成 metadata を `GeneratedProductBundle` に乗せる

## この generator がしないこと
- market data を使って trigger を評価する
- cashflow 実績を管理する
- target 到達を state として判定する
- lifecycle event を生成する
- full-featured business-day adjustment engine になる

つまり、これは **contract generation** であって、**evaluation engine** ではありません。

---

# 3. 基本の使い方

## 3.1 まず definition を作る

たとえば `typical_product_definitions.py` に入っているサンプルを使います。

```python
from typical_product_definitions import example_rule_based_tarf_definition

definition = example_rule_based_tarf_definition()
```

## 3.2 generator を作る

```python
from definition_to_contract_generator import (
    DefinitionToContractGenerator,
    GeneratorPartySet,
)

generator = DefinitionToContractGenerator(
    parties=GeneratorPartySet(
        party1_name="Bank A",
        party2_name="Client B",
        party1_id="BANKA",
        party2_id="CLIENTB",
    ),
    generator_version="1.0",
)
```

ここで渡している `GeneratorPartySet` は、  
生成される bilateral trade の Party1 / Party2 を決めるための最小 party 情報です。

## 3.3 generate する

```python
bundle = generator.generate(definition)
trade = bundle.generated_trade
```

戻り値は `GeneratedProductBundle` です。

- `bundle.definition`
- `bundle.generated_trade`
- `bundle.metadata`

の 3 つを持ちます。

---

# 4. `GeneratedProductBundle` の意味

`GeneratedProductBundle` は、単に Trade だけ返すのではなく、

- **何から作られたのか**
- **何が生成されたのか**
- **どの generator で作ったのか**

を 1 セットで残すための wrapper です。

これはアプリケーション上かなり重要です。

たとえば

- 再編集時に元の definition に戻したい
- 監査のために template 名を残したい
- generator version を追いたい

という要件に自然に対応できます。

---

# 5. `GeneratorPartySet` とは何か

定義層では、商品定義そのものに具体的な Party オブジェクトを埋め込んでいません。  
それは intentional です。

代わりに generator 側で、

```python
GeneratorPartySet(
    party1_name="Bank A",
    party2_name="Client B",
    party1_id="BANKA",
    party2_id="CLIENTB",
)
```

のような最小 bilateral party 情報を渡します。

これにより、

- definition は商品定義に集中できる
- party assignment は generator 呼び出し側で決められる

ようになります。

---

# 6. schedule の展開方針

この generator は、definition 側の schedule を明示 period 群に展開して使います。

## 6.1 Explicit schedule
`ExplicitScheduleDefinition` は、そのまま使います。

## 6.2 Rule-based schedule
`RuleBasedScheduleDefinition` は、内部 helper で period 群に展開します。

現時点では簡略版で、

- 月次 / 年次 / 週次 / 日次の基本 progression
- payment lag の反映

だけを行います。

つまり、**schedule intent を period 群に normalize する** のが役目です。

## 6.3 Mixed schedule
`MixedScheduleDefinition` は、

- base rule を展開
- explicit overrides で period を差し替え

という方針です。

これにより、

- 規則で作った
- でも一部だけ手修正した

という意図を definition 側に残したまま、生成側では explicit period 群に落とせます。

---

# 7. step の展開方針

step も同じです。

## 7.1 Explicit step
period_id または effective_date で period ごとに値を決めます。

## 7.2 Rule-based step
- initial_value
- step_values

を period 順に割り当てます。  
足りない場合は最後の値を繰り返します。

## 7.3 Mixed step
base rule の結果を作った後に、explicit points で override します。

---

# 8. `FxTarfDefinition` の変換

これはこの generator の一番大きな対象です。

## 8.1 どういう contract model に落とすか
`FxTarfDefinition` は、最終的に

- 1 個の scheduled `SettlementPayout`
- `FxRatioForwardFormula`
- `SettlementPeriod` 群
- `TargetAccrualTerms`
- target / KO feature

に変換されます。

つまり、period ごとに payout を乱立させるのではなく、

**1 つの settlement stream として contract model に落とす**方針です。

## 8.2 何が共通 mechanics になるか
- currency pair
- bought / sold currency
- ratio
- base strike
- base bought quantity

などが `FxRatioForwardFormula` に入ります。

## 8.3 何が period override になるか
- fixing date
- settlement date
- strike value
- bought quantity value

が `SettlementPeriod` に入ります。

つまり definition 側で

- schedule
- strike steps
- notional steps

を持っていても、generator はそれを
**formula + period overrides** に正規化します。

## 8.4 target redemption
`TargetRedemptionDefinition` は `TargetAccrualTerms` に変換されます。

ただしここで重要なのは、  
これは **target 条件の契約表現** であって、**target 到達判定そのもの**ではないことです。

## 8.5 knockout rule
`KnockOutRuleDefinition` があれば、generator はそれを `ContingentFeature` に変換します。

---

# 9. `CouponSwapDefinition` / `DigitalCouponSwapDefinition` の変換

これらは component ごとに payout を作ります。

## 9.1 なぜ component ごとか
definition 側の coupon swap は、

- base coupon component
- bonus coupon component
- digital component

のように component-centric です。

これは contract model 側では、**component = payout** に寄せるのが自然だからです。

## 9.2 fixed coupon
`FixedCouponFormulaDefinition` は `InterestRatePayout + FixedRateSpecification` に落とします。

## 9.3 floating coupon
`FloatingCouponFormulaDefinition` は `InterestRatePayout + FloatingRateSpecification` に落とします。

## 9.4 digital coupon
`DigitalCouponFormulaDefinition` は、現時点では
- payout 自体は `InterestRatePayout`
- digital 条件は placeholder feature

として落としています。

つまり digital coupon を fully pricing-ready にしたわけではなく、
**契約上そういう条件がある**ところまでを表します。

## 9.5 AKO / KO
component に `KnockOutRuleDefinition` が付いていれば、対応する `ContingentFeature` を生成します。

これにより、
- base coupon は残す
- bonus coupon だけ AKO
といった構造が自然に表せます。

---

# 10. metadata に何を残しているか

generator は `GenerationMetadata` に最低限

- generator name
- generator version
- definition type
- template name

を残します。

また、生成された contract model の `EconomicTerms.non_standardised_terms` には、

たとえば TARF なら

- `payoff_schedule_kind=RULE_BASED`
- `strike_step_kind=EXPLICIT`
- `notional_step_kind=MIXED`

のような note も入れています。

これは、**definition 側の意図を contract 側に軽く残す**ためです。

---

# 11. 使ってみる最小例

## TARF

```python
from datetime import date

from typical_product_definitions import example_rule_based_tarf_definition
from definition_to_contract_generator import DefinitionToContractGenerator, GeneratorPartySet

definition = example_rule_based_tarf_definition()

generator = DefinitionToContractGenerator(
    parties=GeneratorPartySet(
        party1_name="Bank A",
        party2_name="Client B",
    ),
    generator_version="1.0",
)

bundle = generator.generate(definition, trade_date=date(2026, 1, 20))
trade = bundle.generated_trade

print(type(trade).__name__)
print(len(trade.tradable_product.product.economic_terms.payouts))
```

## AKO coupon swap

```python
from datetime import date

from typical_product_definitions import example_ako_coupon_swap_definition
from definition_to_contract_generator import DefinitionToContractGenerator, GeneratorPartySet

definition = example_ako_coupon_swap_definition()

generator = DefinitionToContractGenerator(
    parties=GeneratorPartySet(
        party1_name="Bank A",
        party2_name="Client B",
    ),
)

bundle = generator.generate(definition, trade_date=date(2026, 1, 20))
trade = bundle.generated_trade

for payout in trade.tradable_product.product.economic_terms.payouts:
    print(payout.payout_id, len(payout.features))
```

---

# 12. 現状の限界

ここは率直に書きます。

## 12.1 business-day engine は簡略版
rule-based schedule の展開は簡略で、完全な market-convention engine ではありません。

## 12.2 digital coupon は placeholder 的
digital coupon 条件は feature として表しているが、
価格決定ロジックや realized-state evaluation は持っていません。

## 12.3 knockout scope はまだ粗い
KO の semantic granularity は generic feature に寄せているため、
専用型ほど厳密ではありません。

## 12.4 lifecycle / evaluation は別レイヤ
この generator は contract generation 層です。  
実現損益、target 到達、remaining payout 判定などは別エンジンに委ねます。

---

# 13. 次にやるとよいこと

この generator の次の自然な発展は、次の 3 つです。

## 13.1 schedule expansion engine を独立させる
今は helper 関数内にありますが、本格化するなら別モジュール化した方がきれいです。

## 13.2 evaluator 層を足す
- market observations
- target accrual state
- KO/AKO trigger state

を扱う別レイヤを作ると、contract と実行を分離できます。

## 13.3 reverse mapping / edit support
`GeneratedProductBundle` から definition を再構築する補助を作ると、UI 編集往復に強くなります。

---

# 14. 一言でまとめる

`definition_to_contract_generator.py` は、

> **クライアント向けの典型商品 definition を、  
> 正規化された CDM-like contract model に落とし込むための橋渡し層**

です。

自由度の高い contract model を直接クライアントに触らせず、
それでも rule-based / explicit / mixed の意図を失わないようにするための重要な層です。
