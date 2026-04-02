#!/usr/bin/env python3
"""One-click registerAndStake: complete register + deposit + allocate in a single transaction
Handles approve (to AWP_REGISTRY) + registerAndStake in two steps.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("One-click registerAndStake: register + deposit + allocate")
    parser.add_argument("--amount", required=True, help="Deposit AWP amount (human readable)")
    parser.add_argument("--lock-days", required=True, help="Lock duration in days")
    parser.add_argument("--agent", required=True, help="Agent address")
    parser.add_argument("--subnet", required=True, help="Worknet ID")
    parser.add_argument("--allocate-amount", required=True, help="Allocate AWP amount (human readable)")
    args = parser.parse_args()

    token: str = args.token
    amount: str = args.amount
    lock_days: str = args.lock_days
    agent: str = args.agent
    subnet: str = args.subnet
    allocate_amount: str = args.allocate_amount

    # Validate numeric inputs
    validate_positive_number(amount, "amount")
    validate_positive_number(lock_days, "lock-days")
    validate_positive_number(allocate_amount, "allocate-amount")
    validate_address(agent, "agent")
    subnet_id: int = validate_positive_int(subnet, "subnet")

    # Pre-check: fetch wallet address
    wallet_addr = get_wallet_address()

    # Fetch contract registry
    registry = get_registry()
    awp_token = require_contract(registry, "awpToken")
    awp_registry = require_contract(registry, "awpRegistry")

    # Unit conversion
    amount_wei = to_wei(amount)
    lock_seconds = days_to_seconds(lock_days)
    allocate_wei = to_wei(allocate_amount)

    # Allocate amount must not exceed deposit amount
    if allocate_wei > amount_wei:
        die(f"allocate-amount ({allocate_amount} AWP) exceeds deposit amount ({amount} AWP)")

    # Step 1: Approve AWP to AWP_REGISTRY (note: target is AWP_REGISTRY, NOT StakeNFT)
    step("approve", spender=awp_registry,
         note="Approve target is AWP_REGISTRY, NOT StakeNFT",
         amount=f"{amount} AWP")
    wallet_approve(token, awp_token, awp_registry, amount)

    # Step 2: registerAndStake(uint256 depositAmount, uint64 lockDuration,
    #          address agent, uint256 subnetId, uint256 allocateAmount)
    # selector = 0x34426564
    calldata = encode_calldata(
        "0x34426564",
        pad_uint256(amount_wei),
        pad_uint256(lock_seconds),
        pad_address(agent),
        pad_uint256(subnet_id),
        pad_uint256(allocate_wei),
    )

    step("registerAndStake", to=awp_registry,
         deposit_amount_wei=str(amount_wei), lock_seconds=lock_seconds,
         agent=agent, subnet=subnet_id, allocate_amount_wei=str(allocate_wei))
    result = wallet_send(token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
