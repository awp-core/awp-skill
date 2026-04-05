#!/usr/bin/env python3
"""On-chain bind(address target) — bind to a target in the account tree
Tree-based binding with anti-cycle checks on the AWPRegistry contract.
"""
import json

from awp_lib import (
    base_parser,
    encode_calldata,
    get_registry,
    get_wallet_address,
    pad_address,
    require_contract,
    rpc,
    step,
    validate_address,
    wallet_send,
)


def main() -> None:
    parser = base_parser("On-chain bind to target address")
    parser.add_argument("--target", required=True, help="Bind target address")
    args = parser.parse_args()

    token: str = args.token
    target: str = args.target
    validate_address(target, "target")

    # Pre-check: get wallet address
    wallet_addr = get_wallet_address()

    # Get contract registry
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # Check if already bound — avoids paying gas for a call the contract would revert
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict):
        bound_to = check.get("boundTo", "")
        zero_addr = "0x0000000000000000000000000000000000000000"
        if bound_to and bound_to != "null" and bound_to != zero_addr:
            print(json.dumps({
                "status": "already_bound",
                "address": wallet_addr,
                "boundTo": bound_to,
            }))
            return

    # bind(address) selector = 0x81bac14f + ABI-encoded address
    calldata = encode_calldata("0x81bac14f", pad_address(target))

    step("bind", address=wallet_addr, target=target)
    result = wallet_send(token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
