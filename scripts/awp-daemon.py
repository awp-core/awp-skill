#!/usr/bin/env python3
"""
AWP Daemon — background monitoring service for AWP skill.

Runs continuously:
  1. Send welcome message (banner + active subnets) via notify or stdout
  2. Check that awp-wallet is installed (does NOT auto-install)
  3. Check that wallet is initialized (does NOT auto-init)
  4. Show registration status + available subnets
  5. Check for version updates (informational only, no auto-update)
  6. Monitor: registration state changes, new subnet detection

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
STATUS_FILE = NOTIFY_DIR / "status.json"
PID_FILE = NOTIFY_DIR / "daemon.pid"

# ── Logging & Notifications ──────────────────────

def log(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] {msg}")

def warn(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ⚠ {msg}")

def err(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ✗ {msg}", file=sys.stderr)

def _get_openclaw_config() -> Tuple[str, str]:
    """Read OpenClaw channel and target from ~/.awp/openclaw.json.

    Reads the file on every call (supports hot-reload — agent can write config at any time).
    This file is written by the agent at skill load time, format:
    {"channel": "telegram", "target": "123456"}
    """
    user_config = NOTIFY_DIR / "openclaw.json"
    if user_config.exists():
        try:
            data = json.loads(user_config.read_text())
            ch = data.get("channel", "")
            tg = data.get("target", "")
            if ch and tg:
                return ch, tg
        except Exception:
            pass
    return "", ""

def _find_openclaw() -> Optional[str]:
    """Locate the openclaw executable, checking common installation paths."""
    found = shutil.which("openclaw")
    if found:
        return found
    # Additional npm global install paths (common locations not in default PATH)
    extra_dirs = [
        Path.home() / ".npm-global" / "bin",
        Path.home() / ".local" / "bin",
        Path.home() / ".yarn" / "bin",
        Path("/usr/local/bin"),
    ]
    for d in extra_dirs:
        candidate = d / "openclaw"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _can_push() -> bool:
    """Check whether messages can be pushed via OpenClaw."""
    if not _find_openclaw():
        return False
    channel, target = _get_openclaw_config()
    return bool(channel and target)


def notify(title: str, message: str, level: str = "info") -> None:
    """Send a notification: write to file + OpenClaw message (if available) + terminal output."""
    timestamp = datetime.now().isoformat()

    # 1. Write to ~/.awp/notifications.json
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
            "title": f"🪼 {title}",
            "message": message,
        })

        # Keep only the latest 50 entries; atomic write (write to temp file then rename)
        notifications = notifications[-50:]
        tmp_file = NOTIFY_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(notifications, indent=2))
        tmp_file.rename(NOTIFY_FILE)
    except Exception as e:
        warn(f"Failed to write notification: {e}")

    # 2. Send via OpenClaw (if openclaw CLI is available)
    openclaw_bin = _find_openclaw()
    if openclaw_bin:
        channel, target = _get_openclaw_config()
        if channel and target:
            try:
                subprocess.run(
                    [openclaw_bin, "message", "send",
                     "--channel", channel,
                     "--target", target,
                     "--message", f"**🪼 {title}**\n```\n{message}\n```"],
                    capture_output=True, timeout=10
                )
            except Exception:
                pass  # Silently skip on send failure

    # 3. Terminal output
    log(f"[NOTIFY] {title}: {message}")

# ── Helpers ──────────────────────────────────────

def run(cmd: list[str]) -> Tuple[int, str]:
    """Run a command (as a list, no shell injection risk) and return (returncode, stdout)."""
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
    """GET request to the AWP API; returns parsed JSON or None."""
    url = f"{API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def fetch_text(url: str) -> str:
    """Fetch remote text content."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return ""

def wei_to_awp(wei: str) -> str:
    """Convert a wei string to a human-readable AWP amount."""
    try:
        return f"{int(wei) / 10**18:,.4f}"
    except (ValueError, TypeError):
        return wei

