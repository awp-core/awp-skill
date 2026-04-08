#!/usr/bin/env python3
"""On-chain deposit AWP to veAWP (V2)
Handles the approve + deposit two-step operation.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain deposit AWP to veAWP (V2)")
    parser.add_argument("--amount", required=True, help="AWP amount (human-readable)")
    parser.add_argument("--lock-days", required=True, help="Lock duration in days (must be > 0)")
    args = parser.parse_args()

    token: str = args.token
    amount: str = args.amount
    lock_days: str = args.lock_days

    # Validate numeric inputs
    validate_positive_number(amount, "amount")
    validate_positive_number(lock_days, "lock-days")

    # Get contract registry
    registry = get_registry()
    awp_token = require_contract(registry, "awpToken")
    ve_awp = require_contract(registry, "veAWP")

    # Unit conversion
    amount_wei = to_wei(amount)
    lock_seconds = days_to_seconds(lock_days)

    # uint64 overflow guard (lockDuration parameter type is uint64)
    if lock_seconds > 2**64 - 1:
        die(f"lock-days too large: {lock_days} days ({lock_seconds}s) exceeds uint64 max")

    # Step 1: approve AWP to veAWP
    step("approve", spender=ve_awp, amount=f"{amount} AWP")
    wallet_approve(token, awp_token, ve_awp, amount)

    # Step 2: deposit
    # deposit(uint256,uint64) selector = 0x7d552ea6
    calldata = encode_calldata(
        "0x7d552ea6",
        pad_uint256(amount_wei),
        pad_uint256(lock_seconds),
    )

    step("deposit", amount_wei=str(amount_wei), lock_seconds=lock_seconds)
    result = wallet_send(token, ve_awp, calldata)
    print(result)
    # Remind: deposit alone does not earn rewards — user must allocate to agent+worknet
    info("Deposit complete. NEXT STEP: allocate this stake to an agent+worknet to start earning rewards. "
         "Run: python3 scripts/onchain-allocate.py --token $TOKEN --agent <addr> --worknet <id> --amount <amount>")


if __name__ == "__main__":
    main()
