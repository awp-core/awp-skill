#!/usr/bin/env python3
"""On-chain bind(address target) — bind to a target in the account tree (V2)
Tree-based binding with anti-cycle checks.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain bind to target address (V2)")
    parser.add_argument("--target", required=True, help="Bind target address")
    # Backward-compatible alias for old parameter name
    parser.add_argument("--principal", dest="target_alt", help=argparse.SUPPRESS)
    args = parser.parse_args()

    token: str = args.token
    target: str = args.target_alt if args.target_alt else args.target
    validate_address(target, "target")

    # Pre-check: get wallet address
    wallet_addr = get_wallet_address()

    # Get contract registry
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # Check if already bound
    check = api_get(f"address/{wallet_addr}/check")
    if isinstance(check, dict):
        # V2: .boundTo; V1: .isRegisteredAgent + .ownerAddress
        bound_to = check.get("boundTo", "")
        is_agent = str(check.get("isRegisteredAgent", False)).lower()
        if is_agent == "true":
            bound_to = check.get("ownerAddress", "")

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
