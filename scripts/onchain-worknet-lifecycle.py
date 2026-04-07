#!/usr/bin/env python3
"""On-chain worknet lifecycle management — pause / resume / cancel (NFT owner only).

Note: activateWorknet is intentionally NOT exposed here. It is a Guardian-only
function per the AWP protocol spec — the Guardian calls it after verifying the
LP pool has been created and the worknet is ready for public participation.
End users cannot activate their own worknet; it transitions Pending → Active
automatically once the Guardian approves. Cancelling a Pending worknet refunds
the full AWP escrow, which is the user's recourse if they want to abandon.

Checks current worknet status before calling to prevent invalid state transitions.
Requires ETH for gas.
"""
from awp_lib import *

# Action -> (required prior state, contract selector)
# Selectors from keccak256 of the actual function signatures on AWPRegistry.
# activateWorknet is Guardian-only (access-controlled); end users always get a
# revert when calling it, so we don't expose it as an action choice.
ACTION_CONFIG: dict[str, tuple[str, str]] = {
    "pause":    ("Active",  "0x71ac3737"),   # pauseWorknet(uint256) — NFT owner only
    "resume":   ("Paused",  "0x9e9769c1"),   # resumeWorknet(uint256) — NFT owner only
    "cancel":   ("Pending", "0x9bc68d94"),   # cancelWorknet(uint256) — NFT owner, full AWP refund
}


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Worknet lifecycle: pause / resume / cancel (NFT owner only)")
    parser.add_argument("--worknet", required=True, help="Worknet ID")
    parser.add_argument("--action", required=True, choices=["pause", "resume", "cancel"],
                        help="action type (activate is Guardian-only, not exposed here)")
    args = parser.parse_args()

    worknet_id = validate_positive_int(args.worknet, "worknet")
    worknet_id = expand_worknet_id(worknet_id)
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
