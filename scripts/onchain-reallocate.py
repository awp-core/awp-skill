#!/usr/bin/env python3
"""On-chain reallocate stake between agent+subnet pairs (V2)
V2 signature: reallocate(address staker, address fromAgent, uint256 fromSubnetId,
                         address toAgent, uint256 toSubnetId, uint256 amount)
The staker parameter is now explicit (first argument). Caller must be staker or delegate.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain reallocate stake between agent+subnet pairs (V2)")
    parser.add_argument("--from-agent", required=True, help="Source agent address")
    parser.add_argument("--from-subnet", required=True, help="Source subnet ID")
    parser.add_argument("--to-agent", required=True, help="Destination agent address")
    parser.add_argument("--to-subnet", required=True, help="Destination subnet ID")
    parser.add_argument("--amount", required=True, help="AWP amount (human readable)")
    args = parser.parse_args()

    token: str = args.token
    from_agent: str = args.from_agent
    from_subnet: str = args.from_subnet
    to_agent: str = args.to_agent
    to_subnet: str = args.to_subnet
    amount: str = args.amount

    # Validate inputs
    validate_address(from_agent, "from-agent")
    validate_address(to_agent, "to-agent")
    validate_positive_number(amount, "amount")
    from_subnet_id: int = validate_positive_int(from_subnet, "from-subnet")
    to_subnet_id: int = validate_positive_int(to_subnet, "to-subnet")

    # Pre-check: fetch wallet address
    wallet_addr = get_wallet_address()

    # Fetch contract registry
    registry = get_registry()
    awp_registry = require_contract(registry, "awpRegistry")

    amount_wei = to_wei(amount)

    # reallocate(address,address,uint256,address,uint256,uint256) selector = 0xd5d5278d
    # Parameters: staker (self), fromAgent, fromSubnetId, toAgent, toSubnetId, amount
    calldata = encode_calldata(
        "0xd5d5278d",
        pad_address(wallet_addr),
        pad_address(from_agent),
        pad_uint256(from_subnet_id),
        pad_address(to_agent),
        pad_uint256(to_subnet_id),
        pad_uint256(amount_wei),
    )

    step("reallocate", staker=wallet_addr, fromAgent=from_agent, fromSubnet=from_subnet_id,
         toAgent=to_agent, toSubnet=to_subnet_id, amount=f"{amount} AWP")
    result = wallet_send(token, awp_registry, calldata)
    print(result)


if __name__ == "__main__":
    main()
