#!/usr/bin/env python3
"""AWP Gasless allocate — allocate or deallocate stake via EIP-712 + relay"""

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
    to_wei,
    validate_address,
    validate_positive_number,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str, str, str]:
    """解析命令行参数，返回 (token, mode, agent, worknet, amount)"""
    parser = base_parser("AWP gasless allocate — allocate or deallocate stake via relay")
    parser.add_argument(
        "--mode", required=True, choices=["allocate", "deallocate"],
        help="allocate (add stake) or deallocate (remove stake)",
    )
    parser.add_argument("--agent", required=True, help="agent address")
    parser.add_argument("--worknet", required=True, help="worknet ID string")
    parser.add_argument("--amount", required=True, help="AWP amount (human-readable)")
    args = parser.parse_args()

    validate_address(args.agent, "agent")
    validate_positive_number(args.amount, "amount")

    return args.token, args.mode, args.agent, args.worknet, args.amount


def main() -> None:
    """Main flow"""
    token, mode, agent, worknet, amount_str = parse_args()

    # Step 1: Fetch registry and EIP-712 domain (AWPAllocator, NOT AWPRegistry)
    step("fetch_registry")
    registry = get_registry()
    domain = get_eip712_domain(registry, "AWPAllocator")
    info(f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}")

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Convert amount to wei
    amount_wei = to_wei(amount_str)

    # Step 4: Parse worknet ID
    step("parse_worknet_id")
    try:
        worknet_id = int(worknet)
    except ValueError:
        die(f"Invalid --worknet: must be a numeric ID, got: {worknet}")
        return  # unreachable

    # Step 5: Get staking nonce (AWPAllocator nonce, NOT nonce.get)
    step("get_nonce")
    nonce_resp = rpc("nonce.getStaking", {"address": wallet_addr})
    if not isinstance(nonce_resp, dict) or "nonce" not in nonce_resp:
        die(f"Invalid nonce response: {nonce_resp}")
    nonce = nonce_resp["nonce"]

    # Step 6: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    chain_id = domain["chainId"]

    # Step 7: Build EIP-712 typed data
    step("build_eip712")
    if mode == "allocate":
        primary_type = "Allocate"
        relay_endpoint = f"{RELAY_BASE}/relay/allocate"
    else:
        primary_type = "Deallocate"
        relay_endpoint = f"{RELAY_BASE}/relay/deallocate"

    eip712_data = build_eip712(
        domain,
        primary_type,
        [
            {"name": "staker", "type": "address"},
            {"name": "agent", "type": "address"},
            {"name": "worknetId", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        {
            "staker": wallet_addr,
            "agent": agent,
            "worknetId": worknet_id,
            "amount": amount_wei,
            "nonce": nonce,
            "deadline": deadline,
        },
    )

    relay_body_base: dict = {
        "chainId": chain_id,
        "staker": wallet_addr,
        "agent": agent,
        "worknetId": str(worknet_id),
        "amount": str(amount_wei),
        "deadline": deadline,
    }

    # Step 8: Sign — combined 65-byte signature (NOT split v/r/s)
    step("sign_eip712")
    signature = wallet_sign_typed_data(token, eip712_data)
    relay_body: dict = {**relay_body_base, "signature": signature}

    # Step 9: Submit to relay
    step("submit_relay", endpoint=relay_endpoint)
    info(f"Submitting to {relay_endpoint}")
    http_code, body = api_post(relay_endpoint, relay_body)

    if 200 <= http_code < 300:
        print(json.dumps(body) if isinstance(body, dict) else body)
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
