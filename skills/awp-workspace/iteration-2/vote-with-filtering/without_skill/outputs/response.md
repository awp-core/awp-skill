# 给 Proposal 55 投赞成票（使用所有符合条件的 Position NFT）

好的，我来帮你完成这个投票操作。AWP DAO 的投票有几个重要限制需要先过滤，下面是完整流程。

## 重要前提

AWP DAO 的投票必须使用 `castVoteWithReasonAndParams` 函数。`castVote()` 和 `castVoteWithReason()` 在合约中被禁用（会直接 revert）。

## 步骤 1：获取你的所有 Position NFT

由于 StakeNFT 合约不支持枚举（没有 `tokenOfOwnerByIndex`），你需要通过 REST API 获取你的所有 position：

```javascript
const response = await fetch(`${AWP_API_URL}/staking/user/${yourAddress}/positions`);
const { positions } = await response.json();
// positions: [{ tokenId, amount, lockEndTime, createdAt, ... }, ...]
```

## 步骤 2：获取 Proposal 创建时间

```javascript
const proposalId = 55n;
const proposalCreatedAt = await publicClient.readContract({
  address: awpDaoAddress,
  abi: parseAbi(['function proposalCreatedAt(uint256) view returns (uint256)']),
  functionName: 'proposalCreatedAt',
  args: [proposalId]
});
```

同时确认 proposal 当前处于 Active 状态：

```javascript
const state = await publicClient.readContract({
  address: awpDaoAddress,
  abi: parseAbi(['function state(uint256) view returns (uint8)']),
  functionName: 'state',
  args: [proposalId]
});
// state === 1 表示 Active，才能投票
```

## 步骤 3：过滤不符合条件的 Position

需要排除以下三类 position：

| 过滤条件 | 原因 | 对应合约错误 |
|----------|------|-------------|
| `createdAt >= proposalCreatedAt` | Position 在 proposal 创建之后铸造，不具备投票资格 | `MintedAfterProposal` |
| `lockEndTime <= block.timestamp` | 锁仓已过期 | `LockExpired` |
| 该 tokenId 已经对此 proposal 投过票 | 同一 token 不能重复投票 | `TokenAlreadyVoted` |

```javascript
const currentTimestamp = BigInt(Math.floor(Date.now() / 1000));

const eligibleTokenIds = [];

for (const pos of positions) {
  const tokenId = BigInt(pos.tokenId);

  // 过滤 1：Position 必须在 proposal 创建之前铸造
  if (BigInt(pos.createdAt) >= proposalCreatedAt) {
    console.log(`跳过 tokenId ${tokenId}：铸造时间晚于 proposal 创建时间`);
    continue;
  }

  // 过滤 2：锁仓未过期
  if (BigInt(pos.lockEndTime) <= currentTimestamp) {
    console.log(`跳过 tokenId ${tokenId}：锁仓已过期`);
    continue;
  }

  // 过滤 3：检查是否已对该 proposal 投过票
  const alreadyVoted = await publicClient.readContract({
    address: awpDaoAddress,
    abi: parseAbi(['function hasVotedWithToken(uint256, uint256) view returns (bool)']),
    functionName: 'hasVotedWithToken',
    args: [proposalId, tokenId]
  });

  if (alreadyVoted) {
    console.log(`跳过 tokenId ${tokenId}：已对 proposal 55 投过票`);
    continue;
  }

  eligibleTokenIds.push(tokenId);
}

console.log(`符合条件的 tokenId: [${eligibleTokenIds.join(', ')}]`);
```

## 步骤 4：编码 params 并发送投票交易

```javascript
import { encodeAbiParameters } from 'viem';

// params 必须编码为 uint256[] 类型
const params = encodeAbiParameters(
  [{ type: 'uint256[]' }],
  [eligibleTokenIds]
);

// support: 0 = Against, 1 = For, 2 = Abstain
// 赞成票 = 1
const txHash = await walletClient.writeContract({
  address: awpDaoAddress,
  abi: parseAbi([
    'function castVoteWithReasonAndParams(uint256 proposalId, uint8 support, string reason, bytes params) returns (uint256)'
  ]),
  functionName: 'castVoteWithReasonAndParams',
  args: [
    55n,           // proposalId
    1,             // support = For（赞成）
    '',            // reason（可留空）
    params         // 编码后的 tokenId 数组
  ]
});

console.log(`投票交易已发送: https://bscscan.com/tx/${txHash}`);
```

## 完整的注意事项

1. **不要使用 `castVote()` 或 `castVoteWithReason()`** —— 合约会直接 revert（错误：`UsecastVoteWithParams`）。
2. **params 编码方式**：必须用 `encodeAbiParameters([{type:'uint256[]'}], [tokenIds])`，不要使用 `encodePacked`。
3. **合约地址**：不要硬编码，应通过 `GET /registry` 动态获取 AWPDAO 和 StakeNFT 的地址。
4. **如果没有任何符合条件的 position**，交易会失败（`NoTokens` 错误），请先确认过滤后的列表不为空。
5. **确认 proposal 状态为 Active（state = 1）** 再投票，否则会收到 `GovernorUnexpectedProposalState` 错误。

## 可能遇到的错误

| 错误 | 含义 |
|------|------|
| `UsecastVoteWithParams` | 使用了被禁用的 castVote/castVoteWithReason |
| `MintedAfterProposal` | Position NFT 在 proposal 创建后才铸造 |
| `LockExpired` | Position 锁仓已过期 |
| `TokenAlreadyVoted` | 该 tokenId 已经对此 proposal 投过票 |
| `NotTokenOwner` | 你不是该 tokenId 的所有者 |
| `NoTokens` | 传入的 tokenId 数组为空 |
| `GovernorUnexpectedProposalState` | Proposal 不在 Active 状态 |
