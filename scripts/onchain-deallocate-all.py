#!/usr/bin/env python3
"""On-chain deallocate all stake from agent+worknet
deallocateAll(address staker, address agent, uint256 worknetId)
Removes all allocated stake in a single call. Takes effect immediately.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain deallocate all stake from agent+worknet")
    parser.add_argument("--agent", required=True, help="Agent address")
    parser.add_argument("--worknet", required=True, help="Worknet ID")
    args = parser.parse_args()

    token: str = args.token
    agent: str = args.agent
    worknet: str = args.worknet

    # Validate inputs
    validate_address(agent, "agent")
    worknet_id: int = validate_positive_int(worknet, "worknet")
    worknet_id = expand_worknet_id(worknet_id)

    # Pre-check: fetch wallet address
    wallet_addr = get_wallet_address()

    # Fetch contract registry
    registry = get_registry()
    awp_allocator = require_contract(registry, "awpAllocator")

    # deallocateAll(address,address,uint256) selector = 0x586ac6b3
    calldata = encode_calldata(
        "0x586ac6b3",
        pad_address(wallet_addr),
        pad_address(agent),
        pad_uint256(worknet_id),
    )

    step("deallocateAll", staker=wallet_addr, agent=agent, worknet=worknet_id)
    result = wallet_send(token, awp_allocator, calldata)
    print(result)


if __name__ == "__main__":
    main()
