#!/usr/bin/env bash
# AWP Registry V2: One-command gasless onboarding
#
# Usage:
#   Principal mode (set recipient to self — explicit registration):
#     ./relay-start.sh --token <session_token> --mode principal
#
#   Agent mode (bind to a target address):
#     ./relay-start.sh --token <session_token> --mode agent --target <address>
#
# In V2, every address is implicitly registered. There is no /relay/register endpoint.
# - Principal mode calls setRecipient(self) via /relay/set-recipient
# - Agent mode calls bind(target) via /relay/bind
# Choose ONE — do not call both for the same address.
#
# Prerequisites: awp-wallet (unlocked), curl, jq, python3

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
RPC_URL="${BSC_RPC_URL:-https://bsc-dataseed.binance.org}"
CHAIN_ID=""
TOKEN=""
MODE=""
TARGET=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --principal) MODE="principal"; shift 1 ;;  # backward compat: --principal = --mode principal
    --api) API_BASE="$2"; shift 2 ;;
    --rpc) RPC_URL="$2"; shift 2 ;;
    *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;;
  esac
done

[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token (get from awp-wallet unlock)"}' >&2; exit 1; }
[[ -z "$MODE" ]] && { echo '{"error": "Missing --mode (principal or agent)"}' >&2; exit 1; }
[[ "$MODE" != "principal" && "$MODE" != "agent" ]] && { echo '{"error": "--mode must be principal or agent"}' >&2; exit 1; }
[[ "$MODE" == "agent" && -z "$TARGET" ]] && { echo '{"error": "Agent mode requires --target <address>"}' >&2; exit 1; }
[[ -n "$TARGET" && ! "$TARGET" =~ ^0x[0-9a-fA-F]{40}$ ]] && { echo '{"error": "Invalid --target address: must be 0x + 40 hex chars"}' >&2; exit 1; }

eth_call() {
  local to="$1" data="$2"
  curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"'"$to"'","data":"'"$data"'"},"latest"],"id":1}' | jq -r '.result'
}

hex_to_dec() {
  local val="$1"
  [[ -z "$val" || "$val" == "null" || "$val" == "0x" ]] && { echo '{"error": "RPC returned empty/null value"}' >&2; exit 1; }
  python3 -c "print(int('$val', 16))"
}

# Step 1: Fetch registry (fresh, never cached)
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }
echo "$REGISTRY" | jq -e '.awpRegistry' > /dev/null 2>&1 || { echo "$REGISTRY" >&2; exit 1; }
AWP_REGISTRY=$(echo "$REGISTRY" | jq -r '.awpRegistry')

# Get chainId from RPC (not in /registry response)
CHAIN_ID_HEX=$(curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' | jq -r '.result')
CHAIN_ID=$(hex_to_dec "$CHAIN_ID_HEX")

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address') || {
  echo '{"error": "Failed to get wallet address — is the token valid?"}' >&2; exit 1
}
[[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]] && {
  echo '{"error": "Wallet address is empty — token may be expired"}' >&2; exit 1
}

# Step 3: Check current status
CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check") || true
IS_REGISTERED=$(echo "$CHECK" | jq -r '.isRegistered' 2>/dev/null || echo "false")
BOUND_TO=$(echo "$CHECK" | jq -r '.boundTo' 2>/dev/null || echo "")
RECIPIENT=$(echo "$CHECK" | jq -r '.recipient' 2>/dev/null || echo "")

if [[ "$MODE" == "principal" && "$RECIPIENT" != "" && "$RECIPIENT" != "null" && "$RECIPIENT" != "0x0000000000000000000000000000000000000000" ]]; then
  echo '{"status": "already_registered", "address": "'"$WALLET_ADDR"'", "recipient": "'"$RECIPIENT"'"}'
  exit 0
fi

if [[ "$MODE" == "agent" && "$BOUND_TO" != "" && "$BOUND_TO" != "null" && "$BOUND_TO" != "0x0000000000000000000000000000000000000000" ]]; then
  echo '{"status": "already_bound", "address": "'"$WALLET_ADDR"'", "boundTo": "'"$BOUND_TO"'"}'
  exit 0
fi

# Step 4: Get nonce
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$AWP_REGISTRY" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 5: Deadline
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 6: Sign and submit based on mode
if [[ "$MODE" == "principal" ]]; then
  # ---- PRINCIPAL: setRecipient(self) via /relay/set-recipient ----
  EIP712_DATA=$(cat <<EIPJSON
{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "SetRecipient": [
      {"name": "user", "type": "address"},
      {"name": "recipient", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "SetRecipient",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$AWP_REGISTRY"
  },
  "message": {
    "user": "$WALLET_ADDR",
    "recipient": "$WALLET_ADDR",
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

  RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/relay/set-recipient" \
    -H "Content-Type: application/json" \
    -d "{\"user\": \"$WALLET_ADDR\", \"recipient\": \"$WALLET_ADDR\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")

else
  # ---- AGENT: bind(target) via /relay/bind ----
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
      {"name": "user", "type": "address"},
      {"name": "target", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRegistry",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$AWP_REGISTRY"
  },
  "message": {
    "user": "$WALLET_ADDR",
    "target": "$TARGET",
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
    -d "{\"user\": \"$WALLET_ADDR\", \"target\": \"$TARGET\", \"deadline\": $DEADLINE, \"signature\": \"$SIGNATURE\"}")
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
