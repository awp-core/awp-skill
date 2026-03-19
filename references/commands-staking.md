# AWP Staking Commands

**API Base URL**: `{API_BASE}/api` (deployment-specific — do not hardcode)

> **Note**: On-chain command templates below use `cast` (Foundry) for calldata encoding.
> For gasless operations, use the bundled scripts instead — they require only curl+jq+python3.
> If `cast` is not available, pre-compute the 4-byte function selectors and use python3 for ABI encoding.

## Setup (run once per session)

```bash
REGISTRY=$(curl -s {API_BASE}/api/registry)
AWP_REGISTRY=$(echo $REGISTRY | jq -r '.awpRegistry')
AWP_TOKEN=$(echo $REGISTRY | jq -r '.awpToken')
STAKE_NFT=$(echo $REGISTRY | jq -r '.stakeNFT')
SUBNET_NFT=$(echo $REGISTRY | jq -r '.subnetNFT')
DAO_ADDR=$(echo $REGISTRY | jq -r '.dao')

WALLET_ADDR=$(awp-wallet status --token {T} | jq -r '.address')
```

## Wallet CLI Reference

### Key Parameters

- `--token {T}` = wallet session token from `awp-wallet unlock`
- `--asset` = token **contract address** (e.g. awpTokenAddr from `/registry`), NOT a symbol like "AWP"
- `--chain base` = always use Base for AWP

### Approve Pattern (used by S1, S2)

```bash
# Approve AWP spending — spender varies by action (see each section)
# --asset must be the AWP token contract address from GET /registry -> awpToken
awp-wallet approve --token {T} --asset {awpTokenAddr} --spender {targetAddr} --amount {humanAmount} --chain base
# -> {"txHash": "0x...", "status": "confirmed"}
```

### Balance Check

```bash
# Check AWP balance in wallet (supplements REST API staking balance)
awp-wallet balance --token {T} --chain base --asset {awpTokenAddr}
```

### EIP-712 Signing (for gasless bindFor / setRecipientFor)

```bash
# Sign typed data for gasless binding or set-recipient
awp-wallet sign-typed-data --token {T} --data '{...EIP712 JSON...}'
# -> {"signature": "0x...", "v": 28, "r": "0x...", "s": "0x..."}
```

---

## S1 · Account System V2: Bind & Delegate

### Check Registration

```
GET /address/{address}/check
```
```json
{
  "isRegistered": true,
  "boundTo": "0x...",
  "recipient": "0x..."
}
```
> `isRegistered` = `boundTo != 0x0 || recipient != 0x0`.

### Contract Calls — Registration (Optional)

```solidity
// register() is optional — equivalent to setRecipient(msg.sender)
function register()

// One-click: register + deposit + allocate
function registerAndStake(uint256 depositAmount, uint64 lockDuration, address agent, uint256 subnetId, uint256 allocateAmount)
// lockDuration is in SECONDS (not epochs)
// IMPORTANT: approve target for registerAndStake is AWPRegistry, NOT StakeNFT
// AWPToken.approve(awpRegistry, depositAmount) -> then registerAndStake(...)
```

### Contract Calls — Tree-Based Binding

```solidity
// Bind msg.sender to a target (tree-based with anti-cycle check; supports rebind)
function bind(address target)

// Gasless bind via EIP-712 signature
function bindFor(address user, address target, uint256 deadline, uint8 v, bytes32 r, bytes32 s)
```
> `unbind()` is **removed** in V2. To change binding, call `bind(newTarget)`.
> `removeAgent()` is **removed** in V2.

### Contract Calls — Delegation & Recipient

```solidity
// Grant delegation to an address
function grantDelegate(address delegate)

// Revoke delegation from an address
function revokeDelegate(address delegate)

// Set reward recipient
function setRecipient(address recipient)

// Gasless set recipient via EIP-712 signature
function setRecipientFor(address user, address recipient, uint256 deadline, uint8 v, bytes32 r, bytes32 s)

// View: walk boundTo chain to resolve final recipient
function resolveRecipient(address addr) view returns (address)

// View: check if address is registered
function isRegistered(address addr) view returns (bool)
```

### Gasless Bind Relay

```
POST /relay/bind
```
**Request:**
```json
{"agent": "0xAgent...", "target": "0xTarget...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```
**Response:**
```json
{"txHash": "0x..."}
```

