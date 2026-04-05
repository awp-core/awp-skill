#!/usr/bin/env python3
"""On-chain worknet settings update — setSkillsURI or setMinStake.
These calls target the AWPWorkNet NFT contract, NOT AWPRegistry.
Only the NFT owner may operate. Requires ETH for gas.
"""
import re

from awp_lib import *


def encode_set_skills_uri(worknet_id: int, uri: str) -> str:
    """Encode setSkillsURI(uint256, string) — selector = 0x7c2f4cd6"""
    uri_bytes = uri.encode("utf-8")
    uri_len = len(uri_bytes)
    padded_len = ((uri_len + 31) // 32) * 32
    uri_hex = uri_bytes.hex().ljust(padded_len * 2, "0")

    selector = "0x7c2f4cd6"
    # tokenId
    p1 = pad_uint256(worknet_id)
    # offset pointing to string data (2 * 32 = 64 bytes)
    p2 = pad_uint256(64)
    # string: length + padded data
    str_len = pad_uint256(uri_len)

    return selector + p1 + p2 + str_len + uri_hex


def encode_set_min_stake(worknet_id: int, min_stake: int) -> str:
    """Encode setMinStake(uint256, uint128) — selector = 0x63a9bbe5"""
    return encode_calldata("0x63a9bbe5", pad_uint256(worknet_id), pad_uint256(min_stake))


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Update worknet settings: setSkillsURI or setMinStake")
    # Kept --worknet as the CLI flag for SKILL.md backward-compat; internally we call it worknet.
    parser.add_argument("--worknet", required=True, help="Worknet ID")
    parser.add_argument("--skills-uri", default="", help="new skills URI")
    parser.add_argument("--min-stake", default="", help="new minimum stake amount (wei)")
    args = parser.parse_args()

    worknet_id = validate_positive_int(args.worknet, "worknet")
    skills_uri: str = args.skills_uri
    min_stake_str: str = args.min_stake

    # Mutual exclusion validation
    if not skills_uri and not min_stake_str:
        die("Provide --skills-uri or --min-stake")
    if skills_uri and min_stake_str:
        die("Provide only one of --skills-uri or --min-stake per call")

    # Validate min-stake — setMinStake(uint256,uint128) on AWPWorkNet
    min_stake: int = 0
    if min_stake_str:
        if not re.match(r"^[0-9]+$", min_stake_str):
            die("Invalid --min-stake: must be a non-negative integer (wei)")
        min_stake = validate_uint128(int(min_stake_str), "min-stake")

    # ── Pre-checks ──
    registry = get_registry()
    awp_worknet = require_contract(registry, "awpWorkNet")

    # ── Build calldata and send ──
    if skills_uri:
        calldata = encode_set_skills_uri(worknet_id, skills_uri)
        step("setSkillsURI", worknet=worknet_id, skillsURI=skills_uri,
             target=f"AWPWorkNet ({awp_worknet})")
    else:
        calldata = encode_set_min_stake(worknet_id, min_stake)
        step("setMinStake", worknet=worknet_id, minStake=min_stake_str,
             target=f"AWPWorkNet ({awp_worknet})")

    result = wallet_send(args.token, awp_worknet, calldata)
    print(result)


if __name__ == "__main__":
    main()
