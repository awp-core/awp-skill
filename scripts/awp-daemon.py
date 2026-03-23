#!/usr/bin/env python3
"""
AWP Daemon — background service for AWP skill.

Runs continuously:
  1. Check and install awp-wallet dependency
  2. Initialize wallet if needed
  3. Show registration status + available subnets
  4. Auto-check and auto-update awp-skill and awp-wallet
  5. Monitor registration state changes

Usage: python3 scripts/awp-daemon.py
       python3 scripts/awp-daemon.py --interval 60   # check every 60s
Stops: Ctrl+C
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Config ───────────────────────────────────────

API_BASE = os.environ.get("AWP_API_URL", "https://tapi.awp.sh/api")
CHECK_INTERVAL = 300  # seconds (5 min default)
SKILL_REPO = "https://github.com/awp-core/awp-skill"
WALLET_REPO = "https://github.com/awp-core/awp-wallet"
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_MD = SCRIPT_DIR.parent / "SKILL.md"

# ── Logging ──────────────────────────────────────

def log(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] {msg}")

def warn(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ⚠ {msg}")

def err(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ✗ {msg}", file=sys.stderr)

# ── Helpers ──────────────────────────────────────

def run(cmd: str, check: bool = False) -> tuple[int, str]:
    """运行 shell 命令，返回 (returncode, stdout)"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return 1, ""
    except Exception as e:
        return 1, str(e)