### Gasless Set-Recipient Relay

```
POST /relay/set-recipient
```
**Request:**
```json
{"user": "0x1234...", "recipient": "0x5678...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```
**Response:**
```json
{"txHash": "0x..."}
```

> Rate limit: 100 requests per IP per 1 hour (shared across all relay endpoints).
> Signature format: Standard EIP-712 signature (r[32] + s[32] + v[1] = 65 bytes), hex-encoded with `0x` prefix.
> `/relay/register` is **removed** in V2 (register() is optional).

**Error responses:**

| Code | Body | Meaning |
|------|------|---------|
| 400 | `{"error": "invalid user address"}` | Malformed Ethereum address |
| 400 | `{"error": "deadline is missing or expired"}` | Deadline is 0 or in the past |
| 400 | `{"error": "missing signature"}` | Signature field empty |
| 400 | `{"error": "invalid signature"}` | EIP-712 signature verification failed |
| 400 | `{"error": "signature expired"}` | On-chain deadline check failed |
| 400 | `{"error": "cycle detected"}` | Binding would create a cycle in the tree |
| 400 | `{"error": "contract is paused"}` | AWPRegistry is in emergency pause state |
| 400 | `{"error": "relay transaction failed"}` | Unrecognized on-chain revert |
| 429 | `{"error": "rate limit exceeded: max 100 requests per 3600s"}` | IP rate limit exceeded |

### Complete Command Templates

**Step 1: Get addresses and nonce**
```bash
# Get nonce for EIP-712 signatures
NONCE=$(cast call $AWP_REGISTRY "nonces(address)" $WALLET_ADDR --rpc-url $RPC_URL | cast --to-dec)
```

**On-chain bind (has ETH gas):**
```bash
# Bind to target (self-bind: TARGET=WALLET_ADDR)
TARGET={targetAddress}
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "bind(address)" $TARGET) --chain base
```

**On-chain registerAndStake (has ETH gas):**
```bash
# Step 1: Approve AWP to AWPRegistry
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $AWP_REGISTRY --amount {depositAmountHuman} --chain base
# Step 2: registerAndStake
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "registerAndStake(uint256,uint64,address,uint256,uint256)" {depositAmountWei} {lockDurationSeconds} {agentAddr} {subnetId} {allocateAmountWei}) --chain base
```

**Gasless bind (no ETH) — EIP-712 template:**
```bash
TARGET={targetAddress}
DEADLINE=$(date -d '+1 hour' +%s)

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Bind": [
      {"name": "user", "type": "address"},
      {"name": "target", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": '$CHAIN_ID',
    "verifyingContract": "'$AWP_REGISTRY'"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "target": "'$TARGET'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST {API_BASE}/api/relay/bind \
  -H "Content-Type: application/json" \
  -d '{"agent": "'$WALLET_ADDR'", "target": "'$TARGET'", "deadline": '$DEADLINE', "signature": "{signatureHex}"}'
```

**Gasless set-recipient (no ETH) — EIP-712 template:**
```bash
RECIPIENT={recipientAddress}
DEADLINE=$(date -d '+1 hour' +%s)

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "SetRecipient": [
      {"name": "user", "type": "address"},
      {"name": "recipient", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "SetRecipient",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": '$CHAIN_ID',
    "verifyingContract": "'$AWP_REGISTRY'"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "recipient": "'$RECIPIENT'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST {API_BASE}/api/relay/set-recipient \
  -H "Content-Type: application/json" \
  -d '{"user": "'$WALLET_ADDR'", "recipient": "'$RECIPIENT'", "deadline": '$DEADLINE', "signature": "{signatureHex}"}'
```

**Delegation management:**
```bash
# Grant delegate
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "grantDelegate(address)" {delegateAddr}) --chain base

# Revoke delegate
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "revokeDelegate(address)" {delegateAddr}) --chain base

# Set reward recipient (on-chain)
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "setRecipient(address)" {recipientAddr}) --chain base
```

---

## S2 · Deposit AWP

### Contract Calls

