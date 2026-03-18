# W2 Emission Alert — Epoch 结算通知 + Top 收益地址

## 订阅事件

连接 WebSocket 并订阅 3 个 emission 事件：

```
WebSocket: wss://api.awp.network/ws/live

发送订阅消息:
{"subscribe": ["EpochSettled", "RecipientAWPDistributed", "DAOMatchDistributed"]}
```

这 3 个事件缺一不可：
- **EpochSettled** — 标志一个 epoch 结算完成，携带 `epoch`、`totalEmission`、`recipientCount`
- **RecipientAWPDistributed** — 每个收益方的分发明细，携带 `epoch`、`recipient`、`awpAmount`
- **DAOMatchDistributed** — DAO 匹配资金总额，携带 `epoch`、`amount`

## 数据累积流程

每个 epoch 结算时，链上会触发多条事件。处理逻辑如下：

### 第 1 步：接收 RecipientAWPDistributed 事件并累积

每收到一条 `RecipientAWPDistributed`，按 epoch 分组存入内存 map：

```
收到消息:
{"type": "RecipientAWPDistributed", "blockNumber": 12345678, "txHash": "0xabc...", "data": {"epoch": "42", "recipient": "0x1234...", "awpAmount": "500000000000000000000000"}}

操作: recipients[epoch][recipient] += BigInt(awpAmount)
```

注意：`awpAmount` 是字符串类型的 wei 值，必须用 BigInt 处理，绝不能用 Number（超过 2^53 会丢失精度）。

### 第 2 步：接收 DAOMatchDistributed 事件

```
收到消息:
{"type": "DAOMatchDistributed", "blockNumber": 12345680, "txHash": "0xdef...", "data": {"epoch": "42", "amount": "7900000000000000000000000"}}

操作: daoMatch[epoch] = BigInt(amount)
```

协议的 emission split 是 50% recipients / 50% DAO，所以 DAO match 金额大约等于 recipient 总分发的一半。

### 第 3 步：接收 EpochSettled 触发展示

```
收到消息:
{"type": "EpochSettled", "blockNumber": 12345682, "txHash": "0x789...", "data": {"epoch": "42", "totalEmission": "15800000000000000000000000", "recipientCount": "128"}}
```

此时：
1. 从已累积的 `recipients[42]` 中按 awpAmount 降序排序，取 top 5
2. 读取 `daoMatch[42]` 获取 DAO 匹配金额
3. 调用 `GET /emission/current` 获取最新 emission 状态（确认 epoch 已更新）
4. 组装并展示告警信息

## 告警展示格式

```
~ Epoch 42 Settled
  Total emission: 15,800,000.0000 AWP
  Recipients: 128
  DAO match: 7,900,000.0000 AWP
  Top recipients:
    1. 0x1234...abcd — 1,250,000.0000 AWP
    2. 0x5678...ef01 — 980,500.0000 AWP
    3. 0x9abc...2345 — 750,200.0000 AWP
    4. 0xdef0...6789 — 620,000.0000 AWP
    5. 0x1111...aaaa — 510,800.0000 AWP
  BSCScan: https://bscscan.com/tx/0x789...
```

格式说明：
- 所有金额从 wei 转换为人类可读格式：`amount / 10^18`，保留 4 位小数，千位分隔符
- 地址使用 `{shortAddr(addr)}` 缩写：前 6 位 + ... + 后 4 位
- 附带 EpochSettled 事件的 BSCScan 交易链接

## Polling 降级方案

当 WebSocket 连接不可用时（连接被拒、超时、反复断线），自动切换到 HTTP 轮询：

### 轮询流程

```
1. 每 60 秒请求 GET /emission/current
   响应: {"epoch": "42", "dailyEmission": "15800000000000000000000000", "totalWeight": "5000"}

2. 比较返回的 epoch 与上一次记录的 epoch
   - 如果 epoch 没变 → 继续等待，60 秒后再查
   - 如果 epoch 增加了 → 检测到新 epoch 结算

3. 发现 epoch 变化后，请求 GET /emission/epochs?page=1&limit=5
   响应: [{"epoch_id": 42, "start_time": 1710000000, "daily_emission": "15800000000000000000000000", "dao_emission": "7500000000000000000000000"}]

4. 用 epoch 详情组装告警（注意：轮询方式无法获取逐条 RecipientAWPDistributed，
   因此 top recipients 列表不可用，只能展示 epoch 总览）
```

### 降级告警格式（无 top recipients）

```
~ Epoch 42 Settled (via polling)
  Daily emission: 15,800,000.0000 AWP
  DAO emission: 7,500,000.0000 AWP
  (Top recipients unavailable — WebSocket required for per-recipient data)
```

## 断线重连策略

WebSocket 断开时自动重连：

| 参数 | 值 |
|------|-----|
| 初始延迟 | 1 秒 |
| 退避因子 | 2x |
| 最大延迟 | 30 秒 |
| 重连后操作 | 重新发送 subscribe 消息 |
| 延迟重置 | 成功收到第一条消息后重置为 1 秒 |

重连序列：1s → 2s → 4s → 8s → 16s → 30s → 30s → ...

如果连续 5 次重连失败（约 85 秒），自动切换到 polling 降级方案。WebSocket 恢复后可随时切回。

## 错误处理

| 错误 | 原因 | 恢复策略 |
|------|------|----------|
| WebSocket 连接被拒 | API 宕机或网络问题 | 指数退避重试；检查 `GET /health` |
| WebSocket 意外关闭 | 服务器重启或超时 | 自动重连，重新订阅 |
| 未收到任何事件 | 事件类型名拼写错误 | 核对 protocol.md 中的 25 种事件类型 |
| 轮询未检测到 epoch 变化 | Epoch 尚未结算 | 继续每 60 秒轮询 |
| `/emission/current` 返回 500 | API 错误 | 30 秒后重试 |
