#!/usr/bin/env python3
"""
AWP Daemon — background monitoring service for AWP skill.

Runs continuously:
  1. Check that awp-wallet is installed (does NOT auto-install)
  2. Check that wallet is initialized (does NOT auto-init)
  3. Show registration status + available subnets
  4. Check for version updates (informational only, no auto-update)
  5. Monitor registration state changes

Security notes:
  - Never auto-downloads or auto-executes remote scripts
  - Never auto-initializes wallets without explicit user action
  - Only reads config from ~/.awp/openclaw.json (no /tmp glob scanning)
  - Update checks are informational — user must update manually

Usage: python3 scripts/awp-daemon.py
       python3 scripts/awp-daemon.py --interval 60   # check every 60s
Stops: Ctrl+C

Requires: Python 3.9+
"""

from __future__ import annotations

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
from typing import Any, Optional, Tuple

# ── Config ───────────────────────────────────────

API_BASE = os.environ.get("AWP_API_URL", "https://tapi.awp.sh/api")
CHECK_INTERVAL = 300  # seconds (5 min default)
SKILL_REPO = "https://github.com/awp-core/awp-skill.git"
WALLET_REPO = "https://github.com/awp-core/awp-wallet.git"
WALLET_INSTALL_DIR = Path.home() / ".awp" / "awp-wallet"
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_MD = SCRIPT_DIR.parent / "SKILL.md"
NOTIFY_DIR = Path.home() / ".awp"
NOTIFY_FILE = NOTIFY_DIR / "notifications.json"

# ── Logging & Notifications ──────────────────────

def log(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] {msg}")

