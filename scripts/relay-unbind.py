#!/usr/bin/env python3
"""AWP Gasless unbind — unbind current wallet from its target via EIP-712 + relay"""

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
    wallet_sign_typed_data,
)


def parse_args() -> str:
    """Parse CLI arguments, return token."""
    parser = base_parser("AWP gasless unbind — unbind wallet from target via relay")
    args = parser.parse_args()
    return args.token


def main() -> None:
    """Main flow"""
    token = parse_args()

    # Step 1: Fetch registry and EIP-712 domain
    step("fetch_registry")
    registry = get_registry()
    domain = get_eip712_domain(registry)
    info(f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}")

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Pre-check — verify the user IS currently bound
    step("check_status")
    check = rpc("address.check", {"address": wallet_addr})
    zero_addr = "0x0000000000000000000000000000000000000000"
    if isinstance(check, dict):
        bound_to = check.get("boundTo", "")
        if not bound_to or bound_to == "null" or bound_to == zero_addr:
            print(json.dumps({"status": "not_bound", "address": wallet_addr}))
            return

    # Step 4: Get nonce
    step("get_nonce")
    nonce_resp = rpc("nonce.get", {"address": wallet_addr})
    if not isinstance(nonce_resp, dict) or "nonce" not in nonce_resp:
        die(f"Invalid nonce response: {nonce_resp}")
    nonce = nonce_resp["nonce"]

    # Step 5: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    chain_id = domain["chainId"]

    # Step 6: Build EIP-712 typed data for Unbind
    step("build_eip712")
    eip712_data = build_eip712(
        domain,
        "Unbind",
        [
            {"name": "user", "type": "address"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        {
            "user": wallet_addr,
            "nonce": nonce,
            "deadline": deadline,
        },
    )

    relay_endpoint = f"{RELAY_BASE}/relay/unbind"
    relay_body_base: dict = {
        "chainId": chain_id,
        "user": wallet_addr,
        "deadline": deadline,
    }

    # Step 7: Sign — combined 65-byte signature (NOT split v/r/s)
    step("sign_eip712")
    signature = wallet_sign_typed_data(token, eip712_data)
    relay_body: dict = {**relay_body_base, "signature": signature}

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
