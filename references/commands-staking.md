# AWP Staking Commands

**API Endpoint**: `POST https://api.awp.sh/v2` (JSON-RPC 2.0)

> **IMPORTANT**: Always use the bundled `scripts/*.py` files for write operations — they handle ABI encoding natively in Python, require only python3, and work without Foundry or curl/jq.
> The `cast calldata` examples below are for reference only; do NOT run them directly.

## Setup (reference only — bundled scripts handle this automatically)

```bash
# Reference only — actual operations are handled automatically by scripts/*.py
# Fetch registry via JSON-RPC
REGISTRY=$(curl -s -X POST https://api.awp.sh/v2 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"registry.get","params":{},"id":1}' | jq -r '.result')

# Contract addresses (same on all chains)
AWP_REGISTRY="0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
AWP_TOKEN="0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1"
VE_AWP="0x0000b534C63D78212f1BDCc315165852793A00A8"
AWP_ALLOCATOR="0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA"
AWP_WORKNET="0x00000bfbdEf8533E5F3228c9C846522D906100A7"
DAO_ADDR="0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0"
LP_MANAGER="0x00001961b9AcCD86b72DE19Be24FaD6f7c5b00A2"

WALLET_ADDR=$(awp-wallet receive | jq -r '.eoaAddress')
```

## Wallet CLI Reference

### Key Parameters

- `--token {T}` = wallet session token from `awp-wallet unlock --scope transfer`
- `--asset` = token **contract address** (e.g. AWP token addr), NOT a symbol like "AWP"
- Chain defaults to Base (configured in awp-wallet config). `--chain` is a global option if needed.

### Approve Pattern (used by S1, S2)

```bash
# Approve AWP spending — spender varies by action (see each section)
# --asset must be the AWP token contract address
awp-wallet approve --token {T} --asset {awpTokenAddr} --spender {targetAddr} --amount {humanAmount} # -> {"txHash": "0x...", "status": "confirmed"}
```

### Balance Check

```bash
# Check AWP balance in wallet (supplements JSON-RPC staking balance)
awp-wallet balance --token {T} --asset {awpTokenAddr}
```

### EIP-712 Signing (for gasless operations)

```bash
# Sign typed data for gasless binding, unbinding, set-recipient, allocate, deallocate
awp-wallet sign-typed-data --token {T} --data '{...EIP712 JSON...}'
# -> {"signature": "0x...(65 bytes hex, compact r||s||v form)"}
```

---

## S1 · Account System: Bind, Unbind & Delegate

### Check Registration

```json
// JSON-RPC
{"jsonrpc": "2.0", "method": "address.check", "params": {"address": "0x..."}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {"isRegistered": true, "boundTo": "0x...", "recipient": "0x..."}, "id": 1}
```
> `isRegistered` = `boundTo != 0x0 || recipient != 0x0`.

### Contract Calls — Registration (Optional)

```solidity
// Registration happens implicitly the first time an address calls setRecipient().
// Passing msg.sender as the recipient registers without changing reward routing.
// AWPRegistry has no standalone register() or registerAndStake() entrypoint.
function setRecipient(address recipient)
```

To combine register + deposit + allocate in a single user intent, invoke each
primitive in sequence: `setRecipient(self)` → `veAWP.deposit(amount, lockSeconds)`
→ `AWPAllocator.allocate(staker, agent, worknetId, amount)`. The bundled scripts
cover all three steps.

### Contract Calls — Tree-Based Binding

```solidity
// Bind msg.sender to a target (tree-based with anti-cycle check; supports rebind)
function bind(address target)

// Unbind msg.sender from current target
function unbind()

// Gasless bind via EIP-712 signature
function bindFor(address user, address target, uint256 deadline, uint8 v, bytes32 r, bytes32 s)
```
> `unbind()` is available — unbinds msg.sender from current binding target.

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

### Gasless Relay Endpoints

```
POST /api/relay/bind
POST /api/relay/unbind
POST /api/relay/set-recipient
POST /api/relay/grant-delegate
POST /api/relay/revoke-delegate
GET  /api/relay/status/{txHash}
```

**Bind request:**
```json
{"chainId": 8453, "agent": "0xAgent...", "target": "0xTarget...", "deadline": 1742400000, "signature": "0x...(65 bytes hex)..."}
```
**Response:**
```json
{"txHash": "0x..."}
```

**Unbind request:**
```json
{"chainId": 8453, "user": "0x1234...", "deadline": 1742400000, "signature": "0x...(65 bytes hex)..."}
```

**Set-recipient request:**
```json
{"chainId": 8453, "user": "0x1234...", "recipient": "0x5678...", "deadline": 1742400000, "signature": "0x...(65 bytes hex)..."}
```

**Grant-delegate request:**
```json
{"chainId": 8453, "user": "0x1234...", "delegate": "0x5678...", "deadline": 1742400000, "signature": "0x...(65 bytes hex)..."}
```

