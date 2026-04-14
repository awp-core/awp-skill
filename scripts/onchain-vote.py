#!/usr/bin/env python3
"""On-chain voting — AWP DAO proposal voting
castVoteWithReasonAndParams(uint256,uint8,string,bytes)
params = abi.encode(uint256[] tokenIds) — eligible veAWP positions only
Requires ETH for gas.
"""

from awp_lib import *

SUPPORT_LABELS = {0: "Against", 1: "For", 2: "Abstain"}


def abi_encode_uint256_array(values: list[int]) -> str:
    """ABI-encode uint256[] as a standalone tuple: 0x + offset(32) + length + elements.

    Uses awp_lib.encode_uint256_array (length + elements) as the building block,
    then wraps with offset header and 0x prefix.
    """
    inner = encode_uint256_array(values)  # length + elements (no offset, no 0x)
    return "0x" + pad_uint256(32) + inner


def encode_vote_calldata(
    proposal_id: int, support: int, reason: str, params_hex: str
) -> str:
    """Build full calldata for castVoteWithReasonAndParams
    selector = 0x5f398a14
    Parameter layout: proposalId(static) + support(static) + offset_reason(dynamic) + offset_params(dynamic)
    """
    params_bytes = bytes.fromhex(params_hex.replace("0x", ""))
    reason_bytes = reason.encode("utf-8")

    # 4 head slots: proposalId(static) + support(static) + offset_reason + offset_params
    reason_padded_len = ((len(reason_bytes) + 31) // 32) * 32
    offset_params = 128 + 32 + reason_padded_len

    # Head portion routed through encode_calldata for selector format validation
    head = encode_calldata(
        "0x5f398a14",
        pad_uint256(proposal_id),
        pad_uint256(support),
        pad_uint256(128),  # offset to reason
        pad_uint256(offset_params),
    )

    # reason (string) — dynamic tail
    reason_enc = format(len(reason_bytes), "064x")
    reason_enc += reason_bytes.hex().ljust(reason_padded_len * 2, "0")

    # params (bytes) — dynamic tail
    params_padded_len = ((len(params_bytes) + 31) // 32) * 32
    params_enc = format(len(params_bytes), "064x")
    params_enc += params_bytes.hex().ljust(params_padded_len * 2, "0")

    return head + reason_enc + params_enc


def main() -> None:
    # ── Argument parsing ──
    parser = base_parser("Vote on AWP DAO proposal")
    parser.add_argument("--proposal", required=True, help="Proposal ID")
    parser.add_argument("--support", required=True, help="0=Against, 1=For, 2=Abstain")
    parser.add_argument("--reason", default="", help="Voting reason (optional)")
    args = parser.parse_args()

    proposal_id = parse_proposal_id(args.proposal)

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
        if isinstance(positions, dict):
            for key in ("items", "data", "positions"):
                if isinstance(positions.get(key), list):
                    positions = positions[key]
                    break
            else:
                die("Unexpected positions response")
        else:
            die("Unexpected positions response")

    # ── Step 3: filter eligible positions (createdAt < proposalCreatedAt, strictly less than) ──
    # The API is camelCase per skill-reference.md (tokenId, createdAt), but historical
    # deployments have exposed snake_case (token_id, created_at). Accept either shape
    # so votes don't silently fail if the server switches conventions.
    def _field(p: dict, *names: str) -> object | None:
        for n in names:
            if n in p:
                return p[n]
        return None

    eligible_ids: list[int] = []
    for p in positions:
        tok = _field(p, "tokenId", "token_id")
        created_raw = _field(p, "createdAt", "created_at")
        if tok is None or created_raw is None:
            continue
        try:
            created = int(created_raw)
            token_id_int = int(tok)
        except (ValueError, TypeError):
            continue
        if created < proposal_created_at:
            eligible_ids.append(token_id_int)

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
    step(
        "castVote",
        proposalId=proposal_id,
        support=support_label,
        reason=reason,
        dao=dao_addr,
    )
    result = wallet_send(args.token, dao_addr, calldata)
    print(result)


if __name__ == "__main__":
    main()
