# Changelog

## v0.22.6

### Simplify — Just tell agent where the wallet skill is
- SKILL.md Step 2: point agent to `https://github.com/awp-core/awp-wallet`, let it handle installation — no hardcoded install commands

## v0.22.5

### Fix — Install from local repo, not remote pipe
- SKILL.md Step 2: `git clone` → `bash install.sh`（先拉到本地再执行，不用 `curl | bash` 远程管道）
- daemon: all install/update messages use `git clone` + local `install.sh` instead of `curl | bash`
- Removed `WALLET_INSTALL_SCRIPT` (raw.githubusercontent.com URL) from daemon

## v0.22.4

### Fix — Inline wallet install instructions
- SKILL.md Step 2: provide `git clone → npm install → npm link` steps directly, instead of depending on a wallet skill that may not be loaded in the current session
- Wallet init (`awp-wallet init`) runs directly — no external skill dependency needed
- Avoids the "start a new session to load the wallet skill" problem

## v0.22.3

### Fix — Wallet install via skill, not bash script
- SKILL.md Step 2: removed hardcoded `curl | bash` install command. Now directs agent to install the AWP Wallet skill (from ClawHub or repo), which handles installation and setup
- Onboarding Step 1 & Session recovery Step 5: delegate wallet init to the AWP Wallet skill
- AWP skill no longer contains any remote install scripts — wallet lifecycle is fully owned by the wallet skill

## v0.22.2

### UX Fix — Agent handles install & init
- SKILL.md Step 2: agent directly runs `curl | bash` to install awp-wallet (not the user)
- SKILL.md Step 5: agent runs `awp-wallet init` if wallet not found (not the user)
- Onboarding Step 1: agent runs `awp-wallet init` directly
- Note: daemon script (`awp-daemon.py`) remains check-only — it does not auto-install or auto-init

## v0.22.1

### Security Hardening
- **Removed auto-install**: daemon no longer downloads or executes remote install scripts (`curl | bash`). Prints manual install instructions instead
- **Removed auto-init**: daemon no longer runs `awp-wallet init` automatically. User must explicitly initialize wallet
- **Removed `/tmp` glob scanning**: `_get_openclaw_config()` no longer reads `/tmp/awp-worker-*-config.json` patterns (writable by any process). Only reads `~/.awp/openclaw.json`
- **Declared OpenClaw env vars**: added `OPENCLAW_CHANNEL` and `OPENCLAW_TARGET` to `requires.env` (optional)
- **Clarified update checks**: version checks are informational only, no auto-download or auto-execute
- **Reference docs**: added default value (`https://tapi.awp.sh/api`) and `AWP_API_URL` env var to all 4 API Base URL annotations

## v0.22.0

### Fixed — awp-wallet CLI Compatibility
- **CRITICAL**: `awp-wallet send --data` does NOT exist — `send` only supports token transfers (`--to`, `--amount`, `--asset`). Added `wallet-raw-call.mjs` bridge script that imports awp-wallet internal modules (keystore/session/viem) for raw contract calls
- **CRITICAL**: `awp_lib.py:wallet_send()` was silently failing — all on-chain Python scripts broken. Fixed to use bridge script
- `--chain base` is a global option, NOT per-subcommand — removed from `approve`, `balance` calls
- `awp-wallet unlock --scope` EXISTS (read|transfer|full) — re-added with `--scope transfer` default
- `awp-wallet status --token` EXISTS — added `wallet_status()` to awp_lib.py
- awp-wallet install: `skill install` → `curl -sSL install.sh | bash` (not on npm registry)
- awp-daemon: wallet version check was reading non-existent SKILL.md from awp-wallet repo → now reads package.json
- Reference docs: replaced all broken `awp-wallet send --data $(cast calldata ...)` templates with bundled Python script commands
- CHANGELOG v0.20.7 correction: `--scope full` DOES exist — it was incorrectly removed in that version

---

## v0.21.0

### Changed — Shell → Python Migration
- **All 14 shell scripts converted to Python** — eliminates `curl`/`jq`/`sed` dependencies, only `python3` required
- New shared library `scripts/awp_lib.py` (~285 lines) — API calls, wallet commands, ABI encoding, input validation, EIP-712 builder
- Shell injection surface fully eliminated — no more `python3 -c` inline, no `$VAR` interpolation in subshells
- All scripts now use native Python `urllib` for HTTP and `argparse` for CLI parsing
- Dependencies reduced from `curl + jq + python3` to `python3` only
- Reference docs updated: `scripts/*.sh` → `scripts/*.py`

---

## v0.20.7

