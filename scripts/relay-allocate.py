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
    expand_worknet_id,
    get_eip712_domain,
    get_registry,
    get_wallet_address,
    info,
    rpc,
    step,
    to_wei,
    validate_address,
    validate_positive_int,
    validate_positive_number,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str, str, str]:
    """Parse CLI arguments, return (token, mode, agent, worknet, amount)."""
    parser = base_parser(
        "AWP gasless allocate — allocate or deallocate stake via relay"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["allocate", "deallocate"],
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
    info(
        f"domain: {domain['name']} v{domain['version']} chain={domain['chainId']} contract={domain['verifyingContract']}"
    )

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 2.5: Precondition check — verify staking state before proceeding
    step("precondition_check")
    balance = rpc("staking.getBalance", {"address": wallet_addr})
    if isinstance(balance, dict):
        try:
            if mode == "allocate" and int(balance.get("totalStaked", "0")) == 0:
                die(
                    "No staked AWP. Stake first: "
                    "python3 scripts/relay-stake.py --token $TOKEN --amount <AMOUNT> --lock-days <DAYS>"
                )
            if mode == "deallocate" and int(balance.get("totalAllocated", "0")) == 0:
                die("No allocations found — nothing to deallocate.")
        except (ValueError, TypeError):
            pass  # 无法解析余额，继续执行（让合约来拒绝）

    # Step 3: Convert amount to wei
    amount_wei = to_wei(amount_str)

    # Step 4: Parse worknet ID and expand short IDs (e.g. 2 → 845300000002)
    step("parse_worknet_id")
    worknet_id = validate_positive_int(worknet, "worknet")
    worknet_id = expand_worknet_id(worknet_id)

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
        result = body if isinstance(body, dict) else {"result": body}
        if mode == "allocate":
            result["nextAction"] = "earning"
            result["nextCommand"] = (
                f"python3 scripts/query-status.py --address {wallet_addr}"
            )
        else:
            result["nextAction"] = "check_status"
            result["nextCommand"] = (
                f"python3 scripts/query-status.py --address {wallet_addr}"
            )
        print(json.dumps(result))
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
