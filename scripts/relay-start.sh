#!/usr/bin/env bash
# AWP RootNet: One-command gasless onboarding
#
# Usage:
#   Principal mode (register as self-managed account):
#     ./relay-start.sh --token <session_token> --mode principal
#
#   Agent mode (bind to a principal):
#     ./relay-start.sh --token <session_token> --mode agent --principal <address>
#
# Principal calls register() via /relay/register
# Agent calls bind() via /relay/bind
# Choose ONE — do not call both for the same address.
#
# Prerequisites: awp-wallet (unlocked), curl, jq, python3

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=""
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
CHAIN_ID=$(echo "$REGISTRY" | jq -r '.chainId // 56')

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')

# Step 3: Check current status
CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check") || true
IS_USER=$(echo "$CHECK" | jq -r '.isRegisteredUser' 2>/dev/null || echo "false")
IS_AGENT=$(echo "$CHECK" | jq -r '.isRegisteredAgent' 2>/dev/null || echo "false")

if [[ "$MODE" == "principal" && "$IS_USER" == "true" ]]; then
  echo '{"status": "already_registered", "address": "'"$WALLET_ADDR"'"}'
  exit 0
fi

if [[ "$MODE" == "agent" && "$IS_AGENT" == "true" ]]; then
  CURRENT_OWNER=$(echo "$CHECK" | jq -r '.ownerAddress' 2>/dev/null || echo "")
  echo '{"status": "already_bound", "address": "'"$WALLET_ADDR"'", "principal": "'"$CURRENT_OWNER"'"}'
  exit 0
fi

# Step 4: Get nonce
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$ROOT_NET" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 5: Deadline
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 6: Sign and submit based on mode
if [[ "$MODE" == "principal" ]]; then
  # ---- PRINCIPAL: register() via /relay/register ----
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

  RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/register" \
    -H "Content-Type: application/json" \
    -d "{\"user\": \"$WALLET_ADDR\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")

else
  # ---- AGENT: bind(principal) via /relay/bind ----
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

  RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/bind" \
    -H "Content-Type: application/json" \
    -d "{\"agent\": \"$WALLET_ADDR\", \"principal\": \"$PRINCIPAL\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")
fi

# Step 7: Parse response
HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
