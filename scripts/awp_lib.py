"""AWP shared script library — API calls, wallet commands, ABI encoding, input validation"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from decimal import Decimal
from pathlib import Path

_UINT256_MAX = 2**256 - 1
_UINT128_MAX = 2**128 - 1

# ── Configuration ────────────────────────────────────────
# API and RPC URLs are hardcoded — not overridable via env vars.
# Rationale: wallet-raw-call.mjs already hardcodes these to prevent allowlist-bypass
# attacks where a malicious environment variable could redirect RPC reads that feed
# into signed-transaction parameters (e.g., lockEndTime, balances).

API_BASE = "https://api.awp.sh/v2"
RELAY_BASE = "https://api.awp.sh/api"
RPC_URL = "https://mainnet.base.org"

# Cloudflare-fronted endpoints (including mainnet.base.org) reject the default
# Python-urllib User-Agent with 403. Send a benign identifier instead.
_USER_AGENT = "awp-skill/1.4 (+https://github.com/awp-core/awp-skill)"

# Chain name → chainId mapping
_CHAIN_IDS: dict[str, int] = {
    "ethereum": 1,
    "eth": 1,
    "bsc": 56,
    "bnb": 56,
    "base": 8453,
    "arbitrum": 42161,
    "arb": 42161,
}
_DEFAULT_CHAIN_ID = 8453  # Base


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


def api_post(url: str, body: dict) -> tuple[int, dict | str]:
    """POST JSON, return (http_code, parsed_body)"""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
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


def rpc(method: str, params: dict | None = None) -> dict | list | None:
    """Call JSON-RPC 2.0 method on AWP API (v2 JSON-RPC endpoint)."""
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        API_BASE,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            if "error" in result:
                err = result["error"]
                msg = (
                    err.get("message", str(err)) if isinstance(err, dict) else str(err)
                )
                die(f"RPC error: {msg}")
            return result.get("result")
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        die(f"API request failed: {method} — {e}")
        return None  # unreachable


def rpc_call(to: str, data: str) -> str:
    """eth_call via JSON-RPC, return hex result"""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
        "id": 1,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        RPC_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            # Check for RPC-level errors (revert, etc.)
            if "error" in result:
                err = result["error"]
                msg = (
                    err.get("message", str(err)) if isinstance(err, dict) else str(err)
                )
                die(f"RPC error: {msg}")
            return result.get("result", "")
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        die(f"RPC call failed: {e}")
        return ""  # unreachable


def rpc_call_batch(calls: list[tuple[str, str]]) -> list[str]:
    """Batch eth_call via JSON-RPC. Returns results in the same order as `calls`.

    Each call is (to, data). Saves RTT when a script needs several independent
    read-only contract queries (e.g., initial price + two nonces in the same flow).
    """
    if not calls:
        return []
    payload = [
        {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
            "id": idx,
        }
        for idx, (to, data) in enumerate(calls, start=1)
    ]
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        RPC_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        die(f"RPC batch call failed: {e}")
        return []  # unreachable
    if not isinstance(results, list):
        die(f"RPC batch: expected list response, got {type(results).__name__}")
    # Sort by id to restore request order (servers may reorder batch responses)
    results.sort(key=lambda r: r.get("id", 0) if isinstance(r, dict) else 0)
    out: list[str] = []
    for r in results:
        if not isinstance(r, dict):
            die(f"RPC batch: malformed entry {r}")
        if "error" in r:
            err = r["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            die(f"RPC batch error: {msg}")
        out.append(r.get("result", ""))
    if len(out) != len(calls):
        die(f"RPC batch: expected {len(calls)} results, got {len(out)}")
    return out


def hex_to_int(val: str) -> int:
    """Convert hex string to int, die on failure"""
    if not val or val in ("null", "0x"):
        die("RPC returned empty/null value")
    return int(val, 16)


# ── Chain selection ─────────────────────────────────────

_ID_TO_CANONICAL: dict[int, str] = {
    1: "ethereum",
    56: "bsc",
    8453: "base",
    42161: "arbitrum",
}


def _get_chain_name() -> str:
    """Return the canonical chain name for wallet CLI commands.

    Reads EVM_CHAIN env var (same source as get_registry) and resolves aliases
    (eth→ethereum, bnb→bsc) to canonical names that wallet-raw-call.mjs recognizes.
    """
    chain_env = os.environ.get("EVM_CHAIN", "base").lower()
    # Resolve aliases to canonical chain names via chain ID lookup
    if chain_env in _CHAIN_IDS:
        return _ID_TO_CANONICAL.get(_CHAIN_IDS[chain_env], chain_env)
    # If it's a numeric chain ID, map back to canonical name
    try:
        chain_id = int(chain_env)
        return _ID_TO_CANONICAL.get(chain_id, "base")
    except ValueError:
        return "base"


# ── Wallet commands ─────────────────────────────────────


def _find_awp_wallet() -> str:
    """Find the awp-wallet binary, checking PATH + common install locations.

    npm/pip/yarn often install to directories NOT in $PATH on fresh shells
    (~/.local/bin, ~/.npm-global/bin, ~/.yarn/bin). This function mirrors
    the search logic in wallet-raw-call.mjs's findAwpWalletDir() so that
    Python scripts work even when Claude's Step 2 PATH export didn't stick.
    """
    import shutil

    # 1. Check PATH first (fast path)
    found = shutil.which("awp-wallet")
    if found:
        return found
    # 2. Check well-known install directories
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "awp-wallet",
        home / ".npm-global" / "bin" / "awp-wallet",
        home / ".yarn" / "bin" / "awp-wallet",
        Path("/usr/local/bin/awp-wallet"),
        Path("/usr/bin/awp-wallet"),
    ]
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            # Auto-add to PATH for the rest of this process so subsequent
            # calls (wallet_cmd, wallet_send) also find it.
            parent = str(candidate.parent)
            os.environ["PATH"] = f"{parent}:{os.environ.get('PATH', '')}"
            info(f"awp-wallet found at {candidate}, added {parent} to PATH")
            return str(candidate)
    die(
        "awp-wallet not found in PATH or common install locations "
        "(~/.local/bin, ~/.npm-global/bin, ~/.yarn/bin, /usr/local/bin). "
        "Install it: https://github.com/awp-core/awp-wallet"
    )
    return ""  # unreachable


# Cache the resolved path so we only search once per process
_AWP_WALLET_BIN: str = ""


def wallet_cmd(args: list[str]) -> str:
    """Execute awp-wallet command, return stdout.

    Automatically appends --chain based on EVM_CHAIN env var (default: base).
    """
    global _AWP_WALLET_BIN
    if not _AWP_WALLET_BIN:
        _AWP_WALLET_BIN = _find_awp_wallet()
    # Append --chain if not already specified by the caller
    if "--chain" not in args:
        args = args + ["--chain", _get_chain_name()]
    try:
        result = subprocess.run(
            [_AWP_WALLET_BIN] + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        die(f"awp-wallet {args[0]} timed out after 60s")
        return ""  # unreachable
    if result.returncode != 0:
        die(
            f"awp-wallet {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
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
    Passes --chain based on EVM_CHAIN env var (default: base).
    """
    bridge = str(Path(__file__).parent / "wallet-raw-call.mjs")
    chain = _get_chain_name()
    args = ["node", bridge, "--to", to, "--data", data, "--value", value, "--chain", chain]
    if token:
        args += ["--token", token]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        die("wallet-raw-call timed out after 120s")
        return ""  # unreachable
    if result.returncode != 0:
        die(f"wallet-raw-call failed: {result.stderr.strip() or result.stdout.strip()}")
    stdout = result.stdout.strip()
    # Detect on-chain reverts: wallet-raw-call.mjs exits 0 but reports status:"reverted"
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and parsed.get("status") == "reverted":
            tx_hash = parsed.get("txHash", "unknown")
            die(
                f"Transaction reverted (txHash: {tx_hash}). Check the transaction on the block explorer."
            )
    except json.JSONDecodeError:
        pass  # Not JSON — return as-is
    return stdout


