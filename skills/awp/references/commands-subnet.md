# AWP Subnet Commands

**API Base URL**: `https://tapi.awp.sh/api`

## Setup (run once per session)

```bash
REGISTRY=$(curl -s {API_BASE}/registry)
ROOT_NET=$(echo $REGISTRY | jq -r '.rootNet')
AWP_TOKEN=$(echo $REGISTRY | jq -r '.awpToken')
STAKE_NFT=$(echo $REGISTRY | jq -r '.stakeNFT')
SUBNET_NFT=$(echo $REGISTRY | jq -r '.subnetNFT')
DAO_ADDR=$(echo $REGISTRY | jq -r '.dao')

WALLET_ADDR=$(awp-wallet status --token {T} | jq -r '.address')
```

---

## M1 · Register Subnet

### LP Cost Calculation

```solidity
function initialAlphaPrice() view returns (uint256)   // on RootNet
// INITIAL_ALPHA_MINT = 100,000,000 x 10^18
// lpCost = INITIAL_ALPHA_MINT x initialAlphaPrice / 10^18
```

### SubnetParams Struct

```solidity
struct SubnetParams {
    string name;               // Alpha token name (1-64 bytes)
    string symbol;             // Alpha token symbol (1-16 bytes)
    string metadataURI;        // IPFS metadata URI
    address subnetManager;     // address(0) = auto-deploy SubnetManager proxy
    string coordinatorURL;     // Subnet coordinator endpoint
    bytes32 salt;              // CREATE2 salt; bytes32(0) = use subnetId as salt
    uint128 minStake;          // Minimum stake for agents (0 = no minimum)
}
```

> **Note**: `subnetManager = address(0)` auto-deploys a SubnetManager proxy with Merkle distribution and AWP strategies (Reserve/AddLiquidity/BuybackBurn). The subnet registrant receives DEFAULT_ADMIN_ROLE on the deployed SubnetManager.

### Contract Calls

```solidity
// Step 1: Approve AWP to RootNet (NOT StakeNFT)
function approve(address spender, uint256 amount) returns (bool)   // on AWPToken
// spender = rootNet address

// Step 2: Register subnet (after approve receipt)
function registerSubnet(SubnetParams params) returns (uint256 subnetId)   // on RootNet
// params.salt = bytes32(0) uses subnetId as CREATE2 salt
// params.subnetManager = address(0) auto-deploys SubnetManager proxy

// Gasless (requires prior AWP approve to RootNet)
function registerSubnetFor(address user, SubnetParams params, uint256 deadline, uint8 v, bytes32 r, bytes32 s)

// Fully gasless (ERC-2612 permit + EIP-712 — no prior approve needed)
function registerSubnetForWithPermit(
    address user, SubnetParams params, uint256 deadline,
    uint8 permitV, bytes32 permitR, bytes32 permitS,
    uint8 registerV, bytes32 registerR, bytes32 registerS
)
```

### Vanity Address (optional)

Compute a CREATE2 salt for a vanity Alpha token address before registering:

```
POST /vanity/compute-salt
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

Use the returned `salt` as `SubnetParams.salt` in `registerSubnet()` to deploy the Alpha token at the vanity address. `source` is `"pool"` (from pre-mined salt pool) or `"mined"` (real-time mining fallback).

| Code | Body | Meaning |
|------|------|---------|
| 408 | `{"error": "search timed out..."}` | No match found within 120s timeout |
| 500 | `{"error": "..."}` | Mining engine error |

### Vanity Salt Pool System

Manage the pre-mined salt pool for fast vanity address allocation:

```
GET /vanity/mining-params
```
Returns parameters for offline salt mining tools:
```json
{"factoryAddress": "0xAe8E...", "initCodeHash": "0xec76...", "vanityRule": "0x0A01FFFF0C0A0F0E"}
```

```
POST /vanity/upload-salts
```
Batch upload pre-mined salts (max 1000/request). Each salt is verified for CREATE2 correctness + vanityRule compliance:
```json
// Request
{"salts": [{"salt": "0x1234...", "address": "0xa1...cafe"}, ...]}
// Response
{"inserted": 98, "rejected": 2}
```

```
GET /vanity/salts
```
List available (unclaimed) salts. Supports `?limit=` pagination.

```
GET /vanity/salts/count
```
```json
{"available": 42}
```

### Complete Command Templates

```bash
# Optional: get vanity salt first
VANITY=$(curl -s -X POST {API_BASE}/vanity/compute-salt)
SALT=$(echo $VANITY | jq -r '.salt')  # or use 0x0000...0000 for auto-salt

# Step 1: Approve AWP to RootNet for LP cost
awp-wallet approve --token {T} --asset $AWP_TOKEN --spender $ROOT_NET --amount {lpCostHuman} --chain bsc

