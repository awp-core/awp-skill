# 存入 10,000 AWP 并分配给 Subnet 3 上的 Agent

本次操作涉及两个步骤：**S2 (Deposit AWP)** 和 **S3 (Allocate)**。两者都需要钱包已就绪。

---

## 前置检查

### 1. 确认钱包已安装并解锁

确认 AWP Wallet skill 已安装（skill URL: `https://raw.githubusercontent.com/awpix/agent-wallet/refs/heads/main/SKILL.md`）。如未安装，先安装。

获取钱包地址（后续用 `{walletAddr}` 表示）：

```bash
awp-wallet status
```

确认钱包已解锁、链为 BSC。如未解锁：

```bash
awp-wallet unlock --chain bsc
```

### 2. 获取合约地址

```
GET {AWP_API_URL}/registry
```

从返回结果中提取：
- `awpToken` → `{awpTokenAddr}`
- `stakeNFT` → `{stakeNFTAddr}`
- `rootNet` → `{rootNetAddr}`

### 3. 检查用户注册状态

```
GET {AWP_API_URL}/address/{walletAddr}/check
```

若 `isRegisteredUser` 为 `false`，需要先执行 **S1 (Register User)** —— 调用 `RootNet.register()`。本流程假设用户已注册。

### 4. 检查钱包 AWP 余额

```bash
awp-wallet balance --token {T} --chain bsc --asset {awpTokenAddr}
```

确认余额 >= 10,000 AWP。若不足，提示用户余额不够，终止操作。

---

## 步骤一：S2 · Deposit AWP（存入 10,000 AWP，锁 26 epoch）

### 1a. Approve AWP 给 StakeNFT

向用户展示交易详情，等待确认：

> **Approve 交易确认**
>
> - 合约: AWPToken (`{shortAddr(awpTokenAddr)}`)
> - 操作: `approve(spender, amount)`
> - Spender: **StakeNFT** (`{shortAddr(stakeNFTAddr)}`)
> - 数量: 10,000.0000 AWP
> - 链: BSC (Chain ID 56)
>
> 是否确认执行 Approve？

用户确认后执行：

```bash
awp-wallet approve --token {T} --asset {awpTokenAddr} --spender {stakeNFTAddr} --amount 10000 --chain bsc
```

返回结果：`{"txHash": "0xAAA...", "status": "confirmed"}`

> Approve 已确认: https://bscscan.com/tx/0xAAA...

**等待 Approve 交易收据确认后，再进行下一步。**

### 1b. 调用 StakeNFT.deposit

向用户展示交易详情，等待确认：

> **Deposit 交易确认**
>
> - 合约: StakeNFT (`{shortAddr(stakeNFTAddr)}`)
> - 操作: `deposit(amount, lockEpochs)`
> - 数量: 10,000.0000 AWP (`10000000000000000000000` wei)
> - 锁定期: 26 epoch（约 182 天 / ~6 个月）
> - 链: BSC (Chain ID 56)
>
> 是否确认执行 Deposit？

用户确认后，通过钱包发送交易：

```bash
awp-wallet send --token {T} --to {stakeNFTAddr} --chain bsc \
  --abi "function deposit(uint256 amount, uint64 lockEpochs) returns (uint256)" \
  --args "10000000000000000000000" "26"
```

返回结果包含 txHash。

> Deposit 已确认: https://bscscan.com/tx/0xBBB...

### 1c. 解析 Deposited 事件

从交易回执的 `Deposited` 事件中提取：
- `tokenId` — 新铸造的 StakeNFT 仓位 ID
- `lockEndEpoch` — 锁定结束的**绝对** epoch 号（注意：这是绝对值，不是输入的相对 lockEpochs=26）

> **存入成功**
>
> | 字段 | 值 |
> |------|-----|
> | 仓位 | Position #{tokenId} |
> | 数量 | 10,000.0000 AWP |
> | 锁定结束 | Epoch {lockEndEpoch} |
> | 交易 | https://bscscan.com/tx/0xBBB... |

---

## 步骤二：S3 · Allocate（将全部 10,000 AWP 分配给 Subnet 3 上的 Agent）

### 2a. 确认未分配余额

```
GET {AWP_API_URL}/staking/user/{walletAddr}/balance
```

确认 `unallocated` >= `10000000000000000000000`（10,000 AWP in wei）。刚存入的 AWP 应该全部处于未分配状态。

### 2b. 验证输入

- Agent 地址: `0xAbCdEf1234567890AbCdEf1234567890AbCdEf12` — 格式合法（0x + 40 hex 字符）
- Subnet ID: `3` — 正整数，合法

可选：确认 agent 在 subnet 3 上存在：

```
GET {AWP_API_URL}/subnets/3/agents/0xAbCdEf1234567890AbCdEf1234567890AbCdEf12
```

### 2c. 调用 RootNet.allocate

向用户展示交易详情，等待确认：

> **Allocate 交易确认**
>
> - 合约: RootNet (`{shortAddr(rootNetAddr)}`)
> - 操作: `allocate(agent, subnetId, amount)`
> - Agent: `0xAbCd...Ef12`
> - Subnet: #3
> - 数量: 10,000.0000 AWP (`10000000000000000000000` wei)
> - 链: BSC (Chain ID 56)
>
> 是否确认执行 Allocate？

用户确认后，通过钱包发送交易：

```bash
awp-wallet send --token {T} --to {rootNetAddr} --chain bsc \
  --abi "function allocate(address agent, uint256 subnetId, uint256 amount)" \
  --args "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12" "3" "10000000000000000000000"
```

返回结果包含 txHash。

> Allocate 已确认: https://bscscan.com/tx/0xCCC...

---

## 最终确认 — 查询更新后的余额

```
GET {AWP_API_URL}/staking/user/{walletAddr}/balance
```

> **操作完成 — 余额概览**
>
> | 项目 | 值 |
> |------|-----|
> | 总质押 | {formatAWP(totalStaked)} |
> | 已分配 | {formatAWP(totalAllocated)} |
> | 未分配 | {formatAWP(unallocated)} |

```
GET {AWP_API_URL}/staking/user/{walletAddr}/allocations
```

> **分配详情**
>
> | Agent | Subnet | 数量 |
> |-------|--------|------|
> | `0xAbCd...Ef12` | #3 | 10,000.0000 AWP |

---

## 交易汇总

| # | 操作 | 合约 | 函数 | BSCScan |
|---|------|------|------|---------|
| 1 | Approve | AWPToken | `approve(StakeNFT, 10000 AWP)` | https://bscscan.com/tx/0xAAA... |
| 2 | Deposit | StakeNFT | `deposit(10000 AWP, 26 epochs)` | https://bscscan.com/tx/0xBBB... |
| 3 | Allocate | RootNet | `allocate(0xAbCd...Ef12, subnet 3, 10000 AWP)` | https://bscscan.com/tx/0xCCC... |

---

## 关键注意事项

- **Approve 目标**: Deposit 的 approve 给 **StakeNFT**（不是 RootNet）。若使用 `registerAndStake` 一步完成，approve 目标则是 RootNet。
- **lockEndEpoch 是绝对值**: `Deposited` 事件的 `lockEndEpoch` 字段是绝对 epoch 号，不是输入的相对 26 epoch。
- **每笔交易需用户确认**: 不自动执行任何写操作，每笔交易展示详情后等待用户明确确认。
- **金额处理**: 所有链上金额为 wei 字符串，用 BigInt 处理，显示时转为人类可读格式（除以 10^18，保留 4 位小数）。
- **合约地址动态获取**: 所有合约地址通过 `GET /registry` 获取，不硬编码。
