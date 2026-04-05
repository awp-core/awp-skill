# AWP Worknet Commands

**API Endpoint**: `POST https://api.awp.sh/v2` (JSON-RPC 2.0)

> **IMPORTANT**: Always use the bundled `scripts/*.py` files for write operations — they handle ABI encoding natively in Python, require only python3, and work without Foundry or curl/jq.
> The `cast calldata` examples below are for reference only; do NOT run them directly.

## Setup (reference only — bundled scripts handle this automatically)

```bash
# Reference only — actual operations are handled automatically by scripts/*.py
# Contract addresses (same on all chains)
AWP_REGISTRY="0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
AWP_TOKEN="0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1"
VE_AWP="0x0000b534C63D78212f1BDCc315165852793A00A8"
AWP_WORKNET="0x00000bfbdEf8533E5F3228c9C846522D906100A7"
DAO_ADDR="0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0"
LP_MANAGER="0x00001961b9AcCD86b72DE19Be24FaD6f7c5b00A2"

WALLET_ADDR=$(awp-wallet receive | jq -r '.eoaAddress')

# WorknetManager implementation addresses (differ per chain due to DEX integration):
# Base (8453):    0x00945e7fd4110b9c56ab4a3c2f53b6fabe6485e5  (Uniswap V4)
# Ethereum (1):   0x0029aABD49BF9ec7a34CDbcf75486B19CFAC3Ea8  (Uniswap V4)
# Arbitrum (42161): 0x00c428DCa1678e41Ed17Cc5AE3cF14430e2085A0  (Uniswap V4)
# BSC (56):       0x00D87f2f81E20cB1583F46d94BC7a7ad8f2DAC78  (PancakeSwap V4)
# These are the default implementations used when worknetManager = address(0).
# Each worknet gets its own ERC1967Proxy pointing to the chain's implementation.
```

---

## M1 · Register Worknet

### LP Cost Calculation

```solidity
function initialAlphaPrice() view returns (uint256)   // on AWPRegistry
// INITIAL_ALPHA_MINT = 100,000,000 x 10^18
// lpCost = INITIAL_ALPHA_MINT x initialAlphaPrice / 10^18
// Currently: 100,000,000 x 0.001 = 100,000 AWP
```

### WorknetParams Struct (6 fields)

```solidity
struct WorknetParams {
    string name;               // Alpha token name (1-64 bytes, no " or \)
    string symbol;             // Alpha token symbol (1-16 bytes, no " or \)
    address worknetManager;    // address(0) = auto-deploy WorknetManager proxy
    bytes32 salt;              // CREATE2 salt; bytes32(0) = use worknetId as salt
    uint128 minStake;          // Minimum stake hint for agents (stored on-chain but NOT enforced by contracts; 0 = no minimum)
    string skillsURI;          // Skills file URI (IPFS/HTTPS)
}
```

> **Note**: `worknetManager = address(0)` auto-deploys a WorknetManager proxy with Merkle distribution and AWP strategies (Reserve/AddLiquidity/BuybackBurn). The worknet registrant receives DEFAULT_ADMIN_ROLE on the deployed WorknetManager.

### Contract Calls

```solidity
// Step 1: Approve AWP to AWPRegistry (NOT veAWP)
function approve(address spender, uint256 amount) returns (bool)   // on AWPToken
// spender = AWPRegistry address: 0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A

// Step 2: Register worknet (after approve receipt)
function registerWorknet(WorknetParams params) returns (uint256 worknetId)   // on AWPRegistry
// params.salt = bytes32(0) uses worknetId as CREATE2 salt
// params.worknetManager = address(0) auto-deploys WorknetManager proxy
// Costs 100,000 AWP (initialAlphaMint x initialAlphaPrice)

// Gasless (requires prior AWP approve to AWPRegistry)
function registerWorknetFor(address user, WorknetParams params, uint256 deadline, uint8 v, bytes32 r, bytes32 s)

// Fully gasless (ERC-2612 permit + EIP-712 — no prior approve needed)
function registerWorknetForWithPermit(
    address user, WorknetParams params, uint256 deadline,
    uint8 permitV, bytes32 permitR, bytes32 permitS,
    uint8 registerV, bytes32 registerR, bytes32 registerS
)
```

### Vanity Address (optional)

Compute a CREATE2 salt for a vanity Alpha token address before registering:

```
POST /api/vanity/compute-salt
```
**Request:** empty body or `{}`

**Response:**
```json
{
  "salt": "0x530c11b79dce8dd3f7300373b2fdf33756a9cf6308415950b1a086be39aee365",
  "address": "0xA1b275f674f70f9fa216eE15B47640DcCD77cafe",
  "source": "pool",
  "elapsed": "1ms"
}
```

