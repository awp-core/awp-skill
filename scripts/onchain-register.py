#!/usr/bin/env python3
"""On-chain register() — explicit registration (V2)
In V2, register() is equivalent to setRecipient(msg.sender).
Each address is implicitly a root; calling register() simply sets recipient to itself explicitly.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain register (V2)")
    args = parser.parse_args()
    token: str = args.token

    # Pre-check: get wallet address
    wallet_addr = get_wallet_address()

    # Get contract registry
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # Check if already registered
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict):
        # V2: .isRegistered; V1: .isRegisteredUser
        is_registered = check.get("isRegistered")
        if is_registered is None:
            is_registered = check.get("isRegisteredUser", False)
        recipient = check.get("recipient", "")

        if str(is_registered).lower() == "true":
            print(json.dumps({
                "status": "already_registered",
                "address": wallet_addr,
                "recipient": recipient,
            }))
            return

    # register() selector = 0x1aa3a008
    step("register", address=wallet_addr)
    result = wallet_send(token, awp_registry, "0x1aa3a008")
    print(result)


if __name__ == "__main__":
    main()
