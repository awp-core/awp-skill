#!/usr/bin/env python3
"""On-chain unstake — deallocate all allocations then withdraw expired positions.
Combines the multi-step exit flow into one script:
  1. Query all allocations via staking.getAllocations
  2. Deallocate each allocation (deallocateAll per agent+worknet)
  3. Query all positions via staking.getPositions
  4. Withdraw each expired position (remainingTime == 0)

If --position is given, only withdraw that specific position (still deallocates all first).
Requires ETH for gas.
"""

from awp_lib import *


def main() -> None:
    parser = base_parser("Unstake AWP: deallocate all + withdraw expired positions")
    parser.add_argument(
        "--position",
        default="",
        help="Specific position ID to withdraw (default: all expired)",
    )
    args = parser.parse_args()

    token: str = args.token
    specific_position: int | None = None
    if args.position:
        specific_position = validate_positive_int(args.position, "position")

    # ── Fetch wallet and registry ──
    wallet_addr = get_wallet_address()
    registry = get_registry()
    awp_allocator = require_contract(registry, "awpAllocator")
    ve_awp = require_contract(registry, "veAWP")

    # ── Step 1: Query current allocations ──
    step("queryAllocations")
    allocations = rpc("staking.getAllocations", {"address": wallet_addr})
    if not isinstance(allocations, list):
        # Paginated response
        if isinstance(allocations, dict):
            for key in ("items", "data", "allocations"):
                if isinstance(allocations.get(key), list):
                    allocations = allocations[key]
                    break
            else:
                allocations = []
        else:
            allocations = []

    # ── Step 2: Deallocate all allocations ──
    deallocated = 0
    if allocations:
        info(f"Found {len(allocations)} allocation(s) to deallocate")
        for alloc in allocations:
            agent = alloc.get("agent", "")
            worknet_id_raw = alloc.get("worknetId") or alloc.get("worknet_id")
            amount_raw = alloc.get("amount", "0")

            try:
                if not agent or not worknet_id_raw or int(amount_raw) == 0:
                    continue
                worknet_id = int(worknet_id_raw)
            except (ValueError, TypeError):
                continue
            # 验证 API 返回的 agent 地址格式（防止短地址导致 pad_address 错误填充）
            if not ADDR_RE.match(agent):
                info(f"Skipping allocation with invalid agent address: {agent}")
                continue
            step("deallocateAll", agent=agent, worknet=worknet_id)

            # deallocateAll(address,address,uint256) selector = 0x586ac6b3
            calldata = encode_calldata(
                "0x586ac6b3",
                pad_address(wallet_addr),
                pad_address(agent),
                pad_uint256(worknet_id),
            )
            result = wallet_send(token, awp_allocator, calldata)
            deallocated += 1
            info(
                f"Deallocated from agent={agent[:10]}... worknet={worknet_id}: {result}"
            )
    else:
        info("No allocations found — skipping deallocate step")

    # ── Step 3: Query positions ──
    step("queryPositions")
    positions = rpc("staking.getPositions", {"address": wallet_addr})
    if not isinstance(positions, list):
        if isinstance(positions, dict):
            for key in ("items", "data", "positions"):
                if isinstance(positions.get(key), list):
                    positions = positions[key]
                    break
            else:
                die("Could not fetch positions")
        else:
            die("Could not fetch positions")

    # ── Step 4: Withdraw expired positions ──
    withdrawn = 0
    skipped = 0
    for p in positions:
        tok = p.get("tokenId") or p.get("token_id")
        amount = p.get("amount", "0")
        try:
            if tok is None or int(amount) == 0:
                continue
            position_id = int(tok)
        except (ValueError, TypeError):
            continue

        # If specific position requested, skip others
        if specific_position is not None and position_id != specific_position:
            continue

        # Check remainingTime on-chain — selector = 0x0c64a7f2
        position_padded = pad_uint256(position_id)
        remaining_hex = rpc_call(ve_awp, encode_calldata("0x0c64a7f2", position_padded))

        if not remaining_hex or remaining_hex in ("0x", "null"):
            info(f"Position #{position_id}: could not read remainingTime, skipping")
            skipped += 1
            continue

        remaining = hex_to_int(remaining_hex)
        if remaining != 0:
            days_left = round(remaining / 86400, 1)
            info(
                f"Position #{position_id}: still locked ({days_left} days remaining), skipping"
            )
            skipped += 1
            continue

        # Withdraw — selector = 0x2e1a7d4d
        step("withdraw", position=position_id)
        calldata = encode_calldata("0x2e1a7d4d", position_padded)
        result = wallet_send(token, ve_awp, calldata)
        info(f"Withdrawn position #{position_id}: {result}")
        withdrawn += 1

    # ── Summary ──
    import json

    summary: dict = {
        "withdrawn": withdrawn,
        "skipped_locked": skipped,
        "deallocated": deallocated,
        "nextAction": "check_status",
        "nextCommand": f"python3 scripts/query-status.py --address {wallet_addr}",
    }
    if withdrawn == 0 and skipped > 0:
        info(f"No positions withdrawn — {skipped} position(s) still locked")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
