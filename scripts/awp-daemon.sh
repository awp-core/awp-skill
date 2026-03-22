#!/usr/bin/env bash
# AWP Daemon — background service for AWP skill
# Runs continuously: checks dependencies, initializes wallet, monitors state, checks updates.
#
# Usage: bash scripts/awp-daemon.sh
# Stops: Ctrl+C or kill $PID
#
# Prerequisites: curl, jq, node/npm (for awp-wallet)

set -euo pipefail

API_BASE="${AWP_API_URL:-https://tapi.awp.sh/api}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WALLET_ADDR=""
CHECK_INTERVAL=300  # seconds between update checks (5 min)
SKILL_REPO="https://github.com/awp-core/awp-skill"
WALLET_REPO="https://github.com/awp-core/awp-wallet"

# ── Logging ──────────────────────────────────────

log()  { echo "[AWP $(date +%H:%M:%S)] $*"; }
warn() { echo "[AWP $(date +%H:%M:%S)] ⚠ $*"; }
err()  { echo "[AWP $(date +%H:%M:%S)] ✗ $*" >&2; }

# ── 1. Wallet Installation ───────────────────────

ensure_wallet_installed() {
  if which awp-wallet >/dev/null 2>&1; then
    return 0
  fi

  log "awp-wallet not found. Installing..."

  if skill install awp-wallet 2>/dev/null; then
    log "awp-wallet installed from registry ✓"
  elif skill install "$WALLET_REPO" 2>/dev/null; then
    log "awp-wallet installed from GitHub ✓"
  else
    err "Failed to install awp-wallet. Please install manually:"
    err "  skill install awp-wallet"
    err "  OR: skill install $WALLET_REPO"
    return 1
  fi
}

# ── 2. Wallet Initialization ─────────────────────

ensure_wallet_initialized() {
  # Try to get wallet address — if it works, wallet is initialized
  local status
  status=$(awp-wallet receive 2>/dev/null) || true

  if echo "$status" | jq -e '.address' >/dev/null 2>&1; then
    WALLET_ADDR=$(echo "$status" | jq -r '.address')
    return 0
  fi

  log "Wallet not initialized. Running awp-wallet init..."
  local init_result
  init_result=$(awp-wallet init 2>&1) || true

  if echo "$init_result" | grep -qi "error\|fail"; then
    err "Wallet init failed: $init_result"
    return 1
  fi

  # Get address after init
  status=$(awp-wallet receive 2>/dev/null) || true
  WALLET_ADDR=$(echo "$status" | jq -r '.address // empty')

  if [[ -z "$WALLET_ADDR" || "$WALLET_ADDR" == "null" ]]; then
    err "Wallet initialized but could not read address"
    return 1
  fi

  log "Wallet initialized ✓"
  log "Address: $WALLET_ADDR"
  log ""
  log "┌─────────────────────────────────────────────┐"
  log "│  This is an AGENT WORK WALLET.              │"
  log "│  Do NOT store personal assets here.          │"
  log "│  Keep only minimal ETH for gas.              │"
  log "└─────────────────────────────────────────────┘"
}

# ── 3. Check Registration & Show Status ──────────

check_and_notify() {
  local check reg_status subnets

  # Check registration
  check=$(curl -s "$API_BASE/address/$WALLET_ADDR/check" 2>/dev/null) || true
  local is_registered
  is_registered=$(echo "$check" | jq -r '.isRegistered // false' 2>/dev/null)

  echo ""
  log "── agent status ──────────────────────"

  if [[ "$is_registered" != "true" ]]; then
    log "Address:    $WALLET_ADDR"
    log "Status:     NOT REGISTERED"
    log ""
    log "┌─────────────────────────────────────────────┐"
    log "│  You are not registered on AWP yet.          │"
    log "│                                              │"
    log "│  To register (free, gasless), tell your      │"
    log "│  agent: \"start working on AWP\"               │"
    log "│                                              │"
    log "│  Or run manually:                            │"
    log "│  bash scripts/relay-start.sh \\               │"
    log "│    --token \$TOKEN --mode principal            │"
    log "└─────────────────────────────────────────────┘"
  else
    local bound_to recipient
    bound_to=$(echo "$check" | jq -r '.boundTo // ""' 2>/dev/null)
    recipient=$(echo "$check" | jq -r '.recipient // ""' 2>/dev/null)

    log "Address:    $WALLET_ADDR"
    log "Status:     REGISTERED ✓"
    [[ -n "$bound_to" && "$bound_to" != "" ]] && log "Bound to:   $bound_to"
    [[ -n "$recipient" && "$recipient" != "" ]] && log "Recipient:  $recipient"

    # Fetch balance
    local balance
    balance=$(curl -s "$API_BASE/staking/user/$WALLET_ADDR/balance" 2>/dev/null) || true
    local staked allocated unallocated
    staked=$(echo "$balance" | jq -r '.totalStaked // "0"' 2>/dev/null)
    allocated=$(echo "$balance" | jq -r '.totalAllocated // "0"' 2>/dev/null)
    unallocated=$(echo "$balance" | jq -r '.unallocated // "0"' 2>/dev/null)

    # Convert wei to AWP (rough, using python3 if available)
    if which python3 >/dev/null 2>&1; then
      staked=$(python3 -c "print(f'{int(\"$staked\") / 10**18:,.4f}')" 2>/dev/null || echo "$staked")
      allocated=$(python3 -c "print(f'{int(\"$allocated\") / 10**18:,.4f}')" 2>/dev/null || echo "$allocated")
      unallocated=$(python3 -c "print(f'{int(\"$unallocated\") / 10**18:,.4f}')" 2>/dev/null || echo "$unallocated")
    fi

    log "Staked:     $staked AWP"
    log "Allocated:  $allocated AWP"
    log "Unallocated:$unallocated AWP"
  fi

  log "──────────────────────────────────────"

  # Fetch active subnets
  echo ""
  log "── available subnets ─────────────────"

  subnets=$(curl -s "$API_BASE/subnets?status=Active&limit=10" 2>/dev/null) || true

  if echo "$subnets" | jq -e '.[0]' >/dev/null 2>&1; then
    echo "$subnets" | jq -r '.[] | "  #\(.subnet_id)  \(.name)\t min: \(.min_stake) AWP\t skills: \(if .skills_uri != "" and .skills_uri != null then "✓" else "—" end)"' 2>/dev/null || echo "  (failed to parse subnets)"

    local count free_count skill_count
    count=$(echo "$subnets" | jq 'length' 2>/dev/null || echo "?")
    free_count=$(echo "$subnets" | jq '[.[] | select(.min_stake == 0)] | length' 2>/dev/null || echo "?")
    skill_count=$(echo "$subnets" | jq '[.[] | select(.skills_uri != "" and .skills_uri != null)] | length' 2>/dev/null || echo "?")

    log ""
    log "$count subnets. $free_count free (no staking). $skill_count with skills."
  else
    log "  No active subnets found (or API unavailable)"
  fi

  log "──────────────────────────────────────"

  # Next action suggestion
  echo ""
  if [[ "$is_registered" != "true" ]]; then
    log "→ Next: say \"start working on AWP\" to register for free"
  else
    log "→ Next: say \"list subnets\" to browse, or \"install skill for subnet #1\" to start"
  fi
  echo ""
}

