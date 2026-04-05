#!/usr/bin/env python3
"""On-chain voting — AWP DAO proposal voting
castVoteWithReasonAndParams(uint256,uint8,string,bytes)
params = abi.encode(uint256[] tokenIds) — eligible veAWP positions only
Requires ETH for gas.
"""
import json

from awp_lib import *

SUPPORT_LABELS = {0: "Against", 1: "For", 2: "Abstain"}


def abi_encode_uint256_array(values: list[int]) -> str:
    """ABI-encode uint256[] — offset + length + elements"""
    parts: list[str] = []
    # offset points to the start of the array data (32 bytes)
    parts.append(format(32, "064x"))
    # array length
    parts.append(format(len(values), "064x"))
    # each element
    for v in values:
        parts.append(format(v, "064x"))
    return "0x" + "".join(parts)


def encode_vote_calldata(proposal_id: int, support: int, reason: str, params_hex: str) -> str:
    """Build full calldata for castVoteWithReasonAndParams
    selector = 0x5f398a14
    Parameter layout: proposalId(static) + support(static) + offset_reason(dynamic) + offset_params(dynamic)
    """
    params_bytes = bytes.fromhex(params_hex.replace("0x", ""))
    reason_bytes = reason.encode("utf-8")

    selector = "5f398a14"

    # proposalId — static
    slot0 = format(proposal_id, "064x")
    # support — static uint8
    slot1 = format(support, "064x")
    # offset to reason data — 4 * 32 = 128
    slot2 = format(128, "064x")

    # reason encoding: length(32) + ceil(len/32)*32
    reason_padded_len = ((len(reason_bytes) + 31) // 32) * 32
    offset_params = 128 + 32 + reason_padded_len
    slot3 = format(offset_params, "064x")

    # encode reason (string)
    reason_enc = format(len(reason_bytes), "064x")
    reason_enc += reason_bytes.hex().ljust(reason_padded_len * 2, "0")

    # encode params (bytes)
    params_padded_len = ((len(params_bytes) + 31) // 32) * 32
    params_enc = format(len(params_bytes), "064x")
    params_enc += params_bytes.hex().ljust(params_padded_len * 2, "0")

    return "0x" + selector + slot0 + slot1 + slot2 + slot3 + reason_enc + params_enc


def main() -> None:
    # ── Argument parsing ──
    parser = base_parser("Vote on AWP DAO proposal")
    parser.add_argument("--proposal", required=True, help="Proposal ID")
    parser.add_argument("--support", required=True, help="0=Against, 1=For, 2=Abstain")
    parser.add_argument("--reason", default="", help="Voting reason (optional)")
    args = parser.parse_args()

    proposal_id = validate_positive_int(args.proposal, "proposal")

    # Validate support value
    if args.support not in ("0", "1", "2"):
        die("Invalid --support: must be 0 (Against), 1 (For), or 2 (Abstain)")
    support = int(args.support)
    reason: str = args.reason

    # ── Pre-checks ──
    wallet_addr = get_wallet_address()
    validate_address(wallet_addr, "wallet")

    registry = get_registry()
    dao_addr = require_contract(registry, "dao")

    # ── Step 1: fetch proposalCreatedAt — selector = 0x5f9103b2 ──
    proposal_padded = pad_uint256(proposal_id)
    created_at_hex = rpc_call(dao_addr, encode_calldata("0x5f9103b2", proposal_padded))

    if not created_at_hex or created_at_hex in ("null", "0x"):
        die("Could not fetch proposalCreatedAt — proposal may not exist")

    proposal_created_at = hex_to_int(created_at_hex)
    if proposal_created_at == 0:
        die(f"Proposal {proposal_id} does not exist (createdAt=0)")

    step("proposalCreatedAt", proposalId=proposal_id, createdAt=proposal_created_at)

    # ── Step 2: fetch user positions ──
    positions = rpc("staking.getPositions", {"address": wallet_addr})
    if not isinstance(positions, list):
        die("Unexpected positions response")

    # ── Step 3: filter eligible positions (created_at < proposalCreatedAt, strictly less than) ──
    eligible_ids: list[int] = []
    for p in positions:
        if "token_id" not in p or "created_at" not in p:
            continue
        try:
            created = int(p["created_at"])
        except (ValueError, TypeError):
            continue
        if created < proposal_created_at:
            eligible_ids.append(int(p["token_id"]))

    if not eligible_ids:
        die(
            f"No eligible positions: all positions were created at or after proposal creation "
            f"timestamp ({proposal_created_at}). You need veAWP positions created before the proposal."
        )

    step("eligibleTokenIds", tokenIds=eligible_ids)

    # ── Step 4: ABI-encode params = abi.encode(uint256[] tokenIds) ──
    abi_params = abi_encode_uint256_array(eligible_ids)

    # ── Step 5: build castVoteWithReasonAndParams calldata ──
    calldata = encode_vote_calldata(proposal_id, support, reason, abi_params)

    support_label = SUPPORT_LABELS.get(support, "Unknown")
    step("castVote", proposalId=proposal_id, support=support_label,
         reason=reason, dao=dao_addr)
    result = wallet_send(args.token, dao_addr, calldata)
    print(result)


if __name__ == "__main__":
    main()
