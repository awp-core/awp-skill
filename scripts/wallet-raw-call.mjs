#!/usr/bin/env node
/**
 * wallet-raw-call.mjs — Send contract calls to AWP protocol contracts only
 *
 * Security: This script restricts --to addresses to known AWP protocol contracts
 * fetched via JSON-RPC 2.0 API. Calls to arbitrary addresses are rejected.
 *
 * The awp-wallet CLI send command only supports token transfers (--to, --amount, --asset)
 * and does not support raw calldata. This script uses awp-wallet's internal modules
 * (keystore, session, viem) to sign and send transactions with calldata.
 *
 * Usage:
 *   node wallet-raw-call.mjs --token <session> --to <contract> --data <hex> [--value <wei>]
 *
 * The script auto-discovers the awp-wallet installation via well-known paths.
 * No environment variables are used (security: avoids env-var-to-network-send patterns).
 */

import { parseArgs } from "node:util"
import { resolve, dirname } from "node:path"
import { realpathSync, existsSync } from "node:fs"
import { homedir as osHomedir } from "node:os"

// ── Parse command-line arguments ──────────────────────────────────
const { values: args } = parseArgs({
  options: {
    token:  { type: "string" },
    to:     { type: "string" },
    data:   { type: "string" },
    value:  { type: "string", default: "0" },
    chain:  { type: "string", default: "base" },
  },
  strict: true,
})

if (!args.token || !args.to || !args.data) {
  console.error(JSON.stringify({ error: "Required: --token, --to, --data" }))
  process.exit(1)
}

// ── Format validation ──────────────────────────────────────────
if (!/^0x[0-9a-fA-F]{40}$/.test(args.to)) {
  console.error(JSON.stringify({ error: `Invalid --to address: ${args.to}` }))
  process.exit(1)
}
if (!/^0x(?:[0-9a-fA-F]{2}){4,}$/.test(args.data)) {
  console.error(JSON.stringify({ error: `Invalid --data hex: ${args.data}` }))
  process.exit(1)
}

// ── Contract allowlist — defense-in-depth with static + remote verification ────────
//
// Security model: the allowlist uses a TWO-LAYER approach to prevent a compromised
// API from injecting malicious contract addresses:
//
//   Layer 1 (static): Hardcoded set of known AWP protocol contract addresses.
//   These are the CREATE2-deployed contracts identical across all 4 chains.
//   This list can only change when the skill itself is updated.
//
//   Layer 2 (remote): Fetch the latest registry from api.awp.sh and INTERSECT
//   with the static set. Only addresses present in BOTH lists are allowed.
//   If the remote call fails, fall back to the static list alone.
//
// Attack scenario mitigated: if api.awp.sh is compromised and returns extra
// addresses (e.g., an attacker's drain contract), the intersection ensures those
// addresses are rejected because they're not in the hardcoded static set.

// Hardcoded registry URL — not overridable via env vars
const REGISTRY_URL = "https://api.awp.sh/v2"

// Chain name → chainId mapping
const CHAIN_IDS = { ethereum: 1, bsc: 56, base: 8453, arbitrum: 42161 }

// Static allowlist: known AWP protocol contracts (identical on all 4 chains via CREATE2).
// Source: verified against live registry.get + eth_getCode on Base mainnet.
// Update this list when new protocol contracts are deployed.
const STATIC_ALLOWED = new Set([
  "0x0000f34ed3594f54faabbcb2ec45738ddd1c001a", // AWPRegistry
  "0x0000a1050acf9dea8af9c2e74f0d7cf43f1000a1", // AWPToken
  "0x3c9cb73f8b81083882c5308cce4f31f93600eaa9", // AWPEmission
  "0x0000d6bb5e040e35081b3aaf59dd71b21c9800aa", // AWPAllocator
  "0x0000b534c63d78212f1bdcc315165852793a00a8", // veAWP
  "0x00000bfbdef8533e5f3228c9c846522d906100a7", // AWPWorkNet
  "0x00001961b9accd86b72de19be24fad6f7c5b00a2", // LPManager
  "0x000058ef25751bb3687eb314185b46b942be00af", // WorknetTokenFactory (live)
  "0x0000d4996bdbb99c772e3fa9f0e94ab52aaffac7", // WorknetTokenFactory (spec)
  "0x00006879f79f3da189b5d0ff6e58ad0127cc0da0", // AWPDAO
  "0x82562023a053025f3201785160cae6051efd759e", // Treasury
])

