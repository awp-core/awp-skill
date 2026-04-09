#!/usr/bin/env python3
"""AWP Gasless staking — deposit AWP into veAWP via ERC-2612 permit relay.
No ETH needed. The user signs a single ERC-2612 permit off-chain; the relayer
pays gas and executes the deposit via VeAWPHelper.
If --agent/--worknet are provided, allocate is also done gasless via relay.

Flow (uses the /prepare endpoint — no manual nonce/domain/typedData construction):
  1. POST /api/relay/stake/prepare → get pre-built typedData + submitTo body
  2. Sign typedData with awp-wallet
  3. POST submitTo.url with signature
  4. (Optional) Wait for confirmation, then allocate via relay

Optional: if --agent and --worknet are provided, also allocate after staking
(uses the existing relay-allocate flow).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from awp_lib import (
    RELAY_BASE,
    _CHAIN_IDS,
    _DEFAULT_CHAIN_ID,
    _USER_AGENT,
    api_post,
    base_parser,
    days_to_seconds,
    die,
    expand_worknet_id,
    get_wallet_address,
    info,
    rpc,
    step,
    to_wei,
    validate_address,
    validate_positive_int,
    validate_positive_number,
    wallet_sign_typed_data,
)


def _get_chain_id() -> int:
    """Get chainId from EVM_CHAIN environment variable."""
    chain_env = os.environ.get("EVM_CHAIN", "base").lower()
    cid = _CHAIN_IDS.get(chain_env)
    if cid is not None:
        return cid
    try:
        return int(chain_env)
    except ValueError:
        return _DEFAULT_CHAIN_ID


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

    # Minimum 1 day (86400s), must be whole days
    if lock_seconds < 86400:
        die("--lock-days must be >= 1 (minimum lock duration is 1 day)")
    if lock_seconds % 86400 != 0:
        die(
            f"--lock-days must be a whole number (got {args.lock_days} days = {lock_seconds}s, not divisible by 86400)"
        )
    # uint64 overflow guard
    if lock_seconds > 2**64 - 1:
        die(f"--lock-days too large: {args.lock_days} days exceeds uint64 max")
    # uint128 guard (VeAWPHelper rejects amounts > uint128 max)
    if amount_wei > 2**128 - 1:
        die("--amount too large: exceeds uint128 max")

    do_allocate = bool(args.agent and args.worknet)
    if bool(args.agent) != bool(args.worknet):
        die("--agent and --worknet must both be provided, or both omitted")

    worknet_id: int = 0
    if do_allocate:
        validate_address(args.agent, "agent")
        worknet_id = validate_positive_int(args.worknet, "worknet")
        worknet_id = expand_worknet_id(worknet_id)

    # ── Step 1: Get wallet address and check preconditions ──
    step("setup")
    wallet_addr = get_wallet_address()
    chain_id = _get_chain_id()

    # Precondition: must be registered (staking without registration is pointless)
    step("precondition_check")
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict) and not check.get("isRegistered", False):
        die(
            "Not registered on AWP. Register first (free, gasless): "
            "python3 scripts/relay-start.py --token $TOKEN --mode principal"
        )

    # ── Step 2: Call /prepare endpoint for pre-built typedData ──
    # Endpoint auto-fetches permit nonce, builds EIP-712 domain/message, sets deadline
    # LLM never needs to remember contract addresses or build typed data manually
    prepare_url = f"{RELAY_BASE}/relay/stake/prepare"
    step("prepare", endpoint=prepare_url)
    prepare_body = {
        "chainId": chain_id,
        "user": wallet_addr,
        "amount": str(amount_wei),
        "lockDuration": lock_seconds,
    }
    http_code, prepare_resp = api_post(prepare_url, prepare_body)
    if not (200 <= http_code < 300) or not isinstance(prepare_resp, dict):
        die(f"Prepare endpoint failed (HTTP {http_code}): {prepare_resp}")

    typed_data = prepare_resp.get("typedData")
    submit_to = prepare_resp.get("submitTo")
    if not isinstance(typed_data, dict) or not isinstance(submit_to, dict):
        die("Invalid prepare response: missing typedData or submitTo")

    submit_url = submit_to.get("url", f"{RELAY_BASE}/relay/stake")
    submit_body = submit_to.get("body")
    if not isinstance(submit_body, dict):
        die("Invalid prepare response: submitTo.body is not a dict")

    info(
        f"Prepare OK: deadline={typed_data.get('message', {}).get('deadline', '?')}, "
        f"nonce={typed_data.get('message', {}).get('nonce', '?')}"
    )

    # ── Step 3: Validate server-returned typedData critical fields, then sign ──
    # Prevents a compromised API from returning max-uint256 value or wrong spender/owner
    step("validateTypedData")
    msg = typed_data.get("message", {})
    if str(msg.get("value")) != str(amount_wei):
        die(
            f"Prepare returned wrong permit value: expected {amount_wei}, "
            f"got {msg.get('value')}"
        )
    msg_owner = (msg.get("owner") or "").lower()
    if msg_owner != wallet_addr.lower():
        die(
            f"Prepare returned wrong owner: expected {wallet_addr}, got {msg.get('owner')}"
        )
    # Verify submitTo.url points to known relay domain only
    if not submit_url.startswith(RELAY_BASE):
        die(f"Prepare returned untrusted submitTo.url: {submit_url}")

    step("signPermit")
    signature = wallet_sign_typed_data(token, typed_data)

    # ── Step 4: Submit to relay — replace signature field ──
    submit_body["signature"] = signature
    step(
        "submitRelay",
        endpoint=submit_url,
        amount=f"{args.amount} AWP",
        lockDays=args.lock_days,
    )
    http_code, body = api_post(submit_url, submit_body)

    if not (200 <= http_code < 300):
        die(f"Relay returned HTTP {http_code}: {body}")

    info(f"Gasless stake successful: {body}")

    if not do_allocate:
        result = body if isinstance(body, dict) else {"result": body}
        result["nextAction"] = "allocate"
        result["nextCommand"] = (
            f"python3 scripts/relay-allocate.py --token $TOKEN --mode allocate "
            f"--agent {wallet_addr} --worknet <WORKNET_ID> --amount {args.amount}"
        )
        print(json.dumps(result))
        return

    # ── Optional Step 5: Wait for confirmation, then allocate ──
    if do_allocate:
        tx_hash = body.get("txHash") if isinstance(body, dict) else None
        if not tx_hash:
            die("Relay did not return txHash — cannot confirm staking before allocate")

        # Poll relay status until confirmed (max ~90 seconds)
        step("waitForConfirmation", txHash=tx_hash)
        status_url = f"{RELAY_BASE}/relay/status/{tx_hash}"
        confirmed = False
        for _ in range(30):
            time.sleep(3)
            try:
                req = urllib.request.Request(
                    status_url,
                    headers={"User-Agent": _USER_AGENT},
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
            except json.JSONDecodeError:
                info(f"Status endpoint returned non-JSON for tx {tx_hash}, retrying...")
            except (urllib.error.URLError, OSError):
                pass  # Transient network error, retry

        if not confirmed:
            die(
                f"Staking tx {tx_hash} not confirmed after 90s. "
                "Allocate skipped — check tx status manually and run "
                "relay-allocate.py separately."
            )

        # Execute allocate (gasless via relay — no ETH needed)
        info(
            f"Now allocating to agent {args.agent} on worknet {worknet_id} (gasless)..."
        )
        allocate_script = str(Path(__file__).parent / "relay-allocate.py")
        alloc_result = subprocess.run(
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
        if alloc_result.returncode != 0:
            die(
                f"Allocate failed after staking: "
                f"{alloc_result.stderr.strip() or alloc_result.stdout.strip()}"
            )
        print(alloc_result.stdout.strip())
        info(
            f"Staked {args.amount} AWP (gasless) and allocated to worknet {worknet_id}. "
            "Entire flow was gasless — no ETH used."
        )


if __name__ == "__main__":
    main()
