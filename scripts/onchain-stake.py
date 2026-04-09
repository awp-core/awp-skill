#!/usr/bin/env python3
"""On-chain stake AWP — combines deposit + allocate in one script.
Performs three steps:
  1. Approve AWP token spend to veAWP
  2. Deposit AWP into veAWP (creates locked position)
  3. Allocate the deposited stake to agent+worknet (starts earning rewards)

If --agent and --worknet are omitted, only deposit is performed (no allocate).
Requires ETH for gas.
"""

import json

from awp_lib import *


def main() -> None:
    parser = base_parser("Stake AWP: deposit + allocate in one step")
    parser.add_argument("--amount", required=True, help="AWP amount (human-readable)")
    parser.add_argument(
        "--lock-days", required=True, help="Lock duration in days (must be > 0)"
    )
    parser.add_argument(
        "--agent",
        default="",
        help="Agent address to allocate to (omit to skip allocate)",
    )
    parser.add_argument(
        "--worknet",
        default="",
        help="Worknet ID to allocate to (omit to skip allocate)",
    )
    args = parser.parse_args()

    token: str = args.token
    amount: str = args.amount
    lock_days: str = args.lock_days

    # Validate numeric inputs
    validate_positive_number(amount, "amount")
    validate_positive_number(lock_days, "lock-days")

    # Determine if allocate step is requested
    do_allocate = bool(args.agent and args.worknet)
    if bool(args.agent) != bool(args.worknet):
        die(
            "--agent and --worknet must both be provided for allocation, or both omitted for deposit-only"
        )

    agent_addr: str = ""
    worknet_id: int = 0
    if do_allocate:
        agent_addr = validate_address(args.agent, "agent")
        worknet_id = validate_positive_int(args.worknet, "worknet")
        worknet_id = expand_worknet_id(worknet_id)

    # Get contract registry
    registry = get_registry()
    awp_token = require_contract(registry, "awpToken")
    ve_awp = require_contract(registry, "veAWP")

    # 前置条件：确认已注册（未注册时质押没有意义）
    step("precondition_check")
    wallet_addr = get_wallet_address()
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict) and not check.get("isRegistered", False):
        die(
            "Not registered on AWP. Register first (free, gasless): "
            "python3 scripts/relay-start.py --token $TOKEN --mode principal"
        )

    # Unit conversion
    amount_wei = to_wei(amount)
    lock_seconds = days_to_seconds(lock_days)

    # uint64 overflow guard (lockDuration parameter type is uint64)
    if lock_seconds > 2**64 - 1:
        die(
            f"lock-days too large: {lock_days} days ({lock_seconds}s) exceeds uint64 max"
        )

    # ── Step 1: Approve AWP to veAWP ──
    step("approve", spender=ve_awp, amount=f"{amount} AWP")
    wallet_approve(token, awp_token, ve_awp, amount)

    # ── Step 2: Deposit ──
    # deposit(uint256,uint64) selector = 0x7d552ea6
    deposit_calldata = encode_calldata(
        "0x7d552ea6",
        pad_uint256(amount_wei),
        pad_uint256(lock_seconds),
    )

    step("deposit", amount_wei=str(amount_wei), lock_seconds=lock_seconds)
    deposit_result = wallet_send(token, ve_awp, deposit_calldata)
    info(f"Deposit confirmed: {deposit_result}")

    if not do_allocate:
        print(
            json.dumps(
                {
                    "status": "deposited",
                    "result": deposit_result,
                    "nextAction": "allocate",
                    "nextCommand": f"python3 scripts/onchain-allocate.py --token $TOKEN --agent {wallet_addr} --worknet <WORKNET_ID> --amount {amount}",
                }
            )
        )
        info(
            "Deposit complete (no allocate). To start earning, allocate to an agent+worknet."
        )
        return

    # ── Step 3: Allocate to agent+worknet ──
    awp_allocator = require_contract(registry, "awpAllocator")

    # allocate(address,address,uint256,uint256) selector = 0xd035a9a7
    allocate_calldata = encode_calldata(
        "0xd035a9a7",
        pad_address(wallet_addr),
        pad_address(agent_addr),
        pad_uint256(worknet_id),
        pad_uint256(amount_wei),
    )

    step(
        "allocate",
        staker=wallet_addr,
        agent=agent_addr,
        worknet=worknet_id,
        amount=f"{amount} AWP",
    )
    allocate_result = wallet_send(token, awp_allocator, allocate_calldata)
    print(
        json.dumps(
            {
                "status": "staked_and_allocated",
                "result": allocate_result,
                "nextAction": "earning",
                "nextCommand": f"python3 scripts/query-status.py --address {wallet_addr}",
            }
        )
    )
    info(
        f"Staked and allocated {amount} AWP to agent {agent_addr} on worknet {worknet_id}. Now earning rewards."
    )


if __name__ == "__main__":
    main()
