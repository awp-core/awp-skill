#!/usr/bin/env python3
"""Read-only DAO governance overview — no wallet token needed.
Queries governance stats, active proposals, voting power, proposal details.

Usage:
  python3 scripts/query-dao.py                                      # DAO overview + active proposals
  python3 scripts/query-dao.py --proposal 12345...                  # Proposal detail + quorum + timeline
  python3 scripts/query-dao.py --address 0x... --mode power         # Voting power for address
  python3 scripts/query-dao.py --address 0x... --mode history       # Vote + proposal history
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from awp_lib import (
    ADDR_RE,
    die,
    get_wallet_address,
    rpc,
    step,
)


def wei_to_awp(wei_str: str | int) -> str:
    """Convert wei string to human-readable AWP amount."""
    try:
        return f"{int(wei_str) / 10**18:,.4f}"
    except (ValueError, TypeError):
        return str(wei_str)


def main() -> None:
    parser = argparse.ArgumentParser(description="DAO governance overview (read-only)")
    parser.add_argument("--address", default="", help="Wallet address (optional)")
    parser.add_argument(
        "--token", default="", help="awp-wallet session token (optional)"
    )
    parser.add_argument("--proposal", default="", help="Proposal ID for detail view")
    parser.add_argument(
        "--mode",
        default="overview",
        choices=["overview", "active", "proposal", "power", "history"],
        help="Query mode (default: overview)",
    )
    args = parser.parse_args()

    # Resolve address
    addr: str = ""
    if args.address:
        if not ADDR_RE.match(args.address):
            die(f"Invalid address format: {args.address}")
        addr = args.address
    elif args.token:
        addr = get_wallet_address()

    output: dict = {"mode": args.mode}

    # ── Overview mode: stats + active proposals ──
    if args.mode == "overview":
        step("getStats")
        stats = rpc("governance.getStats", {})
        if isinstance(stats, dict):
            output["stats"] = stats

        step("getActive")
        active = rpc("governance.getActive", {"limit": 10})
        active_list: list = []
        if isinstance(active, dict):
            active_list = active.get("items", [])
        elif isinstance(active, list):
            active_list = active
        output["activeProposals"] = active_list
        output["activeCount"] = len(active_list)

        # Hints
        hints: list[str] = []
        if active_list:
            hints.append(
                f"{len(active_list)} active proposal(s) — vote with relay-vote.py"
            )
        if addr:
            output["nextAction"] = "check_power"
            output["nextCommand"] = (
                f"python3 scripts/query-dao.py --address {addr} --mode power"
            )
        else:
            output["nextAction"] = "info_only"
        if hints:
            output["hints"] = hints

    # ── Active mode: active proposals with more detail ──
    elif args.mode == "active":
        step("getActive")
        active = rpc("governance.getActive", {"limit": 20})
        active_list = []
        if isinstance(active, dict):
            active_list = active.get("items", [])
        elif isinstance(active, list):
            active_list = active
        output["proposals"] = active_list
        output["count"] = len(active_list)
        output["nextAction"] = "info_only"

    # ── Proposal mode: single proposal detail ──
    elif args.mode == "proposal":
        if not args.proposal:
            die("--proposal is required for proposal mode")

        step("getProposal")
        proposal = rpc("governance.getProposal", {"proposalId": args.proposal})
        if isinstance(proposal, dict):
            output["proposal"] = proposal

        step("getQuorumProgress")
        try:
            quorum = rpc("governance.getQuorumProgress", {"proposalId": args.proposal})
        except SystemExit:
            quorum = None
        if isinstance(quorum, dict):
            output["quorum"] = quorum

        step("getTimeline")
        try:
            timeline = rpc("governance.getTimeline", {"proposalId": args.proposal})
        except SystemExit:
            timeline = None
        if isinstance(timeline, dict):
            output["timeline"] = timeline

        # If address provided, show voter status
        if addr:
            step("getVoterPower")
            try:
                voter = rpc(
                    "governance.getVoterPower",
                    {
                        "proposalId": args.proposal,
                        "voter": addr,
                    },
                )
            except SystemExit:
                voter = None
            if isinstance(voter, dict):
                output["voterStatus"] = voter

        # Hints
        hints = []
        if isinstance(proposal, dict):
            state = proposal.get("state", "")
            if state == "Active" and addr:
                voter_data = output.get("voterStatus", {})
                if not voter_data.get("hasVoted"):
                    hints.append("Proposal is active and you haven't voted yet")
                    output["nextAction"] = "vote"
                    output["nextCommand"] = (
                        f"python3 scripts/relay-vote.py --proposal {args.proposal} "
                        f"--support <0|1|2>"
                    )
            elif state == "Succeeded":
                hints.append("Proposal succeeded — can be queued for execution")
            elif state == "Queued":
                eta = proposal.get("queueEta", 0)
                hints.append(f"Proposal queued — executable after ETA timestamp {eta}")
        if hints:
            output["hints"] = hints
        if "nextAction" not in output:
            output["nextAction"] = "info_only"

    # ── Power mode: voting power for address ──
    elif args.mode == "power":
        if not addr:
            die("--address or --token required for power mode")

        step("getVotingPower")
        power = rpc("governance.getVotingPower", {"address": addr})
        if isinstance(power, dict):
            output["votingPower"] = power

        step("getUserVoteHistory")
        try:
            history = rpc(
                "governance.getUserVoteHistory", {"address": addr, "limit": 5}
            )
        except SystemExit:
            history = None
        if isinstance(history, dict):
            output["recentVotes"] = history.get("items", [])
            output["totalVotes"] = history.get("total", 0)

        hints = []
        if isinstance(power, dict):
            total_power = power.get("totalPower", "0")
            try:
                if int(total_power) > 0:
                    hints.append(f"Voting power: {total_power}")
                else:
                    hints.append(
                        "No voting power — stake AWP to participate in governance"
                    )
            except (ValueError, TypeError):
                pass
        if hints:
            output["hints"] = hints
        output["nextAction"] = "info_only"

    # ── History mode: full participation history ──
    elif args.mode == "history":
        if not addr:
            die("--address or --token required for history mode")

        step("getUserVoteHistory")
        votes = rpc("governance.getUserVoteHistory", {"address": addr, "limit": 20})
        if isinstance(votes, dict):
            output["voteHistory"] = votes.get("items", [])
            output["totalVotes"] = votes.get("total", 0)

        step("getUserProposals")
        try:
            proposals = rpc(
                "governance.getUserProposals", {"address": addr, "limit": 20}
            )
        except SystemExit:
            proposals = None
        if isinstance(proposals, dict):
            output["submittedProposals"] = proposals.get("items", [])
            output["totalProposals"] = proposals.get("total", 0)

        output["nextAction"] = "info_only"

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
