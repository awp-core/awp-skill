#!/usr/bin/env python3
"""
AWP Daemon — background monitoring service for AWP skill.

Runs continuously:
  1. Send welcome message (banner + active worknets) via notify or stdout
  2. Check that awp-wallet is installed (does NOT auto-install)
  3. Check that wallet is initialized (does NOT auto-init)
  4. Show registration status + available worknets
  5. Check for version updates (informational only, no auto-update)
  6. Monitor: registration state changes, new worknet detection

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
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

# Make the shared awp_lib helpers importable when the daemon is launched from anywhere
sys.path.insert(0, str(Path(__file__).parent.resolve()))
from awp_lib import rpc as _awp_rpc  # noqa: E402

# ── Config ───────────────────────────────────────

CHECK_INTERVAL = 300  # seconds (5 min default)
_CHAIN_NAMES: dict[int, str] = {1: "ETH", 56: "BSC", 8453: "Base", 42161: "Arb"}
WALLET_REPO = "https://github.com/awp-core/awp-wallet.git"
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_MD = SCRIPT_DIR.parent / "SKILL.md"
NOTIFY_DIR = Path.home() / ".awp"
NOTIFY_FILE = NOTIFY_DIR / "notifications.json"
STATUS_FILE = NOTIFY_DIR / "status.json"
PID_FILE = NOTIFY_DIR / "daemon.pid"
RECEIPT_WIDTH = 42  # Receipt content width (excluding border)

# ── Logging & Notifications ──────────────────────


def log(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] {msg}")


def warn(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ⚠ {msg}")


def err(msg: str) -> None:
    print(f"[AWP {datetime.now():%H:%M:%S}] ✗ {msg}", file=sys.stderr)


def short_addr(addr: str) -> str:
    """Format an Ethereum address as first-8 + last-4 (e.g., 0xAbCdEf12...cdef)."""
    return f"{addr[:8]}...{addr[-4:]}" if len(addr) >= 12 else addr


def chain_label(worknet: dict[str, Any]) -> str:
    """Derive a short chain label from a worknet's chainId field or worknetId format.

    worknetId = chainId * 100_000_000 + localId, so chainId = worknetId // 100_000_000.
    Falls back to the explicit chainId field if present.
    """
    chain_id = _field(worknet, "chainId", "chain_id", default=None)
    if chain_id is None:
        wid = _field(worknet, "worknetId", "subnet_id", "subnetId", default=None)
        if wid is not None:
            try:
                chain_id = int(wid) // 100_000_000
            except (ValueError, TypeError):
                pass
    if chain_id is not None:
        try:
            return _CHAIN_NAMES.get(int(chain_id), f"#{chain_id}")
        except (ValueError, TypeError):
            pass
    return "?"


def _field(obj: dict[str, Any], *names: str, default: Any = "") -> Any:
    """Return the first present field from `obj`, checking each name in order.

    The AWP API has historically exposed worknet fields in snake_case
    (__`WORKNET_ID_BT`_0__, `min_stake`, `skills_uri`, `created_at`) while the spec
    documents camelCase. Accept either shape so the daemon works across server
    conventions without silent "(none found)" failures.
    """
    for n in names:
        if n in obj and obj[n] is not None:
            return obj[n]
    return default


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
        except (OSError, json.JSONDecodeError):
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
    tmp_file: Optional[Path] = None
    try:
        NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
        notifications = []
        if NOTIFY_FILE.exists():
            try:
                notifications = json.loads(NOTIFY_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                notifications = []

        notifications.append(
            {
                "timestamp": timestamp,
                "level": level,
                "title": f"🪼 {title}",
                "message": message,
            }
        )

        # Keep only the latest 50 entries; atomic write (write to temp file then rename)
        notifications = notifications[-50:]
        tmp_file = NOTIFY_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(notifications, indent=2))
        os.replace(str(tmp_file), str(NOTIFY_FILE))
    except (OSError, TypeError, ValueError) as e:
        warn(f"Failed to write notification: {e}")
        if tmp_file is not None:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass

    # 2. Send via OpenClaw (if openclaw CLI is available)
    openclaw_bin = _find_openclaw()
    if openclaw_bin:
        channel, target = _get_openclaw_config()
        if channel and target:
            try:
                subprocess.run(
                    [
                        openclaw_bin,
                        "message",
                        "send",
                        "--channel",
                        channel,
                        "--target",
                        target,
                        "--message",
                        f"**🪼 {title}**\n```\n{message}\n```",
                    ],
                    capture_output=True,
                    timeout=10,
                )
            except (subprocess.SubprocessError, OSError):
                pass  # Silently skip on send failure

    # 3. Terminal output
    log(f"[NOTIFY] {title}: {message}")


# ── Helpers ──────────────────────────────────────


def run(cmd: list[str]) -> Tuple[int, str]:
    """Run a command (as a list, no shell injection risk) and return (returncode, stdout)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return 1, ""
    except (subprocess.SubprocessError, OSError) as e:
        return 1, str(e)