async function isWorknetManager(address) {
  // Verify an address is a known WorknetManager by querying subnets.list.
  // WorknetManagers are per-worknet contracts deployed by the factory — they are
  // NOT in the static allowlist or the registry. This separate check allows
  // onchain-claim.py to target these contracts safely.
  try {
    const resp = await fetch(REGISTRY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "subnets.list",
        params: { status: "Active", limit: 100 },
        id: 2,
      }),
      signal: AbortSignal.timeout(10_000),
    })
    if (resp.ok) {
      const json = await resp.json()
      if (!json.error) {
        const worknets = Array.isArray(json.result)
          ? json.result
          : (json.result?.items || json.result?.data || [])
        const addr = address.toLowerCase()
        for (const w of worknets) {
          // Check multiple possible field names for the manager address
          const mgr = (w.worknetManager || w.manager || w.worknet_manager || "").toLowerCase()
          if (mgr === addr) return true
        }
      }
    }
  } catch {
    // Network failure — cannot verify, deny by default
  }
  return false
}

async function fetchAllowedContracts(chainName) {
  // Try to fetch the latest registry to get any new addresses the protocol added.
  // On success, INTERSECT remote addresses with the static set (defense-in-depth).
  // On failure, fall back to the static set alone.
  let remoteAddresses = null
  try {
    const resp = await fetch(REGISTRY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "registry.list",
        params: {},
        id: 1,
      }),
      signal: AbortSignal.timeout(10_000),
    })
    if (resp.ok) {
      const json = await resp.json()
      if (!json.error) {
        const result = json.result
        let entry
        if (Array.isArray(result) && result.length > 0) {
          const chainId = CHAIN_IDS[chainName.toLowerCase()]
          entry = (chainId != null && result.find(r => r.chainId === chainId)) || result[0]
        } else if (result && typeof result === "object" && !Array.isArray(result)) {
          entry = result
        }
        if (entry) {
          remoteAddresses = new Set()
          for (const value of Object.values(entry)) {
            if (typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value)) {
              remoteAddresses.add(value.toLowerCase())
            }
          }
        }
      }
    }
  } catch {
    // Network failure — fall back to static allowlist (logged below)
  }

  if (remoteAddresses && remoteAddresses.size > 0) {
    // INTERSECT: only allow addresses in BOTH static and remote sets.
    // This prevents a compromised API from adding unknown contracts.
    const intersection = new Set()
    for (const addr of remoteAddresses) {
      if (STATIC_ALLOWED.has(addr)) {
        intersection.add(addr)
      }
    }
    if (intersection.size > 0) {
      return intersection
    }
    // If intersection is empty (API returned completely unrecognized addresses),
    // fall back to static — something is very wrong with the API response.
    console.error(JSON.stringify({
      error: "Registry returned no recognized addresses — using static allowlist only",
    }))
  }

  // Fallback: static allowlist (API unreachable or returned unrecognized data)
  return new Set(STATIC_ALLOWED)
}

// ── Locate the awp-wallet installation directory ──────────────────────────
// Uses well-known directories and os.homedir() only — no environment variable access.
function findAwpWalletDir() {
  const homedir = osHomedir()
  // 1. Search well-known bin directories for the awp-wallet executable
  const binDirs = [
    resolve(homedir, ".local", "bin"),
    resolve(homedir, ".npm-global", "bin"),
    resolve(homedir, ".yarn", "bin"),
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
  ]
  for (const dir of binDirs) {
    const candidate = resolve(dir, "awp-wallet")
    if (existsSync(candidate)) {
      try {
        const real = realpathSync(candidate)
        // real = .../awp-wallet/scripts/wallet-cli.js → two levels up = awp-wallet/
        return dirname(dirname(real))
      } catch { /* skip symlinks that cannot be resolved */ }
    }
  }
  // 2. Well-known install paths
  const installPaths = [
    resolve(homedir, "awp-wallet"),
    resolve(homedir, ".awp", "awp-wallet"),
  ]
  for (const dir of installPaths) {
    if (existsSync(resolve(dir, "scripts/lib/keystore.js"))) return dir
  }
  console.error(JSON.stringify({ error: "Cannot locate awp-wallet installation. Ensure awp-wallet is installed." }))
  process.exit(1)
}

