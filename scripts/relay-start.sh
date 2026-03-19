#!/usr/bin/env bash
# AWP Gasless onboarding — compatible with both V1 (RootNet) and V2 (AWPRegistry) APIs
#
# Usage:
#   Principal mode (register / set recipient to self):
#     ./relay-start.sh --token <session_token> --mode principal
#
#   Agent mode (bind to a target address):
#     ./relay-start.sh --token <session_token> --mode agent --target <address>
#
# The script auto-detects V1 vs V2 API:
#   V1: /registry returns .rootNet → uses /relay/register, EIP-712 domain "AWPRootNet"
#   V2: /registry returns .awpRegistry → uses /relay/set-recipient, EIP-712 domain "AWPRegistry"
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
    --principal) MODE="principal"; shift 1 ;;
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

# Step 1: Fetch registry — auto-detect V1 (.rootNet) vs V2 (.awpRegistry)
REGISTRY=$(curl -s "$API_BASE/registry") || { echo '{"error": "Failed to fetch /registry"}' >&2; exit 1; }

# Detect API version
API_VERSION="v1"
CONTRACT_ADDR=$(echo "$REGISTRY" | jq -r '.awpRegistry // empty')
if [[ -n "$CONTRACT_ADDR" && "$CONTRACT_ADDR" != "null" ]]; then
  API_VERSION="v2"
  EIP712_DOMAIN_NAME="AWPRegistry"
else
  CONTRACT_ADDR=$(echo "$REGISTRY" | jq -r '.rootNet // empty')
  [[ -z "$CONTRACT_ADDR" || "$CONTRACT_ADDR" == "null" ]] && { echo '{"error": "Registry missing both .awpRegistry and .rootNet"}' >&2; exit 1; }
  EIP712_DOMAIN_NAME="AWPRootNet"
fi
echo '{"info": "API version detected: '"$API_VERSION"', contract: '"$CONTRACT_ADDR"'"}' >&2

# Get chainId — try registry first, fallback to RPC
CHAIN_ID=$(echo "$REGISTRY" | jq -r '.chainId // empty')
if [[ -z "$CHAIN_ID" || "$CHAIN_ID" == "null" ]]; then
  CHAIN_ID_HEX=$(curl -s -X POST "$RPC_URL" -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' | jq -r '.result')
  CHAIN_ID=$(hex_to_dec "$CHAIN_ID_HEX")
fi

# Step 2: Get wallet address
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address') || {
  echo '{"error": "Failed to get wallet address — is the token valid?"}' >&2; exit 1
}
[[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]] && {
  echo '{"error": "Wallet address is empty — token may be expired"}' >&2; exit 1
}

# Step 3: Check current status — handle V1 and V2 response formats
CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check") || true

if [[ "$API_VERSION" == "v2" ]]; then
  IS_REGISTERED=$(echo "$CHECK" | jq -r '.isRegistered // false' 2>/dev/null)
  BOUND_TO=$(echo "$CHECK" | jq -r '.boundTo // empty' 2>/dev/null)
  RECIPIENT=$(echo "$CHECK" | jq -r '.recipient // empty' 2>/dev/null)
else
  # V1 format: {isRegisteredUser, isRegisteredAgent, isManager, ownerAddress}
  IS_REG_USER=$(echo "$CHECK" | jq -r '.isRegisteredUser // false' 2>/dev/null)
  IS_REG_AGENT=$(echo "$CHECK" | jq -r '.isRegisteredAgent // false' 2>/dev/null)
  OWNER_ADDR=$(echo "$CHECK" | jq -r '.ownerAddress // empty' 2>/dev/null)
  IS_REGISTERED="false"
  [[ "$IS_REG_USER" == "true" || "$IS_REG_AGENT" == "true" ]] && IS_REGISTERED="true"
  BOUND_TO="$OWNER_ADDR"
  RECIPIENT=""
fi

# Early exit if already registered/bound
if [[ "$MODE" == "principal" && "$IS_REGISTERED" == "true" ]]; then
  echo '{"status": "already_registered", "address": "'"$WALLET_ADDR"'"}'
  exit 0
fi
if [[ "$MODE" == "agent" && -n "$BOUND_TO" && "$BOUND_TO" != "null" && "$BOUND_TO" != "0x0000000000000000000000000000000000000000" ]]; then
  echo '{"status": "already_bound", "address": "'"$WALLET_ADDR"'", "boundTo": "'"$BOUND_TO"'"}'
  exit 0