**Revoke-delegate request:**
```json
{"chainId": 8453, "user": "0x1234...", "delegate": "0x5678...", "deadline": 1742400000, "signature": "0x...(65 bytes hex)..."}
```

**Relay status check:**
```
GET /api/relay/status/{txHash}
```

> Rate limit: 100 requests per IP per 1 hour (shared across all relay endpoints).
> Signature format: combined 65-byte hex (`r || s || v`) sent as a single `"signature"` field on the request body. The dual-signature `/relay/register-worknet` endpoint uses `"permitSignature"` and `"registerSignature"` instead. All relay endpoints require `chainId` in the request body. Sending split `v/r/s` fields does not work — the relay returns `{"error":"missing signature"}` and the fields are ignored.

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

**Step 1: Get nonce and EIP-712 domain**
```bash
# Get AWPRegistry nonce via JSON-RPC
NONCE=$(curl -s -X POST https://api.awp.sh/v2 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"nonce.get","params":{"address":"'$WALLET_ADDR'"},"id":1}' | jq -r '.result.nonce')

# AWPRegistry EIP-712 domain (same on all chains, only chainId differs)
# name: "AWPRegistry", version: "1", verifyingContract: 0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A
```

**On-chain bind (has ETH gas):**
```bash
python3 scripts/onchain-bind.py --token {T} --target {targetAddress}
```

**Gasless bind (no ETH) — EIP-712 signature flow:**
```bash
# 1. Get nonce:  nonce.get via JSON-RPC
# 2. Sign EIP-712 typed data:

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
      {"name": "target", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
  },
  "message": {
    "agent": "'$WALLET_ADDR'",
    "target": "'$TARGET'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

# 3. Submit to relay:
curl -X POST https://api.awp.sh/api/relay/bind \
  -H "Content-Type: application/json" \
  -d '{"chainId": 8453, "agent": "'$WALLET_ADDR'", "target": "'$TARGET'", "deadline": '$DEADLINE', "signature": "'$SIGNATURE'"}'

# 4. Check relay status:
curl -s https://api.awp.sh/api/relay/status/{txHash}
```

> **Bind type fields are `{agent, target, nonce, deadline}`** — NOT `{user, target}`. The `agent` is the wallet signing the message. The `target` is the address to bind to. Nonce from `nonce.get`. Domain: AWPRegistry.

**Gasless unbind (no ETH) — EIP-712 template:**
```bash
DEADLINE=$(date -d '+1 hour' +%s)

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Unbind": [
      {"name": "user", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Unbind",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST https://api.awp.sh/api/relay/unbind \
  -H "Content-Type: application/json" \
  -d '{"chainId": 8453, "user": "'$WALLET_ADDR'", "deadline": '$DEADLINE', "signature": "'$SIGNATURE'"}'
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
    "chainId": 8453,
    "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "recipient": "'$RECIPIENT'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST https://api.awp.sh/api/relay/set-recipient \
  -H "Content-Type: application/json" \
  -d '{"chainId": 8453, "user": "'$WALLET_ADDR'", "recipient": "'$RECIPIENT'", "deadline": '$DEADLINE', "signature": "'$SIGNATURE'"}'
```

**Delegation management** (use bundled scripts — `awp-wallet send` does NOT support raw calldata):
```bash
# For gasless binding, use relay-start.py:
python3 scripts/relay-start.py --token {T} --mode agent --target {targetAddress}

# For on-chain binding:
python3 scripts/onchain-bind.py --token {T} --target {targetAddress}

# grantDelegate/revokeDelegate/setRecipient: no bundled Python scripts exist for these.
# Use wallet-raw-call.mjs directly to send raw contract calls. Example:
#   node scripts/wallet-raw-call.mjs --token {T} --to {awpRegistryAddr} \
#     --data $(cast calldata "grantDelegate(address)" {delegateAddr})
```

---

## S2 · Deposit AWP

### Contract Calls

```solidity
// Step 1: Approve AWP transfer to veAWP (NOT AWPRegistry)
function approve(address spender, uint256 amount) returns (bool)   // on AWPToken
// spender = veAWP address: 0x0000b534C63D78212f1BDCc315165852793A00A8

// Step 2: Deposit directly on veAWP (after approve receipt confirmed)
function deposit(uint256 amount, uint64 lockDuration) returns (uint256 tokenId)   // on veAWP
// lockDuration in SECONDS (e.g., 15724800 = ~26 weeks)
// Emits Deposited(user, tokenId, amount, lockEndTime) — lockEndTime is ABSOLUTE TIMESTAMP

// Alternative: Deposit with ERC-2612 permit (no prior approve needed)
function depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) returns (uint256 tokenId)   // on veAWP

// Optional: Add to existing position
function addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime)   // on veAWP
// newLockEndTime is absolute timestamp, must be >= current lockEndTime
// Requires AWPToken.approve(veAWP, amount) before calling — same pattern as initial deposit
// CAUTION: Reverts with PositionExpired if the position's lock has already expired.
// Check remainingTime(tokenId) > 0 before calling.

// Withdraw after lock expires (burns position NFT, returns AWP)
function withdraw(uint256 tokenId)   // on veAWP
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

Always use the bundled Python scripts (they handle approve + ABI encoding + raw call via `wallet-raw-call.mjs`):

```bash
# Deposit (approve + deposit in one script)
python3 scripts/onchain-deposit.py --token {T} --amount 5000 --lock-days 90

