#!/usr/bin/env python3
"""Fully gasless AWP onboarding — register + stake + allocate, no ETH needed.
Combines three gasless relay operations in one script:
  1. Register via relay (setRecipient or bind)
  2. Stake via relay (ERC-2612 permit → VeAWPHelper)
  3. Allocate via relay (EIP-712 → AWPAllocator)

Minimal usage (free registration only):
  python3 scripts/relay-onboard.py --token $TOKEN

Full usage (register + stake + allocate):
  python3 scripts/relay-onboard.py --token $TOKEN --amount 5000 --lock-days 90 --worknet 1

Bind to another wallet:
  python3 scripts/relay-onboard.py --token $TOKEN --target <owner_address>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from awp_lib import (
    RELAY_BASE,
    api_post,
    base_parser,
    build_eip712,
    die,
    expand_worknet_id,
    get_eip712_domain,
    get_registry,
    get_wallet_address,
    info,
    rpc,
    step,
    validate_address,
    validate_positive_int,
    validate_positive_number,
    wallet_sign_typed_data,
)

SCRIPTS_DIR = Path(__file__).parent


def _run_script(name: str, args: list[str]) -> str:
    """Run a sibling script, die on failure, return stdout."""
    script = str(SCRIPTS_DIR / name)
    result = subprocess.run(
        [sys.executable, script] + args,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        die(f"{name} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def main() -> None:
    parser = base_parser("Fully gasless AWP onboarding (no ETH needed)")
    parser.add_argument(
        "--target",
        default="",
        help="Bind to this owner address (agent mode). Omit for principal mode.",
    )
    parser.add_argument(
        "--amount",
        default="",
        help="AWP amount to stake (optional, skip staking if omitted)",
    )
    parser.add_argument(
        "--lock-days",
        default="",
        help="Lock duration in days (required if --amount is set)",
    )
    parser.add_argument(
        "--worknet",
        default="",
        help="Worknet ID to allocate to (optional, requires --amount)",
    )
    args = parser.parse_args()

    token: str = args.token
    do_stake = bool(args.amount)
    do_allocate = bool(args.worknet)

    if do_stake and not args.lock_days:
        die("--lock-days is required when --amount is provided")
    if do_allocate and not do_stake:
        die(
            "--worknet requires --amount and --lock-days (must stake before allocating)"
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

    # ── Phase 1: Register via relay (gasless) ──
    step("setup")
    registry = get_registry()
    domain = get_eip712_domain(registry)
    wallet_addr = get_wallet_address()
    chain_id = domain["chainId"]

    step("checkRegistration")
    check = rpc("address.check", {"address": wallet_addr})
    already_registered = False

    if isinstance(check, dict):
        is_registered = bool(check.get("isRegistered", False))
        bound_to = check.get("boundTo", "")
        zero_addr = "0x0000000000000000000000000000000000000000"

        if args.target:
            if bound_to and bound_to != "null" and bound_to != zero_addr:
                info(f"Already bound to {bound_to}, skipping registration")
                already_registered = True
        else:
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

    # ── Phase 2: Gasless stake (optional) ──
    if not do_stake:
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
        info("Registration complete. No staking requested.")
        return

    # Delegate to relay-stake.py which handles permit signing + tx confirmation
    step("gaslessStake", amount=args.amount, lockDays=args.lock_days)
    stake_args = [
        "--token",
        token,
        "--amount",
        args.amount,
        "--lock-days",
        args.lock_days,
    ]
    if do_allocate:
        stake_args += ["--agent", wallet_addr, "--worknet", str(worknet_id)]

    stake_output = _run_script("relay-stake.py", stake_args)
    print(stake_output)

    if do_allocate:
        info(
            f"Onboarding complete! Registered, staked {args.amount} AWP, "
            f"allocated to worknet {worknet_id}. Entire flow was gasless."
        )
    else:
        info(
            f"Onboarding complete! Registered, staked {args.amount} AWP. "
            "To earn rewards, allocate to an agent+worknet."
        )


if __name__ == "__main__":
    main()
