#!/usr/bin/env bash
# Gasless user registration via EIP-712 relay
# Usage: ./relay-register.sh --token <session_token>
#
# Prerequisites: awp-wallet, curl, jq, python3
# No cast/foundry required.

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;;
  esac
done

[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token"}' >&2; exit 1; }

# Helper: eth_call via JSON-RPC (no cast needed)
eth_call() {
  local to="$1" data="$2"
  local result
  result=$(curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"'"$to"'","data":"'"$data"'"},"latest"],"id":1}')
  echo "$result" | jq -r '.result'
}

# Helper: decode uint256 hex to decimal
hex_to_dec() {
  python3 -c "print(int('$1', 16))"
}

# Step 1: Fetch registry
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

# Step 4: Get nonce — nonces(address) selector = 0x7ecebe00
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$ROOT_NET" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 5: Deadline = now + 1 hour
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
  echo '{"error": "EIP-712 signing failed"}' >&2; exit 1
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
