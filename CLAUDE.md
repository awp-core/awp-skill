# AWP RootNet — OpenClaw Skill Development

You are developing **2 OpenClaw skills** for the AWP RootNet protocol (BSC, Chain ID 56). Read all source documents in `skills-dev/abi/` before writing any skill.

## Target Output

```
skills/
├── awp/                         ← all request-response operations (19 actions)
│   ├── SKILL.md                   Query (7) + Staking (3) + Subnet Mgmt (3) + Governance (4)
│   └── references/
│       ├── api-reference.md       endpoints + contract calls, organized by action ID
│       └── protocol.md            structs, 25 event types, shared endpoints
│
└── awp-monitor/                 ← persistent WebSocket subscription (2 actions)
    ├── SKILL.md                   Watch Events + Emission Alert
    └── references/
        ├── api-reference.md       WebSocket protocol, presets, polling fallback
        └── protocol.md            same file (each skill must be self-contained)
```

**Why 2 skills, not more**: The only natural split is **interaction mode**. `awp` is request-response (user asks → agent acts → returns result). `awp-monitor` is persistent subscription (WebSocket, long-running push). Everything else — query vs staking vs governance — is internal organization within `awp`, handled by section headings.

## Source Documents (in `skills-dev/abi/`)

Read ALL of these before writing any skill:

| File | Read for | Critical content |
|------|----------|------------------|
| `CLAUDE.md` | Protocol overview, component roles | Contract responsibilities, skill list |
| `contract-api.md` | Function signatures, data structures, access control | SubnetParams, SubnetInfo, AgentInfo structs; view and write functions with access modifiers |
| `rest-api.md` | HTTP endpoints, response schemas, WebSocket events | All REST paths with exact response JSON; complete event field table (25 types) |
| `examples.md` | Working implementation code | REST fetch, viem readContract/writeContract, WebSocket subscribe patterns |
| `config.md` | Chain config, addresses (TBD), constants | Epoch duration, decay factor, emission split, max limits |
| `agent-skill-guide.md` | Skill discovery and installation flow | How agents find subnets → fetch skillsURI → install SKILL.md |

## SKILL.md Format (OpenClaw Standard)

```yaml
---
name: awp                    # kebab-case identifier
description: >               # ~100 words, cover all trigger keywords
  ...
user-invocable: true          # exposes as /awp slash command
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"]}}}
---

# Title

Reference lines:
- references/api-reference.md — endpoints and contract calls
- references/protocol.md — structs, events, shared endpoints

## Section Name

### Action ID · Action Name

Intent + Steps + Display template (if applicable).
```

### SKILL.md Rules

1. **Workflow only, no code blocks.** SKILL.md describes *what to do*, not *how to implement*. JavaScript, Solidity syntax, and response schemas go in `references/api-reference.md`.
2. **< 500 lines.** Move detail to references/ if approaching the limit.
3. **Each action is 3–8 lines**: intent (1 line), steps (numbered list), key caveats.
4. **Display templates use pseudocode**: `{formatAWP(amount)}`, `{shortAddr(addr)}`, `{tsToDate(ts)}`.
5. **Single error-handling table at the bottom**, shared across all actions.

### references/api-reference.md Rules

1. **Organized by action ID** (Q1, Q2, …, S1, S2, …, G1, G2), not by source (REST vs contract).
2. Each action shows: REST endpoint + response schema + on-chain fallback (if applicable).
3. **Shared definitions** (structs, events, `/registry`) belong in `protocol.md`, not repeated here.
4. Contract call syntax uses Solidity function signatures, not full ABI JSON.

### references/protocol.md Rules

1. Contains **only** content shared between both skills: data structures, event field table, shared endpoints (`/registry`, `/address/check`).
2. Identical file in both skills — each skill must be self-contained for independent installation.

## awp Skill — 19 Actions in 4 Sections

### Section: Query (read-only, no wallet)

| ID | Action | Primary Endpoint | Fallback |
|----|--------|-----------------|----------|
| Q1 | Query Subnet | `GET /subnets/{id}` | `RootNet.getSubnet()` (no string fields on-chain) |
| Q2 | Query Balance | `GET /staking/user/{addr}/balance` + `/positions` + `/allocations` | `StakeNFT.getUserTotalStaked()` |
| Q3 | Query Emission | `GET /emission/current` + `/schedule` + `/epochs` | `AWPEmission.currentDailyEmission()` etc. |
| Q4 | Query Agent | `POST /agents/batch-info` | `RootNet.getAgentInfo()` |
| Q5 | List Subnets | `GET /subnets?status=Active` | — |
| Q6 | Query Skills URI | `GET /subnets/{id}/skills` | — |
| Q7 | Epoch History | `GET /emission/epochs` | — |

