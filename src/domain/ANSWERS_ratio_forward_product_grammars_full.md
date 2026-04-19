# 回答例: Ratio-Forward 系 Product Grammar 完全版

---

## Step 1

### 回答 1-1
契約形態が違うと authoring / editing / legal correspondence が違うから。  
same economics でも same form に潰さない方が自然。

### 回答 1-2
Coupon Swap form の本質は option activation ではなく coupon exchange だから。  
そのため KI は coupon payoff rule に吸収した方が form と整合する。

### 回答 1-3
FX Option Package form の本質は option package だから。  
sold-side KI は option leg の activation / effectiveness として持つ方が form に一致する。

---

## Step 2

### 回答 2-1
per-period builder では fixing/payment/accrual の period count を具体的に知る必要があるから。

### 回答 2-2
core 側で semantic schedule graph を持ち、
`materialize()` 後の explicit date lists を full builder に渡す。

---

## Step 3

### 回答 3-1
AMOUNT は実際の quote-currency payoff 金額、POINTS は notional-free な payoff strength。

### 回答 3-2
TARF 的には利益累積停止と損失累積停止の両バリエーションがあるため。

### 回答 3-3
- including hit CF: hit CF も消す
- partial hit CF: target 到達分だけ交換
- full hit CF then stop: hit CF は満額、その後 stop

---

## Step 4

### 回答 4-1
monitoring start は barrier をいつから見るか、
affected start は hit したときにどの将来 component から止めるか。

### 回答 4-2
trigger と effect scope を分離できるから。  
mechanism は trigger に集中し、どの leg / option が止まるかは structure 側で表せる。

---

## Step 5

### 回答 5-1
ContractForm だけでは period metadata や payment mapping が足りない。  
`BuiltRatioForwardContract` は downstream simulation に必要な情報をまとめて持てる。

### 回答 5-2
- period-level economics
- KI hit
- WKO hit
- target accumulation
- exchange scale
- termination point
を計算する。

### 回答 5-3
hit CF 全額ではなく、残 target 分だけ交換したいから。  
そのため full CF payoff に対して比例縮小係数が必要になる。