# Step 2: Register subnet (SubnetParams encoded as tuple)
# params: (name, symbol, metadataURI, subnetManager, coordinatorURL, salt, minStake)
# subnetManager = 0x0000...0000 for auto-deploy SubnetManager proxy
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "registerSubnet((string,string,string,address,string,bytes32,uint128))" "({name},{symbol},{metadataURI},0x0000000000000000000000000000000000000000,{coordinatorURL},$SALT,{minStakeWei})") --chain bsc
```

### Gasless Subnet Registration — EIP-712 Template

For fully gasless registration via `POST /relay/register-subnet`, the user signs two messages:

**1. ERC-2612 Permit signature** (authorizes RootNet to spend AWP):
```bash
# Get permit nonce
PERMIT_NONCE=$(cast call $AWP_TOKEN "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
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
    "chainId": 56,
    "verifyingContract": "'$AWP_TOKEN'"
  },
  "message": {
    "owner": "'$WALLET_ADDR'",
    "spender": "'$ROOT_NET'",
    "value": "'$LP_COST_WEI'",
    "nonce": '$PERMIT_NONCE',
    "deadline": '$DEADLINE'
  }
}'
```

**2. EIP-712 RegisterSubnet signature** (authorizes registration parameters):
```bash
# Get RootNet nonce
NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)

awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "RegisterSubnet": [
      {"name": "user", "type": "address"},
      {"name": "name", "type": "string"},
      {"name": "symbol", "type": "string"},
      {"name": "metadataURI", "type": "string"},
      {"name": "subnetManager", "type": "address"},
      {"name": "coordinatorURL", "type": "string"},
      {"name": "salt", "type": "bytes32"},
      {"name": "minStake", "type": "uint128"},
      {"name": "deadline", "type": "uint256"},
      {"name": "nonce", "type": "uint256"}
    ]
  },
  "primaryType": "RegisterSubnet",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": 56,
    "verifyingContract": "'$ROOT_NET'"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "name": "{subnetName}",
    "symbol": "{subnetSymbol}",
    "metadataURI": "{metadataURI}",
    "subnetManager": "0x0000000000000000000000000000000000000000",
    "coordinatorURL": "{coordinatorURL}",
    "salt": "'$SALT'",
    "minStake": "{minStakeWei}",
    "deadline": '$DEADLINE',
    "nonce": '$NONCE'
  }
}'
```

**3. Submit to relay:**
```bash
curl -X POST {API_BASE}/relay/register-subnet \
  -H "Content-Type: application/json" \
  -d '{
    "user": "'$WALLET_ADDR'",
    "name": "{subnetName}", "symbol": "{subnetSymbol}",
    "metadataURI": "{metadataURI}",
    "subnetManager": "0x0000000000000000000000000000000000000000",
    "coordinatorURL": "{coordinatorURL}",
    "salt": "'$SALT'", "minStake": "{minStakeWei}",
    "deadline": '$DEADLINE',
    "permitSignature": "{permitSigHex}",
    "registerSignature": "{registerSigHex}"
  }'
```

**Relay error responses:**

| Code | Body | Meaning |
|------|------|---------|
| 400 | `{"error": "..."}` | Invalid params, expired deadline, bad signature format |
| 429 | `{"error": "rate limit exceeded: max 5 requests per 4 hours"}` | IP rate limit exceeded |
| 500 | `{"error": "relay transaction failed"}` | On-chain transaction submission failed |

---

## M2 · Subnet Lifecycle

### Contract Calls

```solidity
function activateSubnet(uint256 subnetId)   // Pending -> Active, NFT owner only
function pauseSubnet(uint256 subnetId)      // Active -> Paused, NFT owner only
function resumeSubnet(uint256 subnetId)     // Paused -> Active, NFT owner only
```

Always check current status via `GET /subnets/{id}` before calling.

### Complete Command Templates

```bash
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "activateSubnet(uint256)" {subnetId}) --chain bsc
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "pauseSubnet(uint256)" {subnetId}) --chain bsc
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "resumeSubnet(uint256)" {subnetId}) --chain bsc
```

---

## M3 · Update Metadata

### Contract Call

```solidity
function updateMetadata(uint256 subnetId, string metadataURI, string coordinatorURL)
// BOTH strings required — pass current values for unchanged fields
// NFT owner only
// skillsURI is now set separately via SubnetNFT.setSkillsURI() — see M4
```

Fetch current values first: `GET /subnets/{subnetId}` -> use `metadata_uri`, `coordinator_url`.

### Complete Command Template

```bash
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "updateMetadata(uint256,string,string)" {subnetId} "{metadataURI}" "{coordinatorURL}") --chain bsc
```

---

## M4 · Update Skills URI

### Contract Call

```solidity
function setSkillsURI(uint256 tokenId, string skillsURI)   // on SubnetNFT
// NFT owner only
// Emits SkillsURIUpdated(tokenId, skillsURI)
// tokenId = subnetId (SubnetNFT tokenId corresponds to subnet ID)
```

### Complete Command Template

```bash
# SUBNET_NFT from GET /registry -> subnetNFT
awp-wallet send --token {T} --to $SUBNET_NFT --data $(cast calldata "setSkillsURI(uint256,string)" {subnetId} "{skillsURI}") --chain bsc
```

---

## M5 · Set Minimum Stake

### Contract Call

```solidity
function setMinStake(uint256 tokenId, uint128 minStake)   // on SubnetNFT
// NFT owner only
// minStake in wei (0 = no minimum)
// Emits MinStakeUpdated(tokenId, minStake)
```

### Complete Command Template

```bash
# SUBNET_NFT from GET /registry -> subnetNFT
awp-wallet send --token {T} --to $SUBNET_NFT --data $(cast calldata "setMinStake(uint256,uint128)" {subnetId} {minStakeWei}) --chain bsc
```
