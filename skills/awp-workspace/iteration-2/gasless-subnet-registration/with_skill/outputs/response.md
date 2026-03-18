# Gasless Subnet Registration: DataMiner (DM)

## Overview

You want to register subnet "DataMiner" (symbol: DM) with no BNB, using only AWP tokens. This triggers the **fully gasless M1 flow** via `POST /relay/register-subnet`, which calls `registerSubnetForWithPermit()` on-chain. The relayer pays all gas. After registration, we set `skillsURI` via **M4** (`SubnetNFT.setSkillsURI`). Since M4 is an on-chain write and you have no BNB, M4 requires BNB gas — gasless relay only covers register/bind/subnet-registration. You will need a small amount of BNB for the M4 step (or ask someone to relay it).

> **Note**: `skillsURI` is NOT part of `SubnetParams` — it must be set separately after registration via M4.

---

## Prerequisites

- AWP Wallet skill installed and unlocked
- Sufficient AWP balance to cover LP cost (`initialAlphaPrice * 100M Alpha`)

---

## Step 0: Setup — Fetch Addresses & Compute LP Cost

```bash
# Set API base
API_BASE="http://ec2-100-31-107-3.compute-1.amazonaws.com"

# Fetch contract addresses from registry (never hardcode)
REGISTRY=$(curl -s $API_BASE/registry)
ROOT_NET=$(echo $REGISTRY | jq -r '.rootNet')
AWP_TOKEN=$(echo $REGISTRY | jq -r '.awpToken')
SUBNET_NFT=$(echo $REGISTRY | jq -r '.subnetNFT')

# Get wallet address
T="<your-session-token>"
WALLET_ADDR=$(awp-wallet status --token $T | jq -r '.address')

# Check BNB balance (confirms gasless path needed)
awp-wallet balance --token $T --chain bsc
# → BNB = 0, so we use the gasless relay path

# Check AWP balance (must cover LP cost)
awp-wallet balance --token $T --chain bsc --asset $AWP_TOKEN

# Compute LP cost on-chain
INITIAL_ALPHA_PRICE=$(cast call $ROOT_NET "initialAlphaPrice()" --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
# LP_COST_WEI = INITIAL_ALPHA_PRICE * 100_000_000 (100M Alpha tokens)
# In bash: use python for BigInt math
LP_COST_WEI=$(python3 -c "print($INITIAL_ALPHA_PRICE * 100_000_000)")
echo "LP Cost: $LP_COST_WEI wei ($(python3 -c "print(f'{$LP_COST_WEI / 10**18:.4f}')") AWP)"
```

## Step 1: Get Nonces

Two separate nonces are needed — one for the ERC-2612 permit (on AWPToken), one for the EIP-712 registerSubnet (on RootNet).

```bash
# ERC-2612 permit nonce (AWPToken.nonces(owner))
PERMIT_NONCE=$(cast call $AWP_TOKEN "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)

# EIP-712 registerSubnet nonce (RootNet.nonces(user))
NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)

# Set deadline (1 hour from now)
DEADLINE=$(date -d '+1 hour' +%s)
```

## Step 2: (Optional) Get Vanity Salt

```bash
VANITY=$(curl -s -X POST $API_BASE/vanity/compute-salt)
SALT=$(echo $VANITY | jq -r '.salt')
echo "Vanity Alpha address: $(echo $VANITY | jq -r '.address')"
# Or use auto-salt: SALT="0x0000000000000000000000000000000000000000000000000000000000000000"
```

## Step 3: Define Subnet Parameters

```bash
SUBNET_NAME="DataMiner"
SUBNET_SYMBOL="DM"
METADATA_URI=""
SUBNET_MANAGER="0x0000000000000000000000000000000000000000"  # auto-deploy SubnetManager proxy
COORDINATOR_URL=""
MIN_STAKE_WEI="100000000000000000000"  # 100 AWP = 100 * 10^18 wei
```

> `subnetManager = address(0)` auto-deploys a SubnetManager proxy with Merkle distribution and AWP strategies (Reserve/AddLiquidity/BuybackBurn). You receive `DEFAULT_ADMIN_ROLE` on it.

## Step 4: Sign ERC-2612 Permit (Signature 1 of 2)

This authorizes RootNet to spend your AWP for the LP cost — no prior `approve` transaction needed.

```bash
PERMIT_SIG=$(awp-wallet sign-typed-data --token $T --data '{
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
}')
PERMIT_SIG_HEX=$(echo $PERMIT_SIG | jq -r '.signature')
echo "Permit signature: $PERMIT_SIG_HEX"
```

## Step 5: Sign EIP-712 RegisterSubnet (Signature 2 of 2)

This authorizes the subnet registration parameters.

```bash
REGISTER_SIG=$(awp-wallet sign-typed-data --token $T --data '{
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
    "name": "DataMiner",
    "symbol": "DM",
    "metadataURI": "",
    "subnetManager": "0x0000000000000000000000000000000000000000",
    "coordinatorURL": "",
    "salt": "'$SALT'",
    "minStake": "'$MIN_STAKE_WEI'",
    "deadline": '$DEADLINE',
    "nonce": '$NONCE'
  }
}')
REGISTER_SIG_HEX=$(echo $REGISTER_SIG | jq -r '.signature')
echo "RegisterSubnet signature: $REGISTER_SIG_HEX"
```

