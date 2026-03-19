#!/usr/bin/env bash
# On-chain allocate stake to agent+subnet
# Usage: ./onchain-allocate.sh --token <T> --agent <addr> --subnet <id> --amount <AWP_human>
# Requires BNB for gas.
set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
TOKEN=""
AGENT=""
SUBNET=""
AMOUNT=""
while [[ $# -gt 0 ]]; do
  case $1 in --token) TOKEN="$2"; shift 2 ;; --agent) AGENT="$2"; shift 2 ;; --subnet) SUBNET="$2"; shift 2 ;; --amount) AMOUNT="$2"; shift 2 ;; *) echo '{"error": "Unknown arg: '"$1"'"}' >&2; exit 1 ;; esac
done
[[ -z "$TOKEN" || -z "$AGENT" || -z "$SUBNET" || -z "$AMOUNT" ]] && { echo '{"error": "Missing --token, --agent, --subnet, --amount"}' >&2; exit 1; }

# Pre-flight
WALLET_ADDR=$(awp-wallet status --token "$TOKEN" | jq -r '.address')
[[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]] && { echo '{"error": "Invalid token"}' >&2; exit 1; }

REGISTRY=$(curl -s "$API_BASE/registry")
ROOT_NET=$(echo "$REGISTRY" | jq -r '.rootNet')

# Check unallocated balance
BALANCE=$(curl -s "$API_BASE/staking/user/$WALLET_ADDR/balance")
UNALLOCATED=$(echo "$BALANCE" | jq -r '.unallocated')
AMOUNT_WEI=$(python3 -c "print(int(float('$AMOUNT') * 10**18))")

python3 -c "
unalloc = int('$UNALLOCATED')
needed = $AMOUNT_WEI
if needed > unalloc:
    import sys
    print('{\"error\": \"Insufficient unallocated balance: have ' + str(unalloc/10**18) + ' AWP, need $AMOUNT AWP\"}', file=sys.stderr)
    sys.exit(1)
" || exit 1

# allocate(address,uint256,uint256) selector = 0x...
AGENT_PADDED=$(python3 -c "print('${AGENT#0x}'.lower().zfill(64))")
SUBNET_PADDED=$(python3 -c "print(hex($SUBNET)[2:].zfill(64))")
AMOUNT_PADDED=$(python3 -c "print(hex($AMOUNT_WEI)[2:].zfill(64))")

# allocate(address,uint256,uint256) keccak selector = 0xab3f22d5 (verify against ABI)
CALLDATA="0xab3f22d5${AGENT_PADDED}${SUBNET_PADDED}${AMOUNT_PADDED}"

echo '{"step": "allocate", "agent": "'"$AGENT"'", "subnet": '"$SUBNET"', "amount": "'"$AMOUNT"' AWP"}' >&2
awp-wallet send --token "$TOKEN" --to "$ROOT_NET" --data "$CALLDATA" --chain bsc
