#!/usr/bin/env python3
"""One-command AWP onboarding — register + optional deposit + allocate.
Combines the full onboarding flow:
  1. Register via relay (gasless — setRecipient or bind)
  2. Optionally deposit AWP into veAWP (if --amount and --lock-days provided)
  3. Optionally allocate stake to agent+worknet (if --worknet provided)

Minimal usage (free registration only):
  python3 scripts/onchain-onboard.py --token $TOKEN

Full usage (register + stake + allocate):
  python3 scripts/onchain-onboard.py --token $TOKEN --amount 5000 --lock-days 90 --worknet 1

Bind to another wallet:
  python3 scripts/onchain-onboard.py --token $TOKEN --target <owner_address>
"""

from __future__ import annotations

import json
import time

from awp_lib import (
    RELAY_BASE,
    api_post,
    base_parser,
    build_eip712,
    die,
    encode_calldata,
    expand_worknet_id,
    get_eip712_domain,
    get_registry,
    get_wallet_address,
    info,
    pad_address,
    pad_uint256,
    require_contract,
    rpc,
    step,
    to_wei,
    days_to_seconds,
    validate_address,
    validate_positive_int,
    validate_positive_number,
    wallet_approve,
    wallet_send,
    wallet_sign_typed_data,
)


def main() -> None:
    parser = base_parser("AWP one-command onboarding: register + deposit + allocate")
    parser.add_argument(
        "--target",
        default="",
        help="Bind to this owner address (agent mode). Omit for principal mode.",
    )
    parser.add_argument(
        "--amount",
        default="",
        help="AWP amount to deposit (optional, skip deposit if omitted)",
    )
    parser.add_argument(
        "--lock-days",
        default="",
        help="Lock duration in days (required if --amount is set)",
    )
    parser.add_argument(
        "--worknet", default="", help="Worknet ID to allocate to (optional)"
    )
    args = parser.parse_args()

    token: str = args.token
    do_deposit = bool(args.amount)
    do_allocate = bool(args.worknet)

    if do_deposit and not args.lock_days:
        die("--lock-days is required when --amount is provided")
    if do_allocate and not do_deposit:
        die(
            "--worknet requires --amount and --lock-days (must deposit before allocating)"
        )

    if args.amount:
        validate_positive_number(args.amount, "amount")
    if args.lock_days:
        validate_positive_number(args.lock_days, "lock-days")
    if args.target:
        validate_address(args.target, "target")

    worknet_id: int = 0
    if do_allocate:
        worknet_id = validate_positive_int(args.worknet, "worknet")
        worknet_id = expand_worknet_id(worknet_id)

    # ── Shared setup ──
    step("setup")
    registry = get_registry()
    domain = get_eip712_domain(registry)
    wallet_addr = get_wallet_address()
    chain_id = domain["chainId"]

    # ── Phase 1: Register via relay (gasless) ──
    step("checkRegistration")
    check = rpc("address.check", {"address": wallet_addr})
    already_registered = False

    if isinstance(check, dict):
        is_registered = bool(check.get("isRegistered", False))
        bound_to = check.get("boundTo", "")
        zero_addr = "0x0000000000000000000000000000000000000000"

        if args.target:
            # Agent mode: check if already bound
            if bound_to and bound_to != "null" and bound_to != zero_addr:
                info(f"Already bound to {bound_to}, skipping registration")
                already_registered = True
        else:
            # Principal mode: check if registered
            if is_registered:
                info("Already registered, skipping registration")
                already_registered = True

    if not already_registered:
        step("register")
        nonce_resp = rpc("nonce.get", {"address": wallet_addr})
        if not isinstance(nonce_resp, dict) or "nonce" not in nonce_resp:
            die(f"Invalid nonce response: {nonce_resp}")
        nonce = nonce_resp["nonce"]
        deadline = int(time.time()) + 3600

        if args.target:
            # Agent mode: bind
            eip712_data = build_eip712(
                domain,
                "Bind",
                [
                    {"name": "agent", "type": "address"},
                    {"name": "target", "type": "address"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
                {
                    "agent": wallet_addr,
                    "target": args.target,
                    "nonce": nonce,
                    "deadline": deadline,
                },
            )
            relay_endpoint = f"{RELAY_BASE}/relay/bind"
            relay_body: dict = {
                "chainId": chain_id,
                "agent": wallet_addr,
                "target": args.target,
                "deadline": deadline,
            }
        else:
            # Principal mode: setRecipient(self)
            eip712_data = build_eip712(
                domain,
                "SetRecipient",
                [
                    {"name": "user", "type": "address"},
                    {"name": "recipient", "type": "address"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
                {
                    "user": wallet_addr,
                    "recipient": wallet_addr,
                    "nonce": nonce,
                    "deadline": deadline,
                },
            )
            relay_endpoint = f"{RELAY_BASE}/relay/set-recipient"
            relay_body = {
                "chainId": chain_id,
                "user": wallet_addr,
                "recipient": wallet_addr,
                "deadline": deadline,
            }

        signature = wallet_sign_typed_data(token, eip712_data)
        relay_body["signature"] = signature

        step("submitRelay", endpoint=relay_endpoint)
        http_code, body = api_post(relay_endpoint, relay_body)
        if 200 <= http_code < 300:
            info(f"Registration successful: {body}")
        else:
            die(f"Registration failed (HTTP {http_code}): {body}")

    # ── Phase 2: Deposit (optional) ──
    if not do_deposit:
        print(
            json.dumps(
                {
                    "status": "registered",
                    "address": wallet_addr,
                    "nextAction": "pick_worknet",
                    "nextCommand": f"python3 scripts/preflight.py --address {wallet_addr}",
                }
            )
        )
        info("Registration complete. No deposit requested.")
        if not already_registered:
            info("To start earning: deposit AWP and allocate to a worknet.")
        return

    awp_token = require_contract(registry, "awpToken")
    ve_awp = require_contract(registry, "veAWP")
    amount_wei = to_wei(args.amount)
    lock_seconds = days_to_seconds(args.lock_days)

    if lock_seconds > 2**64 - 1:
        die(f"lock-days too large: {args.lock_days} days exceeds uint64 max")

    # Approve
    step("approve", spender=ve_awp, amount=f"{args.amount} AWP")
    wallet_approve(token, awp_token, ve_awp, args.amount)

    # Deposit — deposit(uint256,uint64) selector = 0x7d552ea6
    deposit_calldata = encode_calldata(
        "0x7d552ea6", pad_uint256(amount_wei), pad_uint256(lock_seconds)
    )
    step("deposit", amount=args.amount, lockDays=args.lock_days)
    deposit_result = wallet_send(token, ve_awp, deposit_calldata)
    info(f"Deposit confirmed: {deposit_result}")

    # ── Phase 3: Allocate (optional) ──
    if not do_allocate:
        print(
            json.dumps(
                {
                    "status": "deposited",
                    "address": wallet_addr,
                    "amount": args.amount,
                    "nextAction": "allocate",
                    "nextCommand": f"python3 scripts/relay-allocate.py --token $TOKEN --mode allocate --agent {wallet_addr} --worknet <WORKNET_ID> --amount {args.amount}",
                }
            )
        )
        info("Deposit complete. To earn rewards, allocate to an agent+worknet.")
        return

    awp_allocator = require_contract(registry, "awpAllocator")

    # Allocate: agent = target (delegated mode) or self (solo mode)
    agent_for_allocate = args.target if args.target else wallet_addr
    # allocate(address,address,uint256,uint256) selector = 0xd035a9a7
    allocate_calldata = encode_calldata(
        "0xd035a9a7",
        pad_address(wallet_addr),
        pad_address(agent_for_allocate),
        pad_uint256(worknet_id),
        pad_uint256(amount_wei),
    )

    step("allocate", agent=wallet_addr, worknet=worknet_id, amount=f"{args.amount} AWP")
    wallet_send(token, awp_allocator, allocate_calldata)

    print(
        json.dumps(
            {
                "status": "onboarded",
                "address": wallet_addr,
                "deposited": args.amount,
                "allocatedTo": {"agent": wallet_addr, "worknet": worknet_id},
                "nextAction": "earning",
                "nextCommand": f"python3 scripts/query-status.py --address {wallet_addr}",
            }
        )
    )
    info(
        f"Onboarding complete! Registered, deposited {args.amount} AWP, allocated to worknet {worknet_id}. Now earning rewards."
    )


if __name__ == "__main__":
    main()
