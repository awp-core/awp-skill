#!/usr/bin/env python3
"""AWP Gasless staking — deposit AWP into veAWP via ERC-2612 permit relay.
No ETH needed. The user signs a single ERC-2612 permit off-chain; the relayer
pays gas and executes the deposit via VeAWPHelper.
If --agent/--worknet are provided, allocate is also done gasless via relay.

Flow:
  1. Fetch VeAWPHelper address from registry + AWPToken.nonces(user) on-chain
  2. Build EIP-712 Permit typed data (AWP Token domain, NOT AWPRegistry)
  3. Sign with awp-wallet
  4. Submit to POST /api/relay/stake

Optional: if --agent and --worknet are provided, also allocate after staking
(uses the existing relay-allocate flow or on-chain allocate).
"""

from __future__ import annotations

import json
import time

from awp_lib import (
    RELAY_BASE,
    api_post,
    base_parser,
    build_eip712,
    days_to_seconds,
    die,
    expand_worknet_id,
    get_registry,
    get_wallet_address,
    info,
    pad_address,
    rpc_call,
    step,
    to_wei,
    validate_address,
    validate_positive_int,
    validate_positive_number,
    wallet_sign_typed_data,
)

# VeAWPHelper — same address on all 4 chains (CREATE2)
VE_AWP_HELPER = "0x0000561EDE5C1Ba0b81cE585964050bEAE730001"