def wallet_approve(token: str, asset: str, spender: str, amount: str) -> str:
    """Approve token spend, return result JSON"""
    args = ["approve", "--asset", asset, "--spender", spender, "--amount", amount]
    if token:
        args += ["--token", token]
    return wallet_cmd(args)


def wallet_sign_typed_data(token: str, data: dict) -> str:
    """EIP-712 sign, return signature hex"""
    args = ["sign-typed-data", "--data", json.dumps(data)]
    if token:
        args += ["--token", token]
    out = wallet_cmd(args)
    try:
        sig = json.loads(out).get("signature", "")
    except json.JSONDecodeError:
        die(f"Invalid sign response: {out}")
        return ""  # unreachable
    if not sig:
        die("Empty signature returned")
    return sig


# ── Contract registry ───────────────────────────────────


_VALID_CHAIN_NAMES = frozenset(_CHAIN_IDS.keys())


def get_registry() -> dict:
    """Fetch the contract registry entry for the currently selected chain.

    The AWP API's `registry.get` method has returned different shapes at different
    times:
      - Array of per-chain entries when called with no params (historical behavior)
      - Single dict when called with {chainId: N} (current behavior, and also the
        default-chain dict when called with no params in newer API versions)
    We always pass the explicit chainId so we get a deterministic single-dict
    response regardless of server version, then sanity-check the shape.

    Chain selection: EVM_CHAIN env var (name or numeric id), default Base (8453).
    Rejects unknown chain names to prevent env-var injection attacks.
    """
    chain_env = os.environ.get("EVM_CHAIN", "base").lower()
    target_chain_id = _CHAIN_IDS.get(chain_env)
    if target_chain_id is None:
        try:
            cid = int(chain_env)
            # Only accept known chainIds
            if cid not in _ID_TO_CANONICAL:
                die(
                    f"Unknown EVM_CHAIN: {chain_env}. Supported: {', '.join(sorted(_VALID_CHAIN_NAMES))}"
                )
            target_chain_id = cid
        except ValueError:
            die(
                f"Invalid EVM_CHAIN: {chain_env}. Supported: {', '.join(sorted(_VALID_CHAIN_NAMES))}"
            )

    result = rpc("registry.get", {"chainId": target_chain_id})

    # Normalize the response: accept either a single dict or an array (legacy).
    entry: dict | None = None
    if isinstance(result, dict):
        entry = result
    elif isinstance(result, list) and result:
        entry = next(
            (
                r
                for r in result
                if isinstance(r, dict) and r.get("chainId") == target_chain_id
            ),
            None,
        )
        if entry is None:
            info(
                f"Chain {target_chain_id} not found in registry list, using first entry"
            )
            entry = result[0]

    if not isinstance(entry, dict) or not entry.get("chainId"):
        die(f"Invalid registry.get response for chain {target_chain_id}: {result}")

    if entry.get("chainId") != target_chain_id:
        info(
            f"Registry returned chain {entry.get('chainId')}, expected {target_chain_id}"
        )

    return entry


