#!/usr/bin/env bash
# AWP RootNet: One-command gasless onboarding
#
# Usage:
#   Principal mode: ./relay-start.sh --token <session_token> --mode principal
#   Agent mode:     ./relay-start.sh --token <session_token> --mode agent --principal <address>
#
# --token is the awp-wallet session token from `awp-wallet unlock`.
# The agent (OpenClaw) manages the wallet password and provides the token.
#
# bind() auto-registers the principal — no separate register() call needed.
#
# Prerequisites: awp-wallet (unlocked), curl, jq, python3

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=56
TOKEN=""
MODE=""
PRINCIPAL=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --principal) PRINCIPAL="$2"; shift 2 ;;
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;;
  esac
done

[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token (get from awp-wallet unlock)"}' >&2; exit 1; }
[[ -z "$MODE" ]] && { echo '{"error": "Missing --mode (principal or agent)"}' >&2; exit 1; }
[[ "$MODE" != "principal" && "$MODE" != "agent" ]] && { echo '{"error": "--mode must be principal or agent"}' >&2; exit 1; }
[[ "$MODE" == "agent" && -z "$PRINCIPAL" ]] && { echo '{"error": "Agent mode requires --principal <address>"}' >&2; exit 1; }

eth_call() {
  local to="$1" data="$2"
  curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"'"$to"'","data":"'"$data"'"},"latest"],"id":1}' | jq -r '.result'
}

hex_to_dec() { python3 -c "print(int('$1', 16))"; }

# Step 1: Fetch registry (fresh, never cached)
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
echo "$REGISTRY" | jq -e '.rootNet' > /dev/null 2>&1 || { echo "$REGISTRY" >&2; exit 1; }
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Determine bind target
if [[ "$MODE" == "principal" ]]; then
  BIND_PRINCIPAL="$WALLET_ADDR"
else
  BIND_PRINCIPAL="$PRINCIPAL"
fi

# Step 4: Check if already bound
CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check") || true
IS_AGENT=$(echo "$CHECK" | jq -r '.isRegisteredAgent' 2>/dev/null || echo "false")
if [[ "$IS_AGENT" == "true" ]]; then
  CURRENT_OWNER=$(echo "$CHECK" | jq -r '.ownerAddress' 2>/dev/null || echo "")
  echo '{"status": "already_bound", "address": "'"$WALLET_ADDR"'", "principal": "'"$CURRENT_OWNER"'"}'
  exit 0
fi

# Step 5: Get nonce (agent's nonce for bind)
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$ROOT_NET" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 6: Deadline
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 7: Sign EIP-712 Bind
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
    "principal": "$BIND_PRINCIPAL",
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

# Step 8: Submit to relay/bind
RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/bind" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"$WALLET_ADDR\", \"principal\": \"$BIND_PRINCIPAL\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")

HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
