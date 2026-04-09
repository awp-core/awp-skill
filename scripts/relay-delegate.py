#!/usr/bin/env python3
"""AWP Gasless delegate — grant or revoke a delegate via EIP-712 + relay"""

from __future__ import annotations

import json
import time

from awp_lib import (
    RELAY_BASE,
    api_post,
    base_parser,
    build_eip712,
    die,
    get_eip712_domain,
    get_registry,
    get_wallet_address,
    info,
    rpc,
    step,
    validate_address,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str]:
    """Parse CLI arguments, return (token, mode, delegate)."""
    parser = base_parser("AWP gasless delegate — grant or revoke delegate via relay")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["grant", "revoke"],
        help="grant (add delegate) or revoke (remove delegate)",
    )
    parser.add_argument("--delegate", required=True, help="delegate address")
    args = parser.parse_args()

    validate_address(args.delegate, "delegate")

    return args.token, args.mode, args.delegate


def main() -> None:
    """Main flow"""
    token, mode, delegate = parse_args()

    # Step 1: Fetch registry and EIP-712 domain
    step("fetch_registry")
    registry = get_registry()
    domain = get_eip712_domain(registry)
    info(
        f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}"
    )

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Get nonce
    step("get_nonce")
    nonce_resp = rpc("nonce.get", {"address": wallet_addr})
    if not isinstance(nonce_resp, dict) or "nonce" not in nonce_resp:
        die(f"Invalid nonce response: {nonce_resp}")
    nonce = nonce_resp["nonce"]

    # Step 4: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    chain_id = domain["chainId"]

    # Step 5: Build EIP-712 typed data
    step("build_eip712")
    if mode == "grant":
        primary_type = "GrantDelegate"
        relay_endpoint = f"{RELAY_BASE}/relay/grant-delegate"
    else:
        primary_type = "RevokeDelegate"
        relay_endpoint = f"{RELAY_BASE}/relay/revoke-delegate"

    eip712_data = build_eip712(
        domain,
        primary_type,
        [
            {"name": "user", "type": "address"},
            {"name": "delegate", "type": "address"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        {
            "user": wallet_addr,
            "delegate": delegate,
            "nonce": nonce,
            "deadline": deadline,
        },
    )

    relay_body_base: dict = {
        "chainId": chain_id,
        "user": wallet_addr,
        "delegate": delegate,
        "deadline": deadline,
    }

    # Step 6: Sign — combined 65-byte signature (NOT split v/r/s)
    step("sign_eip712")
    signature = wallet_sign_typed_data(token, eip712_data)
    relay_body: dict = {**relay_body_base, "signature": signature}

    # Step 7: Submit to relay
    step("submit_relay", endpoint=relay_endpoint)
    info(f"Submitting to {relay_endpoint}")
    http_code, body = api_post(relay_endpoint, relay_body)

    if 200 <= http_code < 300:
        result = body if isinstance(body, dict) else {"result": body}
        result["nextAction"] = "check_status"
        result["nextCommand"] = (
            f"python3 scripts/query-status.py --address {wallet_addr}"
        )
        print(json.dumps(result))
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
