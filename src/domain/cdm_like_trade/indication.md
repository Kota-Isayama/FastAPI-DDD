
# README: `indication_layer.py`

このモジュールは、**インディケーション層**を表します。  
目的は次の 2 つを両立することです。

1. **大量処理向けの typed indication**
2. **柔軟入力も許す flexible / bespoke indication**

---

# 1. なぜこの層が必要か

前提として、次の 3 層を分けて考えています。

- **Indication layer**  
  見積・RFQ 入力
- **Typical product definition layer**  
  商品型としての必要十分な定義
- **CDM-like contract layer**  
  正規化された契約表現

ここで大事なのは、

- インディケーションでは商品型に支えられた高速処理が重要
- でも現場では柔軟な入力も必要

ということです。

そのため、このモジュールでは **2 つの lane** を用意しています。

---

# 2. 2 つの lane

## 2.1 Typed lane
`TypedIndicationRequest` 系です。

これは

- product type が最初から分かっている
- pricing に必要十分な項目を揃えたい
- validation を強くしたい
- high-volume に向く

というケース向けです。

例:
- `FxTarfIndication`
- `CouponSwapIndication`
- `DigitalCouponSwapIndication`

## 2.2 Flexible lane
`FlexibleIndicationRequest` です。

これは

- まだ product type に完全には乗せたくない
- でも free text だけでなく、ある程度構造化した経済条件を渡したい
- 後で typed definition に uplift できるならしたい

というケース向けです。

---

# 3. Typed indication は何を目指しているか

typed indication は、**インディケーション時点の主戦力**です。

たとえば `FxTarfIndication` は、

- TARF であることを最初から明示
- schedule は rule-based / explicit / mixed のどれでもよい
- strike / notional も rule-based / explicit / mixed のどれでもよい
- target redemption も持てる

という形です。

つまり、typed ではあるけれど、  
**規則的 schedule に限定しているわけではない**  
ところが重要です。

---

# 4. Flexible indication は何を目指しているか

flexible indication は、**自由入力を完全な free text にしない**ための層です。

ここでは `EconomicClause` を使います。

例:
- `ScheduleClause`
- `RatioForwardClause`
- `TargetRedemptionClause`
- `KnockOutClause`
- `CouponComponentClause`

これらを組み合わせて、

- TARF っぽい
- coupon swap っぽい
- でもまだ fully typed にしたくない

という入力を受け取れます。

---

# 5. uplift とは何か

`IndicationUplifter` は、

- typed indication なら deterministic に definition へ
- flexible indication なら best-effort に definition へ

変換します。

戻り値は `IndicationUpliftResult` で、

- `definition`
- `inferred_product_hint`
- `confidence`
- `notes`

を持ちます。

これにより、flexible indication に対しても

- これは `FxTarfDefinition` に uplift できそう
- これは `CouponSwapDefinition` っぽい
- これはまだ柔軟入力のまま残すべき

という判断ができます。

---

# 6. 重要な設計ポイント

## 6.1 typed lane でも irregular schedule を許す
これは今回かなり重要です。

`FxTarfIndication` は typed ですが、

- `RuleBasedScheduleDefinition`
- `ExplicitScheduleDefinition`
- `MixedScheduleDefinition`

のどれでも使えます。

つまり「typed = rigid monthly schedule only」ではありません。

## 6.2 flexible lane でも構造は残す
flexible lane は freeform も許しますが、  
本質は `EconomicClause` にあります。

つまり、
- 自由入力
- でも構造化可能
- 後で uplift しやすい

を狙っています。

## 6.3 uplift は classification + reconstruction
特に flexible lane では、uplift は
- clause の組み合わせを見て product type を推定
- typed definition を再構成
する処理です。

---

# 7. 使い方

## 7.1 Typed TARF indication

```python
from indication_layer import example_typed_tarf_indication

ind = example_typed_tarf_indication()
definition = ind.to_definition()
```

これは deterministic です。

## 7.2 Flexible TARF-like indication

```python
from indication_layer import example_flexible_tarf_like_indication, IndicationUplifter

ind = example_flexible_tarf_like_indication()
uplifter = IndicationUplifter()
result = uplifter.uplift(ind)

print(result.inferred_product_hint)
print(result.confidence)
print(result.definition)
```

これは best-effort uplift です。

## 7.3 Flexible bespoke indication

```python
from indication_layer import example_flexible_bespoke_indication, IndicationUplifter

ind = example_flexible_bespoke_indication()
result = IndicationUplifter().uplift(ind)

if result.definition is None:
    print("keep in flexible lane")
else:
    print("uplifted")
```

---

# 8. 今後の自然な流れ

この層の次は、通常こうなります。

```text
IndicationRequest
   ↓ uplift (optional)
ProductDefinition
   ↓ generate
CDM-like Trade
   ↓ later
pricing / lifecycle / evaluation
```

つまり、このモジュールは
**typed product definition へ昇格する前の入口**です。

---

# 9. 制約と限界

- pricing logic はない
- flexible lane の uplift は heuristic
- freeform_description の意味理解はまだやっていない
- clause の組み合わせから全 product type を完全分類するわけではない

それでも、  
**typed main lane + flexible side lane**  
という構造を作るには十分な土台です。

---

# 10. 一言でまとめる

`indication_layer.py` は、

> **大量処理向けの typed indication を主戦力にしつつ、  
> 現場で必要な flexible indication も structured な形で受け止め、  
> 後で typed product definition へ uplift できるようにする層**

です。
