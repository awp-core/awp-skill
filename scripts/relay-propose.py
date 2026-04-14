#!/usr/bin/env python3
"""Gasless executable proposal via /api/relay/propose/prepare + sign + submit.
No ETH needed. Creates an on-chain governance proposal with execution targets.

IMPORTANT: executable proposals can transfer funds, change protocol parameters,
and modify access control. The user MUST review targets/calldatas carefully.

Usage:
  python3 scripts/relay-propose.py \
    --targets "0xRegistry,0xDAO" \
    --values "0,0" \
    --calldatas "0x2f2ff15d...,0x..." \
    --description "Set new guardian"
"""

from __future__ import annotations

import json
import os
import re

from awp_lib import (
    ADDR_RE,
    RELAY_BASE,
    api_post,
    base_parser,
    die,
    get_wallet_address,
    info,
    rpc,
    step,
    wallet_sign_typed_data,
)

_CHAIN_IDS: dict[str, int] = {
    "ethereum": 1,
    "eth": 1,
    "bsc": 56,
    "bnb": 56,
    "base": 8453,
    "arbitrum": 42161,
    "arb": 42161,
}
_DEFAULT_CHAIN_ID = 8453


def _get_chain_id() -> int:
    """Get chainId from EVM_CHAIN environment variable."""
    chain_env = os.environ.get("EVM_CHAIN", "base").lower()
    cid = _CHAIN_IDS.get(chain_env)
    if cid is not None:
        return cid
    try:
        return int(chain_env)
    except ValueError:
        return _DEFAULT_CHAIN_ID


def main() -> None:
    parser = base_parser("Gasless executable proposal (no ETH needed)")
    parser.add_argument(
        "--targets", required=True, help="Comma-separated target addresses"
    )
    parser.add_argument(
        "--values", required=True, help="Comma-separated ETH values (wei)"
    )
    parser.add_argument(
        "--calldatas", required=True, help="Comma-separated hex calldata"
    )
    parser.add_argument("--description", required=True, help="Proposal description")
    parser.add_argument(
        "--token-ids",
        default="",
        help="Comma-separated veAWP token IDs (optional — auto-discovers if omitted)",
    )
    args = parser.parse_args()

    token: str = args.token
    description: str = args.description
    chain_id = _get_chain_id()

    # Parse and validate targets
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    for t in targets:
        if not ADDR_RE.match(t):
            die(f"Invalid target address: {t}")

    # Parse values
    values = [v.strip() for v in args.values.split(",") if v.strip()]
    for v in values:
        if not re.match(r"^[0-9]+$", v):
            die(f"Invalid value (must be non-negative integer wei): {v}")

    # Parse calldatas
    calldatas = [c.strip() for c in args.calldatas.split(",") if c.strip()]
    for c in calldatas:
        if not re.match(r"^0x[0-9a-fA-F]*$", c):
            die(f"Invalid calldata (must be 0x hex): {c}")

    # Validate array lengths match
    if len(targets) != len(values) or len(targets) != len(calldatas):
        die(
            f"Array length mismatch: {len(targets)} targets, "
            f"{len(values)} values, {len(calldatas)} calldatas"
        )

    if not description.strip():
        die("--description cannot be empty")

    # ── Step 1: Get wallet address ──
    step("setup")
    wallet_addr = get_wallet_address()

    # ── Step 2: Resolve token IDs ──
    if args.token_ids:
        token_ids = [t.strip() for t in args.token_ids.split(",") if t.strip()]
    else:
        step("getPositions")
        positions = rpc(
            "staking.getPositions", {"address": wallet_addr, "chainId": chain_id}
        )
        if not isinstance(positions, list):
            if isinstance(positions, dict):
                for key in ("items", "data", "positions"):
                    if isinstance(positions.get(key), list):
                        positions = positions[key]
                        break
                else:
                    positions = []
            else:
                positions = []
        token_ids = [
            str(p.get("tokenId")) for p in positions if p.get("tokenId") is not None
        ]
        if not token_ids:
            die(
                "No veAWP positions found. You need staked AWP (>= 200K) to create a proposal. "
                "Stake first: python3 scripts/relay-stake.py --amount 200000 --lock-days 90"
            )

    # ── Step 3: Show confirmation — executable proposals are dangerous ──
    info(
        f"EXECUTABLE PROPOSAL: {len(targets)} action(s) targeting "
        f"{', '.join(t[:10] + '...' for t in targets)}"
    )

    # ── Step 4: Call /prepare endpoint ──
    prepare_url = f"{RELAY_BASE}/relay/propose/prepare"
    step("prepare", endpoint=prepare_url)
    prepare_body = {
        "chainId": chain_id,
        "proposer": wallet_addr,
        "targets": targets,
        "values": values,
        "calldatas": calldatas,
        "description": description,
        "tokenIds": token_ids,
    }
    http_code, prepare_resp = api_post(prepare_url, prepare_body)
    if not (200 <= http_code < 300) or not isinstance(prepare_resp, dict):
        die(f"Prepare endpoint failed (HTTP {http_code}): {prepare_resp}")

    typed_data = prepare_resp.get("typedData")
    submit_to = prepare_resp.get("submitTo")
    if not isinstance(typed_data, dict) or not isinstance(submit_to, dict):
        die("Invalid prepare response: missing typedData or submitTo")

    submit_url = submit_to.get("url", f"{RELAY_BASE}/relay/propose")
    submit_body = submit_to.get("body")
    if not isinstance(submit_body, dict):
        die("Invalid prepare response: submitTo.body is not a dict")

    # ── Step 5: Validate critical fields ──
    step("validateTypedData")
    msg = typed_data.get("message", {})
    msg_proposer = (msg.get("proposer") or "").lower()
    if msg_proposer != wallet_addr.lower():
        die(
            f"Prepare returned wrong proposer: expected {wallet_addr}, got {msg.get('proposer')}"
        )
    if not submit_url.startswith(RELAY_BASE):
        die(f"Prepare returned untrusted submitTo.url: {submit_url}")

    # ── Step 6: Sign and submit ──
    step("sign")
    signature = wallet_sign_typed_data(token, typed_data)
    submit_body["signature"] = signature

    step("submitRelay", endpoint=submit_url, actions=len(targets))
    http_code, body = api_post(submit_url, submit_body)

    if not (200 <= http_code < 300):
        die(f"Relay returned HTTP {http_code}: {body}")

    info("Gasless executable proposal submitted successfully")
    result = body if isinstance(body, dict) else {"result": body}
    result["nextAction"] = "check_status"
    result["nextCommand"] = "python3 scripts/query-dao.py --mode active"
    print(json.dumps(result))


if __name__ == "__main__":
    main()
