# 为 Proposal 42 投赞成票（使用所有 Position NFT）

## 步骤 1：确认钱包就绪

检查 AWP Wallet 是否已安装并解锁：

```bash
awp-wallet status
```

获取钱包地址（后续步骤中用 `{walletAddr}` 表示）。如果钱包未解锁，先执行 `awp-wallet unlock`。

---

## 步骤 2：获取合约地址

```
GET /registry
```

从返回结果中取得：
- `dao` — AWPDAO 合约地址（后续称 `{daoAddr}`）

---

## 步骤 3：获取用户所有 StakeNFT 持仓

```
GET /staking/user/{walletAddr}/positions
```

示例返回：
```json
[
  {"token_id": 1, "amount": "5000000000000000000000", "lock_end_epoch": 52, "created_epoch": 1},
  {"token_id": 7, "amount": "5000000000000000000000", "lock_end_epoch": 100, "created_epoch": 5},
  {"token_id": 15, "amount": "2000000000000000000000", "lock_end_epoch": 80, "created_epoch": 12}
]
```

记录所有 `token_id` 和 `created_epoch`。

---

## 步骤 4：获取 proposalEpoch 并过滤有效 tokenId

在链上读取 proposal 42 对应的 epoch：

```solidity
function proposalEpoch(uint256 proposalId) view returns (uint64)
// 调用: AWPDAO.proposalEpoch(42)
```

**过滤规则**：只有 `createdEpoch <= proposalEpoch` 的持仓才有投票资格（防操纵机制）。

假设 `proposalEpoch(42)` 返回 `10`，则：
- token_id 1 (createdEpoch=1) — **有效**
- token_id 7 (createdEpoch=5) — **有效**
- token_id 15 (createdEpoch=12) — **无效**，创建于 proposal 之后

同时可检查每个 tokenId 是否已投过票：

```solidity
function hasVotedWithToken(uint256 proposalId, uint256 tokenId) view returns (bool)
// 调用: AWPDAO.hasVotedWithToken(42, 1), AWPDAO.hasVotedWithToken(42, 7)
```

排除已投票的 tokenId，得到最终可用列表，例如：`[1, 7]`。

---

## 步骤 5：编码 params 参数

**关键**：必须使用 `encodeAbiParameters`，**不能使用 `encodePacked`**。

使用 viem 编码 tokenIds 数组：

```javascript
import { encodeAbiParameters } from 'viem'

const params = encodeAbiParameters(
  [{ type: 'uint256[]' }],
  [[1n, 7n]]
)
// 结果: 0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000007
```

---

## 步骤 6：确认交易详情并等待用户确认

向用户展示：

> **投票交易确认**
>
> | 项目 | 值 |
> |------|-----|
> | 合约 | AWPDAO (`{shortAddr(daoAddr)}`) |
> | 方法 | `castVoteWithReasonAndParams` |
> | Proposal ID | 42 |
> | 投票方向 | **1 (赞成 / For)** |
> | 理由 | (空字符串，用户未提供) |
> | 使用的 Position NFT | #1 (5,000.0000 AWP), #7 (5,000.0000 AWP) |
> | 投票权重 | 各持仓: amount x sqrt(min(remainingEpochs, 54)) |
> | 链 | BSC (Chain ID 56) |
>
> **注意**：`castVote()` 和 `castVoteWithReason()` 已被禁用，必须使用 `castVoteWithReasonAndParams`。
>
> 确认执行此交易？

**等待用户明确确认后再继续。**

---

## 步骤 7：执行投票交易

用户确认后，通过 awp-wallet 发送交易：

```bash
awp-wallet send \
  --token {T} \
  --to {daoAddr} \
  --chain bsc \
  --abi "function castVoteWithReasonAndParams(uint256 proposalId, uint8 support, string reason, bytes params)" \
  --args '42' '1' '' '0x000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000007'
```

参数说明：
- `proposalId` = `42`
- `support` = `1`（赞成）
- `reason` = `""`（空字符串，用户未指定理由）
- `params` = 上一步编码的 tokenIds 数组

---

## 步骤 8：展示结果

交易成功后，显示：

> **投票成功**
>
> - Proposal: #42
> - 投票方向: 赞成 (For)
> - 使用的 Position: #1, #7
> - 交易: https://bscscan.com/tx/{txHash}
>
> 当前投票情况：

随后调用链上 `proposalVotes(42)` 查询最新票数：

```solidity
function proposalVotes(uint256 proposalId) view returns (uint256 againstVotes, uint256 forVotes, uint256 abstainVotes)
```

展示：

> | 类别 | 票数 |
> |------|------|
> | 赞成 (For) | {formatAWP(forVotes)} |
> | 反对 (Against) | {formatAWP(againstVotes)} |
> | 弃权 (Abstain) | {formatAWP(abstainVotes)} |