# Withdraw (after lock expires)
python3 scripts/onchain-withdraw.py --token {T} --position {tokenId}

# Add to existing position
python3 scripts/onchain-add-position.py --token {T} --position {tokenId} --amount 1000 --extend-days 30
```

> **Note**: `awp-wallet send` only supports token transfers (--to, --amount, --asset). It does NOT support raw calldata. All contract calls go through `wallet-raw-call.mjs` which the Python scripts call internally.

---

## S3 · Allocate / Deallocate / Reallocate

### Contract Calls

```solidity
// All on AWPAllocator — caller must be staker or delegate (direct access, NOT onlyAWPRegistry)
function allocate(address staker, address agent, uint256 worknetId, uint256 amount)
function deallocate(address staker, address agent, uint256 worknetId, uint256 amount)
function reallocate(address staker, address fromAgent, uint256 fromWorknetId, address toAgent, uint256 toWorknetId, uint256 amount)
// Reallocate is immediate — no cooldown
```
> `staker` is an explicit parameter. Caller must be the staker themselves or their delegate.
> AWPAllocator functions are called directly (not through AWPRegistry).

### Gasless Allocate/Deallocate Relay

AWPAllocator has its own EIP-712 domain for gasless operations:

```
POST /api/relay/allocate
POST /api/relay/deallocate
GET  /api/relay/status/{txHash}
```

**Get AWPAllocator nonce:**
```json
{"jsonrpc": "2.0", "method": "nonce.getStaking", "params": {"address": "0x..."}, "id": 1}
```

**EIP-712 Allocate signature:**
```bash
awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Allocate": [
      {"name": "staker", "type": "address"},
      {"name": "agent", "type": "address"},
      {"name": "worknetId", "type": "uint256"},
      {"name": "amount", "type": "uint256"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Allocate",
  "domain": {
    "name": "AWPAllocator",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA"
  },
  "message": {
    "staker": "'$WALLET_ADDR'",
    "agent": "'$AGENT'",
    "worknetId": "'$WORKNET_ID'",
    "amount": "'$AMOUNT_WEI'",
    "nonce": '$STAKING_NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST https://api.awp.sh/api/relay/allocate \
  -H "Content-Type: application/json" \
  -d '{"chainId": 8453, "staker": "'$WALLET_ADDR'", "agent": "'$AGENT'", "worknetId": "'$WORKNET_ID'", "amount": "'$AMOUNT_WEI'", "deadline": '$DEADLINE', "signature": "'$SIGNATURE'"}'
```

**EIP-712 Deallocate** follows the same pattern with `"Deallocate"` primaryType and `POST /api/relay/deallocate`.

### AWPAllocator View Functions

```solidity
function userTotalAllocated(address staker) view returns (uint256)
function getAgentStake(address staker, address agent, uint256 worknetId) view returns (uint256)
function getSubnetTotalStake(uint256 worknetId) view returns (uint256)
function getAgentSubnets(address staker, address agent) view returns (uint256[])
function nonces(address) view returns (uint256)   // AWPAllocator EIP-712 nonce
```

### Check Available Balance

```json
// JSON-RPC
{"jsonrpc": "2.0", "method": "staking.getBalance", "params": {"address": "0x..."}, "id": 1}
// Response: {"totalStaked": "...", "totalAllocated": "...", "unallocated": "..."}
```
Verify `unallocated >= amount` before allocating.

### Check Frozen Allocations

```json
// JSON-RPC
{"jsonrpc": "2.0", "method": "staking.getFrozen", "params": {"address": "0x..."}, "id": 1}
```
Returns frozen allocation details for the address. Useful for checking if any allocations are locked during cooldown periods.

### Complete Command Templates

```bash
# Allocate
python3 scripts/onchain-allocate.py --token {T} --agent {agentAddr} --subnet {worknetId} --amount 5000

# Deallocate
python3 scripts/onchain-deallocate.py --token {T} --agent {agentAddr} --subnet {worknetId} --amount 5000

# Reallocate (immediate, no cooldown)
python3 scripts/onchain-reallocate.py --token {T} --from-agent {fromAgent} --from-subnet {fromWorknetId} --to-agent {toAgent} --to-subnet {toWorknetId} --amount 5000
```