### Fixed — Deep Code Review
- **CRITICAL**: `awp-wallet status` command does not exist → replaced with `awp-wallet receive` across 14 scripts + 3 reference files + SKILL.md
- **CRITICAL**: `.address` field does not exist → replaced with `.eoaAddress` across all 20 files
- **CRITICAL**: `--scope full` parameter does not exist → removed from `awp-wallet unlock` (3 places)
- `onchain-vote.sh`: `$ELIGIBLE_TOKEN_IDS` shell injection → now passed via `os.environ`
- `relay-start.sh`: `sed` injection risk → replaced with `jq` for safe JSON construction
- `onchain-deposit.sh`: `--lock-days 0` incorrectly passed validation → now rejected
- `AWP_TOKEN` null check missing in `onchain-deposit.sh` and `onchain-register-and-stake.sh` → added
- `awp-daemon.py`: wallet update falsely reported success on failure → now checks return code
- `awp-daemon.py`: deregistration event silently dropped → now logs and notifies
- `awp-daemon.py`: `except Exception` too broad → narrowed to `(JSONDecodeError, OSError)`
- `$RPC_URL` → `$EVM_RPC_URL` in `commands-subnet.md` and `commands-governance.md`
- SKILL.md: stale example date `2025-12-01` → `2026-12-01`

### Changed
- **Multi-EVM**: `BASE_RPC_URL` → `EVM_RPC_URL` across all scripts and references
- Description updated: "on Base" → "on EVM" to reflect all EVM-compatible chains
- README badges: added Ethereum, EVM Compatible; updated descriptions for multi-chain
- README: removed stale "Proceed? (y/n)" UX description (agent wallet model executes directly)
- Reference docs: clarified that `cast` examples are for reference only; agents must use bundled scripts
- Version history in README aligned with 0.x.x scheme

---

## v0.19.9

### Security
- Q6 subnet skill install: auto-install from `awp-core/*`; third-party sources show `⚠ third-party source` notice (non-blocking)
- Metadata now declares all dependencies: `curl`, `jq`, `python3`
- Wallet auto-manages credentials in default mode — no password files needed

### Changed
- **Agent wallet model** — transactions execute directly, no confirmation prompts. This is a work wallet for AWP tasks only; users are told not to store personal assets.
- `awp-wallet` installs from registry first, falls back to GitHub: `skill install awp-wallet || skill install https://github.com/awp-core/awp-wallet`
- Description rewritten: 511 chars (was 916), natural language instead of keyword list
- Removed all V1 `.rootNet` fallback code — V2 API is now authoritative

### Fixed
- Deep audit: `$REASON`, `$SKILLS_URI`, `$POSITIONS` injection — now passed via `os.environ`
- All 9 onchain scripts: added registry/contract null checks
- `AMOUNT=0` and `POSITION=0` rejected in validation
- `onchain-withdraw.sh`: hardcoded `remainingTime` selector (removed `web3` dependency)
- `relay-start.sh`: removed fallback to deleted `/relay/register` endpoint
- `onchain-vote.sh`: `RPC_URL` → `BASE_RPC_URL` (consistent with other scripts)
- Pre-Flight unlock now includes password pipe

---

## v0.19.1 — Initial Public Release