## Step 6: Submit to Gasless Relay

```bash
RESULT=$(curl -s -X POST $API_BASE/relay/register-subnet \
  -H "Content-Type: application/json" \
  -d '{
    "user": "'$WALLET_ADDR'",
    "name": "DataMiner",
    "symbol": "DM",
    "metadataURI": "",
    "subnetManager": "0x0000000000000000000000000000000000000000",
    "coordinatorURL": "",
    "salt": "'$SALT'",
    "minStake": "'$MIN_STAKE_WEI'",
    "deadline": '$DEADLINE',
    "permitSignature": "'$PERMIT_SIG_HEX'",
    "registerSignature": "'$REGISTER_SIG_HEX'"
  }')

TX_HASH=$(echo $RESULT | jq -r '.txHash')
echo "Subnet registration tx: https://bscscan.com/tx/$TX_HASH"
```

> **Rate limit**: 5 requests per IP per 4 hours across all relay endpoints.

## Step 7: Retrieve New Subnet ID

Wait for the transaction to confirm, then query the API to find the newly registered subnet.

```bash
# Wait for tx confirmation (~3-5 seconds on BSC)
sleep 5

# Find the new subnet by querying your subnets
# Option A: Check the tx receipt for SubnetRegistered event
cast receipt $TX_HASH --rpc-url https://bsc-dataseed.binance.org | jq '.logs'

# Option B: List subnets and find yours
curl -s "$API_BASE/subnets?status=Pending&page=1&limit=100" | \
  jq '.[] | select(.name == "DataMiner" and .owner == "'$WALLET_ADDR'")'

# Extract the subnet ID
SUBNET_ID=$(curl -s "$API_BASE/subnets?status=Pending&page=1&limit=100" | \
  jq '[.[] | select(.name == "DataMiner" and .owner == "'$WALLET_ADDR'")][0].subnet_id')
echo "New subnet ID: $SUBNET_ID"
```

## Step 8: Set Skills URI (M4)

> **Important**: M4 (`setSkillsURI`) is a direct on-chain call to SubnetNFT. It is NOT covered by the gasless relay. You need a small amount of BNB for gas. If you truly have zero BNB, you must acquire some first (e.g., bridge, faucet, or ask someone to send ~0.001 BNB).

Once you have BNB for gas:

```bash
# Confirm subnet ownership
curl -s "$API_BASE/subnets/$SUBNET_ID" | jq '{owner, name, skills_uri}'

# Set skillsURI on SubnetNFT (tokenId = subnetId)
awp-wallet send --token $T \
  --to $SUBNET_NFT \
  --data $(cast calldata "setSkillsURI(uint256,string)" $SUBNET_ID "https://dataminer.io/SKILL.md") \
  --chain bsc
# → {"txHash": "0x...", "status": "confirmed"}

# Extract tx hash and show BSCScan link
echo "setSkillsURI tx: https://bscscan.com/tx/<txHash>"
```

## Step 9: Verify

```bash
# Verify skillsURI was set correctly
curl -s "$API_BASE/subnets/$SUBNET_ID/skills"
# Expected: {"subnetId": <SUBNET_ID>, "skillsURI": "https://dataminer.io/SKILL.md"}

# Full subnet info
curl -s "$API_BASE/subnets/$SUBNET_ID" | jq '{subnet_id, name, symbol: .symbol, status, owner, skills_uri, subnet_contract}'
```

---

## Transaction Summary

| Step | Action | Method | Gas Paid By |
|------|--------|--------|-------------|
| 4 | ERC-2612 Permit sign | Off-chain EIP-712 | No gas |
| 5 | RegisterSubnet sign | Off-chain EIP-712 | No gas |
| 6 | `POST /relay/register-subnet` | `registerSubnetForWithPermit()` | Relayer |
| 8 | `setSkillsURI()` | Direct on-chain tx | **You (BNB required)** |

## Key Details

- **LP Cost**: `initialAlphaPrice * 100,000,000` AWP (paid from your AWP balance via ERC-2612 permit, no approve tx needed)
- **SubnetManager**: `address(0)` = auto-deployed proxy with Merkle distribution + AWP strategies; you get `DEFAULT_ADMIN_ROLE`
- **minStake**: 100 AWP (`100000000000000000000` wei) — agents must stake at least this to join your subnet
- **skillsURI**: Set separately via `SubnetNFT.setSkillsURI()` (M4), NOT part of `SubnetParams`
- **Gasless limitation**: The relay covers subnet registration only. `setSkillsURI` (M4) and `setMinStake` (M5) require BNB gas for direct on-chain calls. Note that `minStake` is already included in `SubnetParams` during registration, so M5 is only needed for later changes.

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| 400 | Invalid params / expired deadline / bad signature | Check all fields, extend deadline, re-sign |
| 429 | Relay rate limit (5/IP/4h) | Wait and retry later |
| 500 | Relay tx failed | Check AWP balance covers LP cost; retry |
| "not subnet owner" on M4 | Wrong wallet or wrong subnetId | Verify SubnetNFT ownership |
| Insufficient AWP | LP cost exceeds balance | Acquire more AWP first |
