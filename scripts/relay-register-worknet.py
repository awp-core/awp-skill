#!/usr/bin/env python3
"""Fully gasless worknet registration — via dual EIP-712 signatures (V2)"""

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
    step,
    validate_address,
    validate_bytes32,
    validate_uint128,
    wallet_sign_typed_data,
)


def parse_args() -> tuple[str, str, str, str, int, str, str]:
    """Parse command-line arguments, returning (token, name, symbol, salt, min_stake, worknet_manager, skills_uri)"""
    parser = base_parser("AWP gasless worknet registration via dual EIP-712 signatures")
    parser.add_argument("--name", required=True, help="worknet name")
    parser.add_argument("--symbol", required=True, help="worknet token symbol")
    parser.add_argument(
        "--salt",
        default="0x0000000000000000000000000000000000000000000000000000000000000000",
        help="bytes32 salt (default all-zero)",
    )
    parser.add_argument("--min-stake", default="0", help="minimum stake amount (wei)")
    parser.add_argument(
        "--worknet-manager",
        default="0x0000000000000000000000000000000000000000",
        help="worknet manager address",
    )
    parser.add_argument("--skills-uri", default="", help="skills URI")
    args = parser.parse_args()

    # Validate min-stake — must fit in uint128 per contract WorknetParams definition
    if not re.match(r"^[0-9]+$", args.min_stake):
        die("Invalid --min-stake: must be a non-negative integer (wei)")
    min_stake = validate_uint128(int(args.min_stake), "min-stake")

    validate_address(args.worknet_manager, "worknet-manager")
    validate_bytes32(args.salt, "salt")

    return (
        args.token,
        args.name,
        args.symbol,
        args.salt,
        min_stake,
        args.worknet_manager,
        args.skills_uri,
    )


def main() -> None:
    """Main flow"""
    token, name, symbol, salt, min_stake, worknet_manager, skills_uri = parse_args()

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

    # Step 3: Batch read-only contract calls (always fetch nonce on-chain — API may lag).
    #   - initialAlphaPrice() on AWPRegistry → wei AWP per whole WorknetToken
    #   - initialAlphaMint()  on AWPRegistry → total WorknetTokens minted for LP (wei)
    #   - nonces(wallet) on AWPToken         → ERC-2612 permit nonce
    #   - nonces(wallet) on AWPRegistry      → EIP-712 registry nonce (authoritative on-chain)
    # Selectors verified by keccak256 against the live AWPRegistry bytecode:
    #   0x6d345eea = initialAlphaPrice()
    #   0x5bd9c498 = initialAlphaMint()
    #   0x7ecebe00 = nonces(address)
    # We read initialAlphaMint dynamically (rather than hardcoding) because Guardian
    # can update it via setInitialAlphaMint. Current on-chain value is 1e27 wei
    # (= 1e9 tokens). Hardcoding 1e8 tokens understates LP cost by 10x.
    step("get_onchain_params")
    addr_padded = pad_address(wallet_addr)
    batch_calls: list[tuple[str, str]] = [
        (awp_registry, "0x6d345eea"),  # initialAlphaPrice()
        (awp_registry, "0x5bd9c498"),  # initialAlphaMint()
        (awp_token, f"0x7ecebe00{addr_padded}"),  # AWPToken.nonces(wallet)
        (
            awp_registry,
            f"0x7ecebe00{addr_padded}",
        ),  # AWPRegistry.nonces(wallet) — 链上权威
    ]

    results = rpc_call_batch(batch_calls)

    price_hex = results[0]
    if not price_hex or price_hex in ("0x", "null"):
        die(
            "initialAlphaPrice() returned empty — is the AWPRegistry contract reachable?"
        )
    initial_alpha_price = hex_to_int(price_hex)  # wei AWP per whole WorknetToken

    mint_hex = results[1]
    if not mint_hex or mint_hex in ("0x", "null"):
        die(
            "initialAlphaMint() returned empty — is the AWPRegistry contract reachable?"
        )
    initial_alpha_mint = hex_to_int(mint_hex)  # total WorknetTokens (wei, 18 decimals)

    # LP cost in AWP wei = initialAlphaPrice × (initialAlphaMint / 1e18)
    # Both price and mint are stored as 18-decimal wei; the division cancels one set of
    # decimals so the result is AWP wei (also 18-decimal). Guardian-controlled params,
    # fetched dynamically on every call.
    lp_cost = initial_alpha_price * initial_alpha_mint // 10**18

    permit_nonce = hex_to_int(results[2])
    registry_nonce = hex_to_int(results[3])  # 始终使用链上 nonce（API 可能延迟）

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
            "value": str(lp_cost),  # 字符串化避免 JS JSON.parse 超过 2^53 时精度丢失
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
                "worknetManager": worknet_manager,
                "salt": salt,
                "minStake": str(
                    min_stake
                ),  # 字符串化避免 JS JSON.parse 超过 2^53 精度丢失
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

    # Step 8: Submit to relay.
    # The live relay API expects the full 65-byte compact signatures as
    # `permitSignature` + `registerSignature`, NOT split v/r/s. We probed the
    # endpoint with both shapes:
    #   - permitV/R/S + registerV/R/S → {"error":"both permitSignature and registerSignature are required"}
    #   - permitSignature + registerSignature → reaches EIP-712 verification
    # skill-reference.md §5 incorrectly documents the v/r/s shape. Do not "fix"
    # this back to v/r/s.
    step("submit_relay")
    relay_body = {
        "chainId": chain_id,
        "user": wallet_addr,
        "name": name,
        "symbol": symbol,
        "worknetManager": worknet_manager,
        "salt": salt,
        "minStake": str(min_stake),
        "skillsURI": skills_uri,
        "deadline": deadline,
        "permitSignature": permit_signature,
        "registerSignature": register_signature,
    }

    relay_url = f"{RELAY_BASE}/relay/register-worknet"
    info(f"Submitting to {relay_url}")
    http_code, body = api_post(relay_url, relay_body)

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
