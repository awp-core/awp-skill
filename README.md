# AWP RootNet Skill

[![Skill Compatible](https://img.shields.io/badge/Skill-Compatible-blue)](https://openclaw.ai)
[![BSC Mainnet](https://img.shields.io/badge/BSC-Mainnet-yellow)](https://bscscan.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Skill for interacting with the AWP RootNet protocol on BSC.** Query protocol state, register and bind agents, stake AWP tokens, manage subnets, create governance proposals, vote, and monitor real-time on-chain events — all through natural language.

## Overview

AWP RootNet is a decentralized **Agent Working** protocol on BNB Smart Chain (BSC). Agents register on subnets, execute tasks for subnet coordinators, and earn AWP token emissions as rewards. Each subnet auto-deploys a **SubnetManager** with Merkle-based reward distribution and configurable AWP strategies (Reserve, AddLiquidity, BuybackBurn).

This repository is a single skill with **20 actions** covering Query, Staking, Subnet Management, Governance, and real-time WebSocket Monitoring (27 event types).

## Quick Install

```bash
skill install https://github.com/awp-core/awp-skill
```

The skill automatically installs the [AWP Wallet](https://github.com/awp-core/awp-wallet) dependency when needed for write operations.

## Features — 20 Actions

#### Query (read-only, no wallet needed)
| ID | Action | Description |
|----|--------|-------------|
| Q1 | Query Subnet | Get subnet info by ID (name, status, owner, alpha token, skills URI, min stake) |
| Q2 | Query Balance | Full staking overview — positions, allocations, unallocated balance |
| Q3 | Query Emission [DRAFT] | Current epoch, daily emission rate, decay projections (30/90/365 days) |
| Q4 | Query Agent | Agent info by subnet — stake, owner, reward recipient |
| Q5 | List Subnets | Browse active subnets with pagination, flag those with published skills |
| Q6 | Install Subnet Skill | Fetch a subnet's SKILL.md and install it for the agent to use |
| Q7 | Epoch History [DRAFT] | Historical epoch settlements with emission amounts |

#### Staking (wallet required)
| ID | Action | Description |
|----|--------|-------------|
| S1 | Register & Bind | Register as Principal or bind as Agent. Supports gasless via EIP-712 relay. |
| S2 | Deposit AWP | Mint StakeNFT position with time-based lock. Approve → deposit flow. |
| S3 | Allocate / Deallocate / Reallocate | Direct stake to agents on subnets. Reallocate is immediate, no cooldown. |

#### Subnet Management (wallet + SubnetNFT ownership)
| ID | Action | Description |
|----|--------|-------------|
| M1 | Register Subnet | Deploy new subnet with Alpha token + LP pool. Gasless option available. |
| M2 | Subnet Lifecycle | Activate, pause, or resume a subnet |
| M3 | Update Skills URI | Set the subnet's SKILL.md URL via SubnetNFT |
| M4 | Set Min Stake | Set minimum stake requirement for agents on the subnet |

#### Governance (wallet + StakeNFT positions)
| ID | Action | Description |
|----|--------|-------------|
| G1 | Create Proposal | Executable (via Timelock) or signal-only proposals |
| G2 | Vote | Cast votes with position NFTs. Anti-manipulation filtering built in. |
| G3 | Query Proposals | List and inspect governance proposals with on-chain enrichment |
| G4 | Query Treasury | Check DAO treasury address and AWP balance |

#### Monitor (real-time WebSocket, no wallet needed)
| ID | Action | Description |
|----|--------|-------------|
| W1 | Watch Events | Subscribe to real-time events via WebSocket with 5 presets |
| W2 | Emission Alert [DRAFT] | Get notified on epoch settlements with top earner ranking |

### 27 Event Types (5 presets)

| Preset | Events | Count |
|--------|--------|-------|
| `staking` | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | 6 |
| `subnets` | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | 10 |
| `emission` | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | 6 |
| `users` | UserRegistered, AgentBound, AgentUnbound, AgentRemoved, DelegationUpdated | 5 |
| `all` | All of the above | 27 |

## Architecture

```
awp-skill/
├── SKILL.md                                # Single skill file (20 actions)
├── references/
│   ├── api-reference.md                    # Q1-Q7 REST endpoint index
│   ├── commands-staking.md                 # S1-S3 command templates + EIP-712
│   ├── commands-subnet.md                  # M1-M4 command templates + gasless
│   ├── commands-governance.md              # G1-G4 commands + supplementary endpoints
│   └── protocol.md                         # Shared structs, 27 events, constants
├── scripts/
│   ├── relay-start.sh                      # Gasless onboarding (register or bind)
│   └── relay-register-subnet.sh            # Gasless subnet registration
├── README.md
└── LICENSE
```

**Progressive loading**: The agent loads only what it needs per action. Query and Monitor actions (Q1-Q7, W1, W2) use SKILL.md alone. Write actions load the specific command file (~200-360 lines each) instead of all references at once, saving ~60% context.

## Gasless Support

Three operations support fully gasless execution via EIP-712 signatures and relay endpoints:

| Operation | Relay Endpoint | Signatures |
|-----------|---------------|------------|
| User Registration | `POST /relay/register` | 1 (EIP-712 Register) |
| Agent Binding | `POST /relay/bind` | 1 (EIP-712 Bind) |
| Subnet Registration | `POST /relay/register-subnet` | 2 (ERC-2612 Permit + EIP-712 RegisterSubnet) |

Rate limit: 100 requests per IP per 1 hour across all relay endpoints.

The skill automatically checks BNB balance and routes to gasless relay when the wallet has no native gas.

## Agent Working — Quick Start

AWP supports two mining modes:

### Principal Mode (self-managed)
Own your funds, earn your own rewards.

```
1. Install wallet skill
2. register() — register as a self-managed Principal
3. Discover active subnets → install subnet skill
4. Deposit AWP → allocate to agent + subnet
5. Execute tasks via subnet skill → earn emissions
```

### Agent Mode (work for a Principal)
Bind to someone else's account. They stake, you work.

```
1. Install wallet skill
2. bind(principalAddress) — auto-registers Principal
3. Principal stakes + allocates
4. Install subnet skill → execute tasks
5. unbind() anytime to leave
```

## Key Protocol Details

| Parameter | Value |
|-----------|-------|
| Chain | BSC Mainnet (Chain ID 56) |
| Epoch Duration | 1 day (86,400 seconds) |
| Initial Daily Emission | 15,800,000 AWP |
| Decay Factor | ~0.3156% per epoch |
| Emission Split | 50% recipients / 50% DAO |
| Token Decimals | 18 (all tokens) |
| Max Active Subnets | 10,000 |
| Voting Power | `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)` |
| Proposal Threshold | 1,000,000 AWP voting power |

## API Endpoints

| Service | URL |
|---------|-----|
| REST API | `https://tapi.awp.sh/api` |
| WebSocket | `wss://tapi.awp.sh/ws/live` |
| Health Check | `GET /health` |
| Contract Registry | `GET /registry` (11 addresses) |

## Smart Contracts

| Contract | Role |
|----------|------|
| **RootNet** | Unified entry point — registration, binding, allocation, subnet lifecycle |
| **StakeNFT** | ERC721 position NFTs — deposit AWP with time-based lock |
| **AWPEmission** | Emission engine — daily epoch settlement via oracle |
| **StakingVault** | Pure allocation logic — allocate, deallocate, reallocate |
| **SubnetNFT** | Subnet identity — on-chain name, skillsURI, minStake |
| **SubnetManager** | Auto-deployed per subnet — Merkle distribution + AWP strategies |
| **AWPDAO** | NFT-based governance — proposals, voting with position NFTs |
| **AWPToken** | ERC20 + ERC1363 + Votes — 10B max supply |
| **AlphaToken** | Per-subnet ERC20 via CREATE2 — 10B max per subnet |
| **Treasury** | TimelockController — DAO governance execution |

## Development

### Source Documents

Protocol specifications live on the `dev` branch (not included in the main install):

```bash
git checkout dev  # access skills-dev/ with contract-api.md, rest-api.md, config.md, ABIs, etc.
```

### Version History

| Version | Changes |
|---------|---------|
| 1.6.1 | Remove cast/foundry dependency from scripts, remove evals/dev files from install, dev branch separation |
| 1.6.0 | Bundled gasless relay scripts, file structure map, enforce script usage over manual EIP-712, no-cache contract addresses |
| 1.5.0 | Remove updateMetadata (SubnetParams now 5 fields), 27 events, relay 100/IP/1h, emission [DRAFT], Agent Working |
| 1.4.0 | Merged awp + awp-monitor into single skill. SKILL.md at repo root for one-command install. |
| 1.3.0 | Split api-reference into focused command files, inline high-frequency commands, session state tracking, response format templates, auto-retry on 429 |
| 1.2.0 | On Skill Load protocol, intent routing with reference file mapping, version check mechanism |
| 1.1.0 | Welcome messages, executable command templates, EIP-712 JSON templates with AWPRootNet domain |
| 1.0.0 | Initial release — 21 actions + 28 event types |

## Contributing

2. Regenerate skill files to match the updated specifications
3. Run eval tests to verify correctness
4. Submit a pull request

## License

[MIT](LICENSE)
