#!/usr/bin/env python3
"""AWP Gasless onboarding — register or bind via relay"""

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
    get_onchain_nonce,
    get_registry,
    get_wallet_address,
    info,
    require_contract,
    rpc,
    step,
    validate_address,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str]:
    """Parse command-line arguments, returning (token, mode, target)"""
    parser = base_parser("AWP gasless onboarding — register or bind via relay")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["principal", "agent"],
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
    chain_id_for_check = int(domain["chainId"])
    info(
        f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}"
    )

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Check current status — pass chainId to get flat response (not multi-chain)
    step("check_status")
    check = rpc("address.check", {"address": wallet_addr, "chainId": chain_id_for_check})
    if isinstance(check, dict):
        is_registered = bool(check.get("isRegistered", False))
        bound_to = check.get("boundTo", "")

        if mode == "principal" and is_registered:
            print(
                json.dumps(
                    {
                        "status": "already_registered",
                        "address": wallet_addr,
                        "nextAction": "pick_worknet",
                        "nextCommand": f"python3 scripts/preflight.py --address {wallet_addr}",
                    }
                )
            )
            return

        zero_addr = "0x0000000000000000000000000000000000000000"
        if (
            mode == "agent"
            and bound_to
            and bound_to != "null"
            and bound_to != zero_addr
        ):
            print(
                json.dumps(
                    {
                        "status": "already_bound",
                        "address": wallet_addr,
                        "boundTo": bound_to,
                        "nextAction": "pick_worknet",
                        "nextCommand": f"python3 scripts/preflight.py --address {wallet_addr}",
                    }
                )
            )
            return

    # Step 4: Get nonce — ALWAYS fetch on-chain (API indexer may lag)
    step("get_nonce")
    awp_registry = require_contract(registry, "awpRegistry")
    nonce = get_onchain_nonce(awp_registry, wallet_addr)
    info(f"Registry nonce (on-chain): {nonce}")

    # Step 5: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    chain_id = domain["chainId"]

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
        relay_endpoint = f"{RELAY_BASE}/relay/set-recipient"
        relay_body_base: dict = {
            "chainId": chain_id,
            "user": wallet_addr,
            "recipient": wallet_addr,
            "deadline": deadline,
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
        relay_endpoint = f"{RELAY_BASE}/relay/bind"
        relay_body_base = {
            "chainId": chain_id,
            "agent": wallet_addr,
            "target": target,
            "deadline": deadline,
        }

    # Step 7: Sign and send the compact 65-byte signature.
    # The relay API expects the full `signature` field, NOT split v/r/s.
    # We probed /relay/set-recipient and /relay/bind with both shapes:
    #   - split v/r/s → {"error":"missing signature"}  (fields ignored)
    #   - combined signature → reaches EIP-712 verification (expected behaviour)
    # skill-reference.md §5 incorrectly documents the v/r/s shape — the live API
    # only accepts the combined form. Do not "fix" this back to v/r/s.
    step("sign_eip712")
    signature = wallet_sign_typed_data(token, eip712_data)
    relay_body: dict = {**relay_body_base, "signature": signature}

    # Step 8: Submit to relay
    step("submit_relay", endpoint=relay_endpoint)
    info(f"Submitting to {relay_endpoint}")
    http_code, body = api_post(relay_endpoint, relay_body)

    if 200 <= http_code < 300:
        result = body if isinstance(body, dict) else {"result": body}
        result["nextAction"] = "pick_worknet"
        result["nextCommand"] = f"python3 scripts/preflight.py --address {wallet_addr}"
        print(json.dumps(result))
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
