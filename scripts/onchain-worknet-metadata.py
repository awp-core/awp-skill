#!/usr/bin/env python3
"""On-chain worknet metadata update — setMetadataURI or setImageURI.
These calls target the AWPWorkNet NFT contract.
Only the NFT owner may operate. Requires ETH for gas.

setMetadataURI(uint256 tokenId, string uri) — selector 0x087dce94
setImageURI(uint256 tokenId, string uri) — selector 0x029624e0
"""
from awp_lib import *


def encode_set_uri(selector: str, worknet_id: int, uri: str) -> str:
    """Encode a (uint256, string) call — selector + tokenId + offset(64) + length + padded data"""
    uri_bytes = uri.encode("utf-8")
    uri_len = len(uri_bytes)
    padded_len = ((uri_len + 31) // 32) * 32
    uri_hex = uri_bytes.hex().ljust(padded_len * 2, "0")

    # tokenId
    p1 = pad_uint256(worknet_id)
    # offset pointing to string data (2 * 32 = 64 bytes)
    p2 = pad_uint256(64)
    # string: length + padded data
    str_len = pad_uint256(uri_len)

    return selector + p1 + p2 + str_len + uri_hex


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Update worknet metadata: setMetadataURI or setImageURI")
    parser.add_argument("--worknet", required=True, help="Worknet ID")
    parser.add_argument("--metadata-uri", default="", help="New metadata URI")
    parser.add_argument("--image-uri", default="", help="New image URI")
    args = parser.parse_args()

    worknet_id = validate_positive_int(args.worknet, "worknet")
    worknet_id = expand_worknet_id(worknet_id)
    metadata_uri: str = args.metadata_uri
    image_uri: str = args.image_uri

    # Mutual exclusion validation
    if not metadata_uri and not image_uri:
        die("Provide --metadata-uri or --image-uri")
    if metadata_uri and image_uri:
        die("Provide only one of --metadata-uri or --image-uri per call")

    # ── Pre-checks ──
    registry = get_registry()
    awp_worknet = require_contract(registry, "awpWorkNet")

    # ── Build calldata and send ──
    if metadata_uri:
        calldata = encode_set_uri("0x087dce94", worknet_id, metadata_uri)
        step("setMetadataURI", worknet=worknet_id, metadataURI=metadata_uri,
             target=f"AWPWorkNet ({awp_worknet})")
    else:
        calldata = encode_set_uri("0x029624e0", worknet_id, image_uri)
        step("setImageURI", worknet=worknet_id, imageURI=image_uri,
             target=f"AWPWorkNet ({awp_worknet})")

    result = wallet_send(args.token, awp_worknet, calldata)
    print(result)


if __name__ == "__main__":
    main()
