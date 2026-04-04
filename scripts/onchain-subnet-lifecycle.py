#!/usr/bin/env python3
"""On-chain subnet lifecycle management — activate/pause/resume (V2)
Checks current subnet status before calling to prevent invalid state transitions.
Only the SubnetNFT owner may operate. Requires ETH for gas.
"""
from awp_lib import *

# Action -> (required prior state, contract selector)
ACTION_CONFIG: dict[str, tuple[str, str]] = {
    "activate": ("Pending", "0xcead1c96"),   # activateWorknet(uint256)
    "pause":    ("Active",  "0x44e047ca"),   # pauseWorknet(uint256)
    "resume":   ("Paused",  "0x5364944c"),   # resumeWorknet(uint256)
    "cancel":   ("Pending", "0x9bc68d94"),   # cancelWorknet(uint256) — full AWP refund
}


def main() -> None:
    # ── Parse arguments ──
    parser = base_parser("Subnet lifecycle: activate / pause / resume")
    parser.add_argument("--subnet", required=True, help="Subnet ID")
    parser.add_argument("--action", required=True, choices=["activate", "pause", "resume", "cancel"],
                        help="action type")
    args = parser.parse_args()

    subnet_id = validate_positive_int(args.subnet, "subnet")
    action: str = args.action

    # ── Pre-checks ──
    wallet_addr = get_wallet_address()
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    # ── Check current subnet status ──
    subnet_info = rpc("subnets.get", {"worknetId": str(subnet_id)})
    if not isinstance(subnet_info, dict):
        die(f"Subnet #{subnet_id} not found")

    status = subnet_info.get("status")
    if not status or status == "null":
        die(f"Subnet #{subnet_id} not found")

    # Validate state transition
    required_status, selector = ACTION_CONFIG[action]
    if status != required_status:
        die(f"Cannot {action}: subnet is {status} (must be {required_status})")

    # ── Send transaction ──
    subnet_padded = pad_uint256(subnet_id)
    calldata = encode_calldata(selector, subnet_padded)

    step(f"{action}Subnet", subnet=subnet_id, currentStatus=status)
    result = wallet_send(args.token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
