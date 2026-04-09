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
import time

from awp_lib import (
    RELAY_BASE,
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

# 链名到 chainId 映射（与 awp_lib 保持一致）
import os

_CHAIN_IDS: dict[str, int] = {
    "ethereum": 1,
    "eth": 1,
    "bsc": 56,
    "bnb": 56,
    "base": 8453,
    "arbitrum": 42161,
    "arb": 42161,
}
_DEFAULT_CHAIN_ID = 8453


def _get_chain_id() -> int:
    """从 EVM_CHAIN 环境变量获取 chainId。"""
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

    # 最短 1 天（86400 秒）
    if lock_seconds < 86400:
        die("--lock-days must be >= 1 (minimum lock duration is 1 day)")
    # uint64 溢出保护
    if lock_seconds > 2**64 - 1:
        die(f"--lock-days too large: {args.lock_days} days exceeds uint64 max")
    # uint128 保护（VeAWPHelper 拒绝 > uint128 max 的金额）
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

    # ── Step 1: 获取钱包地址并检查前置条件 ──
    step("setup")
    wallet_addr = get_wallet_address()
    chain_id = _get_chain_id()

    # 前置条件：确认已注册（未注册时质押没有意义）
    step("precondition_check")
    check = rpc("address.check", {"address": wallet_addr})
    if isinstance(check, dict) and not check.get("isRegistered", False):
        die(
            "Not registered on AWP. Register first (free, gasless): "
            "python3 scripts/relay-start.py --token $TOKEN --mode principal"
        )

    # ── Step 2: 调用 /prepare 端点获取预构建的 typedData ──
    # 该端点自动获取 permit nonce、构建 EIP-712 域和消息、设置 deadline
    # LLM 无需记忆合约地址或手动构建 typed data
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

    # ── Step 3: 签名 — 直接使用服务端返回的 typedData ──
    step("signPermit")
    signature = wallet_sign_typed_data(token, typed_data)

    # ── Step 4: 提交到 relay — 替换 signature 字段 ──
    submit_body["signature"] = signature
    step(
        "submitRelay",
        endpoint=submit_url,
        amount=f"{args.amount} AWP",
        lockDays=args.lock_days,
    )
    http_code, body = api_post(submit_url, submit_body)

    if 200 <= http_code < 300:
        info(f"Gasless stake successful: {body}")
        result = body if isinstance(body, dict) else {"result": body}
        if not do_allocate:
            result["nextAction"] = "allocate"
            result["nextCommand"] = (
                f"python3 scripts/relay-allocate.py --token $TOKEN --mode allocate "
                f"--agent {wallet_addr} --worknet <WORKNET_ID> --amount {args.amount}"
            )
        print(json.dumps(result))
    else:
        die(f"Relay returned HTTP {http_code}: {body}")

    # ── Optional Step 5: 等待确认后 allocate ──
    if do_allocate:
        tx_hash = body.get("txHash") if isinstance(body, dict) else None
        if not tx_hash:
            die("Relay did not return txHash — cannot confirm staking before allocate")

        # 轮询 relay 状态直到确认（最多 ~90 秒）
        step("waitForConfirmation", txHash=tx_hash)
        import urllib.error
        import urllib.request

        status_url = f"{RELAY_BASE}/relay/status/{tx_hash}"
        confirmed = False
        for _ in range(30):
            time.sleep(3)
            try:
                req = urllib.request.Request(
                    status_url,
                    headers={"User-Agent": "awp-skill/1.4"},
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
                # 5xx — 暂时性服务端错误，重试
            except (urllib.error.URLError, json.JSONDecodeError, OSError):
                pass  # 暂时性网络错误，重试

        if not confirmed:
            die(
                f"Staking tx {tx_hash} not confirmed after 90s. "
                "Allocate skipped — check tx status manually and run "
                "relay-allocate.py separately."
            )

        # 执行 allocate（gasless via relay — 无需 ETH）
        info(
            f"Now allocating to agent {args.agent} on worknet {worknet_id} (gasless)..."
        )
        import subprocess
        import sys
        from pathlib import Path

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