const AWP_DIR = findAwpWalletDir()

// ── Import awp-wallet internal modules ─────────────────────────
const { validateSession, requireScope } = await import(`${AWP_DIR}/scripts/lib/session.js`)
const { loadSigner, getAddress } = await import(`${AWP_DIR}/scripts/lib/keystore.js`)
const { resolveChainId, viemChain, publicClient, getRpcUrl } = await import(`${AWP_DIR}/scripts/lib/chains.js`)

const { createWalletClient, http } = await import(`${AWP_DIR}/node_modules/viem/index.js`)

// ── Validate session (cheap local check — do before network calls) ──────
try {
  validateSession(args.token)
  requireScope(args.token, "transfer")
} catch (e) {
  console.error(JSON.stringify({ error: `Session error: ${e.message}` }))
  process.exit(1)
}

// ── Contract allowlist — only AWP protocol contracts are permitted ────────
let allowedContracts
try {
  allowedContracts = await fetchAllowedContracts(args.chain)
} catch (e) {
  console.error(JSON.stringify({ error: `Cannot verify contract allowlist: ${e.message}` }))
  process.exit(1)
}

if (!allowedContracts.has(args.to.toLowerCase())) {
  // Not in the global registry — check if it's a known WorknetManager
  const isManager = await isWorknetManager(args.to)
  if (!isManager) {
    console.error(JSON.stringify({
      error: `Rejected: ${args.to} is not a known AWP protocol contract or WorknetManager. Only calls to contracts listed in /registry or active worknet managers are allowed.`
    }))
    process.exit(1)
  }
}

// ── Build and send transaction ───────────────────────────────────
try {
  const chainId = resolveChainId(args.chain)
  const chainObj = viemChain(chainId)
  const { account: signer } = loadSigner()
  if (!signer) {
    console.error(JSON.stringify({ error: "Failed to load signer from keystore" }))
    process.exit(1)
  }

  const walletClient = createWalletClient({
    account: signer,
    chain: chainObj,
    transport: http(getRpcUrl(chainId)),
  })

  const tx = {
    to: args.to,
    data: args.data,
  }

  // Support sending ETH (contract calls with value > 0)
  if (args.value && args.value !== "0") {
    try {
      const v = BigInt(args.value)
      if (v < 0n) {
        console.error(JSON.stringify({ error: `Invalid --value (must be non-negative): ${args.value}` }))
        process.exit(1)
      }
      tx.value = v
    } catch {
      console.error(JSON.stringify({ error: `Invalid --value (must be integer wei): ${args.value}` }))
      process.exit(1)
    }
  }

  const hash = await walletClient.sendTransaction(tx)

  // Wait for confirmation
  const client = publicClient(chainId)
  let receipt
  try {
    receipt = await client.waitForTransactionReceipt({
      hash,
      timeout: 90_000,
      confirmations: 1,
    })
  } catch (receiptErr) {
    // Transaction was submitted but receipt timed out — include txHash so caller can track it
    console.error(JSON.stringify({
      error: `Receipt timeout: ${receiptErr.message}`,
      status: "pending",
      txHash: hash,
      chain: chainObj.name,
      chainId,
    }))
    process.exit(1)
  }

  console.log(JSON.stringify({
    status: receipt.status === "success" ? "confirmed" : "reverted",
    txHash: hash,
    chain: chainObj.name,
    chainId,
    to: args.to,
    gasUsed: receipt.gasUsed.toString(),
    blockNumber: Number(receipt.blockNumber),
  }))
} catch (e) {
  console.error(JSON.stringify({ error: `Transaction failed: ${e.message}` }))
  process.exit(1)
}
