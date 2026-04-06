#!/usr/bin/env python3
"""On-chain partial withdrawal — withdraw a specific AWP amount from an expired veAWP position
partialWithdraw(uint256 tokenId, uint128 amount)
Only callable when the lock has expired (remainingTime == 0). Requires ETH for gas.
"""
from awp_lib import *


def main() -> None:
    # ── Argument parsing ──
    parser = base_parser("Partial withdraw from expired veAWP position")
    parser.add_argument("--position", required=True, help="veAWP token ID")
    parser.add_argument("--amount", required=True, help="AWP amount (human readable)")
    args = parser.parse_args()

    position = validate_positive_int(args.position, "position")
    amount = validate_positive_number(args.amount, "amount")

    # ── Pre-checks ──
    registry = get_registry()
    ve_awp = require_contract(registry, "veAWP")

    # ── Check remainingTime(tokenId) — selector = 0x0c64a7f2 ──
    position_padded = pad_uint256(position)
    remaining_hex = rpc_call(ve_awp, encode_calldata("0x0c64a7f2", position_padded))

    if not remaining_hex or remaining_hex in ("0x", "null"):
        die("Could not fetch remainingTime — is the position ID valid?")

    remaining = hex_to_int(remaining_hex)

    if remaining != 0:
        days_left = round(remaining / 86400, 1)
        die(f"Position #{position} still locked — {days_left} days remaining. Cannot withdraw yet.")

    # ── Convert and validate amount ──
    amount_wei = to_wei(amount)
    validate_uint128(amount_wei, "amount")

    # ── Send partialWithdraw(uint256,uint128) — selector = 0x808fe782 ──
    calldata = encode_calldata("0x808fe782", pad_uint256(position), pad_uint256(amount_wei))
    step("partialWithdraw", position=position, amount=f"{amount} AWP", target=ve_awp)
    result = wallet_send(args.token, ve_awp, calldata)
    print(result)


if __name__ == "__main__":
    main()
