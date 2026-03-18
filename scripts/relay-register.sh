#!/usr/bin/env bash
# Gasless user registration via EIP-712 relay
# Usage: ./relay-register.sh --token <session_token>
#
# Prerequisites: awp-wallet installed and unlocked, cast (foundry) installed
# The script will:
#   1. Fetch RootNet address from /registry
#   2. Get wallet address and nonce
#   3. Construct and sign EIP-712 Register typed data
#   4. Submit to POST /relay/register
#   5. Output the txHash

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TOKEN" ]]; then
  echo '{"error": "Missing --token <session_token>"}' >&2
  exit 1
fi

# Step 1: Fetch contract addresses
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
echo "$REGISTRY" | jq -e '.rootNet' > /dev/null 2>&1 || { echo "$REGISTRY" >&2; exit 1; }
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Check if already registered
CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check") || { echo '{"error": "Failed to check registration"}' >&2; exit 1; }
IS_REGISTERED=$(echo "$CHECK" | jq -r '.isRegisteredUser')
if [[ "$IS_REGISTERED" == "true" ]]; then
  echo '{"status": "already_registered", "address": "'"$WALLET_ADDR"'"}'
  exit 0
fi

# Step 4: Get nonce
NONCE=$(cast call "$ROOT_NET" "nonces(address)(uint256)" "$WALLET_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
NONCE=$(echo "$NONCE" | tr -d '[:space:]')

# Step 5: Set deadline (1 hour from now)
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 6: Sign EIP-712
EIP712_DATA=$(cat <<EIPJSON
{
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
    "chainId": $CHAIN_ID,
    "verifyingContract": "$ROOT_NET"
  },
  "message": {
    "user": "$WALLET_ADDR",
    "nonce": $NONCE,
    "deadline": $DEADLINE
  }
}
EIPJSON
)

SIG_RESULT=$(awp-wallet sign-typed-data --token "$TOKEN" --data "$EIP712_DATA") || {
  echo '{"error": "EIP-712 signing failed"}' >&2
  exit 1
}
SIGNATURE=$(echo "$SIG_RESULT" | jq -r '.signature')

# Step 7: Submit to relay
RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/register" \
  -H "Content-Type: application/json" \
  -d "{\"user\": \"$WALLET_ADDR\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")

HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