def require_contract(registry: dict, key: str) -> str:
    """Get contract address from registry, die if missing"""
    addr = registry.get(key)
    if not addr or addr == "null":
        die(f"Failed to get {key} from /registry")
    return addr


# ── ABI encoding ─────────────────────────────────────


def pad_address(addr: str) -> str:
    """Pad 0x address to 64 characters (zero-padded on left), validate hex format and length"""
    raw = addr.lower()
    if raw.startswith("0x"):
        raw = raw[2:]
    if not re.match(r"^[0-9a-f]+$", raw):
        die(f"pad_address: invalid hex characters in address: {addr}")
    if len(raw) != 40:
        die(
            f"pad_address: address must be exactly 20 bytes (40 hex chars), got {len(raw)}: {addr}"
        )
    return raw.zfill(64)


def pad_uint256(val: int) -> str:
    """Encode integer as 64-character hex (must be within uint256 range)"""
    if val < 0 or val > _UINT256_MAX:
        die(f"pad_uint256: value out of uint256 range: {val}")
    return format(val, "064x")


def expand_worknet_id(raw_id: int) -> int:
    """Expand a short local worknet ID to the full chainId-prefixed format.

    The AWP API requires worknetId in the format `chainId * 100_000_000 + localId`
    (e.g., 845300000002 for worknet #2 on Base). Users naturally type short IDs
    like `--worknet 2` which the API rejects with "subnet not found".

    If the input is < 100_000_000 (i.e., clearly a local ID without a chain prefix),
    auto-prepend the current chain's prefix using the EVM_CHAIN env var (default Base).
    If the input is >= 100_000_000 (already has a chain prefix), pass through unchanged.
    """
    if raw_id < 100_000_000:
        chain_env = os.environ.get("EVM_CHAIN", "base").lower()
        chain_id = _CHAIN_IDS.get(chain_env)
        if chain_id is None:
            try:
                chain_id = int(chain_env)
            except ValueError:
                chain_id = _DEFAULT_CHAIN_ID
        full_id = chain_id * 100_000_000 + raw_id
        info(f"Expanded worknet ID {raw_id} → {full_id} (chain {chain_id})")
        return full_id
    return raw_id


