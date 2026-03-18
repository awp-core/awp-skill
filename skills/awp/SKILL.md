---
name: awp
description: >
  AWP RootNet protocol on BSC — query subnets/balances/emissions/agents,
  stake AWP via StakeNFT, allocate to agents, register/manage subnets
  (auto-deploy SubnetManager with Merkle distribution), set skills URI
  and min stake, create governance proposals, vote with position NFTs.
  ALWAYS use when the user mentions AWP, RootNet, subnet, staking AWP,
  AWP emission, AWP governance, alpha token, StakeNFT, SubnetNFT, or
  any AWP RootNet on-chain interaction.
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"],"skills":["AWP Wallet"]}}}
---

# AWP RootNet

**Skill version: 1.3.0**

## On Skill Load (do this FIRST)

Every time this skill is invoked, execute these steps before handling the user's request:

**Step 1 — Show welcome** (first session only, skip if already shown):
> **Welcome to AWP RootNet!**
>
> AWP RootNet is a decentralized Agent Mining protocol on BSC. Agents register on subnets, execute tasks, and earn AWP emissions. Each subnet auto-deploys a SubnetManager with Merkle distribution and AWP strategies.
>
> I can help you: **query** protocol state, **mine** (register + stake + work), **manage** subnets, **govern** via proposals, or **monitor** events (use awp-monitor skill).
>
> Say "start mining", "check my balance", "list subnets", or "what can I do?"

**Step 2 — Version check** (silent if up to date):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/SKILL.md | head -20 | grep "Skill version"
```
If remote version > 1.3.0, show: "Update available! Run: `openclaw skill install https://github.com/awp-core/awp-skill/tree/main/skills/awp`"

**Step 3 — Route to action** using the Intent Routing table below.

## Intent Routing

| User wants to... | Action | Reference file to load |
|-------------------|--------|------------------------|
| Query subnet info | Q1 | None |
| Check balance / positions | Q2 | None |
| View emission / epoch info | Q3 | None |
| Look up agent info | Q4 | None |
| Browse subnets | Q5 | None |
| Find / install subnet skill | Q6 | None |
| View epoch history | Q7 | None |
| Register / bind / start mining | S1 | **commands-staking.md** |
| Deposit / stake AWP | S2 | **commands-staking.md** |
| Allocate / deallocate / reallocate | S3 | **commands-staking.md** |
| Register a new subnet | M1 | **commands-subnet.md** |
| Activate / pause / resume subnet | M2 | **commands-subnet.md** |
| Update subnet metadata | M3 | **commands-subnet.md** |
| Update skills URI | M4 | **commands-subnet.md** |
| Set minimum stake | M5 | **commands-subnet.md** |
| Create governance proposal | G1 | **commands-governance.md** |
| Vote on proposal | G2 | **commands-governance.md** |
| Query proposals | G3 | None |
| Check treasury | G4 | None |

## Reference Files

- **api-reference.md** — Thin index of all Q1-Q7 read-only REST endpoints. Load for query actions.
  Local: `references/api-reference.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/references/api-reference.md`
- **commands-staking.md** — S1 register/bind, S2 deposit, S3 allocate. Full command templates, EIP-712, relay.
  Local: `references/commands-staking.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/references/commands-staking.md`
- **commands-subnet.md** — M1 register subnet, M2 lifecycle, M3 metadata, M4 skills URI, M5 min stake. Command templates, vanity, gasless.
  Local: `references/commands-subnet.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/references/commands-subnet.md`
- **commands-governance.md** — G1 proposals, G2 voting, G3/G4 queries, supplementary endpoints.
  Local: `references/commands-governance.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/references/commands-governance.md`
- **protocol.md** — Data structures, 28 event types, shared endpoints, constants.
  Local: `references/protocol.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/references/protocol.md`

**Loading rules**:
- Q1-Q7, G3, G4 — this SKILL.md has enough info. Optionally load api-reference.md for response schemas.
- S1-S3 — ALWAYS load commands-staking.md first. It has the exact bash commands.
- M1-M5 — ALWAYS load commands-subnet.md first.
- G1-G2 — ALWAYS load commands-governance.md first.
- Never guess commands; use the templates in the reference files.

## Wallet Dependency

Write actions (S/M/G sections) require the **AWP Wallet** skill.

1. Check if installed. If not: `openclaw skill install https://github.com/awp-core/awp-wallet`
2. Init: `awp-wallet init` (auto-generates password)
3. Unlock: `awp-wallet unlock --scope full --duration 3600`
4. All commands use `--chain bsc` (BSC, Chain ID 56)
5. Read-only Q actions do not need the wallet.