def rpc(method: str, params: Optional[dict[str, Any]] = None) -> Optional[Any]:
    """Thin wrapper around awp_lib.rpc that never terminates the daemon.

    The shared helper dies on RPC failure (appropriate for one-shot CLI scripts),
    but the long-running daemon must log and continue. We swallow SystemExit and
    network errors here so a temporary API outage does not crash the monitoring loop.
    """
    try:
        return _awp_rpc(method, params)
    except SystemExit:
        warn(f"RPC error for {method}")
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        warn(f"RPC call failed for {method}: {e}")
        return None


def fetch_text(url: str) -> str:
    """Fetch remote text content."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, UnicodeDecodeError):
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
    worknets_count: int,
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
        next_step = 'Tell your agent: "list worknets" or "start working"'

    status = {
        "phase": phase,
        "wallet_installed": wallet_installed,
        "wallet_address": wallet_addr,
        "registered": registered,
        "active_worknets": worknets_count,
        "next_step": next_step,
        "last_check": last_check,
    }
    try:
        NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(status, indent=2))
    except OSError:
        pass


# ── Worknet Tracking ─────────────────────────────


def fetch_announcements() -> list[dict[str, Any]]:
    """Fetch the active-announcements list from the REST endpoint."""
    url = "https://api.awp.sh/api/announcements"
    req = urllib.request.Request(url, headers={"User-Agent": "awp-daemon/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if isinstance(data, list):
                return data
            return []
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        warn(f"Failed to fetch announcements: {e}")
        return []


def fetch_active_worknets() -> list[dict[str, Any]]:
    """Fetch the list of active worknets."""
    result = rpc("subnets.list", {"status": "Active", "limit": 50})
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        # Paginated response: extract items/worknets/data field
        for key in ("items", "worknets", "data"):
            if isinstance(result.get(key), list):
                return result[key]
    return []


def format_worknet_list(worknets: list[dict[str, Any]]) -> str:
    """Format the worknet list in receipt style with detailed info per worknet."""
    W = RECEIPT_WIDTH  # Content width (matches the banner)
    lines: list[str] = []
    lines.append("┌" + "─" * W + "┐")
    lines.append("│" + "ACTIVE WORKNETS".center(W) + "│")
    lines.append("├" + "─" * W + "┤")
    if not worknets:
        lines.append("│" + "  No active worknets yet.".ljust(W) + "│")
        lines.append("│" + "  Your agent is registered".ljust(W) + "│")
        lines.append("│" + "  and ready — waiting for".ljust(W) + "│")
        lines.append("│" + "  the first worknet to go".ljust(W) + "│")
        lines.append("│" + "  live. Check back soon!".ljust(W) + "│")
    else:
        for i, s in enumerate(worknets):
            sid = _field(s, "worknetId", "subnet_id", "subnetId", default="?")
            name = _field(s, "name", default="Unknown")
            symbol = _field(s, "symbol", default="")
            min_stake = _field(s, "minStake", "min_stake", default=0)
            status = _field(s, "status", default="")
            owner_raw = _field(s, "owner", default="") or ""
            owner = (
                (owner_raw[:6] + "..." + owner_raw[-4:])
                if len(owner_raw) > 14
                else owner_raw
            )
            skills_uri = _field(s, "skillsURI", "skills_uri", default="")
            created_raw = _field(s, "createdAt", "created_at", default="")
            created = str(created_raw) if created_raw else ""
            if len(created) >= 10:
                created = created[:10]  # YYYY-MM-DD

            # Line 1: #id NAME (SYMBOL) [Chain]
            chain = chain_label(s)
            header = f"  #{sid} {name}"
            if symbol:
                header += f" ({symbol})"
            header += f" [{chain}]"
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

            # Separator between worknets (not after the last one)
            if i < len(worknets) - 1:
                lines.append(
                    "│" + "  " + "· " * ((W - 4) // 2) + " " * ((W - 4) % 2) + "  │"
                )

        lines.append("├" + "─" * W + "┤")
        total = len(worknets)
        free = sum(
            1 for s in worknets if _field(s, "minStake", "min_stake", default=0) == 0
        )
        with_skills = sum(
            1 for s in worknets if _field(s, "skillsURI", "skills_uri", default="")
        )
        summary = f"  {total} worknets · {free} free · {with_skills} with skills"
        lines.append("│" + summary.ljust(W) + "│")
    lines.append("└" + "─" * W + "┘")
    return "\n".join(lines)


# ── Welcome Message ─────────────────────────────

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
│  "list worknets"     browse active        │
│  "awp help"         all commands         │
│                                          │
│  no AWP tokens needed to start.          │
│  register free → pick a worknet → earn.   │
└──────────────────────────────────────────┘"""


