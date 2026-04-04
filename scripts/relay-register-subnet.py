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
    rpc_call,
    step,
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

    # Validate min-stake is a non-negative integer
    if not re.match(r"^[0-9]+$", args.min_stake):
        die("Invalid --min-stake: must be a non-negative integer (wei)")
    min_stake = int(args.min_stake)

    # Validate subnet-manager address format
    if not re.match(r"^0x[0-9a-fA-F]{40}$", args.subnet_manager):
        die("Invalid --subnet-manager: must be 0x + 40 hex chars")

    # Validate salt format (bytes32)
    if not re.match(r"^0x[0-9a-fA-F]{64}$", args.salt):
        die("Invalid --salt: must be 0x + 64 hex chars (bytes32)")

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

    # Step 3: Get initialAlphaPrice — selector = 0x6d345eea
    step("get_initial_alpha_price")
    price_hex = rpc_call(awp_registry, "0x6d345eea")
    if not price_hex or price_hex in ("0x", "null"):
        die("initialAlphaPrice() returned empty — is AWP_REGISTRY correct?")
    initial_alpha_price = hex_to_int(price_hex)

    # LP_COST = 100M * 10^18 * initialAlphaPrice / 10^18
    lp_cost = 100_000_000 * 10**18 * initial_alpha_price // 10**18

    # Step 4: Get nonces
    step("get_nonces")

    # Registry nonce — try RPC first, fall back to on-chain RPC
    nonce_resp = rpc("nonce.get", {"address": wallet_addr})
    registry_nonce: int | None = None
    if isinstance(nonce_resp, dict):
        raw = nonce_resp.get("nonce")
        if raw is not None and raw != "null":
            registry_nonce = int(raw)

    if registry_nonce is None:
        # Fallback: read nonce from contract
        addr_padded = pad_address(wallet_addr)
        registry_nonce_hex = rpc_call(awp_registry, f"0x7ecebe00{addr_padded}")
        registry_nonce = hex_to_int(registry_nonce_hex)

    # AWPToken permit nonce (always read from RPC — no REST endpoint)
    addr_padded = pad_address(wallet_addr)
    permit_nonce_hex = rpc_call(awp_token, f"0x7ecebe00{addr_padded}")
    permit_nonce = hex_to_int(permit_nonce_hex)

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

    # Step 8: Submit to relay
    # relay 接受拆分的 v/r/s 签名字段（65字节紧凑签名 = r[32] + s[32] + v[1]）
    def split_sig(sig: str) -> tuple[int, str, str]:
        """将 0x<r><s><v> 65字节签名拆分为 (v, r, s)"""
        raw = sig[2:] if sig.startswith("0x") else sig
        if len(raw) != 130:
            die(f"Invalid signature length: expected 130 hex chars, got {len(raw)}")
        r = "0x" + raw[0:64]
        s = "0x" + raw[64:128]
        v = int(raw[128:130], 16)
        return v, r, s

    permit_v, permit_r, permit_s = split_sig(permit_signature)
    register_v, register_r, register_s = split_sig(register_signature)

    step("submit_relay")
    relay_body = {
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

    relay_url = f"{RELAY_BASE}/relay/register-subnet"
    info(f"Submitting to {relay_url}")
    http_code, body = api_post(relay_url, relay_body)

    if 200 <= http_code < 300:
        print(json.dumps(body) if isinstance(body, dict) else body)
    else:
        die(f"Relay returned HTTP {http_code}: {body}")


if __name__ == "__main__":
    main()