First public release of the AWP Skill for [Claude Code](https://github.com/anthropics/claude-code), [OpenClaw](https://openclaw.ai), and other SKILL.md-compatible agents.

### What is AWP Skill?

A natural-language interface to the **AWP (Agent Working Protocol)** on EVM-compatible chains. Install it in any compatible agent, and the agent can register on AWP, join subnets, stake tokens, vote on governance proposals, and monitor real-time on-chain events — all through conversation.

```bash
skill install https://github.com/awp-core/awp-skill
```

### Highlights

- **20 actions** across 5 categories: Query, Staking, Subnet Management, Governance, and WebSocket Monitoring
- **14 bundled shell scripts** that handle all on-chain operations — the agent never constructs calldata manually, eliminating an entire class of ABI-encoding and selector errors
- **Gasless onboarding** — registration is free via EIP-712 relay; no ETH or AWP tokens needed to get started
- **26 real-time event types** via WebSocket with 4 presets (staking, subnets, emission, users)
- **Guided onboarding flow** — 4-step wizard (wallet → register → discover subnets → install skill) with progress indicators
- **Optimized for weaker models** — concrete URLs (no placeholders), one way to do each operation (no choices), and explicit rules preventing common mistakes

### Architecture

```
awp-skill/
├── SKILL.md                    Main skill file (589 lines)
├── references/                 5 reference docs loaded on demand
│   ├── api-reference.md          REST + contract quick reference
│   ├── commands-staking.md       S1-S3 templates + EIP-712
│   ├── commands-subnet.md        M1-M4 templates + gasless
│   ├── commands-governance.md    G1-G4 + supplementary endpoints
│   └── protocol.md              Structs, 26 events, constants
├── scripts/                    14 executable bash scripts
│   ├── awp_lib.py                Shared library (API, wallet, ABI, validation)
│   ├── relay-start.py            Gasless register/bind
│   ├── relay-register-subnet.py  Gasless subnet registration
│   ├── onchain-register.py       On-chain register
│   ├── onchain-bind.py           On-chain bind
│   ├── onchain-deposit.py        Deposit AWP
│   ├── onchain-allocate.py       Allocate stake
│   ├── onchain-deallocate.py     Deallocate stake
│   ├── onchain-reallocate.py     Reallocate stake
│   ├── onchain-withdraw.py       Withdraw expired position
│   ├── onchain-add-position.py   Add to existing position
│   ├── onchain-register-and-stake.py  One-click register+deposit+allocate
│   ├── onchain-vote.py           Cast DAO vote
│   ├── onchain-subnet-lifecycle.py  Activate/pause/resume subnet
│   └── onchain-subnet-update.py  Set skillsURI or minStake
├── assets/
│   └── banner.png
├── README.md
└── LICENSE
```

### Actions

| Category | Actions | Wallet Required |
|----------|---------|:---------------:|
| **Query** | Q1 Subnet, Q2 Balance, Q3 Emission, Q4 Agent, Q5 List Subnets, Q6 Install Skill, Q7 Epoch History | No |
| **Staking** | S1 Register/Bind, S2 Deposit/Withdraw/AddPosition, S3 Allocate/Deallocate/Reallocate | Yes |
| **Subnet** | M1 Register Subnet, M2 Lifecycle, M3 Update Skills URI, M4 Set Min Stake | Yes |
| **Governance** | G1 Create Proposal, G2 Vote, G3 Query Proposals, G4 Query Treasury | Yes |
| **Monitor** | W1 Watch Events, W2 Emission Alert | No |

### UX Features

- ASCII art welcome screen with quick-start commands
- `awp status` / `awp wallet` / `awp subnets` / `awp help` quick commands
- Agent wallet model — transactions execute directly (work wallet, no personal assets)
- Balance change notifications with +/- delta after writes
- Tagged output: `[QUERY]`, `[STAKE]`, `[TX]`, `[NEXT]`, `[!]` prefixes
- Transaction links to basescan.org
- Auto-generate wallet password (never asks user)
- Session recovery on reconnect

### Anti-Hallucination Measures

Every write operation is wrapped in a bundled script that:
- Validates all inputs (address regex, numeric checks, subnet > 0)
- Targets the correct contract (AWPRegistry vs StakeNFT vs SubnetNFT vs DAO)
- Uses hardcoded, keccak256-verified function selectors
- Pre-checks state before submitting (balance, registration, lock expiry)
- Handles unit conversion (human-readable AWP ↔ wei, days ↔ seconds)

The agent never:
- Constructs ABI-encoded calldata manually
- Builds EIP-712 JSON by hand
- Hardcodes contract addresses
- Assumes the user has AWP tokens to start

### Gasless Operations

| Operation | Endpoint | Signatures |
|-----------|----------|:----------:|
| Register (setRecipient) | `POST /relay/set-recipient` | 1 |
| Bind (tree-based) | `POST /relay/bind` | 1 |
| Register Subnet | `POST /relay/register-subnet` | 2 |

Nonce from `GET /nonce/{address}`. EIP-712 domain from `GET /registry → eip712Domain`.

### Protocol Details

| Parameter | Value |
|-----------|-------|
| Chain | EVM-compatible (testnet: Base, Chain ID 8453) |
| Gas Token | ETH |
| Epoch Duration | 1 day |
| Initial Daily Emission | 15,800,000 AWP |
| Decay | ~0.3156% per epoch |
| Max Active Subnets | 10,000 |
| Voting Power | `amount × √(min(remainingTime, 54w) / 7d)` |
| Explorer | deployment-specific (default: basescan.org) |

### Security

- All user inputs validated before reaching `python3 -c` (regex in shell)
- `$REASON` and `$SKILLS_URI` passed via `os.environ`, not string interpolation
- `$POSITIONS` API response passed via environment variable
- Registry address null-checked in all 14 scripts
- AMOUNT=0 and POSITION=0 rejected

### Compatibility

Works with any agent that supports the [SKILL.md standard](https://agentskills.io/specification):
- Claude Code
- OpenClaw
- Cursor
- Codex
- Gemini CLI
- Windsurf

### Install

```bash
skill install https://github.com/awp-core/awp-skill
```

Then say **"start working"** to begin.