def send_welcome(worknets: list[dict[str, Any]]) -> None:
    """Send the welcome message (banner + active worknets). Pushes via notify if possible, otherwise prints to stdout."""
    worknet_text = format_worknet_list(worknets)
    full_message = f"{WELCOME_BANNER}\n\n{worknet_text}"

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


# ── New Worknet Detection ────────────────────────


def detect_new_worknets(
    current: list[dict[str, Any]],
    known_ids: set[int],
) -> list[dict[str, Any]]:
    """Compare current worknets against known IDs and return any newly discovered ones."""
    new_worknets = []
    for s in current:
        sid = _field(s, "worknetId", "subnet_id", "subnetId", default=None)
        if sid is not None:
            try:
                if int(sid) not in known_ids:
                    new_worknets.append(s)
            except (ValueError, TypeError):
                continue
    return new_worknets


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
    err("Install the official AWP wallet:")
    err(f"  {WALLET_REPO}")
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
    check = rpc("address.check", {"address": wallet_addr})

    print()
    log("── agent status ──────────────────────")

    if not check:
        log(f"Address:    {wallet_addr}")
        log("Status:     API unavailable")
        log("──────────────────────────────────────")
        return None  # type: ignore[return-value]  # None = 未知状态，防止假通知

    is_registered = check.get("isRegistered", False)

    if not is_registered:
        log(f"Address:    {wallet_addr}")
        log("Status:     NOT REGISTERED")
        log("")
        log("┌─────────────────────────────────────────────┐")
        log("│  You are not registered yet.                  │")
        log("│                                              │")
        log("│  To register (free, gasless), tell your      │")
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

        balance = rpc("staking.getBalance", {"address": wallet_addr})
        if balance and isinstance(balance, dict):
            log(f"Staked:     {wei_to_awp(balance.get('totalStaked', '0'))} AWP")
            log(f"Allocated:  {wei_to_awp(balance.get('totalAllocated', '0'))} AWP")
            log(f"Unallocated:{wei_to_awp(balance.get('unallocated', '0'))} AWP")

    log("──────────────────────────────────────")

    # Worknet list
    print()
    log("── available worknets ─────────────────")

    worknets = fetch_active_worknets()
    if worknets:
        for s in worknets:
            sid = _field(s, "worknetId", "subnet_id", "subnetId", default="?")
            name = _field(s, "name", default="Unknown")
            min_stake = _field(s, "minStake", "min_stake", default=0)
            skills = "✓" if _field(s, "skillsURI", "skills_uri", default="") else "—"
            chain = chain_label(s)
            log(
                f"  #{sid}  {str(name):<26s} [{chain:<4s}] min: {min_stake} AWP  skills: {skills}"
            )

        total = len(worknets)
        free = sum(
            1 for s in worknets if _field(s, "minStake", "min_stake", default=0) == 0
        )
        with_skills = sum(
            1 for s in worknets if _field(s, "skillsURI", "skills_uri", default="")
        )
        log("")
        log(f"{total} worknets. {free} free (no staking). {with_skills} with skills.")
    else:
        log("  No active worknets yet — your agent is registered and ready.")
        log("  Waiting for the first worknet to go live. No action needed.")

    log("──────────────────────────────────────")

    print()
    if not is_registered:
        log('→ Next: say "start working" to register for free')
    else:
        if worknets:
            log(
                '→ Next: say "list worknets" to browse, or "install skill for worknet #1" to start'
            )
        else:
            log("→ All set! Your agent will start working as soon as worknets go live.")
            log('  Run "list worknets" anytime to check for new ones.')
    print()

    return is_registered


