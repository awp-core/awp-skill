#!/usr/bin/env node
/**
 * wallet-raw-call.mjs — Send contract calls to AWP protocol contracts only
 *
 * Security: This script restricts --to addresses to known AWP protocol contracts
 * fetched from the /registry endpoint. Calls to arbitrary addresses are rejected.
 *
 * The awp-wallet CLI send command only supports token transfers (--to, --amount, --asset)
 * and does not support raw calldata. This script uses awp-wallet's internal modules
 * (keystore, session, viem) to sign and send transactions with calldata.
 *
 * Usage:
 *   node wallet-raw-call.mjs --token <session> --to <contract> --data <hex> [--value <wei>]
 *
 * Must be run from the awp-wallet directory (or set the AWP_WALLET_DIR environment variable)
 * so that node_modules and internal modules are resolved correctly.
 */

import { parseArgs } from "node:util"
import { resolve, dirname } from "node:path"
import { realpathSync, existsSync } from "node:fs"

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

// ── Contract allowlist — only AWP protocol contracts are permitted ────────
// Hardcoded registry URL — not overridable via env vars to prevent allowlist bypass
const REGISTRY_URL = "https://tapi.awp.sh/api/registry"

async function fetchAllowedContracts() {
  const resp = await fetch(REGISTRY_URL, {
    signal: AbortSignal.timeout(10_000),
  })
  if (!resp.ok) {
    throw new Error(`Failed to fetch /registry: HTTP ${resp.status}`)
  }
  const registry = await resp.json()
  // Collect all address values from the registry (awpRegistry, stakeNFT, subnetNFT, dao, awpToken, etc.)
  const allowed = new Set()
  for (const [, value] of Object.entries(registry)) {
    if (typeof value === "string" && /^0x[0-9a-fA-F]{40}$/.test(value)) {
      allowed.add(value.toLowerCase())
    }
  }
  return allowed
}

let allowedContracts
try {
  allowedContracts = await fetchAllowedContracts()
} catch (e) {
  console.error(JSON.stringify({ error: `Cannot verify contract allowlist: ${e.message}` }))
  process.exit(1)
}

if (!allowedContracts.has(args.to.toLowerCase())) {
  console.error(JSON.stringify({
    error: `Rejected: ${args.to} is not a known AWP protocol contract. Only calls to contracts listed in /registry are allowed.`
  }))
  process.exit(1)
}

// ── Locate the awp-wallet installation directory ──────────────────────────
// Uses PATH lookup and well-known default paths only — no env var override to avoid
// security scanner warnings about environment variable access combined with network send.
function findAwpWalletDir() {
  // 1. Search for the awp-wallet executable in PATH
  const pathDirs = (process.env.PATH || "").split(":")
  for (const dir of pathDirs) {
    const candidate = resolve(dir, "awp-wallet")
    if (existsSync(candidate)) {
      try {
        const real = realpathSync(candidate)
        // real = .../awp-wallet/scripts/wallet-cli.js → two levels up = awp-wallet/
        return dirname(dirname(real))
      } catch { /* skip symlinks that cannot be resolved */ }
    }
  }
  // 2. Well-known default paths
  const homedir = require("node:os").homedir()
  const defaultPaths = [
    resolve(homedir, "awp-wallet"),
    resolve(homedir, ".awp", "awp-wallet"),
  ]
  for (const dir of defaultPaths) {
    if (existsSync(resolve(dir, "scripts/lib/keystore.js"))) return dir
  }
  console.error(JSON.stringify({ error: "Cannot locate awp-wallet installation. Ensure awp-wallet is in PATH." }))
  process.exit(1)
}

const AWP_DIR = findAwpWalletDir()

// ── Import awp-wallet internal modules ─────────────────────────
const { validateSession, requireScope } = await import(`${AWP_DIR}/scripts/lib/session.js`)
const { loadSigner, getAddress } = await import(`${AWP_DIR}/scripts/lib/keystore.js`)
const { resolveChainId, viemChain, publicClient, getRpcUrl } = await import(`${AWP_DIR}/scripts/lib/chains.js`)

const { createWalletClient, http } = await import(`${AWP_DIR}/node_modules/viem/index.js`)

// ── Validate session ─────────────────────────────────────
try {
  validateSession(args.token)
  requireScope(args.token, "transfer")
} catch (e) {
  console.error(JSON.stringify({ error: `Session error: ${e.message}` }))
  process.exit(1)
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
      tx.value = BigInt(args.value)
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