fi

# Step 4: Get nonce
ADDR_PADDED=$(python3 -c "print('${WALLET_ADDR#0x}'.lower().zfill(64))")
NONCE_HEX=$(eth_call "$CONTRACT_ADDR" "0x7ecebe00${ADDR_PADDED}")
NONCE=$(hex_to_dec "$NONCE_HEX")

# Step 5: Deadline
DEADLINE=$(( $(date +%s) + 3600 ))

# Step 6: Sign and submit based on mode + API version
if [[ "$MODE" == "principal" ]]; then
  if [[ "$API_VERSION" == "v2" ]]; then
    # V2: setRecipient(self) via /relay/set-recipient
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
    "name": "$EIP712_DOMAIN_NAME",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$CONTRACT_ADDR"
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
    RELAY_ENDPOINT="$API_BASE/relay/set-recipient"
    RELAY_BODY="{\"user\": \"$WALLET_ADDR\", \"recipient\": \"$WALLET_ADDR\", \"deadline\": $DEADLINE, \"signature\": \"__SIG__\"}"
  else
    # V1: register() via /relay/register
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
    "name": "$EIP712_DOMAIN_NAME",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$CONTRACT_ADDR"
  },
  "message": {
    "user": "$WALLET_ADDR",
    "nonce": $NONCE,
    "deadline": $DEADLINE
  }
}
EIPJSON
)
    RELAY_ENDPOINT="$API_BASE/relay/register"
    RELAY_BODY="{\"user\": \"$WALLET_ADDR\", \"deadline\": $DEADLINE, \"signature\": \"__SIG__\"}"
  fi

else
  # AGENT mode: bind(target) via /relay/bind — same for V1 and V2
  if [[ "$API_VERSION" == "v2" ]]; then
    BIND_TYPE_NAME="Bind"
    BIND_FIELD_1="user"
    BIND_FIELD_2="target"
  else
    BIND_TYPE_NAME="Bind"
    BIND_FIELD_1="agent"
    BIND_FIELD_2="principal"
  fi

  EIP712_DATA=$(cat <<EIPJSON
{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "$BIND_TYPE_NAME": [
      {"name": "$BIND_FIELD_1", "type": "address"},
      {"name": "$BIND_FIELD_2", "type": "address"},
      {"name": "nonce", "type": "uint256"},
      {"name": "deadline", "type": "uint256"}
    ]
  },
  "primaryType": "$BIND_TYPE_NAME",
  "domain": {
    "name": "$EIP712_DOMAIN_NAME",
    "version": "1",
    "chainId": $CHAIN_ID,
    "verifyingContract": "$CONTRACT_ADDR"
  },
  "message": {
    "$BIND_FIELD_1": "$WALLET_ADDR",
    "$BIND_FIELD_2": "$TARGET",
    "nonce": $NONCE,
    "deadline": $DEADLINE
  }
}
EIPJSON
)

  if [[ "$API_VERSION" == "v2" ]]; then
    RELAY_ENDPOINT="$API_BASE/relay/bind"
    RELAY_BODY="{\"user\": \"$WALLET_ADDR\", \"target\": \"$TARGET\", \"deadline\": $DEADLINE, \"signature\": \"__SIG__\"}"
  else
    RELAY_ENDPOINT="$API_BASE/relay/bind"
    RELAY_BODY="{\"agent\": \"$WALLET_ADDR\", \"principal\": \"$TARGET\", \"deadline\": $DEADLINE, \"signature\": \"__SIG__\"}"
  fi
fi

# Sign
SIG_RESULT=$(awp-wallet sign-typed-data --token "$TOKEN" --data "$EIP712_DATA") || {
  echo '{"error": "EIP-712 signing failed"}' >&2; exit 1
}
SIGNATURE=$(echo "$SIG_RESULT" | jq -r '.signature')

# Replace signature placeholder in body
FINAL_BODY=$(echo "$RELAY_BODY" | sed "s|__SIG__|$SIGNATURE|")

# Submit
echo '{"info": "Submitting to '"$RELAY_ENDPOINT"'"}' >&2
RELAY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$RELAY_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d "$FINAL_BODY")

# Step 7: Parse response
HTTP_CODE=$(echo "$RELAY_RESULT" | tail -1)
BODY=$(echo "$RELAY_RESULT" | sed '$d')

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "$BODY"
else
  echo "$BODY" >&2
  exit 1
fi