# ── 4. Update Checker ────────────────────────────


def get_local_version() -> str:
    """Read the version number from the local SKILL.md."""
    try:
        text = SKILL_MD.read_text()
        match = re.search(r"Skill version:\s*([\d.]+)", text)
        return match.group(1) if match else ""
    except (OSError, UnicodeDecodeError):
        return ""


def get_remote_version(url: str) -> str:
    """Read the version number from a remote SKILL.md."""
    text = fetch_text(url)
    if not text:
        return ""
    match = re.search(r"Skill version:\s*([\d.]+)", text)
    return match.group(1) if match else ""


def fetch_changelog(version: str) -> str:
    """Extract changelog summary for a specific version from remote CHANGELOG.md."""
    text = fetch_text(
        "https://raw.githubusercontent.com/awp-core/awp-skill/main/CHANGELOG.md"
    )
    if not text:
        return ""
    # Find the target version section: ## vX.Y.Z
    pattern = rf"(?m)^## v{re.escape(version)}\s*\n"
    match = re.search(pattern, text)
    if not match:
        return ""
    start = match.end()
    # Extract until next ## or end of file
    next_section = re.search(r"(?m)^## ", text[start:])
    section = (
        text[start : start + next_section.start()] if next_section else text[start:]
    )
    # Extract heading lines and first 8 bullet points
    lines: list[str] = []
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            # Sub-heading (### ...)
            lines.append(stripped.lstrip("# "))
        elif stripped.startswith("- "):
            lines.append(stripped)
        if len(lines) >= 8:
            break
    if len(lines) >= 8:
        lines.append("...")
    return "\n".join(lines)


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
            changelog = fetch_changelog(remote_ver)
            msg = f"awp-skill {remote_ver} available (current: {local_ver})"
            if changelog:
                msg += f"\n\nChangelog:\n{changelog}"
            notify("Update Available", msg)
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
                notify(
                    "Update Available",
                    f"awp-wallet {remote_wallet} available (current: {local_wallet})",
                )
            else:
                log(f"awp-wallet {local_wallet} — up to date ✓")
        elif remote_wallet:
            log(f"awp-wallet latest: {remote_wallet}")


# ── Main ─────────────────────────────────────────


def main() -> None:
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="AWP Daemon")
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Check interval in seconds (minimum 10, default {CHECK_INTERVAL})",
    )
    args = parser.parse_args()

    interval = max(args.interval, 10)

    # Handle SIGTERM so `kill $(cat ~/.awp/daemon.pid)` triggers PID cleanup via finally.
    # Default SIGTERM terminates at C level, bypassing Python finally blocks.
    # SystemExit propagates through finally blocks, ensuring PID file is removed.
    def _sigterm_handler(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    # Write PID file so the daemon can be stopped externally (kill $(cat ~/.awp/daemon.pid))
    NOTIFY_DIR.mkdir(parents=True, exist_ok=True)

    # 并发保护：检查已有 daemon 是否在运行
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text().strip())
            os.kill(existing_pid, 0)  # 信号 0 仅检查进程是否存在
            die(
                f"Daemon already running (PID {existing_pid}). Stop it first: kill {existing_pid}"
            )
        except (ValueError, OSError):
            pass  # PID 文件过期或进程已终止 — 安全覆盖

    try:
        PID_FILE.write_text(str(os.getpid()))
        _run_daemon(interval)
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