def warn(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ⚠ {msg}")

def err(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ✗ {msg}", file=sys.stderr)

_openclaw_config_cache: Optional[Tuple[str, str]] = None

def _get_openclaw_config() -> Tuple[str, str]:
    """从 ~/.awp/openclaw.json 读取 OpenClaw channel 和 target（带缓存）。

    只读取用户显式配置的文件，不扫描 /tmp 或其他临时目录。
    该文件由 SKILL.md Step 3 在 OpenClaw 环境下创建。
    """
    global _openclaw_config_cache
    if _openclaw_config_cache is not None:
        return _openclaw_config_cache

    user_config = NOTIFY_DIR / "openclaw.json"
    if user_config.exists():
        try:
            data = json.loads(user_config.read_text())
            result = data.get("channel", ""), data.get("target", "")
            if result[0] and result[1]:
                _openclaw_config_cache = result
                return result
        except Exception:
            pass

    return "", ""

def notify(title: str, message: str, level: str = "info") -> None:
    """发送通知：写入文件 + OpenClaw 消息（如果可用）"""
    timestamp = datetime.now().isoformat()

    # 1. 写入 ~/.awp/notifications.json
    try:
        NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
        notifications = []
        if NOTIFY_FILE.exists():
            try:
                notifications = json.loads(NOTIFY_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                notifications = []

        notifications.append({
            "timestamp": timestamp,
            "level": level,
            "title": title,
            "message": message,
        })

        # 只保留最近 50 条
        notifications = notifications[-50:]
        NOTIFY_FILE.write_text(json.dumps(notifications, indent=2))
    except Exception as e:
        warn(f"Failed to write notification: {e}")

    # 2. OpenClaw 消息发送（如果 openclaw CLI 可用）
    openclaw_bin = shutil.which("openclaw")
    if openclaw_bin:
        channel, target = _get_openclaw_config()
        if channel and target:
            try:
                subprocess.run(
                    [openclaw_bin, "message", "send",
                     "--channel", channel,
                     "--target", target,
                     "--message", f"[AWP] {title}: {message}"],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass  # 发送失败时静默跳过

    # 3. 终端输出
    log(f"[NOTIFY] {title}: {message}")

# ── Helpers ──────────────────────────────────────

def run(cmd: list[str]) -> Tuple[int, str]:
    """运行命令（list 形式，无 shell 注入风险），返回 (returncode, stdout)"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return 1, ""
    except Exception as e:
        return 1, str(e)

def api_get(path: str) -> Optional[Any]:
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

def parse_version(v: str) -> Tuple[int, ...]:
    """解析版本号为可比较的整数元组"""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)

# ── 1. Wallet Installation ───────────────────────

def ensure_wallet_installed() -> bool:
    """检查 awp-wallet 是否已安装（不自动下载或执行远程脚本）。

    如果未安装，打印安装说明并返回 False。
    用户需要自行审查并执行安装命令。
    """
    if shutil.which("awp-wallet"):
        return True

    # 也检查 ~/.local/bin（install.sh 的默认安装位置）
    wallet_local = Path.home() / ".local" / "bin" / "awp-wallet"
    if wallet_local.exists():
        os.environ["PATH"] = f"{wallet_local.parent}:{os.environ.get('PATH', '')}"
        if shutil.which("awp-wallet"):
            return True

    err("awp-wallet is required but not installed.")
    err("Install it:")
    err(f"  git clone {WALLET_REPO} {WALLET_INSTALL_DIR}")
    err(f"  bash {WALLET_INSTALL_DIR}/install.sh")
    err("")
    err("Then restart the daemon.")
    return False

# ── 2. Wallet Initialization ─────────────────────

def ensure_wallet_initialized() -> Optional[str]:
    """检查钱包是否已初始化，返回地址或 None。

    不自动初始化钱包 — 钱包创建会生成密钥对，
    必须由用户显式执行 `awp-wallet init`。
    """
    code, out = run(["awp-wallet", "receive"])
    if code == 0 and out:
        try:
            addr = json.loads(out).get("eoaAddress")
            if addr:
                return addr
        except json.JSONDecodeError:
            pass

    err("Wallet not initialized.")
    err("Initialize it manually:")
    err("  awp-wallet init")
    err("")
    err("This creates an agent work wallet (key pair stored locally).")
    err("Do NOT store personal assets in this wallet.")
    err("After init, restart the daemon.")
    return None

# ── 3. Check Registration & Show Status ──────────

def check_and_notify(wallet_addr: str) -> bool:
    """检查注册状态并显示信息，返回 is_registered"""
    check = api_get(f"/address/{wallet_addr}/check")

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
        log("")
        log(f"{total} subnets. {free} free (no staking). {with_skills} with skills.")
    else:
        log("  No active subnets found (or API unavailable)")

    log("──────────────────────────────────────")

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
    """检查 awp-skill 和 awp-wallet 更新（仅通知，不自动下载或执行）"""
    log("Checking for updates...")

    # awp-skill
    local_ver = get_local_version()
    remote_ver = get_remote_version(
        "https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md"
    )

    if remote_ver and local_ver:
        if parse_version(remote_ver) > parse_version(local_ver):
            log(f"awp-skill {remote_ver} available (current: {local_ver})")
            notify("Update Available",
                   f"awp-skill {remote_ver} available (current: {local_ver})")
        else:
            log(f"awp-skill {local_ver} — up to date ✓")

    # awp-wallet — 版本比较，只通知不自动更新
    if shutil.which("awp-wallet"):
        remote_wallet = ""
        try:
            pkg_text = fetch_text(
                "https://raw.githubusercontent.com/awp-core/awp-wallet/main/package.json"
            )
            if pkg_text:
                remote_wallet = json.loads(pkg_text).get("version", "")
        except (json.JSONDecodeError, KeyError):
            pass

        local_wallet = ""
        wcode, wout = run(["awp-wallet", "--version"])
        if wcode == 0 and wout:
            match = re.search(r"[\d.]+", wout)
            if match:
                local_wallet = match.group(0)

        if remote_wallet and local_wallet:
            if parse_version(remote_wallet) > parse_version(local_wallet):
                log(f"awp-wallet {remote_wallet} available (current: {local_wallet})")
                notify("Update Available",
                       f"awp-wallet {remote_wallet} available (current: {local_wallet})")
            else:
                log(f"awp-wallet {local_wallet} — up to date ✓")
        elif remote_wallet:
            log(f"awp-wallet latest: {remote_wallet}")

# ── Main ─────────────────────────────────────────

def main() -> None:
    interval = CHECK_INTERVAL
    if "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        if idx + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[idx + 1])
            except ValueError:
                pass

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

    # Phase 1: 检查依赖（不自动安装）
    log("Phase 1: Checking awp-wallet dependency...")
    if not ensure_wallet_installed():
        err("Cannot continue without awp-wallet. Install it and restart.")
        sys.exit(1)

    # Phase 2: 检查钱包（不自动初始化）
    log("Phase 2: Checking wallet...")
    wallet_addr = ensure_wallet_initialized()
    if not wallet_addr:
        err("Cannot continue without wallet. Run 'awp-wallet init' and restart.")
        sys.exit(1)

    # Phase 3: 显示状态
    log("Phase 3: Checking status...")
    last_registered = check_and_notify(wallet_addr)

    # Phase 4: 检查更新（仅通知，不自动更新）
    log("Phase 4: Checking for updates (informational only)...")
    check_updates()

    # Phase 5
    log("")
    log(f"Daemon running. Checking every {interval}s.")
    log("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            time.sleep(interval)

            try:
                # 注册状态检查
                is_registered = False
                check = api_get(f"/address/{wallet_addr}/check")
                if check:
                    is_registered = check.get("isRegistered", False)

                if is_registered != last_registered and last_registered is not None:
                    if is_registered:
                        log("Registration detected! You are now registered on AWP.")
                        notify("Registered", f"Address {wallet_addr} is now registered on AWP")
                        check_and_notify(wallet_addr)
                    else:
                        log("Registration lost — address is no longer registered.")
                        notify("Deregistered", f"Address {wallet_addr} is no longer registered on AWP")

                last_registered = is_registered

                # 更新检查
                check_updates()

            except Exception as e:
                warn(f"Monitor cycle error: {e}")

    except KeyboardInterrupt:
        print()
        log("Daemon stopped.")

if __name__ == "__main__":
    main()
