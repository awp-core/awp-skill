#!/usr/bin/env bash
# Gasless agent binding via EIP-712 relay
# Usage: ./relay-bind.sh --token <session_token> --principal <address>
#
# Prerequisites: awp-wallet, curl, jq, python3
# No cast/foundry required.

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""
PRINCIPAL=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --principal) PRINCIPAL="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;;
  esac
done

[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token"}' >&2; exit 1; }
[[ -z "$PRINCIPAL" ]] && { echo '{"error": "Missing --principal"}' >&2; exit 1; }

eth_call() {
  local to="$1" data="$2"
  curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"'"$to"'","data":"'"$data"'"},"latest"],"id":1}' | jq -r '.result'
}

hex_to_dec() { python3 -c "print(int('$1', 16))"; }

# Step 1: Fetch registry
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
echo "$REGISTRY" | jq -e '.rootNet' > /dev/null 2>&1 || { echo "$REGISTRY" >&2; exit 1; }
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

# Step 2: Get wallet address (this is the agent)
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Get nonce — bind uses the AGENT's nonce (not principal's)
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$ROOT_NET" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 4: Deadline
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
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
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

# Step 6: Submit to relay
RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/bind" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"$WALLET_ADDR\", \"principal\": \"$PRINCIPAL\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")

HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
