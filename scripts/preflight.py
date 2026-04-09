#!/usr/bin/env python3
"""Preflight state machine — diagnose current state and return exactly what to do next.
No wallet token needed. Read-only. Safe to run at any time.

The LLM should run this FIRST, then follow the nextCommand field.
If any step fails, run this again to get back on track.

Returns JSON with:
  - state: complete snapshot of wallet/registration/staking/allocation status
  - progress: "N/4" progress indicator
  - nextAction: machine-readable action identifier
  - nextCommand: exact shell command to run next
  - message: human-readable explanation

Usage:
  python3 scripts/preflight.py
  python3 scripts/preflight.py --address 0x...  (skip wallet detection, read-only)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Does not use awp_lib's die() — preflight must never crash, always returns JSON
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
API_BASE = "https://api.awp.sh/v2"
_USER_AGENT = "awp-skill/1.4 (+https://github.com/awp-core/awp-skill)"
_ZERO_ADDR = "0x0000000000000000000000000000000000000000"


def _find_wallet_bin() -> str | None:
    """Find the awp-wallet binary, return None if not found."""
    found = shutil.which("awp-wallet")
    if found:
        return found
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "awp-wallet",
        home / ".npm-global" / "bin" / "awp-wallet",
        home / ".yarn" / "bin" / "awp-wallet",
        Path("/usr/local/bin/awp-wallet"),
        Path("/usr/bin/awp-wallet"),
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    return None


def _try_wallet_cmd(wallet_bin: str, args: list[str]) -> tuple[bool, str]:
    """Run a wallet command, return (success, stdout). Never raises."""
    try:
        result = subprocess.run(
            [wallet_bin] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return False, ""


def _rpc(method: str, params: dict | None = None) -> dict | list | None:
    """Call API, return None on error."""
    body = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    ).encode()
    req = urllib.request.Request(
        API_BASE,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if "error" in data:
                return None
            return data.get("result")
    except Exception:
        return None


def _output(
    state: dict,
    progress: str,
    next_action: str,
    next_command: str,
    message: str,
    **extra: object,
) -> None:
    """Output structured JSON and exit (terminal semantics like die(), prevents double output)."""
    result: dict = {
        "state": state,
        "progress": progress,
        "nextAction": next_action,
        "nextCommand": next_command,
        "message": message,
    }
    result.update(extra)
    print(json.dumps(result, indent=2))
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preflight state check — diagnose current state, return next action"
    )
    parser.add_argument(
        "--address",
        default="",
        help="Skip wallet detection, query this address directly (read-only mode)",
    )
    args = parser.parse_args()

    state: dict = {
        "walletInstalled": False,
        "walletInitialized": False,
        "walletUnlocked": False,
        "walletAddress": None,
        "registered": None,
        "boundTo": None,
        "recipient": None,
        "hasStake": False,
        "totalStaked": "0",
        "hasAllocations": False,
        "totalAllocated": "0",
        "freeWorknetsAvailable": 0,
    }

    # ── Phase 1: Wallet detection ──
    if args.address:
        if not ADDR_RE.match(args.address):
            print(json.dumps({"error": f"Invalid --address format: {args.address}"}))
            sys.exit(1)
        state["walletAddress"] = args.address
        state["walletInstalled"] = True
        state["walletInitialized"] = True
        state["walletUnlocked"] = True
    else:
        wallet_bin = _find_wallet_bin()
        if not wallet_bin:
            _output(
                state,
                "0/4",
                "install_wallet",
                "skill install https://github.com/awp-core/awp-wallet",
                "awp-wallet not installed. Install the wallet CLI first.",
            )
            return

        state["walletInstalled"] = True

        # Try receive — if successful, wallet is initialized and unlocked
        ok, stdout = _try_wallet_cmd(wallet_bin, ["receive"])
        if ok:
            try:
                addr = json.loads(stdout).get("eoaAddress", "")
                if ADDR_RE.match(addr):
                    state["walletInitialized"] = True
                    state["walletUnlocked"] = True
                    state["walletAddress"] = addr
            except (json.JSONDecodeError, AttributeError):
                pass

        if not state["walletAddress"]:
            # Check if wallet directory exists to determine initialization state
            wallet_dir = Path.home() / ".awp-wallet"
            try:
                is_initialized = wallet_dir.exists() and any(wallet_dir.iterdir())
            except (PermissionError, OSError):
                # Directory unreadable — conservatively assume initialized (let unlock attempt)
                is_initialized = wallet_dir.exists()
            if is_initialized:
                state["walletInitialized"] = True
                _output(
                    state,
                    "1/4",
                    "unlock_wallet",
                    "TOKEN=$(awp-wallet unlock --duration 3600 --scope transfer | python3 -c \"import sys,json; print(json.load(sys.stdin)['token'])\")",
                    "Wallet installed and initialized but locked. Unlock to continue.",
                )
                return
            else:
                _output(
                    state,
                    "0/4",
                    "init_wallet",
                    "awp-wallet init",
                    "Wallet CLI installed but not initialized. Run init to create a new wallet (no password needed).",
                )
                return

    addr = state["walletAddress"]

    # ── Phase 2: Check registration status ──
    check = _rpc("address.check", {"address": addr})
    if isinstance(check, dict):
        state["registered"] = bool(check.get("isRegistered", False))
        bound_to = check.get("boundTo", "") or ""
        state["boundTo"] = (
            bound_to if bound_to not in ("", "null", _ZERO_ADDR) else None
        )
        state["recipient"] = check.get("recipient", "") or None
    else:
        # API unreachable — report but don't block
        state["registered"] = None

    if state["registered"] is False:
        _output(
            state,
            "1/4",
            "register",
            "python3 scripts/relay-start.py --token $TOKEN --mode principal",
            "Wallet ready but not registered. Choose Solo (A) or Delegated (B) mode. Free, gasless.",
            options={
                "A": {
                    "label": "Solo Mining — register as independent agent",
                    "command": "python3 scripts/relay-start.py --token $TOKEN --mode principal",
                },
                "B": {
                    "label": "Delegated Mining — bind to your existing wallet",
                    "command": "python3 scripts/relay-start.py --token $TOKEN --mode agent --target <OWNER_ADDRESS>",
                },
            },
        )
        return

    if state["registered"] is None:
        # API unreachable
        _output(
            state,
            "1/4",
            "retry_preflight",
            f"python3 scripts/preflight.py --address {addr}",
            "Could not reach AWP API to check registration. Retry when network is available.",
        )
        return

    # ── Phase 3: Check staking and allocations ──
    balance = _rpc("staking.getBalance", {"address": addr})
    if isinstance(balance, dict):
        try:
            # Parse both fields together to avoid inconsistent state if only one succeeds
            total_staked = int(balance.get("totalStaked", "0"))
            total_allocated = int(balance.get("totalAllocated", "0"))
        except (ValueError, TypeError):
            total_staked = 0
            total_allocated = 0
        state["hasStake"] = total_staked > 0
        state["totalStaked"] = str(total_staked)
        state["hasAllocations"] = total_allocated > 0
        state["totalAllocated"] = str(total_allocated)

    # ── Phase 4: Check available worknets ──
    worknets_resp = _rpc("subnets.list", {"status": "Active", "limit": 20})
    free_worknets: list[dict] = []
    raw_list: list = []
    if isinstance(worknets_resp, list):
        raw_list = worknets_resp
    elif isinstance(worknets_resp, dict):
        for key in ("items", "data", "subnets"):
            if isinstance(worknets_resp.get(key), list):
                raw_list = worknets_resp[key]
                break

    for w in raw_list:
        min_stake = w.get("minStake") or w.get("min_stake", "0")
        try:
            if int(min_stake) == 0:
                free_worknets.append(
                    {
                        "worknetId": w.get("worknetId") or w.get("id"),
                        "name": w.get("name", ""),
                        "hasSkill": bool(w.get("skillsURI") or w.get("skills_uri")),
                    }
                )
        except (ValueError, TypeError):
            pass

    state["freeWorknetsAvailable"] = len(free_worknets)

    # ── Decision: what's the next step? ──

    # Validate worknetId is numeric before embedding in nextCommand (prevent API injection)
    def _safe_wid(wid: object) -> str:
        s = str(wid)
        if re.match(r"^[0-9]+$", s):
            return s
        return "<WORKNET_ID>"

    # Registered, no stake, no allocations → pick worknet or wait
    if not state["hasStake"] and not state["hasAllocations"]:
        if free_worknets:
            safe_id = _safe_wid(free_worknets[0]["worknetId"])
            _output(
                state,
                "2/4",
                "pick_worknet",
                f"python3 scripts/query-worknet.py --worknet {safe_id}",
                f"Registered. {len(free_worknets)} free worknet(s) available — no staking needed to join.",
                freeWorknets=free_worknets,
            )
        else:
            _output(
                state,
                "2/4",
                "wait_for_worknets",
                f"python3 scripts/query-status.py --address {addr}",
                "Registered but no free worknets available yet. This is normal on new chains.",
            )
    elif state["hasStake"] and not state["hasAllocations"]:
        # Has stake but no allocations → needs allocate
        _output(
            state,
            "3/4",
            "allocate",
            f"python3 scripts/relay-allocate.py --token $TOKEN --mode allocate --agent {addr} --worknet <WORKNET_ID> --amount <AMOUNT>",
            "Staked but not allocated — not earning rewards. Allocate to an agent+worknet to start earning.",
        )
    elif not state["hasStake"] and state["hasAllocations"]:
        # Has allocations but no stake — inconsistent state (stake may have expired/withdrawn)
        _output(
            state,
            "3/4",
            "check_status",
            f"python3 scripts/query-status.py --address {addr}",
            "Has allocations but no active stake — run query-status for details. May need to re-stake or deallocate.",
        )
    else:
        # hasStake=True AND hasAllocations=True → all set
        _output(
            state,
            "4/4",
            "ready",
            f"python3 scripts/query-status.py --address {addr}",
            "All set! Registered, staked, and allocated. Earning rewards.",
        )


if __name__ == "__main__":
    main()
