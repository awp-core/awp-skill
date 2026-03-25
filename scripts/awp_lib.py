"""AWP shared script library — API calls, wallet commands, ABI encoding, input validation"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from decimal import Decimal
from pathlib import Path

_UINT256_MAX = 2**256 - 1

# ── Configuration ────────────────────────────────────────

API_BASE = os.environ.get("AWP_API_URL", "https://tapi.awp.sh/api")
RPC_URL = os.environ.get("EVM_RPC_URL", "https://mainnet.base.org")


# ── Output ────────────────────────────────────────

def info(msg: str) -> None:
    """Print JSON info message to stderr"""
    print(json.dumps({"info": msg}), file=sys.stderr)


def step(name: str, **kwargs: object) -> None:
    """Print execution step to stderr"""
    print(json.dumps({"step": name, **kwargs}), file=sys.stderr)


def die(msg: str) -> None:
    """Print error to stderr and exit"""
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


# ── HTTP ────────────────────────────────────────

def api_get(path: str) -> dict | list | None:
    """GET {API_BASE}/{path}, return parsed JSON"""
    url = f"{API_BASE}/{path.lstrip('/')}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        die(f"API request failed: {url} — {e}")
        return None  # unreachable


def api_post(url: str, body: dict) -> tuple[int, dict | str]:
    """POST JSON, return (http_code, parsed_body)"""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_str = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body_str)
        except json.JSONDecodeError:
            return e.code, body_str
    except (urllib.error.URLError, OSError) as e:
        die(f"POST failed: {url} — {e}")
        return 0, ""  # unreachable


def rpc_call(to: str, data: str) -> str:
    """eth_call via JSON-RPC, return hex result"""
    payload = {
        "jsonrpc": "2.0", "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"], "id": 1,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        RPC_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            # Check for RPC-level errors (revert, etc.)
            if "error" in result:
                err = result["error"]
                msg = err.get("message", err) if isinstance(err, dict) else err
                die(f"RPC error: {msg}")
            return result.get("result", "")
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        die(f"RPC call failed: {e}")
        return ""  # unreachable


def hex_to_int(val: str) -> int:
    """Convert hex string to int, die on failure"""
    if not val or val in ("null", "0x"):
        die("RPC returned empty/null value")
    return int(val, 16)


# ── Wallet commands ─────────────────────────────────────

def wallet_cmd(args: list[str]) -> str:
    """Execute awp-wallet command, return stdout"""
    try:
        result = subprocess.run(
            ["awp-wallet"] + args,
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        die(f"awp-wallet {args[0]} timed out after 60s")
        return ""  # unreachable
    if result.returncode != 0:
        die(f"awp-wallet {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def get_wallet_address() -> str:
    """Get wallet address (no token required), validate returned address format"""
    out = wallet_cmd(["receive"])
    try:
        addr = json.loads(out).get("eoaAddress")
    except json.JSONDecodeError:
        die(f"Invalid wallet response: {out}")
        return ""  # unreachable
    if not addr or addr == "null":
        die("Wallet address is empty")
    if not ADDR_RE.match(addr):
        die(f"Wallet returned invalid address format: {addr}")
    return addr


def wallet_send(token: str, to: str, data: str, value: str = "0") -> str:
    """Send raw contract call (calldata), return result JSON.

    awp-wallet send only supports token transfers, not calldata.
    This function bridges to the awp-wallet internal signing module via wallet-raw-call.mjs.
    """
    bridge = str(Path(__file__).parent / "wallet-raw-call.mjs")
    args = ["node", bridge, "--token", token, "--to", to, "--data", data, "--value", value]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        die("wallet-raw-call timed out after 120s")
        return ""  # unreachable
    if result.returncode != 0:
        die(f"wallet-raw-call failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def wallet_approve(token: str, asset: str, spender: str, amount: str) -> str:
    """Approve token spend, return result JSON"""
    return wallet_cmd(["approve", "--token", token, "--asset", asset,
                        "--spender", spender, "--amount", amount])


def wallet_sign_typed_data(token: str, data: dict) -> str:
    """EIP-712 sign, return signature hex"""
    out = wallet_cmd(["sign-typed-data", "--token", token, "--data", json.dumps(data)])
    try:
        sig = json.loads(out).get("signature", "")
    except json.JSONDecodeError:
        die(f"Invalid sign response: {out}")
        return ""  # unreachable
    if not sig:
        die("Empty signature returned")
    return sig


def wallet_balance(token: str, asset: str | None = None) -> str:
    """Query balance"""
    args = ["balance", "--token", token]
    if asset:
        args += ["--asset", asset]
    return wallet_cmd(args)


def wallet_status(token: str) -> str:
    """Query wallet status (address, session validity)"""
    return wallet_cmd(["status", "--token", token])


# ── Contract registry ───────────────────────────────────

def get_registry() -> dict:
    """Fetch /registry and return the full dictionary"""
    reg = api_get("registry")
    if not isinstance(reg, dict):
        die("Invalid /registry response")
    return reg


def require_contract(registry: dict, key: str) -> str:
    """Get contract address from registry, die if missing"""
    addr = registry.get(key)
    if not addr or addr == "null":
        die(f"Failed to get {key} from /registry")
    return addr


# ── ABI encoding ─────────────────────────────────────

def pad_address(addr: str) -> str:
    """Pad 0x address to 64 characters (zero-padded on left), validate hex format"""
    raw = addr.lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if not re.match(r"^[0-9a-f]+$", raw):
        die(f"pad_address: invalid hex characters in address: {addr}")
    if len(raw) > 64:
        die(f"pad_address: address too long after stripping 0x prefix: {addr}")
    return raw.zfill(64)


def pad_uint256(val: int) -> str:
    """Encode integer as 64-character hex (must be within uint256 range)"""
    if val < 0 or val > _UINT256_MAX:
        die(f"pad_uint256: value out of uint256 range: {val}")
    return format(val, "064x")


def to_wei(human_amount: str) -> int:
    """Convert human-readable AWP amount to wei (uses Decimal to avoid floating-point precision loss)"""
    try:
        result = int(Decimal(human_amount) * Decimal(10**18))
    except (ValueError, TypeError, ArithmeticError) as e:
        die(f"to_wei: invalid amount: {human_amount} ({e})")
        return 0  # unreachable
    if result <= 0:
        die(f"to_wei: converted amount is zero (input: {human_amount})")
    return result


def days_to_seconds(days: str) -> int:
    """Convert days to seconds (uses Decimal to avoid floating-point truncation)"""
    try:
        result = int(Decimal(days) * Decimal(86400))
    except (ValueError, TypeError, ArithmeticError) as e:
        die(f"days_to_seconds: invalid input: {days} ({e})")
        return 0  # unreachable
    if result <= 0:
        die(f"days_to_seconds: result is zero (input: {days} days)")
    return result


def encode_calldata(selector: str, *params: str) -> str:
    """Concatenate selector + params, validate selector format (0x + 8 hex)"""
    if not re.match(r"^0x[0-9a-fA-F]{8}$", selector):
        die(f"encode_calldata: invalid selector format: {selector} (expected 0x + 8 hex chars)")
    return selector + "".join(params)


# ── Input validation ─────────────────────────────────────

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def validate_address(addr: str, name: str = "address") -> str:
    """Validate Ethereum address format"""
    if not ADDR_RE.match(addr):
        die(f"Invalid --{name}: must be 0x + 40 hex chars")
    return addr


def validate_positive_number(val: str, name: str = "amount") -> str:
    """Validate positive number (decimals allowed)"""
    if not re.match(r"^[0-9]+\.?[0-9]*$", val):
        die(f"Invalid --{name}: must be a positive number")
    if Decimal(val) <= 0:
        die(f"Invalid --{name}: must be > 0")
    return val


def validate_positive_int(val: str, name: str = "id") -> int:
    """Validate positive integer (within uint256 range)"""
    if not re.match(r"^[0-9]+$", val):
        die(f"Invalid --{name}: must be a positive integer > 0")
    n = int(val)
    if n <= 0 or n > _UINT256_MAX:
        die(f"Invalid --{name}: must be > 0 and <= 2^256-1")
    return n


# ── EIP-712 construction ─────────────────────────────────

def get_eip712_domain(registry: dict) -> dict:
    """Get EIP-712 domain info from registry"""
    domain = registry.get("eip712Domain", {})
    name = domain.get("name")
    version = domain.get("version")
    chain_id = domain.get("chainId")
    contract = domain.get("verifyingContract")

    # fallback
    if not name:
        name = "AWPRegistry"
        version = "1"
        info("eip712Domain not in registry, using fallback")
    if not version:
        version = "1"
    if not chain_id:
        chain_id = registry.get("chainId")
    if not contract:
        contract = registry.get("awpRegistry")

    if not chain_id or not contract:
        die("Cannot determine EIP-712 domain from /registry")

    return {
        "name": name,
        "version": str(version),
        "chainId": int(chain_id),
        "verifyingContract": contract,
    }


def build_eip712(domain: dict, primary_type: str, type_fields: list[dict],
                 message: dict) -> dict:
    """Build complete EIP-712 typed data"""
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            primary_type: type_fields,
        },
        "primaryType": primary_type,
        "domain": domain,
        "message": message,
    }


# ── Common argument parsing ─────────────────────────────────

def base_parser(description: str) -> argparse.ArgumentParser:
    """Create base argument parser with --token"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--token", required=True, help="awp-wallet session token")
    return parser