# ── 4. Update Checker ────────────────────────────

check_updates() {
  log "Checking for updates..."

  # Check awp-skill version
  local remote_skill_version local_skill_version
  local_skill_version=$(grep "Skill version:" "$SCRIPT_DIR/../SKILL.md" 2>/dev/null | head -1 | sed 's/.*: //' | tr -d '*' | tr -d ' ')

  remote_skill_version=$(curl -s "https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md" 2>/dev/null | head -30 | grep "Skill version:" | sed 's/.*: //' | tr -d '*' | tr -d ' ')

  if [[ -n "$remote_skill_version" && -n "$local_skill_version" && "$remote_skill_version" != "$local_skill_version" ]]; then
    log "┌─────────────────────────────────────────────┐"
    log "│  AWP Skill update available!                 │"
    log "│  Local:  $local_skill_version"
    log "│  Remote: $remote_skill_version"
    log "│                                              │"
    log "│  Run: skill install $SKILL_REPO"
    log "└─────────────────────────────────────────────┘"

    # Auto-update
    log "Auto-updating awp-skill..."
    if skill install "$SKILL_REPO" 2>/dev/null; then
      log "awp-skill updated to $remote_skill_version ✓"
    else
      warn "Auto-update failed. Please update manually."
    fi
  else
    log "awp-skill $local_skill_version — up to date ✓"
  fi

  # Check awp-wallet version
  if which awp-wallet >/dev/null 2>&1; then
    local remote_wallet_version
    remote_wallet_version=$(curl -s "https://raw.githubusercontent.com/awp-core/awp-wallet/main/SKILL.md" 2>/dev/null | head -30 | grep -i "version:" | head -1 | sed 's/.*: //' | tr -d '*' | tr -d ' ')

    if [[ -n "$remote_wallet_version" ]]; then
      log "awp-wallet remote: $remote_wallet_version"

      # Try auto-update
      if skill install awp-wallet 2>/dev/null || skill install "$WALLET_REPO" 2>/dev/null; then
        log "awp-wallet checked/updated ✓"
      fi
    fi
  fi
}

# ── Main Loop ────────────────────────────────────

main() {
  echo ""
  echo "╭──────────────╮"
  echo "│              │"
  echo "│  >       <   │"
  echo "│      ~       │"
  echo "│              │"
  echo "╰──────────────╯"
  echo ""
  echo "AWP Daemon starting..."
  echo ""

  # Phase 1: Dependencies
  log "Phase 1: Checking dependencies..."
  ensure_wallet_installed || { err "Cannot continue without awp-wallet"; exit 1; }

  # Phase 2: Wallet initialization
  log "Phase 2: Checking wallet..."
  ensure_wallet_initialized || { err "Cannot continue without wallet"; exit 1; }

  # Phase 3: Status and notification
  log "Phase 3: Checking status..."
  check_and_notify

  # Phase 4: Update check
  log "Phase 4: Checking updates..."
  check_updates

  # Phase 5: Continuous monitoring
  log ""
  log "Daemon running. Checking every ${CHECK_INTERVAL}s for updates and status changes."
  log "Press Ctrl+C to stop."
  echo ""

  local last_registered="unknown"

  while true; do
    sleep "$CHECK_INTERVAL"

    # Re-check registration status
    local check is_registered
    check=$(curl -s "$API_BASE/address/$WALLET_ADDR/check" 2>/dev/null) || true
    is_registered=$(echo "$check" | jq -r '.isRegistered // false' 2>/dev/null)

    # Notify on status change
    if [[ "$is_registered" != "$last_registered" && "$last_registered" != "unknown" ]]; then
      if [[ "$is_registered" == "true" ]]; then
        log "🎉 Registration detected! You are now registered on AWP."
        check_and_notify
      fi
    fi
    last_registered="$is_registered"

    # Periodic update check
    check_updates 2>/dev/null || true
  done
}

# ── Run ──────────────────────────────────────────

main "$@"