### Section: Staking (wallet required)

| ID | Action | Contract Call | Key Detail |
|----|--------|--------------|------------|
| S1 | Register User | `RootNet.register()` or `registerAndStake(…)` | `registerAndStake` approve target is **RootNet**, not StakeNFT |
| S2 | Deposit AWP | `AWPToken.approve(stakeNFT, amt)` → `StakeNFT.deposit(amt, lockEpochs)` | Wait for approve receipt; Deposited event emits `lockEndEpoch` (absolute) |
| S3 | Allocate / Deallocate / Reallocate | `RootNet.allocate / deallocate / reallocate(…)` | Reallocate is immediate, no cooldown |

### Section: Subnet Management (wallet + SubnetNFT ownership)

| ID | Action | Contract Call | Key Detail |
|----|--------|--------------|------------|
| M1 | Register Subnet | `approve(rootNet, lpCost)` → `registerSubnet(params)` | LP cost = `initialAlphaPrice × 100M Alpha` |
| M2 | Lifecycle | `activateSubnet / pauseSubnet / resumeSubnet(subnetId)` | Verify current status before transition |
| M3 | Update Metadata | `updateMetadata(subnetId, metadataURI, coordinatorURL, skillsURI)` | ALL THREE strings required every call; skillsURI is off-chain indexed |

### Section: Governance (wallet + StakeNFT positions)

| ID | Action | Contract Call | Key Detail |
|----|--------|--------------|------------|
| G1 | Create Proposal | `AWPDAO.proposeWithTokens(…)` or `signalPropose(…)` | Min 1M AWP voting power; signal = no on-chain execution |
| G2 | Vote | `castVoteWithReasonAndParams(proposalId, support, reason, params)` | **`castVote()` is BLOCKED**; `params = encodeAbiParameters([{type:'uint256[]'}], [tokenIds])` |
| G3 | Query Proposals | `GET /governance/proposals` + on-chain `proposalVotes()` | Use `isSignalProposal()` to distinguish proposal types |
| G4 | Treasury | `GET /governance/treasury` | Optional: `AWPToken.balanceOf(treasury)` |

## awp-monitor Skill — 2 Actions

| ID | Action | Data Source | Key Detail |
|----|--------|------------|------------|
| W1 | Watch Events | `wss://api.awp.network/ws/live` | 25 event types, 5 presets; auto-reconnect with exponential backoff |
| W2 | Emission Alert | WebSocket `EpochSettled` + `RecipientAWPDistributed` | Polling fallback: `GET /emission/current` every 60s |

## Implementation Rules

1. **Data source priority**: REST API (fast, cached) → on-chain read (authoritative fallback).
2. **Wei → human-readable**: Never display raw wei. Always convert `amount / 10^18`, show 4 decimal places.
3. **Write safety**: Never auto-execute. Show transaction details → wait for user confirmation → execute → show BSCScan tx link.
4. **Approve-then-act**: Deposit needs `approve(stakeNFT, …)`. RegisterSubnet needs `approve(rootNet, …)`. RegisterAndStake needs `approve(rootNet, …)`. Always wait for approve receipt before the next transaction.
5. **viem, not ethers.js**: Use `parseAbi`, `encodeAbiParameters`. Never use `encodePacked` for AWPDAO vote params.
6. **No hardcoded addresses**: Fetch all contract addresses dynamically via `GET /registry`.
7. **Input validation**: Address (0x + 40 hex chars), subnetId (positive integer), amount (positive BigInt).
8. **Pagination**: All list endpoints default limit=20, max=100. Always expose page/limit params.

## Pitfall Checklist

Before finalizing any skill, verify each item:

- [ ] `Deposited` event field is `lockEndEpoch` (absolute epoch number), NOT `lockEpochs` (relative input param)
- [ ] `Allocated`, `Deallocated`, `AgentRemoved`, `ManagerUpdated` events include `operator` field
- [ ] `SubnetRegistered` event includes full string fields: `metadataURI`, `coordinatorURL`, `skillsURI`
- [ ] On-chain `SubnetInfo` struct does NOT include name/symbol/skills_uri (off-chain indexed only)
- [ ] StakeNFT is NOT Enumerable — cannot iterate tokenIds on-chain, must use API
- [ ] AWPDAO `castVote()` and `castVoteWithReason()` are blocked — must use `castVoteWithReasonAndParams`
- [ ] `registerAndStake` approve target is RootNet, NOT StakeNFT
- [ ] `updateMetadata` requires ALL THREE string params (pass current values for unchanged fields)
- [ ] `signalPropose` creates signal-only proposals (no execution) — use `isSignalProposal()` to check
- [ ] All amounts in API responses are string-type wei — process with BigInt, never Number
