#!/usr/bin/env bash
# Gasless agent binding via EIP-712 relay
# Usage: ./relay-bind.sh --token <session_token> --principal <address>
#
# Prerequisites: awp-wallet installed and unlocked, cast (foundry) installed
# The script will:
#   1. Fetch RootNet address from /registry
#   2. Get wallet address (agent) and nonce
#   3. Construct and sign EIP-712 Bind typed data
#   4. Submit to POST /relay/bind
#   5. Output the txHash

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""
PRINCIPAL=""

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --principal) PRINCIPAL="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$TOKEN" ]]; then
  echo '{"error": "Missing --token <session_token>"}' >&2
  exit 1
fi
if [[ -z "$PRINCIPAL" ]]; then
  echo '{"error": "Missing --principal <address>"}' >&2
  exit 1
fi

# Step 1: Fetch contract addresses
REGISTRY=$(curl -sf "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

# Step 2: Get wallet address (this is the agent)
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Get nonce
NONCE=$(cast call "$ROOT_NET" "nonces(address)(uint256)" "$WALLET_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || echo "0")
NONCE=$(echo "$NONCE" | tr -d '[:space:]')

# Step 4: Set deadline (1 hour from now)
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 5: Sign EIP-712
EIP712_DATA=$(cat <<EIPJSON
{
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
      {"name": "deadline", "type": "uint256"},
      {"name": "nonce", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$ROOT_NET"
  },
  "message": {
    "agent": "$WALLET_ADDR",
    "principal": "$PRINCIPAL",
    "deadline": $DEADLINE,
    "nonce": $NONCE
  }
}
EIPJSON
)

SIG_RESULT=$(awp-wallet sign-typed-data --token "$TOKEN" --data "$EIP712_DATA") || {
  echo '{"error": "EIP-712 signing failed"}' >&2
  exit 1
}
SIGNATURE=$(echo "$SIG_RESULT" | jq -r '.signature')

# Step 6: Submit to relay
RELAY_RESULT=$(curl -sf -X POST "$API_BASE/relay/bind" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"$WALLET_ADDR\", \"principal\": \"$PRINCIPAL\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}") || {
  echo '{"error": "Relay submission failed"}' >&2
  exit 1
}

echo "$RELAY_RESULT"
