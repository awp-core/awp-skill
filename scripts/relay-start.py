#!/usr/bin/env python3
"""AWP Gasless onboarding — register or bind via relay"""

from __future__ import annotations

import json
import time

from awp_lib import (
    API_BASE,
    api_get,
    api_post,
    base_parser,
    build_eip712,
    die,
    get_eip712_domain,
    get_registry,
    get_wallet_address,
    info,
    step,
    validate_address,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str]:
    """Parse command-line arguments, returning (token, mode, target)"""
    parser = base_parser("AWP gasless onboarding — register or bind via relay")
    parser.add_argument(
        "--mode", required=True, choices=["principal", "agent"],
        help="principal (register / set self as recipient) or agent (bind to target address)",
    )
    parser.add_argument("--target", default="", help="target address in agent mode")
    args = parser.parse_args()

    if args.mode == "agent" and not args.target:
        die("Agent mode requires --target <address>")
    if args.target:
        validate_address(args.target, "target")

    return args.token, args.mode, args.target


def main() -> None:
    """Main flow"""
    token, mode, target = parse_args()

    # Step 1: Fetch registry and EIP-712 domain
    step("fetch_registry")
    registry = get_registry()
    domain = get_eip712_domain(registry)
    info(f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}")

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Check current status
    step("check_status")
    check = api_get(f"address/{wallet_addr}/check")
    if isinstance(check, dict):
        is_registered = check.get("isRegistered", check.get("isRegisteredUser", False))
        bound_to = check.get("boundTo", "")

        if mode == "principal" and str(is_registered).lower() == "true":
            print(json.dumps({"status": "already_registered", "address": wallet_addr}))
            return

        zero_addr = "0x0000000000000000000000000000000000000000"
        if mode == "agent" and bound_to and bound_to != "null" and bound_to != zero_addr:
            print(json.dumps({"status": "already_bound", "address": wallet_addr, "boundTo": bound_to}))
            return

    # Step 4: Get nonce
    step("get_nonce")
    nonce_resp = api_get(f"nonce/{wallet_addr}")
    if not isinstance(nonce_resp, dict) or "nonce" not in nonce_resp:
        die(f"Invalid nonce response: {nonce_resp}")
    nonce = nonce_resp["nonce"]

    # Step 5: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    # Step 6: Build EIP-712 typed data
    if mode == "principal":
        # Principal mode: setRecipient(self) via /relay/set-recipient
        eip712_data = build_eip712(
            domain,
            "SetRecipient",
            [
                {"name": "user", "type": "address"},
                {"name": "recipient", "type": "address"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint256"},
            ],
            {
                "user": wallet_addr,
                "recipient": wallet_addr,
                "nonce": nonce,
                "deadline": deadline,
            },
        )
        relay_endpoint = f"{API_BASE}/relay/set-recipient"
        relay_body: dict = {
            "user": wallet_addr,
            "recipient": wallet_addr,
            "deadline": deadline,
            "signature": None,
        }
    else:
        # Agent mode: bind(target) via /relay/bind
        eip712_data = build_eip712(
            domain,
            "Bind",
            [
                {"name": "agent", "type": "address"},
                {"name": "target", "type": "address"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint256"},
            ],
            {
                "agent": wallet_addr,
                "target": target,
                "nonce": nonce,
                "deadline": deadline,
            },
        )
        relay_endpoint = f"{API_BASE}/relay/bind"
        relay_body = {
            "agent": wallet_addr,
            "target": target,
            "deadline": deadline,
            "signature": None,
        }

    # Step 7: Sign
    step("sign_eip712")
    signature = wallet_sign_typed_data(token, eip712_data)
    relay_body["signature"] = signature

    # Step 8: Submit to relay
    step("submit_relay", endpoint=relay_endpoint)
    info(f"Submitting to {relay_endpoint}")
    http_code, body = api_post(relay_endpoint, relay_body)

    if 200 <= http_code < 300:
        print(json.dumps(body) if isinstance(body, dict) else body)
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
