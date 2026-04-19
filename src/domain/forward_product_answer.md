# 回答例: Ratio-Forward 系 Product Grammar

---

## Step 1

### 回答 1-1
- NORMAL: `K_call = K_put`
- GAP: `K_call < K_put` で sold side KI
- RANGE_GAP: `K_call = K_put` で sold side KI
- COLLAR: `K_put < K_call`
- TWO_STAGE: 各 CF 内では call/put 同 strike、途中で strike が一回変わる

### 回答 1-2
`call_level` / `put_level` は user-input 的な情報であり、
ContractForm / Product Grammar 側では actual option amount の方が contract substance に近いから。

### 回答 1-3
「put 固定」より一般化されており、
どちらを売り側として定義しても同じ grammar を使えるから。

---

## Step 2

### 回答 2-1
Coupon Swap form では、本当に base / quote の通貨交換が起きるので、
少なくとも pay / receive の 2 本の coupon stream が必要になるため。

### 回答 2-2
Coupon Swap form の本質は option activation ではなく coupon exchange だから。
form を分ける以上、KI を option mechanism として前面化しない方が自然である。

### 回答 2-3
trigger と effect scope を分離できるから。
mechanism は trigger に集中し、対象期間は component 構造で表せる。

---

## Step 3

### 回答 3-1
各 CF ごとに exercise / settlement / KI の意味を独立に持てるようになるから。

### 回答 3-2
sold side option に対して `KnockInMechanism` を張る。

### 回答 3-3
1. Coupon Swap は currency exchange coupon で持つ
2. FX Option Package は option package で持つ
3. KI は Coupon Swap では formula 側、FX Option Package では option mechanism 側に出る

---

## Step 4

### 回答 4-1
amount は notional を含む金額ベース、
points は notional に依らない payoff strength 的な尺度だから。

### 回答 4-2
- including hit CF stop: hit した CF も消える
- partial hit CF to target then stop: hit CF では target 到達分だけ交換
- full hit CF then stop: hit CF は full exchange、その後 stop

### 回答 4-3
顧客利益を累積停止条件にする TARF と、
顧客損失側を累積停止条件にする派生バリエーションを分けて扱えるから。

---

## Step 5

### 回答 5-1
同じ economics でも、契約条項・編集方法・説明責任・法的 correspondence が違うから。

### 回答 5-2
Coupon Swap form では
- 2 本の `AccrualCouponLeg`
- GAP economics を埋め込んだ formula
- WKO を future coupon stream deactivate として表す
のが自然。

### 回答 5-3
FX Option Package form では
- per-period call/put package
- two-stage strike switch
- TARGET accumulation mechanism
で構成するのが自然。
