#!/usr/bin/env python3
"""Switch worknet — move all allocated stake from one worknet to another.
Queries current allocations automatically and reallocates the full amount.
  1. Query staking.getAllocations to find allocations on --from-worknet
  2. Reallocate each allocation to --to-worknet (preserving agent)

Optionally specify --agent to only move allocations for a specific agent.
Optionally specify --amount to move a partial amount instead of all.
Requires ETH for gas.
"""

from awp_lib import *


def main() -> None:
    parser = base_parser("Switch worknet: move allocations from one worknet to another")
    parser.add_argument("--from-worknet", required=True, help="Source worknet ID")
    parser.add_argument("--to-worknet", required=True, help="Destination worknet ID")
    parser.add_argument(
        "--agent",
        default="",
        help="Specific agent address (default: all agents on source worknet)",
    )
    parser.add_argument(
        "--amount", default="", help="AWP amount to move (default: all)"
    )
    args = parser.parse_args()

    token: str = args.token
    from_wid: int = validate_positive_int(args.from_worknet, "from-worknet")
    from_wid = expand_worknet_id(from_wid)
    to_wid: int = validate_positive_int(args.to_worknet, "to-worknet")
    to_wid = expand_worknet_id(to_wid)

    if from_wid == to_wid:
        die("--from-worknet and --to-worknet must be different")

    specific_agent: str = ""
    if args.agent:
        specific_agent = validate_address(args.agent, "agent")

    partial_amount_wei: int | None = None
    if args.amount:
        validate_positive_number(args.amount, "amount")
        partial_amount_wei = to_wei(args.amount)

    # ── Fetch wallet and registry ──
    wallet_addr = get_wallet_address()
    registry = get_registry()
    awp_allocator = require_contract(registry, "awpAllocator")

    # ── Query allocations ──
    step("queryAllocations")
    allocations = rpc("staking.getAllocations", {"address": wallet_addr})
    if not isinstance(allocations, list):
        if isinstance(allocations, dict):
            for key in ("items", "data", "allocations"):
                if isinstance(allocations.get(key), list):
                    allocations = allocations[key]
                    break
            else:
                allocations = []
        else:
            allocations = []

    # Filter to source worknet
    matching: list[dict] = []
    for alloc in allocations:
        wid_raw = alloc.get("worknetId") or alloc.get("worknet_id")
        agent = alloc.get("agent", "")
        try:
            amount = int(alloc.get("amount", "0"))
            wid_int = int(wid_raw) if wid_raw is not None else None
        except (ValueError, TypeError):
            continue
        if wid_int is None or amount == 0:
            continue
        if wid_int != from_wid:
            continue
        if specific_agent and agent.lower() != specific_agent.lower():
            continue
        matching.append(alloc)

    if not matching:
        die(
            f"No allocations found on worknet {from_wid}"
            + (f" for agent {specific_agent}" if specific_agent else "")
        )

    # ── Reallocate each matching allocation ──
    moved = 0
    for alloc in matching:
        agent = alloc.get("agent", "")
        amount_raw = int(alloc.get("amount", "0"))
        move_amount = (
            partial_amount_wei if partial_amount_wei is not None else amount_raw
        )

        if move_amount > amount_raw:
            die(
                f"Requested amount exceeds allocation for agent {agent}: "
                f"have {amount_raw / 10**18} AWP, requested {move_amount / 10**18} AWP"
            )

        # reallocate(address,address,uint256,address,uint256,uint256) selector = 0xd5d5278d
        calldata = encode_calldata(
            "0xd5d5278d",
            pad_address(wallet_addr),
            pad_address(agent),
            pad_uint256(from_wid),
            pad_address(agent),
            pad_uint256(to_wid),
            pad_uint256(move_amount),
        )

        step(
            "reallocate",
            agent=agent,
            fromWorknet=from_wid,
            toWorknet=to_wid,
            amount=f"{move_amount / 10**18} AWP",
        )
        result = wallet_send(token, awp_allocator, calldata)
        info(f"Reallocated agent={agent[:10]}... : {result}")
        moved += 1

    import json

    print(
        json.dumps(
            {
                "status": "switched",
                "moved": moved,
                "fromWorknet": from_wid,
                "toWorknet": to_wid,
            }
        )
    )


if __name__ == "__main__":
    main()
