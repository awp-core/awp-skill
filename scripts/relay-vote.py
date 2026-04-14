#!/usr/bin/env python3
"""Gasless DAO vote via /api/relay/vote/prepare + sign + submit.
No ETH needed. Uses the LLM-friendly /prepare endpoint — server returns
pre-built EIP-712 ExtendedBallot typedData, sign and submit.

If --token-ids is omitted, auto-discovers eligible veAWP positions via
governance.getEligibleTokens API.

Usage:
  python3 scripts/relay-vote.py --proposal 12345... --support 1 --reason "I support this"
  python3 scripts/relay-vote.py --proposal 12345... --support 0 --token-ids 1,2,3
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

_SUPPORT_LABELS = {0: "Against", 1: "For", 2: "Abstain"}


def main() -> None:
    parser = base_parser("Gasless DAO vote (no ETH needed)")
    parser.add_argument(
        "--proposal", required=True, help="Proposal ID (hex 0x... or decimal)"
    )
    parser.add_argument(
        "--support",
        required=True,
        type=int,
        choices=[0, 1, 2],
        help="0=Against, 1=For, 2=Abstain",
    )
    parser.add_argument("--reason", default="", help="Vote reason (optional)")
    parser.add_argument(
        "--token-ids",
        default="",
        help="Comma-separated veAWP token IDs (optional — auto-discovers if omitted)",
    )
    args = parser.parse_args()

    token: str = args.token
    proposal_id: str = args.proposal
    support: int = args.support
    reason: str = args.reason
    chain_id = get_chain_id()

    # ── Step 1: Get wallet address ──
    step("setup")
    wallet_addr = get_wallet_address()

    # ── Step 2: Resolve token IDs ──
    if args.token_ids:
        token_ids = [t.strip() for t in args.token_ids.split(",") if t.strip()]
    else:
        # Auto-discover eligible tokens via API
        step("getEligibleTokens")
        resp = rpc(
            "governance.getEligibleTokens",
            {
                "address": wallet_addr,
                "proposalId": proposal_id,
                "chainId": chain_id,
            },
        )
        if not isinstance(resp, dict):
            die(f"Could not fetch eligible tokens: {resp}")
        tokens = resp.get("tokens", [])
        # Filter: eligible AND not yet voted
        token_ids = [
            str(t.get("tokenId"))
            for t in tokens
            if t.get("eligible") and not t.get("hasVoted")
        ]
        if not token_ids:
            eligible_count = resp.get("eligibleCount", 0)
            if eligible_count == 0:
                die(
                    "No eligible veAWP positions for this proposal. "
                    "Positions must be created BEFORE the proposal was submitted."
                )
            else:
                die(
                    f"All {eligible_count} eligible positions have already voted on this proposal."
                )
        info(
            f"Auto-discovered {len(token_ids)} eligible token(s): {', '.join(token_ids)}"
        )

    if not token_ids:
        die("No token IDs provided and auto-discovery returned none")

    # ── Step 3: Call /prepare endpoint ──
    prepare_url = f"{RELAY_BASE}/relay/vote/prepare"
    step("prepare", endpoint=prepare_url)
    prepare_body = {
        "chainId": chain_id,
        "proposalId": proposal_id,
        "support": support,
        "voter": wallet_addr,
        "reason": reason,
        "tokenIds": token_ids,
    }
    http_code, prepare_resp = api_post(prepare_url, prepare_body)
    if not (200 <= http_code < 300) or not isinstance(prepare_resp, dict):
        die(f"Prepare endpoint failed (HTTP {http_code}): {prepare_resp}")

    typed_data = prepare_resp.get("typedData")
    submit_to = prepare_resp.get("submitTo")
    if not isinstance(typed_data, dict) or not isinstance(submit_to, dict):
        die("Invalid prepare response: missing typedData or submitTo")

    submit_url = submit_to.get("url", f"{RELAY_BASE}/relay/vote")
    submit_body = submit_to.get("body")
    if not isinstance(submit_body, dict):
        die("Invalid prepare response: submitTo.body is not a dict")

    # ── Step 4: Validate critical fields ──
    step("validateTypedData")
    msg = typed_data.get("message", {})
    msg_voter = (msg.get("voter") or "").lower()
    if msg_voter != wallet_addr.lower():
        die(
            f"Prepare returned wrong voter: expected {wallet_addr}, got {msg.get('voter')}"
        )
    # Compare proposalId as int — user may pass hex, server returns decimal
    try:
        local_pid = (
            int(proposal_id, 0) if isinstance(proposal_id, str) else int(proposal_id)
        )
        server_pid = int(str(msg.get("proposalId", "0")), 0)
        if local_pid != server_pid:
            die(
                f"Prepare returned wrong proposalId: expected {proposal_id}, got {msg.get('proposalId')}"
            )
    except (ValueError, TypeError):
        die(f"Prepare returned invalid proposalId: {msg.get('proposalId')}")
    try:
        if int(msg.get("support", -1)) != support:
            die(
                f"Prepare returned wrong support: expected {support}, got {msg.get('support')}"
            )
    except (ValueError, TypeError):
        die(f"Prepare returned invalid support value: {msg.get('support')}")
    if not submit_url.startswith(RELAY_BASE):
        die(f"Prepare returned untrusted submitTo.url: {submit_url}")

    # ── Step 5: Sign and submit ──
    step("sign")
    signature = wallet_sign_typed_data(token, typed_data)
    submit_body["signature"] = signature

    step(
        "submitRelay",
        endpoint=submit_url,
        support=_SUPPORT_LABELS.get(support, str(support)),
    )
    http_code, body = api_post(submit_url, submit_body)

    if not (200 <= http_code < 300):
        die(f"Relay returned HTTP {http_code}: {body}")

    info(f"Gasless vote successful: {_SUPPORT_LABELS.get(support, str(support))}")
    result = body if isinstance(body, dict) else {"result": body}
    result["nextAction"] = "check_status"
    result["nextCommand"] = f"python3 scripts/query-dao.py --proposal {proposal_id}"
    print(json.dumps(result))


if __name__ == "__main__":
    main()
