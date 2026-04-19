# 学習課題: Ratio-Forward 系 Product Grammar 完全版

---

## Step 1: Form separation

### 問題 1-1
同じ economics を Coupon Swap form と FX Option Package form に分ける理由を説明してください。

### 問題 1-2
Coupon Swap form で sold-side KI を coupon formula に吸収する理由を説明してください。

### 問題 1-3
FX Option Package form で sold-side KI を explicit `KnockInMechanism` にする理由を説明してください。

---

## Step 2: Schedules

### 問題 2-1
なぜ full builder は explicit `DateListSchedule` を要求するのか説明してください。

### 問題 2-2
core の semantic schedule graph と full grammar builder をどう接続するか説明してください。

---

## Step 3: TARGET

### 問題 3-1
`AMOUNT` と `POINTS` の違いを説明してください。

### 問題 3-2
`CLIENT_GAIN` と `CLIENT_LOSS` を分ける理由を説明してください。

### 問題 3-3
3 つの `TargetHitAction` の違いを説明してください。

---

## Step 4: WKO

### 問題 4-1
monitoring start と affected start の違いを説明してください。

### 問題 4-2
なぜ WKO の effect scope は component ids で持つ方が自然か説明してください。

---

## Step 5: Simulation

### 問題 5-1
`BuiltRatioForwardContract` が `ContractForm` 単体より有用な理由を説明してください。

### 問題 5-2
`simulate_ratio_forward_series(...)` が何を計算するか整理してください。

### 問題 5-3
partial hit-CF target action で exchange scale を使う意味を説明してください。
