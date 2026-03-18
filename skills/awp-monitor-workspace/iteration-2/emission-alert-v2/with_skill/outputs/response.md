# Emission Alert — Epoch 结算通知（W2 工作流）

## 1. WebSocket 订阅（主模式）

连接 WebSocket 并订阅 3 个事件：

```
ws://ec2-100-31-107-3.compute-1.amazonaws.com/ws/live
```

发送订阅消息：

```json
{"subscribe": ["EpochSettled", "RecipientAWPDistributed", "DAOMatchDistributed"]}
```

### 事件处理逻辑

**第一步 — EpochSettled 触发总览：**

收到 `EpochSettled` 事件时，提取 `epoch`、`totalEmission`、`recipientCount`，显示 epoch 结算总览。

**第二步 — DAOMatchDistributed 捕获 DAO 匹配金额：**

收到 `DAOMatchDistributed` 事件时，提取 `epoch` 和 `amount`，记录该 epoch 的 DAO 匹配分配金额。

**第三步 — RecipientAWPDistributed 累计收益排名：**

每收到一条 `RecipientAWPDistributed` 事件，按 `recipient` 地址累加 `awpAmount`。同一 epoch 所有分发事件接收完毕后，按金额降序排列，取 top 收益地址。

### 通知展示格式

```
~ Epoch 42 Settled
  Total: 15,800,000.0000 AWP · DAO: 7,900,000.0000 AWP · Recipients: 128
  Top:
    1. 0x1234...abcd — 523,000.0000 AWP
    2. 0x5678...ef01 — 410,500.0000 AWP
    3. 0xaaaa...bbbb — 389,200.0000 AWP
  bscscan.com/tx/0xabcd...1234
```

说明：
- 所有金额从 wei 转换为人类可读格式（`amount / 10^18`，保留 4 位小数）
- 地址使用缩写形式 `0x前4字节...后4字节`
- 附上 BSCScan 交易链接

### 断线重连

WebSocket 断开时自动重连，使用指数退避策略：

| 重试次数 | 等待时间 |
|---------|---------|
| 1 | 1s |
| 2 | 2s |
| 3 | 4s |
| 4 | 8s |
| 5 | 16s |
| 6+ | 30s（上限） |

重连成功后，重新发送订阅消息 `{"subscribe": ["EpochSettled", "RecipientAWPDistributed", "DAOMatchDistributed"]}`。收到第一条有效消息后重置退避计时。

---

## 2. 轮询回退（WebSocket 不可用时）

当 WebSocket 连接失败（连接被拒绝、持续超时等），切换为 HTTP 轮询模式。

### 步骤 1 — 轮询当前 emission 状态

```
GET /emission/current
```

响应示例：
```json
{"epoch": "42", "dailyEmission": "15000000000000000000000000", "totalWeight": "5000"}
```

每 **60 秒**轮询一次，比较 `epoch` 值。如果 epoch 递增，说明新 epoch 已结算。

### 步骤 2 — 获取 epoch 结算详情

检测到 epoch 变化后，请求历史记录：

```
GET /emission/epochs?page=1&limit=5
```

响应示例：
```json
[{"epoch_id": 42, "start_time": 1710000000, "daily_emission": "15000000000000000000000000", "dao_emission": "7500000000000000000000000"}]
```

从响应中提取：
- `daily_emission` — epoch 总排放量（epoch 时长为 1 天，与 WebSocket 的 `totalEmission` 近似相等）
- `dao_emission` — DAO 匹配分配金额

### 轮询模式下的通知格式

```
~ Epoch 42 Settled (polling mode)
  Total: 15,000,000.0000 AWP · DAO: 7,500,000.0000 AWP · Recipients: N/A
  Top earners: N/A (WebSocket required for per-recipient breakdown)
```

**重要限制**：轮询模式下 `recipientCount` 不可用（该字段仅在 WebSocket `EpochSettled` 事件中提供），显示为 "N/A"。同样，per-recipient 分发明细（`RecipientAWPDistributed`）仅通过 WebSocket 推送，轮询模式无法获取 top 收益排名。

### 轮询错误处理

| 错误 | 恢复策略 |
|------|---------|
| `/emission/current` 返回 500 | 30 秒后重试 |
| epoch 无变化 | 继续按 60 秒间隔轮询 |
| 网络超时 | 指数退避重试，上限 30 秒 |

---

## 3. 模式切换策略

1. 启动时优先尝试 WebSocket 连接
2. 若连接失败，先检查 `GET /health` 确认 API 可用性
3. API 健康但 WebSocket 不可用 → 切换为轮询模式
4. 轮询期间持续尝试恢复 WebSocket 连接（每 5 分钟尝试一次）
5. WebSocket 恢复后自动切回实时推送模式
