#!/usr/bin/env python3
"""Read-only AWP status overview — no wallet token needed, just an address.
Queries all key information in one shot:
  - Registration status (address.check)
  - Balance summary (staking.getBalance)
  - Staking positions (staking.getPositions)
  - Allocations (staking.getAllocations)
  - Delegates (users.getDelegates)

Outputs structured JSON for easy LLM consumption.
Does NOT require ETH or awp-wallet session token.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

# Add scripts dir to path for awp_lib import
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from awp_lib import (
    ADDR_RE,
    die,
    get_wallet_address,
    rpc,
    step,
)

_CHAIN_NAMES: dict[int, str] = {
    1: "Ethereum",
    56: "BSC",
    8453: "Base",
    42161: "Arbitrum",
}


def _worknet_chain(worknet_id: int) -> str:
    """Derive chain name from worknetId format (chainId * 100_000_000 + localId)."""
    chain_id = worknet_id // 100_000_000
    return _CHAIN_NAMES.get(chain_id, f"chain:{chain_id}")


def wei_to_awp(wei_str: str | int) -> str:
    """Convert wei string to human-readable AWP amount."""
    try:
        return f"{int(wei_str) / 10**18:,.4f}"
    except (ValueError, TypeError):
        return str(wei_str)


def main() -> None:
    parser = argparse.ArgumentParser(description="AWP status overview (read-only)")
    parser.add_argument(
        "--address", default="", help="Wallet address to query (omit to use awp-wallet)"
    )
    parser.add_argument(
        "--token",
        default="",
        help="awp-wallet session token (only needed if --address is omitted)",
    )
    args = parser.parse_args()

    # Determine address
    if args.address:
        if not ADDR_RE.match(args.address):
            die(f"Invalid address format: {args.address}")
        addr = args.address
    elif args.token:
        addr = get_wallet_address()
    else:
        die("Provide --address or --token (to read address from awp-wallet)")
        return

    step("queryStatus", address=addr)

    # ── Batch all queries ──
    check = rpc("address.check", {"address": addr})
    balance = rpc("staking.getBalance", {"address": addr})
    positions = rpc("staking.getPositions", {"address": addr})
    allocations = rpc("staking.getAllocations", {"address": addr})

    # ── Build output ──
    output: dict = {"address": addr}

    # Registration
    if isinstance(check, dict):
        output["registered"] = bool(check.get("isRegistered", False))
        output["boundTo"] = check.get("boundTo", "") or ""
        output["recipient"] = check.get("recipient", "") or ""
    else:
        output["registered"] = None

    # Balance
    if isinstance(balance, dict):
        total_staked = balance.get("totalStaked", "0")
        total_allocated = balance.get("totalAllocated", "0")
        unallocated = balance.get("unallocated", "0")
        output["balance"] = {
            "totalStaked": wei_to_awp(total_staked),
            "totalAllocated": wei_to_awp(total_allocated),
            "unallocated": wei_to_awp(unallocated),
            "totalStaked_wei": str(total_staked),
            "totalAllocated_wei": str(total_allocated),
            "unallocated_wei": str(unallocated),
        }
    else:
        output["balance"] = None

    # Positions — handle both list and paginated dict responses
    now = int(time.time())
    if not isinstance(positions, list):
        if isinstance(positions, dict):
            for key in ("items", "data", "positions"):
                if isinstance(positions.get(key), list):
                    positions = positions[key]
                    break
            else:
                positions = []
        else:
            positions = []
    if isinstance(positions, list):
        pos_list: list[dict] = []
        for p in positions:
            tok = p.get("tokenId") or p.get("token_id")
            amount = p.get("amount", "0")
            lock_end = (
                p.get("lockEndTime") or p.get("lock_end_time") or p.get("lockEnd", 0)
            )
            created = p.get("createdAt") or p.get("created_at", 0)

            try:
                if tok is None or int(amount) == 0:
                    continue
            except (ValueError, TypeError):
                continue

            try:
                lock_end_int = int(lock_end)
            except (ValueError, TypeError):
                lock_end_int = 0

            expired = lock_end_int > 0 and lock_end_int <= now
            remaining_days = (
                max(0, round((lock_end_int - now) / 86400, 1))
                if lock_end_int > 0
                else 0
            )

            pos_list.append(
                {
                    "tokenId": int(tok),
                    "amount": wei_to_awp(amount),
                    "amount_wei": str(amount),
                    "lockEnd": lock_end_int,
                    "expired": expired,
                    "remainingDays": remaining_days,
                    "createdAt": int(created) if created else 0,
                }
            )
        output["positions"] = pos_list
    else:
        output["positions"] = []

    # Allocations
    def _parse_allocations(raw_list: list) -> list[dict]:
        result: list[dict] = []
        for a in raw_list:
            agent = a.get("agent", "")
            wid = a.get("worknetId") or a.get("worknet_id", "")
            amount = a.get("amount", "0")
            try:
                if int(amount) == 0:
                    continue
            except (ValueError, TypeError):
                continue
            wid_int = int(wid) if wid else 0
            result.append(
                {
                    "agent": agent,
                    "worknetId": wid_int,
                    "chain": _worknet_chain(wid_int) if wid_int else "?",
                    "amount": wei_to_awp(amount),
                    "amount_wei": str(amount),
                }
            )
        return result

    if isinstance(allocations, list):
        output["allocations"] = _parse_allocations(allocations)
    elif isinstance(allocations, dict):
        items = allocations.get("items") or allocations.get("data") or []
        output["allocations"] = _parse_allocations(items)
    else:
        output["allocations"] = []

    # ── Summary hints for LLM ──
    hints: list[str] = []
    next_action: str = "ready"
    next_command: str = ""

    if output.get("registered") is False:
        hints.append("Not registered. Run: relay-start.py or relay-onboard.py")
        next_action = "register"
        next_command = "python3 scripts/preflight.py"
    elif (
        output["balance"]
        and int(output["balance"]["totalStaked_wei"]) > 0
        and not output["allocations"]
    ):
        hints.append(
            "Has staked AWP but no allocations — not earning rewards. Allocate to an agent+worknet."
        )
        next_action = "allocate"
        next_command = f"python3 scripts/relay-allocate.py --token $TOKEN --mode allocate --agent {addr} --worknet <WORKNET_ID> --amount <AMOUNT>"
    elif output.get("registered") is True and (
        not output["balance"] or int(output["balance"]["totalStaked_wei"]) == 0
    ):
        next_action = "pick_worknet"
        next_command = f"python3 scripts/preflight.py --address {addr}"

    if output["positions"]:
        expired_count = sum(1 for p in output["positions"] if p["expired"])
        if expired_count > 0:
            hints.append(
                f"{expired_count} expired position(s) — can withdraw. Run: onchain-unstake.py"
            )
    if output["allocations"] and output["positions"]:
        all_expired = all(p["expired"] for p in output["positions"])
        if all_expired and output["allocations"]:
            hints.append(
                "All positions expired but still allocated — deallocate first, then withdraw."
            )
            next_action = "deallocate_then_withdraw"
            next_command = "python3 scripts/onchain-unstake.py --token $TOKEN"

    if hints:
        output["hints"] = hints
    output["nextAction"] = next_action
    output["nextCommand"] = (
        next_command or f"python3 scripts/query-status.py --address {addr}"
    )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