def api_get(path: str) -> dict | list | None:
    """GET 请求 AWP API，返回 JSON 或 None"""
    url = f"{API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def fetch_text(url: str) -> str:
    """获取远程文本内容"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return ""

def wei_to_awp(wei: str) -> str:
    """wei 字符串转 AWP 可读格式"""
    try:
        return f"{int(wei) / 10**18:,.4f}"
    except (ValueError, TypeError):
        return wei

# ── 1. Wallet Installation ───────────────────────

def ensure_wallet_installed() -> bool:
    """检查 awp-wallet 是否安装，未装则自动安装"""
    if shutil.which("awp-wallet"):
        return True

    log("awp-wallet not found. Installing...")

    # 先尝试 registry，再尝试 GitHub
    code, out = run("skill install awp-wallet")
    if code == 0:
        log("awp-wallet installed from registry ✓")
        return True

    code, out = run(f"skill install {WALLET_REPO}")
    if code == 0:
        log("awp-wallet installed from GitHub ✓")
        return True

    err("Failed to install awp-wallet. Install manually:")
    err(f"  skill install awp-wallet")
    err(f"  OR: skill install {WALLET_REPO}")
    return False

# ── 2. Wallet Initialization ─────────────────────

def ensure_wallet_initialized() -> str | None:
    """确保钱包已初始化，返回地址或 None"""
    # 尝试获取地址
    code, out = run("awp-wallet receive")
    if code == 0 and out:
        try:
            data = json.loads(out)
            addr = data.get("address")
            if addr:
                return addr
        except json.JSONDecodeError:
            pass

    log("Wallet not initialized. Running awp-wallet init...")
    code, out = run("awp-wallet init")
    if code != 0:
        err(f"Wallet init failed: {out}")
        return None

    # 重新获取地址
    code, out = run("awp-wallet receive")
    if code != 0:
        err("Wallet initialized but could not read address")
        return None

    try:
        data = json.loads(out)
        addr = data.get("address")
    except json.JSONDecodeError:
        err(f"Invalid wallet response: {out}")
        return None

    if not addr:
        err("Wallet address is empty")
        return None

    log(f"Wallet initialized ✓")
    log(f"Address: {addr}")
    log("")
    log("┌─────────────────────────────────────────────┐")
    log("│  This is an AGENT WORK WALLET.              │")
    log("│  Do NOT store personal assets here.          │")
    log("│  Keep only minimal ETH for gas.              │")
    log("└─────────────────────────────────────────────┘")

    return addr

# ── 3. Check Registration & Show Status ──────────

def check_and_notify(wallet_addr: str) -> bool:
    """检查注册状态并显示信息，返回 is_registered"""
    check = api_get(f"/address/{wallet_addr}/check")
    is_registered = False

    print()
    log("── agent status ──────────────────────")

    if not check:
        log(f"Address:    {wallet_addr}")
        log("Status:     API unavailable")
        log("──────────────────────────────────────")
        return False

    is_registered = check.get("isRegistered", False)

    if not is_registered:
        log(f"Address:    {wallet_addr}")
        log("Status:     NOT REGISTERED")
        log("")
        log("┌─────────────────────────────────────────────┐")
        log("│  You are not registered on AWP yet.          │")
        log("│                                              │")
        log('│  To register (free, gasless), tell your      │')
        log('│  agent: "start working on AWP"               │')
        log("└─────────────────────────────────────────────┘")
    else:
        bound_to = check.get("boundTo", "")
        recipient = check.get("recipient", "")

        log(f"Address:    {wallet_addr}")
        log("Status:     REGISTERED ✓")
        if bound_to:
            log(f"Bound to:   {bound_to}")
        if recipient:
            log(f"Recipient:  {recipient}")

        # 余额
        balance = api_get(f"/staking/user/{wallet_addr}/balance")
        if balance:
            log(f"Staked:     {wei_to_awp(balance.get('totalStaked', '0'))} AWP")
            log(f"Allocated:  {wei_to_awp(balance.get('totalAllocated', '0'))} AWP")
            log(f"Unallocated:{wei_to_awp(balance.get('unallocated', '0'))} AWP")

    log("──────────────────────────────────────")

    # 子网列表
    print()
    log("── available subnets ─────────────────")

    subnets = api_get("/subnets?status=Active&limit=10")
    if subnets and isinstance(subnets, list) and len(subnets) > 0:
        for s in subnets:
            sid = s.get("subnet_id", "?")
            name = s.get("name", "Unknown")
            min_stake = s.get("min_stake", 0)
            skills = "✓" if s.get("skills_uri") else "—"
            log(f"  #{sid}  {name:<30s} min: {min_stake} AWP  skills: {skills}")

        total = len(subnets)
        free = sum(1 for s in subnets if s.get("min_stake", 0) == 0)
        with_skills = sum(1 for s in subnets if s.get("skills_uri"))
        log(f"")
        log(f"{total} subnets. {free} free (no staking). {with_skills} with skills.")
    else:
        log("  No active subnets found (or API unavailable)")

    log("──────────────────────────────────────")

    # 下一步建议
    print()
    if not is_registered:
        log('→ Next: say "start working on AWP" to register for free')
    else:
        log('→ Next: say "list subnets" to browse, or "install skill for subnet #1" to start')
    print()

    return is_registered

# ── 4. Update Checker ────────────────────────────

def get_local_version() -> str:
    """从本地 SKILL.md 读取版本号"""
    try:
        text = SKILL_MD.read_text()
        match = re.search(r"Skill version:\s*([\d.]+)", text)
        return match.group(1) if match else ""
    except Exception:
        return ""

def get_remote_version(url: str) -> str:
    """从远程 SKILL.md 读取版本号"""
    text = fetch_text(url)
    if not text:
        return ""
    match = re.search(r"Skill version:\s*([\d.]+)", text)
    return match.group(1) if match else ""

def check_updates() -> None:
    """检查 awp-skill 和 awp-wallet 更新"""
    log("Checking for updates...")

    # awp-skill
    local_ver = get_local_version()
    remote_ver = get_remote_version(
        "https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md"
    )

    if remote_ver and local_ver and remote_ver != local_ver:
        log("┌─────────────────────────────────────────────┐")
        log("│  AWP Skill update available!                 │")
        log(f"│  Local:  {local_ver}")
        log(f"│  Remote: {remote_ver}")
        log("└─────────────────────────────────────────────┘")

        log("Auto-updating awp-skill...")
        code, _ = run(f"skill install {SKILL_REPO}")
        if code == 0:
            log(f"awp-skill updated to {remote_ver} ✓")
        else:
            warn("Auto-update failed. Please update manually.")
    elif local_ver:
        log(f"awp-skill {local_ver} — up to date ✓")

    # awp-wallet
    if shutil.which("awp-wallet"):
        remote_wallet = get_remote_version(
            "https://raw.githubusercontent.com/awp-core/awp-wallet/main/SKILL.md"
        )
        if remote_wallet:
            log(f"awp-wallet remote: {remote_wallet}")
            code, _ = run("skill install awp-wallet")
            if code != 0:
                run(f"skill install {WALLET_REPO}")
            log("awp-wallet checked/updated ✓")

# ── Main ─────────────────────────────────────────

def main() -> None:
    # 解析参数
    interval = CHECK_INTERVAL
    if "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        if idx + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[idx + 1])
            except ValueError:
                pass

    # 欢迎屏
    print()
    print("╭──────────────╮")
    print("│              │")
    print("│  >       <   │")
    print("│      ~       │")
    print("│              │")
    print("╰──────────────╯")
    print()
    print("AWP Daemon starting...")
    print()

    # Phase 1: 依赖
    log("Phase 1: Checking dependencies...")
    if not ensure_wallet_installed():
        err("Cannot continue without awp-wallet")
        sys.exit(1)

    # Phase 2: 钱包
    log("Phase 2: Checking wallet...")
    wallet_addr = ensure_wallet_initialized()
    if not wallet_addr:
        err("Cannot continue without wallet")
        sys.exit(1)

    # Phase 3: 状态
    log("Phase 3: Checking status...")
    last_registered = check_and_notify(wallet_addr)

    # Phase 4: 更新
    log("Phase 4: Checking updates...")
    check_updates()

    # Phase 5: 持续监控
    log("")
    log(f"Daemon running. Checking every {interval}s for updates and status changes.")
    log("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            time.sleep(interval)

            # 检查注册状态变化
            is_registered = False
            check = api_get(f"/address/{wallet_addr}/check")
            if check:
                is_registered = check.get("isRegistered", False)

            if is_registered != last_registered and last_registered is not None:
                if is_registered:
                    log("🎉 Registration detected! You are now registered on AWP.")
                    check_and_notify(wallet_addr)

            last_registered = is_registered

            # 更新检查
            try:
                check_updates()
            except Exception:
                pass

    except KeyboardInterrupt:
        print()
        log("Daemon stopped.")

if __name__ == "__main__":
    main()
