#!/usr/bin/env python3
"""On-chain withdrawal — withdraw AWP from an expired StakeNFT position (V2)
withdraw(uint256 tokenId) — burns the position NFT and returns AWP
Only callable when the lock has expired (remainingTime == 0). Requires ETH for gas.
"""
from awp_lib import *


def main() -> None:
    # ── Argument parsing ──
    parser = base_parser("Withdraw from expired StakeNFT position")
    parser.add_argument("--position", required=True, help="StakeNFT token ID")
    args = parser.parse_args()

    position = validate_positive_int(args.position, "position")

    # ── Pre-checks ──
    wallet_addr = get_wallet_address()
    registry = get_registry()
    stake_nft = require_contract(registry, "stakeNFT")

    # ── Check remainingTime(tokenId) — selector = 0x0c64a7f2 ──
    position_padded = pad_uint256(position)
    remaining_hex = rpc_call(stake_nft, encode_calldata("0x0c64a7f2", position_padded))

    if not remaining_hex or remaining_hex in ("0x", "null"):
        die("Could not fetch remainingTime — is the position ID valid?")

    remaining = hex_to_int(remaining_hex)

    if remaining != 0:
        days_left = round(remaining / 86400, 1)
        die(f"Position #{position} still locked — {days_left} days remaining. Cannot withdraw yet.")

    # ── Send withdraw(uint256) — selector = 0x2e1a7d4d ──
    calldata = encode_calldata("0x2e1a7d4d", position_padded)
    step("withdraw", position=position, target=stake_nft)
    result = wallet_send(args.token, stake_nft, calldata)
    print(result)


if __name__ == "__main__":
    main()
