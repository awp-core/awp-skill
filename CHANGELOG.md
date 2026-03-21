# Changelog

## v0.19.9

### Security
- Q6 subnet skill install: auto-install from `awp-core/*`; third-party sources show `⚠ third-party source` notice (non-blocking)
- Metadata now declares all dependencies: `curl`, `jq`, `python3`, `~/.awp-wallet-password`
- Wallet password management transparent to user — informed about file location on first setup

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

A natural-language interface to the **AWP (Agent Working Protocol)** on Base (EVM). Install it in any compatible agent, and the agent can register on AWP, join subnets, stake tokens, vote on governance proposals, and monitor real-time on-chain events — all through conversation.

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
│   ├── relay-start.sh            Gasless register/bind
│   ├── relay-register-subnet.sh  Gasless subnet registration
│   ├── onchain-register.sh       On-chain register
│   ├── onchain-bind.sh           On-chain bind
│   ├── onchain-deposit.sh        Deposit AWP
│   ├── onchain-allocate.sh       Allocate stake
│   ├── onchain-deallocate.sh     Deallocate stake
│   ├── onchain-reallocate.sh     Reallocate stake
│   ├── onchain-withdraw.sh       Withdraw expired position
│   ├── onchain-add-position.sh   Add to existing position
│   ├── onchain-register-and-stake.sh  One-click register+deposit+allocate
│   ├── onchain-vote.sh           Cast DAO vote
│   ├── onchain-subnet-lifecycle.sh  Activate/pause/resume subnet
│   └── onchain-subnet-update.sh  Set skillsURI or minStake
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
- Write safety — confirmation preview before every transaction with `Proceed? (y/n)`
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
| Chain | Base (Chain ID 8453) |
| Gas Token | ETH |
| Epoch Duration | 1 day |
| Initial Daily Emission | 15,800,000 AWP |
| Decay | ~0.3156% per epoch |
| Max Active Subnets | 10,000 |
| Voting Power | `amount × √(min(remainingTime, 54w) / 7d)` |
| Explorer | basescan.org |

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