Use the returned `salt` as `WorknetParams.salt` in `registerWorknet()` to deploy the Alpha token at the vanity address. `source` is `"pool"` (from pre-mined salt pool) or `"mined"` (real-time mining fallback).

> Rate limit: compute-salt **20 requests per IP per hour**; upload-salts **5 requests per IP per hour**.

| Code | Body | Meaning |
|------|------|---------|
| 408 | `{"error": "search timed out..."}` | No match found within 120s timeout |
| 429 | `{"error": "rate limit exceeded"}` | IP rate limit exceeded |
| 500 | `{"error": "..."}` | Mining engine error |

### Vanity Salt Pool System

Manage the pre-mined salt pool for fast vanity address allocation:

```
GET /api/vanity/mining-params
```
Returns parameters for offline salt mining tools:
```json
{"factoryAddress": "0xAe8E...", "initCodeHash": "0xec76...", "vanityRule": "0x0A01FFFF0C0A0F0E"}
```

```
POST /api/vanity/upload-salts
```
Batch upload pre-mined salts (max 1000/request). Each salt is verified for CREATE2 correctness + vanityRule compliance:
```json
// Request
{"salts": [{"salt": "0x1234...", "address": "0xa1...cafe"}, ...]}
// Response
{"inserted": 98, "rejected": 2}
```

```
GET /api/vanity/salts
```
List available (unclaimed) salts. Supports `?limit=` pagination.

```
GET /api/vanity/salts/count
```
```json
{"available": 42}
```

### Complete Command Templates

```bash
# Gasless registration (recommended — no ETH needed, AWP only):
python3 scripts/relay-register-subnet.py --token {T} --name "MyWorknet" --symbol "MWRK" --skills-uri "ipfs://QmHash"
```

### Gasless Worknet Registration — EIP-712 Template

For fully gasless registration via `POST /api/relay/register-worknet`, the user signs two messages:

**1. ERC-2612 Permit signature** (authorizes AWPRegistry to spend AWP):
```bash
# Get permit nonce from AWPToken contract via RPC (NOT from nonce.get — that returns the registry nonce)
# nonces(address) selector = 0x7ecebe00
# Reference uses the hardcoded Base RPC URL — scripts/relay-register-subnet.py wraps this in awp_lib.rpc_call().
PERMIT_NONCE=$(python3 -c "
import json, urllib.request
addr = '$WALLET_ADDR'.lower().replace('0x','').zfill(64)
payload = json.dumps({'jsonrpc':'2.0','method':'eth_call','params':[{'to':'$AWP_TOKEN','data':'0x7ecebe00'+addr},'latest'],'id':1}).encode()
req = urllib.request.Request('https://mainnet.base.org', data=payload, headers={'Content-Type':'application/json','User-Agent':'awp-skill/1.1'})
r = json.loads(urllib.request.urlopen(req).read())
print(int(r['result'],16))
")
DEADLINE=$(date -d '+1 hour' +%s)

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Permit": [
      {"name": "owner", "type": "address"},
      {"name": "spender", "type": "address"},
      {"name": "value", "type": "uint256"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Permit",
  "domain": {
    "name": "AWP Token",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1"
  },
  "message": {
    "owner": "'$WALLET_ADDR'",
    "spender": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A",
    "value": '$LP_COST_WEI',
    "nonce": '$PERMIT_NONCE',
    "deadline": '$DEADLINE'
  }
}'
```

**2. EIP-712 RegisterWorknet signature** (authorizes registration parameters):
```bash
# Get AWPRegistry nonce via JSON-RPC
NONCE=$(curl -s -X POST https://api.awp.sh/v2 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"nonce.get","params":{"address":"'$WALLET_ADDR'"},"id":1}' | jq -r '.result.nonce')

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "RegisterWorknet": [
      {"name": "user", "type": "address"},
      {"name": "params", "type": "WorknetParams"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ],
    "WorknetParams": [
      {"name": "name", "type": "string"},
      {"name": "symbol", "type": "string"},
      {"name": "worknetManager", "type": "address"},
      {"name": "salt", "type": "bytes32"},
      {"name": "minStake", "type": "uint128"},
      {"name": "skillsURI", "type": "string"}
    ]
  },
  "primaryType": "RegisterWorknet",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "params": {
      "name": "{worknetName}",
      "symbol": "{worknetSymbol}",
      "worknetManager": "0x0000000000000000000000000000000000000000",
      "salt": "'$SALT'",
      "minStake": "{minStakeWei}",
      "skillsURI": "{skillsURI}"
    },
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'
```

