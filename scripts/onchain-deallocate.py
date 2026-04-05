#!/usr/bin/env python3
"""On-chain deallocate stake from agent+subnet (V2)
deallocate(address staker, address agent, uint256 subnetId, uint256 amount)
Takes effect immediately, no cooldown period.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain deallocate stake from agent+subnet (V2)")
    parser.add_argument("--agent", required=True, help="Agent address")
    parser.add_argument("--subnet", required=True, help="Subnet ID")
    parser.add_argument("--amount", required=True, help="AWP amount (human readable)")
    args = parser.parse_args()

    token: str = args.token
    agent: str = args.agent
    subnet: str = args.subnet
    amount: str = args.amount

    # Validate inputs
    validate_address(agent, "agent")
    validate_positive_number(amount, "amount")
    subnet_id: int = validate_positive_int(subnet, "subnet")

    # Pre-check: fetch wallet address
    wallet_addr = get_wallet_address()

    # Fetch contract registry
    registry = get_registry()
    awp_allocator = require_contract(registry, "awpAllocator")

    amount_wei = to_wei(amount)

    # deallocate(address,address,uint256,uint256) selector = 0x716fb83d
    calldata = encode_calldata(
        "0x716fb83d",
        pad_address(wallet_addr),
        pad_address(agent),
        pad_uint256(subnet_id),
        pad_uint256(amount_wei),
    )

    step("deallocate", staker=wallet_addr, agent=agent, subnet=subnet_id, amount=f"{amount} AWP")
    result = wallet_send(token, awp_allocator, calldata)
    print(result)


if __name__ == "__main__":
    main()
