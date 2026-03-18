#!/usr/bin/env bash
# Fully gasless subnet registration via dual EIP-712 signatures
# Usage: ./relay-register-subnet.sh --token <session_token> --name <name> --symbol <symbol> [options]
#
# Required: --token, --name, --symbol
# Optional: --salt <hex>, --min-stake <wei>, --subnet-manager <address>
#
# Prerequisites: awp-wallet installed and unlocked, cast (foundry) installed
# The script will:
#   1. Fetch contract addresses from /registry
#   2. Calculate LP cost from initialAlphaPrice
#   3. Get nonces (RootNet EIP-712 nonce + AWPToken permit nonce)
#   4. Sign ERC-2612 Permit (authorize AWP spend)
#   5. Sign EIP-712 RegisterSubnet (authorize registration params)
#   6. Submit both signatures to POST /relay/register-subnet
#   7. Output the txHash

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""
NAME=""
SYMBOL=""
SALT="0x0000000000000000000000000000000000000000000000000000000000000000"
MIN_STAKE="0"
SUBNET_MANAGER="0x0000000000000000000000000000000000000000"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --symbol) SYMBOL="$2"; shift 2 ;;
    --salt) SALT="$2"; shift 2 ;;
    --min-stake) MIN_STAKE="$2"; shift 2 ;;
    --subnet-manager) SUBNET_MANAGER="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TOKEN" || -z "$NAME" || -z "$SYMBOL" ]]; then
  echo '{"error": "Missing required args: --token, --name, --symbol"}' >&2
  exit 1
fi

# Step 1: Fetch contract addresses
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
echo "$REGISTRY" | jq -e '.rootNet' > /dev/null 2>&1 || { echo "$REGISTRY" >&2; exit 1; }
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')
AWP_TOKEN=$(echo "$REGISTRY" | jq -r '.awpToken')

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Calculate LP cost
INITIAL_ALPHA_PRICE=$(cast call "$ROOT_NET" "initialAlphaPrice()(uint256)" --rpc-url "$RPC_URL" 2>/dev/null)
INITIAL_ALPHA_PRICE=$(echo "$INITIAL_ALPHA_PRICE" | tr -d '[:space:]')
# LP_COST = INITIAL_ALPHA_MINT (100M * 10^18) * initialAlphaPrice / 10^18
LP_COST=$(python3 -c "print(100_000_000 * 10**18 * $INITIAL_ALPHA_PRICE // 10**18)")

# Step 4: Get nonces
ROOTNET_NONCE=$(cast call "$ROOT_NET" "nonces(address)(uint256)" "$WALLET_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
ROOTNET_NONCE=$(echo "$ROOTNET_NONCE" | tr -d '[:space:]')

PERMIT_NONCE=$(cast call "$AWP_TOKEN" "nonces(address)(uint256)" "$WALLET_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
PERMIT_NONCE=$(echo "$PERMIT_NONCE" | tr -d '[:space:]')

# Step 5: Set deadline (1 hour from now)
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 6: Sign ERC-2612 Permit (authorize AWP spend to RootNet)
PERMIT_DATA=$(cat <<EIPJSON
{
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
    "chainId": $CHAIN_ID,
    "verifyingContract": "$AWP_TOKEN"
  },
  "message": {
    "owner": "$WALLET_ADDR",
    "spender": "$ROOT_NET",
    "value": $LP_COST,
    "nonce": $PERMIT_NONCE,
    "deadline": $DEADLINE
  }
}
EIPJSON
)

PERMIT_SIG=$(awp-wallet sign-typed-data --token "$TOKEN" --data "$PERMIT_DATA") || {
  echo '{"error": "Permit signing failed"}' >&2; exit 1
}
PERMIT_SIGNATURE=$(echo "$PERMIT_SIG" | jq -r '.signature')

# Step 7: Sign EIP-712 RegisterSubnet
REGISTER_DATA=$(cat <<EIPJSON
{
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
      {"name": "subnetManager", "type": "address"},
      {"name": "salt", "type": "bytes32"},
      {"name": "minStake", "type": "uint128"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "RegisterSubnet",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$ROOT_NET"
  },
  "message": {
    "user": "$WALLET_ADDR",
    "name": "$NAME",
    "symbol": "$SYMBOL",
    "subnetManager": "$SUBNET_MANAGER",
    "salt": "$SALT",
    "minStake": $MIN_STAKE,
    "nonce": $ROOTNET_NONCE,
    "deadline": $DEADLINE
  }
}
EIPJSON
)

REGISTER_SIG=$(awp-wallet sign-typed-data --token "$TOKEN" --data "$REGISTER_DATA") || {
  echo '{"error": "RegisterSubnet signing failed"}' >&2; exit 1
}
REGISTER_SIGNATURE=$(echo "$REGISTER_SIG" | jq -r '.signature')

# Step 8: Submit to relay
RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/register-subnet" \
  -H "Content-Type: application/json" \
  -d "{
    \"user\": \"$WALLET_ADDR\",
    \"name\": \"$NAME\",
    \"symbol\": \"$SYMBOL\",
    \"subnetManager\": \"$SUBNET_MANAGER\",
    \"salt\": \"$SALT\",
    \"minStake\": \"$MIN_STAKE\",
    \"deadline\": $DEADLINE,
    \"permitSignature\": \"$PERMIT_SIGNATURE\",
    \"registerSignature\": \"$REGISTER_SIGNATURE\"
  }")

HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
