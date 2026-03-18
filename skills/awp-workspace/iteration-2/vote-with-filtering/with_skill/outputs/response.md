# Vote For Proposal 55 — Full Workflow

## Step 1: Setup — Fetch Contract Addresses & Wallet

```bash
# 获取合约地址
REGISTRY=$(curl -s {API_BASE}/registry)
ROOT_NET=$(echo $REGISTRY | jq -r '.rootNet')
AWP_TOKEN=$(echo $REGISTRY | jq -r '.awpToken')
STAKE_NFT=$(echo $REGISTRY | jq -r '.stakeNFT')
DAO_ADDR=$(echo $REGISTRY | jq -r '.dao')

# 获取钱包地址
WALLET_ADDR=$(awp-wallet status --token {T} | jq -r '.address')
```

## Step 2: Fetch Your Positions

```bash
POSITIONS=$(curl -s {API_BASE}/staking/user/$WALLET_ADDR/positions)
# 返回示例:
# [
#   {"token_id": 1, "amount": "5000000000000000000000", "lock_end_time": 1710604800, "created_at": 1710000000},
#   {"token_id": 7, "amount": "5000000000000000000000", "lock_end_time": 1713196800, "created_at": 1710345600},
#   ...
# ]
```

> **注意**: StakeNFT 不是 ERC721Enumerable，无法在链上枚举 tokenId，必须通过 REST API 获取 position 列表。

## Step 3: Fetch Proposal Creation Timestamp

```bash
PROPOSAL_CREATED=$(cast call $DAO_ADDR "proposalCreatedAt(uint256)" 55 --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
echo "Proposal 55 创建时间: $PROPOSAL_CREATED"
```

## Step 4: Filter Eligible Positions (Anti-Manipulation Rule)

**规则**: 只有 `created_at` **严格小于** `proposalCreatedAt` 的 position 才有投票资格。`created_at >= proposalCreatedAt` 的 position 会被**屏蔽**，无法参与投票。

这是防操纵机制——防止用户在提案创建后才去质押以获取投票权。

```bash
# 过滤逻辑: 只保留 created_at < PROPOSAL_CREATED 的 position
ELIGIBLE_IDS=$(echo $POSITIONS | jq -r --arg pc "$PROPOSAL_CREATED" \
  '[.[] | select(.created_at < ($pc | tonumber)) | .token_id] | join(",")')

echo "符合条件的 tokenIds: $ELIGIBLE_IDS"

# 被过滤掉的 position（不符合条件）
BLOCKED_IDS=$(echo $POSITIONS | jq -r --arg pc "$PROPOSAL_CREATED" \
  '[.[] | select(.created_at >= ($pc | tonumber)) | .token_id] | join(",")')

echo "被屏蔽的 tokenIds (created_at >= proposalCreatedAt): $BLOCKED_IDS"
```

**过滤示例**:

假设 `proposalCreatedAt = 1710200000`:

| token_id | created_at | 是否符合条件 | 原因 |
|----------|------------|-------------|------|
| 1 | 1710000000 | 符合 | 1710000000 < 1710200000 |
| 7 | 1710345600 | 屏蔽 | 1710345600 >= 1710200000 |

## Step 5: Encode Token IDs as ABI Parameters

```bash
# 将符合条件的 tokenIds 编码为 ABI 参数
# 使用 encodeAbiParameters，不要用 encodePacked！
PARAMS=$(cast abi-encode "f(uint256[])" "[$ELIGIBLE_IDS]")
```

> **关键**: 必须使用 `encodeAbiParameters`（即 `cast abi-encode`），绝对不能用 `encodePacked`。

## Step 6: Show Transaction Details (Write Safety)

投票前确认交易详情:

| 字段 | 值 |
|------|-----|
| **合约** | AWPDAO (`$DAO_ADDR`) |
| **方法** | `castVoteWithReasonAndParams(uint256,uint8,string,bytes)` |
| **Proposal ID** | `55` |
| **Support** | `1` (For / 赞成) |
| **Reason** | 用户提供的理由（可为空字符串） |
| **Params** | ABI 编码的 tokenIds 数组 |
| **使用的 NFTs** | `$ELIGIBLE_IDS` |
| **Chain** | BSC (Chain ID 56) |

> **注意**: `castVote()` 和 `castVoteWithReason()` 已被合约屏蔽，会 revert。必须使用 `castVoteWithReasonAndParams`。

**是否确认执行?** (等待用户确认)

## Step 7: Execute Vote

```bash
# 投赞成票 (support=1)，使用所有符合条件的 position NFT
awp-wallet send --token {T} \
  --to $DAO_ADDR \
  --data $(cast calldata "castVoteWithReasonAndParams(uint256,uint8,string,bytes)" \
    55 \
    1 \
    "" \
    $PARAMS) \
  --chain bsc
```

## Step 8: Confirm & Show Result

交易成功后显示:

> **投票成功!**
>
> - Proposal: #55
> - 投票方向: **For (赞成)**
> - 使用的 Position NFTs: {ELIGIBLE_IDS}
> - 被屏蔽的 Position NFTs: {BLOCKED_IDS} (created_at >= proposalCreatedAt)
> - 投票力公式: `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)`
> - BSCScan: `https://bscscan.com/tx/{txHash}`

---

## Anti-Manipulation Rule Summary

| 条件 | 结果 |
|------|------|
| `position.created_at < proposalCreatedAt` | **可以投票** — 该 position 在提案创建之前就已存在 |
| `position.created_at >= proposalCreatedAt` | **不能投票** — 该 position 在提案创建时或之后才创建，被视为操纵行为 |

此规则确保只有在提案发起**之前**就已质押的用户才能参与投票，防止有人看到提案后临时质押来影响投票结果。每个 tokenId 还有单独的防重复投票检查（`hasVotedWithToken`）。
