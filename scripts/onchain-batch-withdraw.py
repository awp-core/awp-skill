#!/usr/bin/env python3
"""On-chain batch withdrawal — withdraw AWP from multiple expired veAWP positions in one tx
batchWithdraw(uint256[] tokenIds)
Burns each position NFT and returns AWP. Contract checks lock expiry internally. Requires ETH for gas.
"""
from awp_lib import *


def main() -> None:
    # ── Argument parsing ──
    parser = base_parser("Batch withdraw from multiple expired veAWP positions")
    parser.add_argument("--positions", required=True, help="Comma-separated veAWP token IDs (e.g. 1,2,3)")
    args = parser.parse_args()

    # ── Parse and validate position IDs ──
    raw_ids = args.positions.split(",")
    token_ids: list[int] = []
    for raw in raw_ids:
        raw = raw.strip()
        if not raw:
            die("Empty token ID in --positions list")
        tid = validate_positive_int(raw, "position")
        token_ids.append(tid)

    if not token_ids:
        die("No token IDs provided")

    # ── Pre-checks ──
    registry = get_registry()
    ve_awp = require_contract(registry, "veAWP")

    # ── ABI encode batchWithdraw(uint256[]) — selector = 0x72e55399 ──
    # Layout: selector + offset(32) + length + each tokenId padded to 32 bytes
    parts: list[str] = []
    # offset to array data = 32 bytes
    parts.append(pad_uint256(32))
    # array length
    parts.append(pad_uint256(len(token_ids)))
    # each element
    for tid in token_ids:
        parts.append(pad_uint256(tid))

    calldata = encode_calldata("0x72e55399", *parts)

    step("batchWithdraw", positions=token_ids, count=len(token_ids), target=ve_awp)
    result = wallet_send(args.token, ve_awp, calldata)
    print(result)


if __name__ == "__main__":
    main()
