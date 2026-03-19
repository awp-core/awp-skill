# AWP Staking Commands

**API Base URL**: `https://tapi.awp.sh/api`

> **Note**: On-chain command templates below use `cast` (Foundry) for calldata encoding.
> For gasless operations, use the bundled scripts instead — they require only curl+jq+python3.
> If `cast` is not available, pre-compute the 4-byte function selectors and use python3 for ABI encoding.

## Setup (run once per session)

```bash
REGISTRY=$(curl -s {API_BASE}/registry)
CHAIN_ID=$(echo $REGISTRY | jq -r '.chainId')
ROOT_NET=$(echo $REGISTRY | jq -r '.rootNet')
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
- `--chain bsc` = always use BSC for AWP RootNet

### Approve Pattern (used by S1, S2)

```bash
# Approve AWP spending — spender varies by action (see each section)
# --asset must be the AWP token contract address from GET /registry -> awpToken
awp-wallet approve --token {T} --asset {awpTokenAddr} --spender {targetAddr} --amount {humanAmount} --chain bsc
# -> {"txHash": "0x...", "status": "confirmed"}
```

### Balance Check

```bash
# Check AWP balance in wallet (supplements REST API staking balance)
awp-wallet balance --token {T} --chain bsc --asset {awpTokenAddr}
```

### EIP-712 Signing (for gasless registerFor / bindFor)

```bash
# Sign typed data for gasless registration or binding
awp-wallet sign-typed-data --token {T} --data '{...EIP712 JSON...}'
# -> {"signature": "0x...", "v": 28, "r": "0x...", "s": "0x..."}
```

---

## S1 · Register User & Agent Binding

### Check Registration

```
GET /address/{address}/check
```
```json
{
  "isRegisteredUser": true,
  "isRegisteredAgent": false,
  "ownerAddress": "",
  "isManager": false
}
```

### Contract Calls — User Registration

```solidity
// Simple registration
function register()

// Gasless via EIP-712 signature
function registerFor(address user, uint256 deadline, uint8 v, bytes32 r, bytes32 s)

// One-click: register + deposit + allocate
function registerAndStake(uint256 depositAmount, uint64 lockDuration, address agent, uint256 subnetId, uint256 allocateAmount)
// lockDuration is in SECONDS (not epochs)
// IMPORTANT: approve target for registerAndStake is RootNet, NOT StakeNFT
// AWPToken.approve(rootNet, depositAmount) -> then registerAndStake(...)
```

### Contract Calls — Agent Binding

```solidity
// Bind msg.sender as Agent to a Principal (supports rebind; auto-registers Principal)
function bind(address principal)

// Gasless bind via EIP-712 signature
function bindFor(address agent, address principal, uint256 deadline, uint8 v, bytes32 r, bytes32 s)

// Agent voluntarily unbinds, returns to unregistered status
function unbind()
```

### Contract Calls — Agent Management

```solidity
// Remove agent — Owner/Manager only; StakingVault auto-enumerates subnets
function removeAgent(address agent)

// Grant or revoke manager delegation — Owner/Manager only
function setDelegation(address agent, bool _isManager)