def parse_version(v: str) -> Tuple[int, ...]:
    """Parse a version string into a comparable tuple of integers."""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)

# ── Status File ─────────────────────────────────

def write_status(
    wallet_installed: bool,
    wallet_addr: Optional[str],
    registered: Optional[bool],
    subnets_count: int,
    last_check: str,
) -> None:
    """Write the daemon's latest state to ~/.awp/status.json. Agent can read this at any time."""
    # Determine current phase and next-step guidance
    if not wallet_installed:
        phase = "wallet_not_installed"
        next_step = 'Tell your agent: "install awp-wallet from https://github.com/awp-core/awp-wallet"'
    elif not wallet_addr:
        phase = "wallet_not_initialized"
        next_step = 'Tell your agent: "initialize my wallet"'
    elif registered is None or not registered:
        phase = "not_registered"
        next_step = 'Tell your agent: "start working" (free, gasless)'
    else:
        phase = "ready"
        next_step = 'Tell your agent: "list subnets" or "start working"'

    status = {
        "phase": phase,
        "wallet_installed": wallet_installed,
        "wallet_address": wallet_addr,
        "registered": registered,
        "active_subnets": subnets_count,
        "next_step": next_step,
        "last_check": last_check,
    }
    try:
        NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(status, indent=2))
    except Exception:
        pass


# ── Subnet Tracking ─────────────────────────────

def fetch_active_subnets() -> list[dict[str, Any]]:
    """Fetch the list of active subnets."""
    subnets = api_get("/subnets?status=Active&limit=50")
    if subnets and isinstance(subnets, list):
        return subnets
    return []


