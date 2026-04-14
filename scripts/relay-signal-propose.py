#!/usr/bin/env python3
"""Gasless signal proposal via /api/relay/signal-propose/prepare + sign + submit.
No ETH needed. Signal proposals are community sentiment polls with no on-chain
execution — only title + body go on-chain (body stored as contentHash for gas savings).

Usage:
  python3 scripts/relay-signal-propose.py --title "Should we expand to Solana?" --body "Full rationale..."
  python3 scripts/relay-signal-propose.py --title "..." --body @proposal.md  (read body from file)
"""

from __future__ import annotations

import json

from awp_lib import (
    RELAY_BASE,
    api_post,
    base_parser,
    die,
    get_chain_id,
    get_wallet_address,
    info,
    rpc,
    step,
    wallet_sign_typed_data,
)


def main() -> None:
    parser = base_parser("Gasless signal proposal (no ETH needed)")
    parser.add_argument("--title", required=True, help="Proposal title")
    parser.add_argument(
        "--body",
        required=True,
        help="Proposal body text (or @filename to read from file)",
    )
    parser.add_argument(
        "--token-ids",
        default="",
        help="Comma-separated veAWP token IDs (optional — auto-discovers if omitted)",
    )
    args = parser.parse_args()

    token: str = args.token
    title: str = args.title
    chain_id = get_chain_id()

    # Read body from file if @filename syntax
    body_arg: str = args.body
    if body_arg.startswith("@"):
        filepath = body_arg[1:]
        try:
            with open(filepath, encoding="utf-8") as f:
                body_text = f.read()
        except (OSError, IOError) as e:
            die(f"Could not read body from file {filepath}: {e}")
    else:
        body_text = body_arg

    if not title.strip():
        die("--title cannot be empty")
    if not body_text.strip():
        die("--body cannot be empty")

    # ── Step 1: Get wallet address ──
    step("setup")
    wallet_addr = get_wallet_address()

    # ── Step 2: Resolve token IDs (need >= 200K AWP staked to propose) ──
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
        info(f"Using {len(token_ids)} veAWP position(s) for proposal threshold check")

    # ── Step 3: Call /prepare endpoint ──
    prepare_url = f"{RELAY_BASE}/relay/signal-propose/prepare"
    step("prepare", endpoint=prepare_url)
    prepare_body = {
        "chainId": chain_id,
        "proposer": wallet_addr,
        "title": title,
        "body": body_text,
        "tokenIds": token_ids,
    }
    http_code, prepare_resp = api_post(prepare_url, prepare_body)
    if not (200 <= http_code < 300) or not isinstance(prepare_resp, dict):
        die(f"Prepare endpoint failed (HTTP {http_code}): {prepare_resp}")

    typed_data = prepare_resp.get("typedData")
    submit_to = prepare_resp.get("submitTo")
    if not isinstance(typed_data, dict) or not isinstance(submit_to, dict):
        die("Invalid prepare response: missing typedData or submitTo")

    submit_url = submit_to.get("url", f"{RELAY_BASE}/relay/signal-propose")
    submit_body = submit_to.get("body")
    if not isinstance(submit_body, dict):
        die("Invalid prepare response: submitTo.body is not a dict")

    content_hash = prepare_resp.get("contentHash", "")

    # ── Step 4: Validate critical fields ──
    step("validateTypedData")
    msg = typed_data.get("message", {})
    msg_proposer = (msg.get("proposer") or "").lower()
    if msg_proposer != wallet_addr.lower():
        die(
            f"Prepare returned wrong proposer: expected {wallet_addr}, got {msg.get('proposer')}"
        )
    if not submit_url.startswith(RELAY_BASE):
        die(f"Prepare returned untrusted submitTo.url: {submit_url}")

    info(f"Content hash: {content_hash}")

    # ── Step 5: Sign and submit ──
    step("sign")
    signature = wallet_sign_typed_data(token, typed_data)
    submit_body["signature"] = signature

    step("submitRelay", endpoint=submit_url, title=title[:50])
    http_code, body = api_post(submit_url, submit_body)

    if not (200 <= http_code < 300):
        die(f"Relay returned HTTP {http_code}: {body}")

    info("Gasless signal proposal submitted successfully")
    result = body if isinstance(body, dict) else {"result": body}
    result["nextAction"] = "check_status"
    result["nextCommand"] = "python3 scripts/query-dao.py --mode active"
    print(json.dumps(result))


if __name__ == "__main__":
    main()
