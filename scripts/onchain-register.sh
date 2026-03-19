#!/usr/bin/env bash
# On-chain register() — optional explicit registration (V2)
# In V2, register() is equivalent to setRecipient(msg.sender).
# Every address is implicitly a root; calling register() just explicitly
# sets your recipient to yourself.
# Usage: ./onchain-register.sh --token <session_token>
# Requires BNB for gas.
set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
TOKEN=""
while [[ $# -gt 0 ]]; do
  case $1 in --token) TOKEN="$2"; shift 2 ;; *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;; esac
done
[[ -z "$TOKEN" ]] && { echo '{"error": "Missing --token"}' >&2; exit 1; }

# Pre-flight
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')
[[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]] && { echo '{"error": "Invalid token"}' >&2; exit 1; }

REGISTRY=$(curl -s "$API_BASE/registry")
AWP_REGISTRY=$(echo "$REGISTRY" | jq -r '.awpRegistry')

CHECK=$(curl -s "$API_BASE/address/$WALLET_ADDR/check")
IS_REGISTERED=$(echo "$CHECK" | jq -r '.isRegistered')
RECIPIENT=$(echo "$CHECK" | jq -r '.recipient')
[[ "$IS_REGISTERED" == "true" ]] && { echo '{"status": "already_registered", "address": "'"$WALLET_ADDR"'", "recipient": "'"$RECIPIENT"'"}'; exit 0; }

# register() selector = 0x1aa3a008
awp-wallet send --token "$TOKEN" --to "$AWP_REGISTRY" --data "0x1aa3a008" --chain bsc