// Redirect emission rewards — Owner only
function setRewardRecipient(address recipient)
```

### Gasless Registration Relay

```
POST /relay/register
```
**Request:**
```json
{"user": "0x1234...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```
**Response:**
```json
{"txHash": "0x..."}
```

```
POST /relay/bind
```
**Request:**
```json
{"agent": "0xAgent...", "principal": "0xPrincipal...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```
**Response:**
```json
{"txHash": "0x..."}
```

> Rate limit: 100 requests per IP per 1 hour (shared across all relay endpoints).
> Signature format: Standard EIP-712 signature (r[32] + s[32] + v[1] = 65 bytes), hex-encoded with `0x` prefix.

**Error responses:**

| Code | Body | Meaning |
|------|------|---------|
| 400 | `{"error": "invalid user address"}` | Malformed Ethereum address |
| 400 | `{"error": "deadline is missing or expired"}` | Deadline is 0 or in the past |
| 400 | `{"error": "missing signature"}` | Signature field empty |
| 400 | `{"error": "invalid signature"}` | EIP-712 signature verification failed |
| 400 | `{"error": "signature expired"}` | On-chain deadline check failed |
| 400 | `{"error": "user already registered"}` | User is already registered on-chain |
| 400 | `{"error": "agent already bound"}` | Agent is already bound to a principal |
| 400 | `{"error": "contract is paused"}` | RootNet is in emergency pause state |
| 400 | `{"error": "relay transaction failed"}` | Unrecognized on-chain revert |
| 429 | `{"error": "rate limit exceeded: max 100 requests per 3600s"}` | IP rate limit exceeded |

### Complete Command Templates

**Step 1: Get addresses and nonce**
```bash
# Get nonce for EIP-712 signatures
NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
```

**On-chain bind (has BNB gas):**
```bash
# Bind as agent to principal (self-bind: PRINCIPAL=WALLET_ADDR)
PRINCIPAL={principalAddress}
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "bind(address)" $PRINCIPAL) --chain bsc
```

**On-chain registerAndStake (has BNB gas):**
```bash
# Step 1: Approve AWP to RootNet
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $ROOT_NET --amount {depositAmountHuman} --chain bsc
# Step 2: registerAndStake
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "registerAndStake(uint256,uint64,address,uint256,uint256)" {depositAmountWei} {lockDurationSeconds} {agentAddr} {subnetId} {allocateAmountWei}) --chain bsc
```

**Gasless register (no BNB) — EIP-712 template:**
```bash
# Step 1: Set deadline (e.g. 1 hour from now)
DEADLINE=$(date -d '+1 hour' +%s)

# Step 2: Sign EIP-712 typed data
awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Register": [
      {"name": "user", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Register",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": '$CHAIN_ID',
    "verifyingContract": "'$ROOT_NET'"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'
# -> {"signature": "0x...130 hex chars", "v": 28, "r": "0x...", "s": "0x..."}

# Step 3: Submit to relay
curl -X POST {API_BASE}/relay/register \
  -H "Content-Type: application/json" \
  -d '{"user": "'$WALLET_ADDR'", "deadline": '$DEADLINE', "signature": "{signatureHex}"}'
```

**Gasless bind (no BNB) — EIP-712 template:**
```bash
PRINCIPAL={principalAddress}
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
      {"name": "agent", "type": "address"},
      {"name": "principal", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": '$CHAIN_ID',
    "verifyingContract": "'$ROOT_NET'"
  },
  "message": {
    "agent": "'$WALLET_ADDR'",
    "principal": "'$PRINCIPAL'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST {API_BASE}/relay/bind \
  -H "Content-Type: application/json" \
  -d '{"agent": "'$WALLET_ADDR'", "principal": "'$PRINCIPAL'", "deadline": '$DEADLINE', "signature": "{signatureHex}"}'
```

**Other agent management:**
```bash
# Unbind (agent self-unbind)
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "unbind()") --chain bsc

# Remove agent (principal/manager only)
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "removeAgent(address)" {agentAddr}) --chain bsc

# Set delegation (grant/revoke manager)
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "setDelegation(address,bool)" {agentAddr} {true|false}) --chain bsc

# Set reward recipient (principal only)
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "setRewardRecipient(address)" {recipientAddr}) --chain bsc
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
function remainingTime(uint256 tokenId) view returns (uint64)        // Remaining lock time in seconds
function getVotingPower(uint256 tokenId) view returns (uint256)      // amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
function getUserVotingPower(address user, uint256[] tokenIds) view returns (uint256)
function getPositionForVoting(uint256 tokenId) view returns (address owner, uint128 amount, uint64 lockEndTime, uint64 createdAt, uint64 remaining, uint256 votingPower)
```

### Complete Command Templates

```bash
# Step 1: Approve AWP to StakeNFT
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $STAKE_NFT --amount {humanAmount} --chain bsc
# Wait for {"status": "confirmed"}

# Step 2: Deposit (lockDuration in seconds, e.g. 182 days = 15724800)
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "deposit(uint256,uint64)" {amountWei} {lockDurationSeconds}) --chain bsc

# Withdraw (after lock expires)
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "withdraw(uint256)" {tokenId}) --chain bsc

# Add to position (approve first, then addToPosition — check remainingTime > 0 first!)
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $STAKE_NFT --amount {addAmountHuman} --chain bsc
awp-wallet send --token {T} --to $STAKE_NFT --data $(cast calldata "addToPosition(uint256,uint256,uint64)" {tokenId} {addAmountWei} {newLockEndTimestamp}) --chain bsc
```

---

## S3 · Allocate / Deallocate / Reallocate

### Contract Calls

```solidity
// All on RootNet — caller must be owner or manager
function allocate(address agent, uint256 subnetId, uint256 amount)
function deallocate(address agent, uint256 subnetId, uint256 amount)
function reallocate(address fromAgent, uint256 fromSubnetId, address toAgent, uint256 toSubnetId, uint256 amount)
// Reallocate is immediate — no cooldown
```

### StakingVault View Functions

```solidity
function userTotalAllocated(address user) view returns (uint256)
function getAgentStake(address user, address agent, uint256 subnetId) view returns (uint256)
function subnetTotalStake(uint256 subnetId) view returns (uint256)
function getAgentSubnets(address user, address agent) view returns (uint256[])
```

### Check Unallocated Balance

```
GET /staking/user/{address}/balance
```
Verify `unallocated >= amount` before allocating.

### Complete Command Templates

```bash
# Allocate
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "allocate(address,uint256,uint256)" {agentAddr} {subnetId} {amountWei}) --chain bsc

# Deallocate
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "deallocate(address,uint256,uint256)" {agentAddr} {subnetId} {amountWei}) --chain bsc

# Reallocate (immediate, no cooldown)
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "reallocate(address,uint256,address,uint256,uint256)" {fromAgent} {fromSubnetId} {toAgent} {toSubnetId} {amountWei}) --chain bsc
```