def format_subnet_list(subnets: list[dict[str, Any]]) -> str:
    """Format the subnet list in receipt style with detailed info per subnet."""
    W = RECEIPT_WIDTH  # Content width (matches the banner)
    lines: list[str] = []
    lines.append("┌" + "─" * W + "┐")
    lines.append("│" + "ACTIVE SUBNETS".center(W) + "│")
    lines.append("├" + "─" * W + "┤")
    if not subnets:
        lines.append("│" + "  (none found)".ljust(W) + "│")
    else:
        for i, s in enumerate(subnets):
            sid = s.get("subnet_id", "?")
            name = s.get("name", "Unknown")
            symbol = s.get("symbol", "")
            min_stake = s.get("min_stake", 0)
            status = s.get("status", "")
            owner_raw = s.get("owner", "") or ""
            owner = (owner_raw[:6] + "..." + owner_raw[-4:]) if len(owner_raw) > 14 else owner_raw
            skills_uri = s.get("skills_uri", "")
            created_raw = s.get("created_at", "")
            created = str(created_raw) if created_raw else ""
            if len(created) >= 10:
                created = created[:10]  # YYYY-MM-DD

            # Line 1: #id NAME (SYMBOL)
            header = f"  #{sid} {name}"
            if symbol:
                header += f" ({symbol})"
            lines.append("│" + header.ljust(W) + "│")

            # Line 2: owner + status
            detail = f"    owner: {owner}" if owner else "    owner: —"
            if status:
                detail += f"  [{status}]"
            if len(detail) > W:
                detail = detail[:W]
            lines.append("│" + detail.ljust(W) + "│")

            # Line 3: min_stake + skills + created
            info_parts: list[str] = []
            if min_stake == 0:
                info_parts.append("FREE")
            else:
                info_parts.append(f"min: {min_stake} AWP")
            info_parts.append("skills: ✓" if skills_uri else "skills: ·")
            if created:
                info_parts.append(created)
            info_line = "    " + "  ".join(info_parts)
            if len(info_line) > W:
                info_line = info_line[:W]
            lines.append("│" + info_line.ljust(W) + "│")

            # Separator between subnets (not after the last one)
            if i < len(subnets) - 1:
                lines.append("│" + "  " + "· " * ((W - 4) // 2) + " " * ((W - 4) % 2) + "  │")

        lines.append("├" + "─" * W + "┤")
        total = len(subnets)
        free = sum(1 for s in subnets if s.get("min_stake", 0) == 0)
        with_skills = sum(1 for s in subnets if s.get("skills_uri"))
        summary = f"  {total} subnets · {free} free · {with_skills} with skills"
        lines.append("│" + summary.ljust(W) + "│")
    lines.append("└" + "─" * W + "┘")
    return "\n".join(lines)


# ── Welcome Message ─────────────────────────────

RECEIPT_WIDTH = 42  # Receipt content width (excluding border)

WELCOME_BANNER = """\
┌──────────────────────────────────────────┐
│                                          │
│           ╭──────────────╮               │
│           │              │               │
│           │   >     <    │               │
│           │      ‿       │               │
│           │              │               │
│           ╰──────────────╯               │
│                                          │
│        agent · work · protocol           │
│                                          │
│    one protocol. infinite jobs.          │
│    nonstop earnings.                     │
│                                          │
├──────────────────────────────────────────┤
│  QUICK START                             │
│                                          │
│  "start working"    register + join      │
│  "check my balance" staking overview     │
│  "list subnets"     browse active        │
│  "awp help"         all commands         │
│                                          │
│  no AWP tokens needed to start.          │
│  register free → pick a subnet → earn.   │
└──────────────────────────────────────────┘"""


def send_welcome(subnets: list[dict[str, Any]]) -> None:
    """Send the welcome message (banner + active subnets). Pushes via notify if possible, otherwise prints to stdout."""
    subnet_text = format_subnet_list(subnets)
    full_message = f"{WELCOME_BANNER}\n\n{subnet_text}"

    if _can_push():
        notify("Hello World from the World of Agents!", full_message)
    else:
        # Cannot push — print to stdout instead
        print()
        for line in full_message.split("\n"):
            print(line)
        print()
        # Still write to the notification file (agent can read it on next load)
        notify("Hello World from the World of Agents!", full_message)


# ── New Subnet Detection ────────────────────────

def detect_new_subnets(
    current: list[dict[str, Any]],
    known_ids: set[int],
) -> list[dict[str, Any]]:
    """Compare current subnets against known IDs and return any newly discovered subnets."""
    new_subnets = []
    for s in current:
        sid = s.get("subnet_id")
        if sid is not None and int(sid) not in known_ids:
            new_subnets.append(s)
    return new_subnets


# ── 1. Wallet Installation ───────────────────────

def ensure_wallet_installed() -> bool:
    """Check whether awp-wallet is installed (does NOT auto-download or execute remote scripts).

    If not installed, prints installation instructions and returns False.
    The user must review and run the install commands themselves.
    """
    if shutil.which("awp-wallet"):
        return True

    # Also check ~/.local/bin (the default install location used by install.sh)
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
    """Check whether the wallet is initialized and return the address, or None.

    Does NOT auto-initialize — wallet creation generates a key pair and
    must be explicitly run by the user via `awp-wallet init`.
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
    """Check registration status, display info, and return is_registered."""
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
        log("│  You are not registered yet.                  │")
        log("│                                              │")
        log('│  To register (free, gasless), tell your      │')
        log('│  agent: "start working"                      │')
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

    # Subnet list
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
        log('→ Next: say "start working" to register for free')
    else:
        log('→ Next: say "list subnets" to browse, or "install skill for subnet #1" to start')
    print()

    return is_registered

# ── 4. Update Checker ────────────────────────────

def get_local_version() -> str:
    """Read the version number from the local SKILL.md."""
    try:
        text = SKILL_MD.read_text()
        match = re.search(r"Skill version:\s*([\d.]+)", text)
        return match.group(1) if match else ""
    except Exception:
        return ""

def get_remote_version(url: str) -> str:
    """Read the version number from a remote SKILL.md."""
    text = fetch_text(url)
    if not text:
        return ""
    match = re.search(r"Skill version:\s*([\d.]+)", text)
    return match.group(1) if match else ""

def check_updates() -> None:
    """Check for awp-skill and awp-wallet updates (informational only — no auto-download or execution)."""
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

    # awp-wallet — compare versions, notify only, no auto-update
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
    import argparse
    parser = argparse.ArgumentParser(description="AWP Daemon")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL,
                        help=f"Check interval in seconds (minimum 10, default {CHECK_INTERVAL})")
    args = parser.parse_args()

    interval = max(args.interval, 10)

    # Write PID file so the daemon can be stopped externally (kill $(cat ~/.awp/daemon.pid))
    NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Phase 1: Fetch subnets + send welcome message
    log("Phase 1: Welcome...")
    initial_subnets = fetch_active_subnets()
    send_welcome(initial_subnets)
    known_subnet_ids: set[int] = {
        int(s["subnet_id"]) for s in initial_subnets if s.get("subnet_id") is not None
    }

    # Phase 2: Check dependencies (no auto-install; notify and continue if missing)
    log("Phase 2: Checking awp-wallet dependency...")
    wallet_ready = ensure_wallet_installed()

    # Phase 3: Check wallet (no auto-init; notify and continue if missing)
    wallet_addr: Optional[str] = None
    if wallet_ready:
        log("Phase 3: Checking wallet...")
        wallet_addr = ensure_wallet_initialized()

    # Phase 4: Display status + push onboarding notification
    last_registered: Optional[bool] = None
    if wallet_addr:
        log("Phase 4: Checking status...")
        last_registered = check_and_notify(wallet_addr)
        # Wallet ready but not registered — prompt to register
        if not last_registered:
            short_addr = f"{wallet_addr[:8]}...{wallet_addr[-4:]}" if len(wallet_addr) >= 12 else wallet_addr
            notify("Wallet Ready — Next Step",
                   f"Wallet is ready: {short_addr}\n"
                   "You are not registered yet. Registration is FREE (gasless).\n"
                   'Tell your agent: "start working"',
                   "info")
        # Wallet ready and registered — guide user to pick a subnet and start working
        else:
            short_addr = f"{wallet_addr[:8]}...{wallet_addr[-4:]}" if len(wallet_addr) >= 12 else wallet_addr
            notify("Registered — Ready to Work",
                   f"Wallet {short_addr} is registered.\n"
                   'Next steps:\n'
                   '  - Tell your agent: "list subnets" to browse available subnets\n'
                   '  - Tell your agent: "install skill for subnet #N" to join a subnet\n'
                   '  - Or just say: "start working" to auto-pick a free subnet',
                   "info")
    else:
        if not wallet_ready:
            notify("Wallet Not Ready",
                   "awp-wallet is not installed. Cannot proceed without it.\n"
                   "Tell your agent:\n"
                   '  "install awp-wallet from https://github.com/awp-core/awp-wallet"\n'
                   "The agent will clone the repo and run install.sh for you.",
                   "warning")
        else:
            notify("Wallet Not Initialized",
                   "awp-wallet is installed but no wallet exists yet.\n"
                   "Tell your agent:\n"
                   '  "initialize my wallet"\n'
                   "The agent will run awp-wallet init to create an agent work wallet.\n"
                   "Note: Do NOT store personal assets in this wallet.",
                   "warning")

    # Write initial status file
    write_status(wallet_ready, wallet_addr, last_registered,
                 len(initial_subnets), datetime.now().isoformat())

    # Phase 5: Check for updates (informational only, no auto-update)
    log("Phase 5: Checking for updates (informational only)...")
    check_updates()

    # Phase 6: Continuous monitoring loop
    log("")
    log(f"Daemon running. Checking every {interval}s.")
    log("Press Ctrl+C to stop.")
    print()

    # Update check interval: every 12 cycles (~1 hour) to avoid network requests every cycle
    UPDATE_CHECK_EVERY = 12
    cycle_count = 0

    try:
        while True:
            time.sleep(interval)
            cycle_count += 1

            try:
                # If wallet was previously unavailable, re-check each cycle
                if not wallet_addr:
                    if not wallet_ready:
                        wallet_ready = ensure_wallet_installed()
                    if wallet_ready:
                        wallet_addr = ensure_wallet_initialized()
                    if wallet_addr:
                        log("Wallet now available!")
                        last_registered = check_and_notify(wallet_addr)
                        # Wallet just became ready — push next-step guidance
                        if not last_registered:
                            short_addr = f"{wallet_addr[:8]}...{wallet_addr[-4:]}" if len(wallet_addr) >= 12 else wallet_addr
                            notify("Wallet Ready — Next Step",
                                   f"Wallet is now ready: {short_addr}\n"
                                   "You are not registered yet. Registration is FREE (gasless).\n"
                                   'Tell your agent: "start working"',
                                   "info")

                # Registration status check (only when wallet is available)
                if wallet_addr:
                    is_registered = False
                    check = api_get(f"/address/{wallet_addr}/check")
                    if check:
                        is_registered = check.get("isRegistered", False)

                    if is_registered != last_registered and last_registered is not None:
                        if is_registered:
                            log("Registration detected! You are now registered.")
                            short_addr = f"{wallet_addr[:8]}...{wallet_addr[-4:]}" if len(wallet_addr) >= 12 else wallet_addr
                            notify("Registered — Ready to Work",
                                   f"Wallet {short_addr} is now registered!\n"
                                   'Next steps:\n'
                                   '  - Tell your agent: "list subnets" to browse available subnets\n'
                                   '  - Tell your agent: "install skill for subnet #N" to join a subnet\n'
                                   '  - Or just say: "start working" to auto-pick a free subnet',
                                   "info")
                            check_and_notify(wallet_addr)
                        else:
                            log("Registration lost — address is no longer registered.")
                            short_addr = f"{wallet_addr[:8]}...{wallet_addr[-4:]}" if len(wallet_addr) >= 12 else wallet_addr
                            notify("Deregistered",
                                   f"Address {short_addr} is no longer registered.\n"
                                   'To re-register (free), tell your agent: "start working"',
                                   "warning")

                    last_registered = is_registered

                # New subnet detection
                current_subnets = fetch_active_subnets()
                new_subnets = detect_new_subnets(current_subnets, known_subnet_ids)
                if new_subnets:
                    for s in new_subnets:
                        sid = s.get("subnet_id", "?")
                        name = s.get("name", "Unknown")
                        symbol = s.get("symbol", "")
                        owner_raw = s.get("owner", "") or ""
                        owner = (owner_raw[:10] + "...") if len(owner_raw) > 10 else owner_raw
                        min_stake = s.get("min_stake", 0)
                        skills = s.get("skills_uri", "")
                        msg = f"#{sid} \"{name}\" ({symbol}) by {owner}"
                        if min_stake == 0:
                            msg += " | FREE (no staking required)"
                        else:
                            msg += f" | min stake: {min_stake} AWP"
                        if skills:
                            msg += " | has skills"
                        notify("New Subnet", msg)
                    # Update known subnet set
                    known_subnet_ids.update(
                        int(s["subnet_id"]) for s in new_subnets if s.get("subnet_id") is not None
                    )

                # Update status file
                write_status(wallet_ready, wallet_addr, last_registered,
                             len(current_subnets), datetime.now().isoformat())

                # Update check (every UPDATE_CHECK_EVERY cycles)
                if cycle_count % UPDATE_CHECK_EVERY == 0:
                    check_updates()

            except Exception as e:
                warn(f"Monitor cycle error: {e}")

    except KeyboardInterrupt:
        print()
        log("Daemon stopped.")
    finally:
        # Clean up PID file on exit
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

if __name__ == "__main__":
    main()
