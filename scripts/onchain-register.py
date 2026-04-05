#!/usr/bin/env python3
"""On-chain registration on AWPRegistry.

AWPRegistry has no standalone `register()` function; registration happens implicitly
the first time an address calls `setRecipient(address)`. Setting the recipient to the
caller's own address is the canonical way to mark an address as active without
changing the reward recipient from its default (self).

If the agent is already registered, this script is a no-op.
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
    wallet_send,
)


def main() -> None:
    parser = base_parser("On-chain register (setRecipient to self)")
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

    # setRecipient(address) selector = 0x3bbed4a0
    # Passing the caller's own address registers without changing reward routing.
    calldata = encode_calldata("0x3bbed4a0", pad_address(wallet_addr))
    step("register", address=wallet_addr, method="setRecipient(self)")
    result = wallet_send(token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
