#!/usr/bin/env python3
"""Query worknet details — read-only, no wallet token needed.
Fetches comprehensive worknet info from the API:
  - Basic info: name, symbol, status, chain, owner, minStake
  - Skills URI
  - Agent count and top agents (ranked by stake)
  - Earnings summary (latest epochs)

Usage:
  python3 scripts/query-worknet.py --worknet 1
  python3 scripts/query-worknet.py --worknet 845300000001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from awp_lib import (
    die,
    expand_worknet_id,
    info,
    rpc,
    step,
    validate_positive_int,
)

_CHAIN_NAMES: dict[int, str] = {
    1: "Ethereum",
    56: "BSC",
    8453: "Base",
    42161: "Arbitrum",
}


def wei_to_awp(wei_str: str | int) -> str:
    """Convert wei string to human-readable AWP amount."""
    try:
        return f"{int(wei_str) / 10**18:,.4f}"
    except (ValueError, TypeError):
        return str(wei_str)


def chain_name(worknet_id: int) -> str:
    """Derive chain name from worknetId format."""
    cid = worknet_id // 100_000_000
    return _CHAIN_NAMES.get(cid, f"chain:{cid}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query worknet details (read-only)")
    parser.add_argument("--worknet", required=True, help="Worknet ID (short or full)")
    parser.add_argument(
        "--agents",
        type=int,
        default=10,
        help="Number of top agents to show (default: 10)",
    )
    args = parser.parse_args()

    wid = validate_positive_int(args.worknet, "worknet")
    wid = expand_worknet_id(wid)

    step("queryWorknet", worknetId=wid)

    # ── Fetch worknet details ──
    # rpc() calls die() (sys.exit) on API errors before returning, so catch
    # SystemExit to produce a clean JSON error for this read-only script.
    try:
        worknet = rpc("subnets.get", {"worknetId": str(wid)})
    except SystemExit:
        print(json.dumps({"error": f"Worknet {wid} not found or API error"}))
        sys.exit(1)
    if not isinstance(worknet, dict):
        print(json.dumps({"error": f"Worknet {wid} not found or API error"}))
        sys.exit(1)

    # ── Build output ──
    output: dict = {"worknetId": wid, "chain": chain_name(wid)}

    # Basic fields (handle both camelCase and snake_case)
    def _f(obj: dict, *names: str, default: object = "") -> object:
        for n in names:
            if n in obj and obj[n] is not None:
                return obj[n]
        return default

    output["name"] = _f(worknet, "name", default="Unknown")
    output["symbol"] = _f(worknet, "symbol", default="")
    output["status"] = _f(worknet, "status", default="")
    output["owner"] = _f(worknet, "owner", default="")

    min_stake = _f(worknet, "minStake", "min_stake", default="0")
    output["minStake"] = wei_to_awp(min_stake)
    output["minStake_wei"] = str(min_stake)

    total_staked = _f(worknet, "totalStaked", "total_staked", default="0")
    output["totalStaked"] = wei_to_awp(total_staked)

    alpha_token = _f(worknet, "alphaToken", "alpha_token", default="")
    if alpha_token:
        output["alphaToken"] = alpha_token

    lp_pool = _f(worknet, "lpPool", "lp_pool", default="")
    if lp_pool:
        output["lpPool"] = lp_pool

    created = _f(worknet, "createdAt", "created_at", default="")
    if created:
        output["createdAt"] = created

    # ── Fetch skills URI (non-critical — graceful fallback on error) ──
    try:
        skills = rpc("subnets.getSkills", {"worknetId": str(wid)})
    except SystemExit:
        skills = None
    if isinstance(skills, dict):
        skills_uri = _f(skills, "skillsURI", "skills_uri", default="")
        output["skillsURI"] = skills_uri if skills_uri else "(none)"
    elif isinstance(skills, str) and skills:
        output["skillsURI"] = skills
    else:
        output["skillsURI"] = "(none)"

    # ── Fetch top agents (non-critical) ──
    try:
        agents_resp = rpc(
            "subnets.listAgents",
            {"worknetId": str(wid), "limit": args.agents},
        )
    except SystemExit:
        agents_resp = None
    agent_list: list[dict] = []
    raw_agents: list = []
    if isinstance(agents_resp, list):
        raw_agents = agents_resp
    elif isinstance(agents_resp, dict):
        for key in ("items", "data", "agents"):
            if isinstance(agents_resp.get(key), list):
                raw_agents = agents_resp[key]
                break

    for a in raw_agents:
        agent_addr = a.get("agent") or a.get("address", "")
        stake = a.get("stake") or a.get("amount", "0")
        try:
            if int(stake) == 0 and not agent_addr:
                continue
        except (ValueError, TypeError):
            continue
        agent_list.append(
            {
                "agent": agent_addr,
                "stake": wei_to_awp(stake),
                "stake_wei": str(stake),
            }
        )

    output["agentCount"] = len(agent_list)
    output["topAgents"] = agent_list

    # ── Fetch recent earnings (non-critical) ──
    try:
        earnings_resp = rpc(
            "subnets.getEarnings",
            {"worknetId": str(wid), "limit": 5},
        )
    except SystemExit:
        earnings_resp = None
    earnings_list: list[dict] = []
    raw_earnings: list = []
    if isinstance(earnings_resp, list):
        raw_earnings = earnings_resp
    elif isinstance(earnings_resp, dict):
        for key in ("items", "data", "earnings"):
            if isinstance(earnings_resp.get(key), list):
                raw_earnings = earnings_resp[key]
                break

    for e in raw_earnings:
        epoch = e.get("epoch", "?")
        amount = e.get("amount") or e.get("reward", "0")
        earnings_list.append(
            {
                "epoch": epoch,
                "amount": wei_to_awp(amount),
            }
        )

    if earnings_list:
        output["recentEarnings"] = earnings_list

    # ── Hints ──
    hints: list[str] = []
    status = output.get("status", "")
    if status == "Paused":
        hints.append("Worknet is paused — no new work accepted until resumed.")
    elif status == "Banned":
        hints.append("Worknet is banned — allocations are frozen.")
    elif status == "Pending":
        hints.append("Worknet is pending activation — not yet accepting work.")

    try:
        ms = int(min_stake)
    except (ValueError, TypeError):
        ms = 0
    if ms == 0:
        hints.append("FREE — no staking required to join this worknet.")
    else:
        hints.append(f"Requires minimum {wei_to_awp(min_stake)} AWP staked to join.")

    if output.get("skillsURI") and output["skillsURI"] != "(none)":
        hints.append("Has skills definition — install to see worknet capabilities.")

    if hints:
        output["hints"] = hints

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
