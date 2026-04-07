#!/usr/bin/env python3
"""On-chain proposal creation — AWP DAO governance
Supports two modes:
  - executable: proposeWithTokens(address[], uint256[], bytes[], string, uint256[])
    selector 0xb407dd87 — creates a proposal that executes on-chain actions if passed
  - signal: signalPropose(string, uint256[])
    selector 0xb1b5d01d — creates a signal-only proposal (no on-chain execution)
Both require veAWP positions whose aggregate voting power meets the proposalThreshold.
Requires ETH for gas.
"""
from awp_lib import *


# ── ABI encoding helpers ──


def encode_dynamic_string(s: str) -> str:
    """ABI-encode a dynamic string: length(32) + padded UTF-8 bytes"""
    raw = s.encode("utf-8")
    padded_len = ((len(raw) + 31) // 32) * 32
    enc = format(len(raw), "064x")
    enc += raw.hex().ljust(padded_len * 2, "0")
    return enc


def encode_uint256_array(values: list[int]) -> str:
    """ABI-encode a uint256[] (without leading offset): length + elements"""
    parts: list[str] = []
    parts.append(format(len(values), "064x"))
    for v in values:
        parts.append(pad_uint256(v))
    return "".join(parts)


def encode_address_array(addrs: list[str]) -> str:
    """ABI-encode an address[] (without leading offset): length + elements"""
    parts: list[str] = []
    parts.append(format(len(addrs), "064x"))
    for a in addrs:
        parts.append(pad_address(a))
    return "".join(parts)


def encode_bytes_array(items: list[bytes]) -> str:
    """ABI-encode a bytes[] (without leading offset): length + offsets + each bytes element

    Each element is itself a dynamic type (length + padded data).
    The offsets are relative to the start of the array data area (after length word).
    """
    n = len(items)
    # Each element's offset occupies n slots
    # Calculate each element's encoded size
    encoded_elements: list[str] = []
    for item in items:
        padded_len = ((len(item) + 31) // 32) * 32
        elem = format(len(item), "064x")
        elem += item.hex().ljust(padded_len * 2, "0")
        encoded_elements.append(elem)

    # Offset area: n 32-byte slots pointing to each element
    # First element offset = n * 32 (skip all offset slots)
    offsets: list[str] = []
    current_offset = n * 32
    for elem_hex in encoded_elements:
        offsets.append(format(current_offset, "064x"))
        current_offset += len(elem_hex) // 2  # hex chars / 2 = bytes

    parts: list[str] = []
    parts.append(format(n, "064x"))  # array length
    parts.extend(offsets)
    parts.extend(encoded_elements)
    return "".join(parts)


def build_signal_propose_calldata(description: str, token_ids: list[int]) -> str:
    """Build calldata for signalPropose(string description, uint256[] tokenIds)
    selector = 0xb1b5d01d
    Layout: selector + offset_description + offset_tokenIds + description_data + tokenIds_data
    """
    selector = "b1b5d01d"

    # 2 dynamic params, each with one offset slot
    # offset_description = 2 * 32 = 64
    desc_encoded = encode_dynamic_string(description)
    token_ids_encoded = encode_uint256_array(token_ids)

    offset_description = 2 * 32
    offset_token_ids = offset_description + len(desc_encoded) // 2

    head = format(offset_description, "064x") + format(offset_token_ids, "064x")

    return "0x" + selector + head + desc_encoded + token_ids_encoded


def build_executable_propose_calldata(
    targets: list[str],
    values: list[int],
    calldatas: list[bytes],
    description: str,
    token_ids: list[int],
) -> str:
    """Build calldata for proposeWithTokens(address[], uint256[], bytes[], string, uint256[])
    selector = 0xb407dd87
    Layout: selector + 5 offset slots + targets_data + values_data + calldatas_data + description_data + tokenIds_data
    """
    selector = "b407dd87"

    # Encode each dynamic segment
    targets_enc = encode_address_array(targets)
    values_enc = encode_uint256_array(values)
    calldatas_enc = encode_bytes_array(calldatas)
    desc_enc = encode_dynamic_string(description)
    token_ids_enc = encode_uint256_array(token_ids)

    # 5 offset slots, 32 bytes each
    header_size = 5 * 32  # 160 bytes

    # Calculate each segment's offset (relative to params area start)
    offset_targets = header_size
    offset_values = offset_targets + len(targets_enc) // 2
    offset_calldatas = offset_values + len(values_enc) // 2
    offset_description = offset_calldatas + len(calldatas_enc) // 2
    offset_token_ids = offset_description + len(desc_enc) // 2

    head = (
        format(offset_targets, "064x")
        + format(offset_values, "064x")
        + format(offset_calldatas, "064x")
        + format(offset_description, "064x")
        + format(offset_token_ids, "064x")
    )

    return "0x" + selector + head + targets_enc + values_enc + calldatas_enc + desc_enc + token_ids_enc


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Create AWP DAO proposal")
    parser.add_argument("--mode", required=True, choices=["executable", "signal"],
                        help="Proposal mode: executable (on-chain actions) or signal (advisory)")
    parser.add_argument("--description", required=True, help="Proposal description text")
    parser.add_argument("--token-ids", required=True,
                        help="Comma-separated veAWP position IDs for voting power threshold")
    # Executable-mode-only arguments
    parser.add_argument("--targets", default="",
                        help="Comma-separated target addresses (executable mode only)")
    parser.add_argument("--values", default="",
                        help="Comma-separated wei amounts (executable mode only)")
    parser.add_argument("--calldatas", default="",
                        help="Comma-separated hex calldata strings (executable mode only)")
    args = parser.parse_args()

    mode: str = args.mode
    description: str = args.description

    if not description.strip():
        die("--description must not be empty")

    # Parse token IDs
    token_id_strs = [s.strip() for s in args.token_ids.split(",") if s.strip()]
    if not token_id_strs:
        die("--token-ids must contain at least one position ID")
    token_ids = [validate_positive_int(tid, "token-ids") for tid in token_id_strs]

    # Executable mode requires additional arguments
    targets: list[str] = []
    values_wei: list[int] = []
    calldatas_bytes: list[bytes] = []

    if mode == "executable":
        if not args.targets or not args.values or not args.calldatas:
            die("Executable mode requires --targets, --values, and --calldatas")

        targets = [s.strip() for s in args.targets.split(",") if s.strip()]
        value_strs = [s.strip() for s in args.values.split(",") if s.strip()]
        calldata_strs = [s.strip() for s in args.calldatas.split(",") if s.strip()]

        if not (len(targets) == len(value_strs) == len(calldata_strs)):
            die(f"Mismatch: {len(targets)} targets, {len(value_strs)} values, "
                f"{len(calldata_strs)} calldatas — all must have the same count")

        for t in targets:
            validate_address(t, "targets")

        for v in value_strs:
            if not re.match(r"^[0-9]+$", v):
                die(f"Invalid --values entry: {v} (must be a non-negative integer in wei)")
            values_wei.append(int(v))

        for cd in calldata_strs:
            if not cd.startswith("0x"):
                die(f"Invalid --calldatas entry: {cd} (must start with 0x)")
            try:
                calldatas_bytes.append(bytes.fromhex(cd[2:]))
            except ValueError:
                die(f"Invalid --calldatas entry: {cd} (invalid hex)")

    # ── Pre-checks ──
    wallet_addr = get_wallet_address()
    validate_address(wallet_addr, "wallet")

    registry = get_registry()
    dao_addr = require_contract(registry, "dao")

    # Read proposalThreshold — selector 0xb58131b0 (no params)
    threshold_hex = rpc_call(dao_addr, "0xb58131b0")
    if not threshold_hex or threshold_hex in ("null", "0x"):
        die("Could not read proposalThreshold from DAO contract")
    proposal_threshold = hex_to_int(threshold_hex)
    step("proposalThreshold", threshold=proposal_threshold)

    # Fetch user veAWP positions, verify the specified token IDs exist
    positions = rpc("staking.getPositions", {"address": wallet_addr})
    if not isinstance(positions, list):
        die("Unexpected positions response")

    def _field(p: dict, *names: str) -> object | None:
        for n in names:
            if n in p:
                return p[n]
        return None

    owned_ids: set[int] = set()
    for p in positions:
        tok = _field(p, "tokenId", "token_id")
        if tok is not None:
            try:
                owned_ids.add(int(tok))
            except (ValueError, TypeError):
                continue

    missing = [tid for tid in token_ids if tid not in owned_ids]
    if missing:
        die(f"Token IDs not found in your positions: {missing}")

    step("eligibleTokenIds", tokenIds=token_ids)

    # ── Build calldata ──
    if mode == "signal":
        calldata = build_signal_propose_calldata(description, token_ids)
        step("signalPropose", dao=dao_addr, description=description[:80])
    else:
        calldata = build_executable_propose_calldata(
            targets, values_wei, calldatas_bytes, description, token_ids
        )
        step("proposeWithTokens", dao=dao_addr, targets=targets,
             description=description[:80])

    result = wallet_send(args.token, dao_addr, calldata)
    print(result)


if __name__ == "__main__":
    main()