## Gas Routing (for S1 and M1)

Before register/bind/registerSubnet, check BNB:
```bash
awp-wallet balance --token {T} --chain bsc
```
- **Has BNB** — direct on-chain tx via awp-wallet
- **No BNB** — Gasless Relay (EIP-712 sign then POST /relay/*). Limit: 5/IP/4h
  - Register: `POST /relay/register`
  - Bind: `POST /relay/bind`
  - Subnet: `POST /relay/register-subnet` (two signatures)
- deposit/allocate always need BNB — no gasless option

### Inline High-Frequency Commands (S1)

These are used so often they belong here. For full EIP-712 templates and gasless flows, load commands-staking.md.

**Check registration:**
```bash
curl -s {API_BASE}/address/{addr}/check
```

**Check BNB gas:**
```bash
awp-wallet balance --token {T} --chain bsc
```

**Bind (on-chain, has BNB):**
```bash
awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "bind(address)" {addr}) --chain bsc
```

## Quick Start: Agent Mining

Ask user: **Principal (self-managed) or Agent (work for someone)?**

**Principal**: wallet setup -> S1 bind(myAddress) -> Q5 discover subnets -> Q6 install skill -> S2 deposit -> S3 allocate -> work -> earn

**Agent**: wallet setup -> S1 bind(principalAddr) -> Principal does S2+S3 -> install subnet skill -> work -> unbind() anytime

## Conventions

- **API Base URL**: `https://tapi.awp.sh/api` (or `AWP_API_URL` env var)
- **Data source**: REST API first -> on-chain fallback
- **Amounts**: `{formatAWP(amount)}` = wei / 10^18, 4 decimals. Never show raw wei.
- **Addresses**: `{shortAddr(addr)}` for display, full for params
- **Contract addresses**: `GET /registry` — never hardcode
- **Pagination**: limit=20 default, max=100
- **Validation**: address = 0x+40hex, subnetId = positive int, amount = positive BigInt

## Session State

Track these across the conversation to avoid redundant checks:
- `registered`: set to true after successful S1 bind/register — skip /address/check on subsequent actions
- `wallet_addr`: cache after first awp-wallet status call
- `registry`: cache GET /registry response — addresses don't change within a session
- `has_gas`: cache BNB balance check result — re-check only if a tx fails with insufficient gas

---

## Query (read-only, no wallet needed)

### Q1 · Query Subnet
1. `GET /subnets/{id}` -> full subnet object
2. Display: name, status, owner, alpha_token, skills_uri, subnet_contract, min_stake
3. On-chain fallback: getSubnetFull(id) -> SubnetFullInfo (10 fields incl. skillsURI, minStake, owner)

**Sample output:**
> Subnet #5 "DataMiner" | Status: Active | Owner: 0x1234...abcd | Alpha: 0xAAAA...BBBB | Skills: ipfs://Qm...

### Q2 · Query Balance
1. Parallel fetch: `GET /staking/user/{addr}/balance` + `/positions` + `/allocations`
2. Display: summary + position table (token_id, `{formatAWP(amount)}`, `{tsToDate(lock_end_time)}`)

**Sample output:**
> Total Staked: 10,000.0000 AWP | Allocated: 5,000.0000 | Unallocated: 5,000.0000
>   Position #1: 5,000 AWP, lock ends 2025-06-15
>   Position #7: 5,000 AWP, lock ends 2025-12-01

### Q3 · Query Emission
1. Parallel fetch: `GET /emission/current` + `/schedule` + `/epochs`
2. Display: epoch, daily emission, decay ~0.3156%/epoch (1-day epochs)

**Sample output:**
> Epoch 42 | Daily Emission: 15,000,000.0000 AWP | Decay: ~0.32%/day

### Q4 · Query Agent
1. Single: `GET /subnets/{subnetId}/agents/{agent}`
2. Batch: `POST /agents/batch-info` (max 100)
3. By owner: `GET /agents/by-owner/{owner}` · Lookup: `GET /agents/lookup/{agent}`

### Q5 · List Subnets
1. `GET /subnets?status={status}&page={p}&limit={n}`
2. Table: ID, Name, Status, Owner, skillsURI (flag subnets with skills)

### Q6 · Install Subnet Skill
1. `GET /subnets/{id}/skills` -> skillsURI
2. Fetch SKILL.md, show frontmatter
3. Install: `mkdir -p skills/awp-subnet-{id}` -> download -> restart session

### Q7 · Epoch History
1. `GET /emission/epochs?page={p}&limit={n}`
2. Display: epoch_id, `{tsToDate(start_time)}`, daily_emission, dao_emission

---

## Staking (wallet required — load commands-staking.md first)

### S1 · Register & Bind
Check `GET /address/{addr}/check` first. Use Gas Routing.

**Principal**: bind(myAddress) — auto-registers + binds
- setRewardRecipient(addr), setDelegation(agent, true) — optional
- registerAndStake(depositAmount, lockDuration, agent, subnetId, allocateAmount) — one-click, needs gas

**Agent**: bind(principalAddr) — auto-registers Principal
- unbind() anytime, rebind(newPrincipal) directly

**Gasless**: EIP-712 -> relay. Templates in commands-staking.md S1.

### S2 · Deposit AWP
1. approve AWP -> StakeNFT (not RootNet!)
2. deposit(amount, lockDuration_seconds) -> tokenId
3. lockEndTime is absolute timestamp in Deposited event
4. withdraw(tokenId) after lock expires
5. addToPosition(tokenId, amount, newLockEndTime) — **reverts PositionExpired if expired**

### S3 · Allocate / Deallocate / Reallocate
1. Check unallocated via `GET /staking/user/{addr}/balance`
2. allocate(agent, subnetId, amount) / deallocate / reallocate (immediate, no cooldown)

---

## Subnet Management (wallet + SubnetNFT ownership — load commands-subnet.md first)

### M1 · Register Subnet
1. LP cost = initialAlphaPrice x 100M. Optional: `POST /vanity/compute-salt`
2. approve AWP -> RootNet, then registerSubnet(7 params: name, symbol, metadataURI, subnetManager=0x0 for auto-deploy, coordinatorURL, salt, minStake)
3. **Gasless**: `POST /relay/register-subnet` (ERC-2612 permit + EIP-712). See commands-subnet.md M1.

### M2 · Lifecycle
Check `GET /subnets/{id}` -> activateSubnet / pauseSubnet / resumeSubnet

### M3 · Update Metadata
updateMetadata(subnetId, metadataURI, coordinatorURL) — BOTH strings required. skillsURI is separate (M4).

### M4 · Update Skills URI
SubnetNFT.setSkillsURI(subnetId, skillsURI) — NFT owner only. Emits SkillsURIUpdated.

### M5 · Set Min Stake
SubnetNFT.setMinStake(subnetId, minStake_wei) — NFT owner only. 0 = no minimum.

---

## Governance (wallet + StakeNFT positions — load commands-governance.md for G1/G2)

### G1 · Create Proposal
proposeWithTokens (executable, Timelock) or signalPropose (vote-only). Needs >= 1M AWP voting power.

### G2 · Vote
1. Fetch positions + proposalCreatedAt(id) on-chain
2. Filter: positions with createdAt >= proposalCreatedAt are **BLOCKED**
3. Encode tokenIds via ABI encode (NOT encodePacked)
4. castVoteWithReasonAndParams — the ONLY allowed vote function
5. Power: amount x sqrt(min(remainingTime, 54w) / 7d)

### G3 · Query Proposals
`GET /governance/proposals?status={status}&page={p}&limit={n}` + on-chain proposalVotes()

### G4 · Query Treasury
`GET /governance/treasury` -> optional AWPToken.balanceOf(treasury)

---

## Error Recovery

| Error | Fix |
|-------|-----|
| 400 Bad Request | Check address format (0x+40hex), amount > 0, subnetId > 0 |
| 404 Not Found | `GET /subnets` or `GET /agents/by-owner` to find valid IDs |
| 429 Rate Limit | Auto-retry: wait 60s then retry. If still 429, inform user of the 5/IP/4h limit. |
| "not registered" | Run S1: bind(myAddress) or bind(principalAddr) |
| "insufficient balance" | Q2 to check -> S2 to deposit more AWP |
| "not subnet owner" | Check SubnetNFT ownership via `GET /subnets/{id}` owner field |
| PositionExpired | Cannot addToPosition — withdraw first, then create new position via S2 |
| Approve not confirmed | Wait for receipt — `awp-wallet tx-status --hash {hash} --chain bsc` |
| Session expired | `awp-wallet unlock --scope full --duration 3600` |
| Wallet not found | `awp-wallet init` then `awp-wallet unlock` |
| AWP Wallet missing | `openclaw skill install https://github.com/awp-core/awp-wallet` |