def _run_daemon(interval: int) -> None:
    """Main daemon logic (wrapped by main() in try/finally for PID file cleanup)."""
    # Phase 1: Fetch worknets + send welcome message
    log("Phase 1: Welcome...")
    initial_worknets = fetch_active_worknets()
    send_welcome(initial_worknets)
    known_worknet_ids: set[int] = set()
    for s in initial_worknets:
        sid = _field(s, "worknetId", "subnet_id", "subnetId", default=None)
        if sid is not None:
            try:
                known_worknet_ids.add(int(sid))
            except (ValueError, TypeError):
                continue

    # Initialize announcement tracking set — pre-populate with existing IDs to avoid duplicate notifications on first start
    seen_announcement_ids: set[int] = set()
    initial_announcements = fetch_announcements()
    for ann in initial_announcements:
        ann_id = ann.get("id")
        if ann_id is not None:
            seen_announcement_ids.add(int(ann_id))
    if initial_announcements:
        log(
            f"Recorded {len(seen_announcement_ids)} existing announcements (no notifications sent)"
        )

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
            addr = short_addr(wallet_addr)
            notify(
                "Wallet Ready — Next Step",
                f"Wallet is ready: {addr}\n"
                "You are not registered yet. Registration is FREE (gasless).\n"
                'Tell your agent: "start working"',
                "info",
            )
        # Wallet ready and registered — guide user to pick a worknet and start working
        else:
            addr = short_addr(wallet_addr)
            notify(
                "Registered — Ready to Work",
                f"Wallet {addr} is registered.\n"
                "Next steps:\n"
                '  - Tell your agent: "list worknets" to browse available worknets\n'
                '  - Tell your agent: "install skill for worknet #N" to join a worknet\n'
                '  - Or just say: "start working" to auto-pick a free worknet',
                "info",
            )
    else:
        if not wallet_ready:
            notify(
                "Wallet Not Ready",
                "awp-wallet is not installed. Cannot proceed without it.\n"
                "Tell your agent to install the official AWP wallet:\n"
                '  "install awp-wallet from https://github.com/awp-core/awp-wallet"',
                "warning",
            )
        else:
            notify(
                "Wallet Not Initialized",
                "awp-wallet is installed but no wallet exists yet.\n"
                "Tell your agent:\n"
                '  "initialize my wallet"\n'
                "The agent will run awp-wallet init to create an agent work wallet.\n"
                "Note: Do NOT store personal assets in this wallet.",
                "warning",
            )

    # Write initial status file
    write_status(
        wallet_ready,
        wallet_addr,
        last_registered,
        len(initial_worknets),
        datetime.now().isoformat(),
    )

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
                            addr = short_addr(wallet_addr)
                            notify(
                                "Wallet Ready — Next Step",
                                f"Wallet is now ready: {addr}\n"
                                "You are not registered yet. Registration is FREE (gasless).\n"
                                'Tell your agent: "start working"',
                                "info",
                            )

                # Registration status check (only when wallet is available)
                if wallet_addr:
                    is_registered = None  # None = API 不可达，不更新状态
                    check = rpc("address.check", {"address": wallet_addr})
                    if check:
                        is_registered = bool(check.get("isRegistered", False))

                    # 仅在 API 可达时（is_registered 非 None）才更新状态和触发通知
                    if (
                        is_registered is not None
                        and is_registered != last_registered
                        and last_registered is not None
                    ):
                        if is_registered:
                            log("Registration detected! You are now registered.")
                            addr = short_addr(wallet_addr)
                            notify(
                                "Registered — Ready to Work",
                                f"Wallet {addr} is now registered!\n"
                                "Next steps:\n"
                                '  - Tell your agent: "list worknets" to browse available worknets\n'
                                '  - Tell your agent: "install skill for worknet #N" to join a worknet\n'
                                '  - Or just say: "start working" to auto-pick a free worknet',
                                "info",
                            )
                            check_and_notify(wallet_addr)
                        else:
                            log("Registration lost — address is no longer registered.")
                            addr = short_addr(wallet_addr)
                            notify(
                                "Deregistered",
                                f"Address {addr} is no longer registered.\n"
                                'To re-register (free), tell your agent: "start working"',
                                "warning",
                            )

                    if is_registered is not None:
                        last_registered = is_registered

                # New worknet detection
                current_worknets = fetch_active_worknets()
                new_worknets = detect_new_worknets(current_worknets, known_worknet_ids)
                if new_worknets:
                    for s in new_worknets:
                        sid = _field(
                            s, "worknetId", "subnet_id", "subnetId", default="?"
                        )
                        name = _field(s, "name", default="Unknown")
                        symbol = _field(s, "symbol", default="")
                        owner_raw = _field(s, "owner", default="") or ""
                        owner = (
                            (owner_raw[:10] + "...")
                            if len(owner_raw) > 10
                            else owner_raw
                        )
                        min_stake = _field(s, "minStake", "min_stake", default=0)
                        skills = _field(s, "skillsURI", "skills_uri", default="")
                        chain = chain_label(s)
                        msg = f'#{sid} "{name}" ({symbol}) [{chain}] by {owner}'
                        if min_stake == 0:
                            msg += " | FREE (no staking required)"
                        else:
                            msg += f" | min stake: {min_stake} AWP"
                        if skills:
                            msg += " | has skills"
                        notify("New Worknet", msg)
                    # Update known worknet set
                    for s in new_worknets:
                        sid = _field(
                            s, "worknetId", "subnet_id", "subnetId", default=None
                        )
                        if sid is not None:
                            try:
                                known_worknet_ids.add(int(sid))
                            except (ValueError, TypeError):
                                continue

                # Poll announcements — check for new ones and send notifications
                announcements = fetch_announcements()
                priority_map: dict[int, str] = {0: "info", 1: "warning", 2: "critical"}
                for ann in announcements:
                    ann_id = ann.get("id")
                    try:
                        ann_id_int = int(ann_id) if ann_id is not None else None
                    except (ValueError, TypeError):
                        continue
                    if (
                        ann_id_int is not None
                        and ann_id_int not in seen_announcement_ids
                    ):
                        category = ann.get("category", "general")
                        title = ann.get("title", "Announcement")
                        content = ann.get("content", "")
                        priority = ann.get("priority", 0)
                        level = priority_map.get(priority, "info")
                        notify(f"[{category.upper()}] {title}", content, level)
                        seen_announcement_ids.add(ann_id_int)

                # Prevent seen_announcement_ids from growing unbounded (keep latest 500)
                if len(seen_announcement_ids) > 500:
                    sorted_ids = sorted(seen_announcement_ids)
                    seen_announcement_ids = set(sorted_ids[-500:])

                # Update status file
                write_status(
                    wallet_ready,
                    wallet_addr,
                    last_registered,
                    len(current_worknets),
                    datetime.now().isoformat(),
                )

                # Update check (every UPDATE_CHECK_EVERY cycles)
                if cycle_count % UPDATE_CHECK_EVERY == 0:
                    check_updates()

            except (
                OSError,
                urllib.error.URLError,
                json.JSONDecodeError,
                subprocess.SubprocessError,
                ValueError,
                KeyError,
                TypeError,
            ) as e:
                # Broad enough to keep the daemon alive through transient failures,
                # but narrow enough that real programming bugs (AttributeError,
                # NameError, etc.) still crash the loop so they can be fixed.
                warn(f"Monitor cycle error: {e}")

    except KeyboardInterrupt:
        print()
        log("Daemon stopped.")


if __name__ == "__main__":
    main()