def main() -> None:
    parser = base_parser("Gasless staking: deposit AWP into veAWP (no ETH needed)")
    parser.add_argument("--amount", required=True, help="AWP amount (human-readable)")
    parser.add_argument(
        "--lock-days", required=True, help="Lock duration in days (minimum 1)"
    )
    parser.add_argument(
        "--agent",
        default="",
        help="Agent address to allocate to after staking (optional)",
    )
    parser.add_argument(
        "--worknet",
        default="",
        help="Worknet ID to allocate to after staking (optional)",
    )
    args = parser.parse_args()

    token: str = args.token
    validate_positive_number(args.amount, "amount")
    validate_positive_number(args.lock_days, "lock-days")

    amount_wei = to_wei(args.amount)
    lock_seconds = days_to_seconds(args.lock_days)

    # Minimum 1 day (86400 seconds) per VeAWPHelper contract
    if lock_seconds < 86400:
        die("--lock-days must be >= 1 (minimum lock duration is 1 day)")
    # uint64 overflow guard
    if lock_seconds > 2**64 - 1:
        die(f"--lock-days too large: {args.lock_days} days exceeds uint64 max")
    # uint128 guard (VeAWPHelper rejects amounts > uint128 max)
    if amount_wei > 2**128 - 1:
        die(f"--amount too large: exceeds uint128 max")

    do_allocate = bool(args.agent and args.worknet)
    if bool(args.agent) != bool(args.worknet):
        die("--agent and --worknet must both be provided, or both omitted")

    worknet_id: int = 0
    if do_allocate:
        validate_address(args.agent, "agent")
        worknet_id = validate_positive_int(args.worknet, "worknet")
        worknet_id = expand_worknet_id(worknet_id)

    # ── Step 1: Fetch registry + permit nonce ──
    step("setup")
    registry = get_registry()
    awp_token = registry.get("awpToken", "")
    if not awp_token:
        die("awpToken not found in registry")

    # Prefer registry's veAWPHelper if available, fallback to hardcoded
    ve_awp_helper = registry.get("veAWPHelper", VE_AWP_HELPER)

    wallet_addr = get_wallet_address()
    chain_id = registry.get("chainId", 8453)

    # Read AWPToken.nonces(user) on-chain — selector 0x7ecebe00
    step("getNonce")
    addr_padded = pad_address(wallet_addr)
    nonce_hex = rpc_call(awp_token, f"0x7ecebe00{addr_padded}")
    if not nonce_hex or nonce_hex in ("0x", "null"):
        die("Could not read AWPToken.nonces — is the wallet address correct?")
    permit_nonce = int(nonce_hex, 16)
    info(f"Permit nonce: {permit_nonce}")

    # ── Step 2: Build ERC-2612 Permit typed data ──
    # Domain is AWP Token (NOT AWPRegistry) — standard ERC-2612
    deadline = int(time.time()) + 3600  # 1 hour from now

    eip712_data = build_eip712(
        domain={
            "name": "AWP Token",
            "version": "1",
            "chainId": int(chain_id),
            "verifyingContract": awp_token,
        },
        primary_type="Permit",
        type_fields=[
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        message={
            "owner": wallet_addr,
            "spender": ve_awp_helper,
            "value": amount_wei,
            "nonce": permit_nonce,
            "deadline": deadline,
        },
    )

    # ── Step 3: Sign permit ──
    step("signPermit")
    signature = wallet_sign_typed_data(token, eip712_data)

    # ── Step 4: Submit to relay ──
    relay_body = {
        "chainId": int(chain_id),
        "user": wallet_addr,
        "amount": str(amount_wei),
        "lockDuration": lock_seconds,
        "deadline": deadline,
        "signature": signature,
    }

    relay_url = f"{RELAY_BASE}/relay/stake"
    step(
        "submitRelay",
        endpoint=relay_url,
        amount=f"{args.amount} AWP",
        lockDays=args.lock_days,
    )
    http_code, body = api_post(relay_url, relay_body)

    if 200 <= http_code < 300:
        info(f"Gasless stake successful: {body}")
        if isinstance(body, dict):
            print(json.dumps(body))
        else:
            print(body)
    else:
        die(f"Relay returned HTTP {http_code}: {body}")

    # ── Optional Step 5: Wait for confirmation, then allocate ──
    if do_allocate:
        tx_hash = body.get("txHash") if isinstance(body, dict) else None
        if not tx_hash:
            die("Relay did not return txHash — cannot confirm staking before allocate")

        # Poll relay status until confirmed (max ~90 seconds)
        step("waitForConfirmation", txHash=tx_hash)
        import urllib.request
        import urllib.error

        status_url = f"{RELAY_BASE}/relay/status/{tx_hash}"
        confirmed = False
        for _ in range(30):
            time.sleep(3)
            try:
                req = urllib.request.Request(
                    status_url,
                    headers={"User-Agent": "awp-skill/1.3"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_data = json.loads(resp.read().decode())
                    if isinstance(status_data, dict):
                        tx_status = status_data.get("status", "")
                        if tx_status == "confirmed":
                            info(f"Staking tx confirmed: {tx_hash}")
                            confirmed = True
                            break
                        elif tx_status == "failed":
                            die(f"Staking tx failed on-chain: {tx_hash}")
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    die(f"Status endpoint returned HTTP {e.code} for tx {tx_hash}")
                # 5xx — transient server error, retry
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                pass  # Transient network error, retry

        if not confirmed:
            die(
                f"Staking tx {tx_hash} not confirmed after 90s. "
                "Allocate skipped — check tx status manually and run "
                "relay-allocate.py separately."
            )

        # Now allocate (gasless via relay — no ETH needed)
        info(
            f"Now allocating to agent {args.agent} on worknet {worknet_id} (gasless)..."
        )
        import subprocess
        import sys
        from pathlib import Path

        allocate_script = str(Path(__file__).parent / "relay-allocate.py")
        result = subprocess.run(
            [
                sys.executable,
                allocate_script,
                "--token",
                token,
                "--mode",
                "allocate",
                "--agent",
                args.agent,
                "--worknet",
                str(worknet_id),
                "--amount",
                args.amount,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            die(
                f"Allocate failed after staking: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        print(result.stdout.strip())
        info(
            f"Staked {args.amount} AWP (gasless) and allocated to worknet {worknet_id}. "
            "Entire flow was gasless — no ETH used."
        )


if __name__ == "__main__":
    main()
