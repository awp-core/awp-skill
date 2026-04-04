#!/usr/bin/env python3
"""On-chain subnet settings update — setSkillsURI or setMinStake (V2)
Important: these calls are sent to the SubnetNFT contract, NOT AWPRegistry!
Only the NFT owner may operate. Requires ETH for gas.
"""
import re

from awp_lib import *


def encode_set_skills_uri(subnet_id: int, uri: str) -> str:
    """Encode setSkillsURI(uint256, string) — selector = 0x7c2f4cd6"""
    uri_bytes = uri.encode("utf-8")
    uri_len = len(uri_bytes)
    padded_len = ((uri_len + 31) // 32) * 32
    uri_hex = uri_bytes.hex().ljust(padded_len * 2, "0")

    selector = "0x7c2f4cd6"
    # tokenId
    p1 = pad_uint256(subnet_id)
    # offset pointing to string data (2 * 32 = 64 bytes)
    p2 = pad_uint256(64)
    # string: length + padded data
    str_len = pad_uint256(uri_len)

    return selector + p1 + p2 + str_len + uri_hex


def encode_set_min_stake(subnet_id: int, min_stake: int) -> str:
    """Encode setMinStake(uint256, uint128) — selector = 0x63a9bbe5"""
    return encode_calldata("0x63a9bbe5", pad_uint256(subnet_id), pad_uint256(min_stake))


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Update subnet settings: setSkillsURI or setMinStake")
    parser.add_argument("--subnet", required=True, help="Subnet ID")
    parser.add_argument("--skills-uri", default="", help="new skills URI")
    parser.add_argument("--min-stake", default="", help="new minimum stake amount (wei)")
    args = parser.parse_args()

    subnet_id = validate_positive_int(args.subnet, "subnet")
    skills_uri: str = args.skills_uri
    min_stake_str: str = args.min_stake

    # Mutual exclusion validation
    if not skills_uri and not min_stake_str:
        die("Provide --skills-uri or --min-stake")
    if skills_uri and min_stake_str:
        die("Provide only one of --skills-uri or --min-stake per call")

    # Validate min-stake
    min_stake: int = 0
    if min_stake_str:
        if not re.match(r"^[0-9]+$", min_stake_str):
            die("Invalid --min-stake: must be a non-negative integer (wei)")
        min_stake = int(min_stake_str)

    # ── Pre-checks ──
    wallet_addr = get_wallet_address()
    registry = get_registry()
    subnet_nft = require_contract(registry, "worknetNFT")

    # ── Build calldata and send ──
    if skills_uri:
        calldata = encode_set_skills_uri(subnet_id, skills_uri)
        step("setSkillsURI", subnet=subnet_id, skillsURI=skills_uri,
             target=f"SubnetNFT ({subnet_nft})")
    else:
        calldata = encode_set_min_stake(subnet_id, min_stake)
        step("setMinStake", subnet=subnet_id, minStake=min_stake_str,
             target=f"SubnetNFT ({subnet_nft})")

    result = wallet_send(args.token, subnet_nft, calldata)
    print(result)


if __name__ == "__main__":
    main()