```solidity
// Step 1: Approve AWP transfer to StakeNFT
function approve(address spender, uint256 amount) returns (bool)   // on AWPToken
// spender = stakeNFT address (from /registry)

// Step 2: Deposit (after approve receipt confirmed)
function deposit(uint256 amount, uint64 lockDuration) returns (uint256 tokenId)   // on StakeNFT
// lockDuration in SECONDS (e.g., 15724800 = ~26 weeks)
// Emits Deposited(user, tokenId, amount, lockEndTime) — lockEndTime is ABSOLUTE TIMESTAMP

// Optional: Add to existing position
function addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime)   // on StakeNFT
// newLockEndTime is absolute timestamp, must be >= current lockEndTime
// Requires AWPToken.approve(stakeNFT, amount) before calling — same pattern as initial deposit
// CAUTION: Reverts with PositionExpired if the position's lock has already expired.
// Check remainingTime(tokenId) > 0 before calling.

// Withdraw after lock expires (burns position NFT, returns AWP)
function withdraw(uint256 tokenId)   // on StakeNFT
// Only callable when remainingTime(tokenId) == 0
```

### View Functions

```solidity
function positions(uint256 tokenId) view returns (uint128 amount, uint64 lockEndTime, uint64 createdAt)
function getUserTotalStaked(address user) view returns (uint256)     // O(1) total staked balance
function remainingTime(uint256 tokenId) view returns (uint64)        // Remaining lock time in seconds
function getVotingPower(uint256 tokenId) view returns (uint256)      // amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
function getUserVotingPower(address user, uint256[] tokenIds) view returns (uint256)
function getPositionForVoting(uint256 tokenId) view returns (address owner, uint128 amount, uint64 lockEndTime, uint64 createdAt, uint64 remaining, uint256 votingPower)
```

### Complete Command Templates

```bash
# Step 1: Approve AWP to StakeNFT
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $STAKE_NFT --amount {humanAmount} --chain base
# Wait for {"status": "confirmed"}

# Step 2: Deposit (lockDuration in seconds, e.g. 182 days = 15724800)
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "deposit(uint256,uint64)" {amountWei} {lockDurationSeconds}) --chain base

# Withdraw (after lock expires)
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "withdraw(uint256)" {tokenId}) --chain base

# Add to position (approve first, then addToPosition — check remainingTime > 0 first!)
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $STAKE_NFT --amount {addAmountHuman} --chain base
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "addToPosition(uint256,uint256,uint64)" {tokenId} {addAmountWei} {newLockEndTimestamp}) --chain base
```

---

## S3 · Allocate / Deallocate / Reallocate

### Contract Calls

```solidity
// All on AWPRegistry — caller must be staker or delegate
function allocate(address staker, address agent, uint256 subnetId, uint256 amount)
function deallocate(address staker, address agent, uint256 subnetId, uint256 amount)
function reallocate(address staker, address fromAgent, uint256 fromSubnetId, address toAgent, uint256 toSubnetId, uint256 amount)
// Reallocate is immediate — no cooldown
```
> `staker` is an explicit parameter. Caller must be the staker themselves or their delegate.

### StakingVault View Functions

```solidity
function userTotalAllocated(address staker) view returns (uint256)
function getAgentStake(address staker, address agent, uint256 subnetId) view returns (uint256)
function subnetTotalStake(uint256 subnetId) view returns (uint256)
function getSubnetTotalStake(uint256 subnetId) view returns (uint256)
function getAgentSubnets(address staker, address agent) view returns (uint256[])
```
> StakingVault uses `onlyAWPRegistry` modifier and `staker` param name.

### Check Unallocated Balance

```
GET /staking/user/{address}/balance
```
Verify `unallocated >= amount` before allocating.

### Complete Command Templates

```bash
# Allocate (staker = WALLET_ADDR for self-allocation)
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "allocate(address,address,uint256,uint256)" $WALLET_ADDR {agentAddr} {subnetId} {amountWei}) --chain base

# Deallocate
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "deallocate(address,address,uint256,uint256)" $WALLET_ADDR {agentAddr} {subnetId} {amountWei}) --chain base

# Reallocate (immediate, no cooldown)
awp-wallet send --token {T} --to $AWP_REGISTRY --data $(cast calldata "reallocate(address,address,uint256,address,uint256,uint256)" $WALLET_ADDR {fromAgent} {fromSubnetId} {toAgent} {toSubnetId} {amountWei}) --chain base
```
