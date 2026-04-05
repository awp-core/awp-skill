#!/usr/bin/env python3
"""On-chain register() — explicit registration on AWPRegistry.
register() is equivalent to setRecipient(msg.sender). Each address is implicitly a root;
calling register() simply sets recipient to itself explicitly.
"""
import json

from awp_lib import (
    base_parser,
    get_registry,
    get_wallet_address,
    require_contract,
    rpc,
    step,
    wallet_send,
)


def main() -> None:
    parser = base_parser("On-chain register")
    args = parser.parse_args()
    token: str = args.token

    # Pre-check: get wallet address
    wallet_addr = get_wallet_address()

    # Get contract registry
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # Check if already registered — avoids paying gas for a no-op
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict) and check.get("isRegistered"):
        print(json.dumps({
            "status": "already_registered",
            "address": wallet_addr,
            "recipient": check.get("recipient", ""),
        }))
        return

    # register() selector = 0x1aa3a008
    step("register", address=wallet_addr)
    result = wallet_send(token, awp_registry, "0x1aa3a008")
    print(result)


if __name__ == "__main__":
    main()
