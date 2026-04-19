# 学習課題: Ratio-Forward 系 Product Grammar

この課題集は `ratio_forward_product_grammars.py` に慣れるためのものです。

---

## Step 1: Shared economics

### 問題 1-1
`NORMAL`, `GAP`, `RANGE_GAP`, `COLLAR`, `TWO_STAGE` の違いを日本語で説明してください。

### 問題 1-2
`OptionAmountSpec` において、なぜ Product Grammar では `call_level` / `put_level` ではなく
計算後の option amount を使う方が自然か説明してください。

### 問題 1-3
「sold side option にのみ KI」という汎用定義の利点を説明してください。

---

## Step 2: Coupon Swap form

### 問題 2-1
Coupon Swap form で `AccrualCouponLeg` を 2 本使う理由を説明してください。

### 問題 2-2
Coupon Swap form では、なぜ KI を option mechanism として持たず
coupon formula に吸収する方針が自然なのか説明してください。

### 問題 2-3
WKO がつくとき、なぜ mechanism に特殊な per-period 条件を増やすより
対象 component 群を明示する方がよいか説明してください。

---

## Step 3: FX Option Package form

### 問題 3-1
FX Option Package form で「1 期 = 1 option package」とする意味を説明してください。

### 問題 3-2
sold-side KI を option package form でどう表現するか説明してください。

### 問題 3-3
Coupon Swap form と FX Option Package form の最大の違いを 3 点挙げてください。

---

## Step 4: TARGET

### 問題 4-1
TARGET の metric として amount / points があることの意味を説明してください。

### 問題 4-2
TARGET の hit action 3 パターンを、それぞれ言葉で説明してください。

### 問題 4-3
TARGET accumulation side として client gain / client loss を分ける意味を説明してください。

---

## Step 5: 総合

### 問題 5-1
同じ economics を 2 つの contract form に落とし分けることの利点を説明してください。

### 問題 5-2
GAP + WKO を Coupon Swap form で設計する方針を文章で書いてください。

### 問題 5-3
TWO_STAGE + TARGET を FX Option Package form で設計する方針を文章で書いてください。
