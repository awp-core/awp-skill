#!/usr/bin/env python3
"""On-chain worknet lifecycle management — activate/pause/resume/cancel
Checks current worknet status before calling to prevent invalid state transitions.
Only the AWPWorkNet NFT owner may operate. Requires ETH for gas.
"""
from awp_lib import *

# Action -> (required prior state, contract selector)
# Selectors from keccak256 of the actual function signatures on AWPRegistry.
ACTION_CONFIG: dict[str, tuple[str, str]] = {
    "activate": ("Pending", "0x6d0c9b50"),   # activateWorknet(uint256)
    "pause":    ("Active",  "0x71ac3737"),   # pauseWorknet(uint256)
    "resume":   ("Paused",  "0x9e9769c1"),   # resumeWorknet(uint256)
    "cancel":   ("Pending", "0x9bc68d94"),   # cancelWorknet(uint256) — full AWP refund
}


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Worknet lifecycle: activate / pause / resume / cancel")
    parser.add_argument("--worknet", required=True, help="Worknet ID")
    parser.add_argument("--action", required=True, choices=["activate", "pause", "resume", "cancel"],
                        help="action type")
    args = parser.parse_args()

    worknet_id = validate_positive_int(args.worknet, "worknet")
    action: str = args.action

    # ── Pre-checks ──
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # ── Check current worknet status ──
    worknet_info = rpc("subnets.get", {"worknetId": str(worknet_id)})
    if not isinstance(worknet_info, dict):
        die(f"Worknet #{worknet_id} not found")

    status = worknet_info.get("status")
    if not status or status == "null":
        die(f"Worknet #{worknet_id} not found")

    # Validate state transition
    required_status, selector = ACTION_CONFIG[action]
    if status != required_status:
        die(f"Cannot {action}: worknet is {status} (must be {required_status})")

    # ── Send transaction ──
    worknet_padded = pad_uint256(worknet_id)
    calldata = encode_calldata(selector, worknet_padded)

    step(f"{action}Worknet", worknet=worknet_id, currentStatus=status)
    result = wallet_send(args.token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
