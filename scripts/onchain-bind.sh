#!/usr/bin/env bash
# On-chain bind(ownerAddress) — become an Agent for a Principal
# Usage: ./onchain-bind.sh --token <session_token> --principal <address>
# Requires BNB for gas. bind() auto-registers the principal if needed.
set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
TOKEN=""
PRINCIPAL=""
while [[ $# -gt 0 ]]; do
  case $1 in --token) TOKEN="$2"; shift 2 ;; --principal) PRINCIPAL="$2"; shift 2 ;; *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;; esac
done
[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token"}' >&2; exit 1; }
[[ -z "$PRINCIPAL" ]] && { echo '{"error": "Missing --principal"}' >&2; exit 1; }

# Pre-flight
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')
[[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]] && { echo '{"error": "Invalid token"}' >&2; exit 1; }

REGISTRY=$(curl -s "$API_BASE/registry")
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check")
IS_AGENT=$(echo "$CHECK" | jq -r '.isRegisteredAgent')
[[ "$IS_AGENT" == "true" ]] && { echo '{"status": "already_bound", "address": "'"$WALLET_ADDR"'"}'; exit 0; }

# bind(address) selector = 0x81bac14f + ABI-encoded address
ADDR_PADDED=$(python3 -c "print('${PRINCIPAL#0x}'.lower().zfill(64))")
awp-wallet send --token "$TOKEN" --to "$ROOT_NET" --data "0x81bac14f${ADDR_PADDED}" --chain bsc
