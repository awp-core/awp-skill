#!/usr/bin/env python3
"""On-chain allocate stake to agent+subnet (V2)
V2 signature: allocate(address staker, address agent, uint256 subnetId, uint256 amount)
The staker parameter is now explicit (first argument). Caller must be staker or delegate.
"""
from awp_lib import *


def main() -> None:
    parser = base_parser("On-chain allocate stake to agent+subnet (V2)")
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
    staking_vault = require_contract(registry, "stakingVault")

    # Check unallocated balance
    balance = rpc("staking.getBalance", {"address": wallet_addr})
    if not isinstance(balance, dict):
        die("Could not fetch balance — check address")
    unallocated = balance.get("unallocated")
    if unallocated is None or unallocated == "null":
        die("Could not fetch balance — check address")

    amount_wei = to_wei(amount)
    unallocated_int = int(unallocated)
    # Note: API data may be delayed (by a few seconds) and on-chain state may have changed.
    # This check is intended to catch obvious errors early; the on-chain validation is authoritative.
    if amount_wei > unallocated_int:
        die(f"Insufficient unallocated balance: have {unallocated_int / 10**18} AWP, need {amount} AWP")

    # allocate(address,address,uint256,uint256) selector = 0xd035a9a7
    # Parameters: staker (self), agent, subnetId, amount
    calldata = encode_calldata(
        "0xd035a9a7",
        pad_address(wallet_addr),
        pad_address(agent),
        pad_uint256(subnet_id),
        pad_uint256(amount_wei),
    )

    step("allocate", staker=wallet_addr, agent=agent, subnet=subnet_id, amount=f"{amount} AWP")
    result = wallet_send(token, staking_vault, calldata)
    print(result)


if __name__ == "__main__":
    main()
