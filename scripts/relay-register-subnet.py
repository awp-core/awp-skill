#!/usr/bin/env python3
"""Fully gasless subnet registration — via dual EIP-712 signatures (V2)"""

from __future__ import annotations

import json
import re
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
    hex_to_int,
    info,
    pad_address,
    require_contract,
    rpc,
    rpc_call_batch,
    split_sig,
    step,
    validate_address,
    validate_bytes32,
    validate_uint128,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str, str, int, str, str]:
    """Parse command-line arguments, returning (token, name, symbol, salt, min_stake, subnet_manager, skills_uri)"""
    parser = base_parser("AWP gasless subnet registration via dual EIP-712 signatures")
    parser.add_argument("--name", required=True, help="worknet name")
    parser.add_argument("--symbol", required=True, help="worknet token symbol")
    parser.add_argument(
        "--salt",
        default="0x0000000000000000000000000000000000000000000000000000000000000000",
        help="bytes32 salt (default all-zero)",
    )
    parser.add_argument("--min-stake", default="0", help="minimum stake amount (wei)")
    parser.add_argument(
        "--subnet-manager",
        default="0x0000000000000000000000000000000000000000",
        help="worknet manager address",
    )
    parser.add_argument("--skills-uri", default="", help="skills URI")
    args = parser.parse_args()

    # Validate min-stake — must fit in uint128 per contract WorknetParams definition
    if not re.match(r"^[0-9]+$", args.min_stake):
        die("Invalid --min-stake: must be a non-negative integer (wei)")
    min_stake = validate_uint128(int(args.min_stake), "min-stake")

    validate_address(args.subnet_manager, "subnet-manager")
    validate_bytes32(args.salt, "salt")

    return args.token, args.name, args.symbol, args.salt, min_stake, args.subnet_manager, args.skills_uri


def main() -> None:
    """Main flow"""
    token, name, symbol, salt, min_stake, subnet_manager, skills_uri = parse_args()

    # Step 1: Fetch registry
    step("fetch_registry")
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")
    awp_token = require_contract(registry, "awpToken")
    domain = get_eip712_domain(registry)
    chain_id = domain["chainId"]

    # Step 2: Get wallet address
    step("get_wallet_address")
    wallet_addr = get_wallet_address()

    # Step 3: Try the API for the AWPRegistry EIP-712 nonce — the API has lower latency
    # than an eth_call round-trip, and several scripts share the same code path.
    step("get_registry_nonce")
    nonce_resp = rpc("nonce.get", {"address": wallet_addr})
    registry_nonce: int | None = None
    if isinstance(nonce_resp, dict):
        raw = nonce_resp.get("nonce")
        if raw is not None and raw != "null":
            registry_nonce = int(raw)

    # Step 4: Batch the remaining read-only contract calls.
    #   - initialAlphaPrice() on AWPRegistry → to compute the AWP deposit the user permits
    #   - nonces(wallet) on AWPToken       → ERC-2612 permit nonce
    #   - nonces(wallet) on AWPRegistry    → fallback if the API did not provide a nonce
    # Selector 0x7ecebe00 = nonces(address).
    step("get_onchain_params")
    addr_padded = pad_address(wallet_addr)
    batch_calls: list[tuple[str, str]] = [
        (awp_registry, "0x6d345eea"),                        # initialAlphaPrice()
        (awp_token, f"0x7ecebe00{addr_padded}"),            # AWPToken.nonces(wallet)
    ]
    if registry_nonce is None:
        batch_calls.append((awp_registry, f"0x7ecebe00{addr_padded}"))

    results = rpc_call_batch(batch_calls)

    price_hex = results[0]
    if not price_hex or price_hex in ("0x", "null"):
        die("initialAlphaPrice() returned empty — is the AWPRegistry contract reachable?")
    initial_alpha_price = hex_to_int(price_hex)

    # LP_COST = 100M * 10^18 * initialAlphaPrice / 10^18
    lp_cost = 100_000_000 * 10**18 * initial_alpha_price // 10**18

    permit_nonce = hex_to_int(results[1])

    if registry_nonce is None:
        registry_nonce = hex_to_int(results[2])

    # Step 5: Deadline (1 hour from now)
    deadline = int(time.time()) + 3600

    # Step 6: Sign ERC-2612 Permit
    step("sign_permit")
    permit_domain = {
        "name": "AWP Token",
        "version": "1",
        "chainId": chain_id,
        "verifyingContract": awp_token,
    }
    permit_data = build_eip712(
        permit_domain,
        "Permit",
        [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        {
            "owner": wallet_addr,
            "spender": awp_registry,
            "value": lp_cost,
            "nonce": permit_nonce,
            "deadline": deadline,
        },
    )
    permit_signature = wallet_sign_typed_data(token, permit_data)

    # Step 7: Sign EIP-712 RegisterWorknet (nested WorknetParams struct)
    step("sign_register_worknet")
    register_data = build_eip712(
        domain,
        "RegisterWorknet",
        [
            {"name": "user", "type": "address"},
            {"name": "params", "type": "WorknetParams"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        {
            "user": wallet_addr,
            "params": {
                "name": name,
                "symbol": symbol,
                "worknetManager": subnet_manager,
                "salt": salt,
                "minStake": min_stake,
                "skillsURI": skills_uri,
            },
            "nonce": registry_nonce,
            "deadline": deadline,
        },
        extra_types={
            "WorknetParams": [
                {"name": "name", "type": "string"},
                {"name": "symbol", "type": "string"},
                {"name": "worknetManager", "type": "address"},
                {"name": "salt", "type": "bytes32"},
                {"name": "minStake", "type": "uint128"},
                {"name": "skillsURI", "type": "string"},
            ],
        },
    )
    register_signature = wallet_sign_typed_data(token, register_data)

    # Step 8: Submit to relay — split compact 65-byte signatures into (v, r, s)
    permit_v, permit_r, permit_s = split_sig(permit_signature)
    register_v, register_r, register_s = split_sig(register_signature)

    step("submit_relay")
    relay_body = {
        "chainId": chain_id,
        "user": wallet_addr,
        "name": name,
        "symbol": symbol,
        "worknetManager": subnet_manager,
        "salt": salt,
        "minStake": str(min_stake),
        "skillsURI": skills_uri,
        "deadline": deadline,
        "permitV": permit_v,
        "permitR": permit_r,
        "permitS": permit_s,
        "registerV": register_v,
        "registerR": register_r,
        "registerS": register_s,
    }

    relay_url = f"{RELAY_BASE}/relay/register-worknet"
    info(f"Submitting to {relay_url}")
    http_code, body = api_post(relay_url, relay_body)

    if 200 <= http_code < 300:
        print(json.dumps(body) if isinstance(body, dict) else body)
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