**3. Submit to relay:**
```bash
curl -X POST https://api.awp.sh/api/relay/register-worknet \
  -H "Content-Type: application/json" \
  -d '{
    "chainId": 8453,
    "user": "'$WALLET_ADDR'",
    "name": "{worknetName}", "symbol": "{worknetSymbol}",
    "worknetManager": "0x0000000000000000000000000000000000000000",
    "salt": "'$SALT'", "minStake": "{minStakeWei}",
    "skillsURI": "{skillsURI}",
    "deadline": '$DEADLINE',
    "permitSignature": "0x...(65 bytes hex)...", "registerSignature": "0x...(65 bytes hex)..."
  }'

# Check relay status:
curl -s https://api.awp.sh/api/relay/status/{txHash}
```

**Relay error responses:**

| Code | Body | Meaning |
|------|------|---------|
| 400 | `{"error": "invalid user address"}` | Malformed Ethereum address |
| 400 | `{"error": "deadline is missing or expired"}` | Deadline is 0 or in the past |
| 400 | `{"error": "missing signature"}` | Signature field empty |
| 400 | `{"error": "invalid signature"}` | EIP-712 signature verification failed |
| 400 | `{"error": "signature expired"}` | On-chain deadline check failed |
| 400 | `{"error": "invalid subnet params (name 1-64 bytes, symbol 1-16 bytes)"}` | Name/symbol length violation |
| 400 | `{"error": "subnet manager address required (auto-deploy not available)"}` | No default WorknetManager impl set |
| 400 | `{"error": "insufficient AWP balance"}` | User lacks AWP for worknet registration |
| 400 | `{"error": "insufficient AWP allowance"}` | Permit signature did not authorize enough AWP |
| 400 | `{"error": "contract is paused"}` | AWPRegistry is in emergency pause state |
| 400 | `{"error": "relay transaction failed"}` | Unrecognized on-chain revert |
| 429 | `{"error": "rate limit exceeded: max 100 requests per 3600s"}` | IP rate limit exceeded |

---

## M2 · Worknet Lifecycle

### Contract Calls

```solidity
function activateWorknet(uint256 worknetId)   // Pending -> Active, AWPWorkNet owner only
function pauseWorknet(uint256 worknetId)       // Active -> Paused, AWPWorkNet owner only
function resumeWorknet(uint256 worknetId)      // Paused -> Active, AWPWorkNet owner only
function cancelWorknet(uint256 worknetId)      // Pending -> None (full AWP refund), AWPWorkNet owner only
```

Always check current status via JSON-RPC before calling:
```json
{"jsonrpc": "2.0", "method": "subnets.get", "params": {"worknetId": "123"}, "id": 1}
```

### Gasless Activate Worknet

```
POST /api/relay/activate-subnet
```

**EIP-712 ActivateWorknet signature:**
```bash
# Get AWPRegistry nonce via JSON-RPC
NONCE=$(curl -s -X POST https://api.awp.sh/v2 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"nonce.get","params":{"address":"'$WALLET_ADDR'"},"id":1}' | jq -r '.result.nonce')

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "ActivateWorknet": [
      {"name": "user", "type": "address"},
      {"name": "worknetId", "type": "uint256"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "ActivateWorknet",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": 8453,
    "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "worknetId": "'$WORKNET_ID'",
    "nonce": '$NONCE',
    "deadline": '$DEADLINE'
  }
}'

curl -X POST https://api.awp.sh/api/relay/activate-subnet \
  -H "Content-Type: application/json" \
  -d '{"chainId": 8453, "user": "'$WALLET_ADDR'", "worknetId": "'$WORKNET_ID'", "deadline": '$DEADLINE', "signature": "0x...(65 bytes hex)..."}'
```

### Complete Command Templates

```bash
python3 scripts/onchain-subnet-lifecycle.py --token {T} --subnet {worknetId} --action activate
python3 scripts/onchain-subnet-lifecycle.py --token {T} --subnet {worknetId} --action pause
python3 scripts/onchain-subnet-lifecycle.py --token {T} --subnet {worknetId} --action resume
python3 scripts/onchain-subnet-lifecycle.py --token {T} --subnet {worknetId} --action cancel
```

---

## M3 · Update Skills URI

### Contract Call

```solidity
function setSkillsURI(uint256 worknetId, string skillsURI)   // on AWPWorkNet
// AWPWorkNet owner only
// Emits SkillsURIUpdated(worknetId, skillsURI)
// worknetId = AWPWorkNet tokenId (they correspond 1:1)
```

### Complete Command Template

```bash
python3 scripts/onchain-subnet-update.py --token {T} --subnet {worknetId} --skills-uri "{skillsURI}"
```

---

## M4 · Set Minimum Stake

### Contract Call

```solidity
function setMinStake(uint256 worknetId, uint128 minStake)   // on AWPWorkNet
// AWPWorkNet owner only
// minStake in wei (0 = no minimum)
// Emits MinStakeUpdated(worknetId, minStake)
```

### Complete Command Template

```bash
python3 scripts/onchain-subnet-update.py --token {T} --subnet {worknetId} --min-stake {minStakeWei}
```