def validate_uint128(val: int, name: str = "value") -> int:
    """Enforce that val fits in a Solidity uint128 (0 .. 2^128-1).

    Some contract parameters like `minStake` are declared uint128, but our calldata
    encoder pads everything to uint256. Without an explicit check here, values ≥ 2^128
    pass our encoder and then revert on the contract side with a cryptic abi-decode
    error. Validating early gives a clear JSON error message instead.
    """
    if val < 0 or val > _UINT128_MAX:
        die(f"{name}: value out of uint128 range (0..2^128-1): {val}")
    return val


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
        die(
            f"encode_calldata: invalid selector format: {selector} (expected 0x + 8 hex chars)"
        )
    return selector + "".join(params)


# ── Dynamic ABI encoding helpers ─────────────────────────
# Building blocks for encoding Solidity dynamic types (string, uint256[], address[],
# bytes[]). These return raw hex WITHOUT a leading offset or 0x prefix, so callers
# can compose them into larger calldata structures.


def encode_dynamic_string(s: str) -> str:
    """ABI-encode a dynamic string: length(32 bytes) + right-padded UTF-8 data."""
    raw = s.encode("utf-8")
    padded_len = ((len(raw) + 31) // 32) * 32
    return format(len(raw), "064x") + raw.hex().ljust(padded_len * 2, "0")


def encode_uint256_array(values: list[int]) -> str:
    """ABI-encode a uint256[]: length(32 bytes) + each element(32 bytes)."""
    parts = [format(len(values), "064x")]
    for v in values:
        parts.append(pad_uint256(v))
    return "".join(parts)


def encode_address_array(addrs: list[str]) -> str:
    """ABI-encode an address[]: length(32 bytes) + each element(32 bytes, left-padded)."""
    parts = [format(len(addrs), "064x")]
    for a in addrs:
        parts.append(pad_address(a))
    return "".join(parts)


def encode_bytes_array(items: list[bytes]) -> str:
    """ABI-encode a bytes[]: length + per-element offsets + each element (length + padded data).

    Offsets are relative to the start of the array data area (after the length word).
    """
    n = len(items)
    encoded_elements: list[str] = []
    for item in items:
        padded_len = ((len(item) + 31) // 32) * 32
        elem = format(len(item), "064x") + item.hex().ljust(padded_len * 2, "0")
        encoded_elements.append(elem)

    offsets: list[str] = []
    current_offset = n * 32  # first element starts after all offset slots
    for elem_hex in encoded_elements:
        offsets.append(format(current_offset, "064x"))
        current_offset += len(elem_hex) // 2  # hex chars / 2 = bytes

    parts = [format(n, "064x")]
    parts.extend(offsets)
    parts.extend(encoded_elements)
    return "".join(parts)


# ── Input validation ─────────────────────────────────────

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BYTES32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def validate_address(addr: str, name: str = "address") -> str:
    """Validate Ethereum address format"""
    if not ADDR_RE.match(addr):
        die(f"Invalid --{name}: must be 0x + 40 hex chars")
    return addr


def validate_bytes32(val: str, name: str = "value") -> str:
    """Validate a 0x-prefixed bytes32 hex string (0x + 64 hex chars)"""
    if not BYTES32_RE.match(val):
        die(f"Invalid --{name}: must be 0x + 64 hex chars (bytes32)")
    return val


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


def get_eip712_domain(registry: dict, contract_name: str = "AWPRegistry") -> dict:
    """Get EIP-712 domain info for AWPRegistry or AWPAllocator."""
    domain = registry.get("eip712Domain", {})
    chain_id = domain.get("chainId") or registry.get("chainId")

    if contract_name == "AWPAllocator":
        # AWPAllocator uses the dedicated allocatorEip712Domain field from registry
        alloc_domain = registry.get("allocatorEip712Domain", {})
        alloc_contract = alloc_domain.get("verifyingContract") or registry.get(
            "awpAllocator", ""
        )
        if not alloc_contract:
            die("Cannot determine AWPAllocator verifyingContract from registry")
        return {
            "name": alloc_domain.get("name", "AWPAllocator"),
            "version": str(alloc_domain.get("version", "1")),
            "chainId": int(
                alloc_domain.get("chainId") or chain_id or _DEFAULT_CHAIN_ID
            ),
            "verifyingContract": alloc_contract,
        }

    # AWPRegistry domain (default)
    name = domain.get("name")
    version = domain.get("version")
    contract = domain.get("verifyingContract")

    # fallback
    if not name:
        name = "AWPRegistry"
        version = "1"
        info("eip712Domain not in registry, using fallback")
    if not version:
        version = "1"
    if not contract:
        contract = registry.get("awpRegistry")

    if not chain_id or not contract:
        die("Cannot determine EIP-712 domain from registry")

    return {
        "name": name,
        "version": str(version),
        "chainId": int(chain_id),
        "verifyingContract": contract,
    }


def build_eip712(
    domain: dict,
    primary_type: str,
    type_fields: list[dict],
    message: dict,
    extra_types: dict[str, list[dict]] | None = None,
) -> dict:
    """Build complete EIP-712 typed data (supports nested struct types)."""
    types: dict[str, list[dict]] = {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        primary_type: type_fields,
    }
    if extra_types:
        types.update(extra_types)
    return {
        "types": types,
        "primaryType": primary_type,
        "domain": domain,
        "message": message,
    }


# ── Common argument parsing ─────────────────────────────────


def get_onchain_nonce(contract_addr: str, wallet_addr: str) -> int:
    """Read nonces(address) on-chain from any contract with ERC-2612-style nonce tracking.

    Selector 0x7ecebe00 = nonces(address). Used by AWPRegistry, AWPAllocator, AWPToken.
    ALWAYS prefer this over API nonce endpoints — the API indexer may lag behind the
    chain state after a recent transaction, causing signed messages to use stale nonces
    and producing 'invalid EIP-712 signature' errors.
    """
    nonce_hex = rpc_call(contract_addr, encode_calldata("0x7ecebe00", pad_address(wallet_addr)))
    if not nonce_hex or nonce_hex in ("0x", "null"):
        die(f"Could not read nonces({wallet_addr}) from {contract_addr}")
    return hex_to_int(nonce_hex)


def base_parser(description: str) -> argparse.ArgumentParser:
    """Create base argument parser with --token (optional for new wallet versions)"""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--token",
        default="",
        help="awp-wallet session token (optional for new wallet versions that no longer require unlock)",
    )
    return parser
