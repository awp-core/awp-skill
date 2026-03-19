---
name: awp
description: >
  AWP RootNet protocol on BSC — query subnets/balances/emissions/agents,
  stake AWP via StakeNFT, allocate to agents, register/manage subnets
  (auto-deploy SubnetManager with Merkle distribution), set skills URI
  and min stake, create governance proposals, vote with position NFTs,
  and monitor real-time on-chain events via WebSocket (27 event types).
  ALWAYS use when the user mentions AWP, RootNet, subnet, staking AWP,
  AWP emission, AWP governance, alpha token, StakeNFT, SubnetNFT, or
  any AWP RootNet on-chain interaction — including monitoring, watching,
  tracking, or subscribing to AWP events.
metadata: {"claude":{"requires":{"env":["AWP_API_URL"],"skills":["AWP Wallet"]}}}
---

# AWP RootNet

**Skill version: 1.6.1-test**

## On Skill Load (do this FIRST)

**Step 1 — Show welcome** (first session only, skip if already shown):
> **Welcome to AWP RootNet!**
>
> AWP RootNet is a decentralized Agent Working protocol on BSC. Agents register on subnets, execute tasks, and earn AWP emissions. Each subnet auto-deploys a SubnetManager with Merkle distribution and AWP strategies.
>
> I can help you: **query** protocol state, **mine** (register + stake + work), **manage** subnets, **govern** via proposals, and **monitor** real-time events via WebSocket.
>
> Say "start mining", "check my balance", "list subnets", "watch staking events", or "what can I do?"

**Step 2 — Version check** (silent if up to date):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
```
If remote version > 1.6.1-test, show: "Update available! Run: `claude skill install https://github.com/awp-core/awp-skill`"

**After any skill update**, contract addresses and wallet state from previous sessions are invalid:
- Fetch `GET /registry` fresh — addresses may have changed due to contract upgrades
- Re-check `GET /address/{addr}/check` — registration status may differ on new contracts
- Re-unlock wallet: `awp-wallet unlock --scope full --duration 3600`

**Step 3 — Route to action** using the Intent Routing table below.

## Intent Routing

| User wants to... | Action | Reference file to load |
|-------------------|--------|------------------------|
| Query subnet info | Q1 | None |
| Check balance / positions | Q2 | None |
| View emission / epoch info | Q3 [DRAFT] | None |
| Look up agent info | Q4 | None |
| Browse subnets | Q5 | None |
| Find / install subnet skill | Q6 | None |
| View epoch history | Q7 [DRAFT] | None |
| Register / bind / start mining | S1 | **commands-staking.md** |
| Deposit / stake AWP | S2 | **commands-staking.md** |
| Allocate / deallocate / reallocate | S3 | **commands-staking.md** |
| Register a new subnet | M1 | **commands-subnet.md** |
| Activate / pause / resume subnet | M2 | **commands-subnet.md** |
| Update skills URI | M3 | **commands-subnet.md** |
| Set minimum stake | M4 | **commands-subnet.md** |
| Create governance proposal | G1 | **commands-governance.md** |
| Vote on proposal | G2 | **commands-governance.md** |
| Query proposals | G3 | None |
| Check treasury | G4 | None |
| Watch / monitor events | W1 | None (presets below) |
| Emission settlement alerts | W2 [DRAFT] | None (workflow below) |

## Bundled Files

This skill ships with reference docs and executable scripts. They are installed alongside SKILL.md:

```
awp-skill/
├── SKILL.md                          ← you are here
├── references/                       ← documentation (load on demand)
│   ├── api-reference.md                Q1-Q7 REST endpoint index
│   ├── commands-staking.md             S1-S3 command templates + EIP-712
│   ├── commands-subnet.md              M1-M4 command templates + gasless
│   ├── commands-governance.md          G1-G4 commands + supplementary endpoints
│   └── protocol.md                     Data structures, 27 events, constants
└── scripts/                          ← executable bash scripts (run directly)
    ├── relay-start.sh                    Gasless onboarding (register + bind in ONE call)
    └── relay-register-subnet.sh          Gasless subnet registration (dual signature)
```

**Remote fallback** (if local files are missing, fetch from GitHub):
- `https://raw.githubusercontent.com/awp-core/awp-skill/main/references/{filename}`
- `https://raw.githubusercontent.com/awp-core/awp-skill/main/scripts/{filename}`

**Loading rules**:
- Q1-Q7, G3, G4, W1, W2 — this SKILL.md has enough info.
- S1-S3 — ALWAYS load commands-staking.md first.
- M1-M4 — ALWAYS load commands-subnet.md first.
- G1-G2 — ALWAYS load commands-governance.md first.
- Gasless onboarding — use `scripts/relay-start.sh` with `--mode principal` (register) or `--mode agent` (bind). Choose one per address, not both.
- Gasless subnet — use `scripts/relay-register-subnet.sh`.
- NEVER manually construct EIP-712 JSON. NEVER call register() and bind() as two separate steps.

## Wallet Dependency

Write actions (S/M/G sections) require the **AWP Wallet** skill.

1. Check if installed. If not: `claude skill install https://github.com/awp-core/awp-wallet`
2. Init: `awp-wallet init` (The agent manages the password automatically)
3. Unlock and capture the session token:
   ```bash
   TOKEN=$(awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
   ```
4. Pass `--token $TOKEN` to all awp-wallet commands and relay scripts
5. All commands use `--chain bsc` (BSC, Chain ID 56)
6. Read-only Q/W actions do not need the wallet.

## Gas Routing (for S1 and M1)

Before register/bind/registerSubnet, check BNB:
```bash
awp-wallet balance --token $TOKEN --chain bsc
```
- **Has BNB** — direct on-chain tx via awp-wallet
- **No BNB** — use the gasless relay scripts:
  - Onboarding (Principal): `bash scripts/relay-start.sh --token $TOKEN --mode principal`
  - Onboarding (Agent): `bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}`
  - Subnet registration: `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym}`
  - Rate limit: 100/IP/1h
  - Choose register (Principal) OR bind (Agent) — not both
- deposit/allocate always need BNB — no gasless option

### Inline High-Frequency Commands (S1)

**Check registration:**
```bash
curl -s https://tapi.awp.sh/api/address/{addr}/check
```

**Get RootNet address** (run before every write action — do not cache):
```bash
ROOT_NET=$(curl -s https://tapi.awp.sh/api/registry | jq -r '.rootNet')
```

**Bind (on-chain, has BNB):**
```bash
awp-wallet send --token $TOKEN --to $ROOT_NET --data $(cast calldata "bind(address)" {addr}) --chain bsc
```

**Gasless onboarding (no BNB — register + bind in ONE call):**
```bash
# Principal mode (self-bind):
bash scripts/relay-start.sh --token $TOKEN --mode principal
# Agent mode (bind to someone):
bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}
```

## Quick Start: Agent Working

Ask user: **Principal (self-managed) or Agent (work for someone)?**

**Principal**: wallet setup -> S1 register() -> Q5 discover subnets -> Q6 install skill -> S2 deposit -> S3 allocate -> work -> earn

**Agent**: wallet setup -> S1 bind(ownerAddress) -> Principal does S2+S3 -> install subnet skill -> work -> unbind() anytime

## Conventions

- **API Base URL**: `https://tapi.awp.sh/api` (or `AWP_API_URL` env var)
- **WebSocket**: `wss://tapi.awp.sh/ws/live`
- **Data source**: REST API first -> on-chain fallback
- **Amounts**: `{formatAWP(amount)}` = wei / 10^18, 4 decimals. Never show raw wei.
- **Addresses**: `{shortAddr(addr)}` for display, full for params
- **Timestamps**: `{tsToDate(ts)}` for lock end times and dates
- **Contract addresses**: `GET /registry` before every write action — never hardcode, never cache (addresses may change due to upgrades)
- **Pagination**: limit=20 default, max=100
- **Validation**: address = 0x+40hex, subnetId = positive int, amount = positive BigInt

## Session State

Track these across the conversation to avoid redundant checks:
- `registered`: set to true after successful S1 bind/register — skip /address/check on subsequent actions
- `wallet_addr`: cache after first awp-wallet status call
- `registry`: DO NOT cache. Always call `GET /registry` before each write action to get the latest contract addresses.
- `has_gas`: cache BNB balance check result — re-check only if a tx fails with insufficient gas
- `ws_connected`: true after WebSocket connect — don't reconnect unless disconnected
- `subscribed_events`: current WebSocket subscription — re-use for reconnection

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

### Q3 · Query Emission [DRAFT]
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

### Q7 · Epoch History [DRAFT]
1. `GET /emission/epochs?page={p}&limit={n}`
2. Display: epoch_id, `{tsToDate(start_time)}`, daily_emission, dao_emission

---

## Staking (wallet required — load commands-staking.md first)

### S1 · Register & Bind

To participate in subnet work, a wallet address needs ONE of these (not both):
- **register()** — become a Principal (self-managed account, can stake and earn directly)
- **bind(ownerAddress)** — become an Agent bound to a Principal (work for them). The owner does not need to be registered first — bind() will auto-register them if needed.

Pick one based on the user's role. Do NOT call both register() and bind() for the same address.

**Principal** (has BNB): `awp-wallet send --token $TOKEN --to $ROOT_NET --data $(cast calldata "register()") --chain bsc`
**Principal** (no BNB): `bash scripts/relay-start.sh --token $TOKEN --mode principal`
**Agent** (has BNB): `awp-wallet send --token $TOKEN --to $ROOT_NET --data $(cast calldata "bind(address)" {ownerAddress}) --chain bsc`
**Agent** (no BNB): `bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}`

- setRewardRecipient(addr), setDelegation(agent, true) — optional, after binding
- registerAndStake(depositAmount, lockDuration, agent, subnetId, allocateAmount) — one-click alternative, needs gas
- unbind() anytime, rebind(newPrincipal) directly

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
2. approve AWP -> RootNet, then registerSubnet(5 params: name, symbol, subnetManager=0x0 for auto-deploy, salt, minStake)
3. **Gasless**: Use the bundled script — do not construct EIP-712 JSON manually.
   `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym} [--salt {hex}] [--min-stake {wei}]`

### M2 · Lifecycle
Check `GET /subnets/{id}` -> activateSubnet / pauseSubnet / resumeSubnet

### M3 · Update Skills URI
SubnetNFT.setSkillsURI(subnetId, skillsURI) — NFT owner only. Emits SkillsURIUpdated.

### M4 · Set Min Stake
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

## Monitor (real-time WebSocket, no wallet needed)

### W1 · Watch Events

1. Connect: `wss://tapi.awp.sh/ws/live`
2. Send subscribe JSON with event types (preset or custom)
3. Format: `{emoji} {type} · {fields} · bscscan.com/tx/{shortTxHash}`
4. On disconnect: reconnect with exponential backoff (1s -> 2s -> 4s -> ... -> max 30s), re-subscribe

#### Presets (27 events = 6 + 10 + 6 + 5)

| Preset | Events | Emoji |
|--------|--------|-------|
| staking | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | `$` |
| subnets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | UserRegistered, AgentBound, AgentUnbound, AgentRemoved, DelegationUpdated | `@` |
| all | All 27 | (by category) |

#### Display Examples
- `$ Deposited · {shortAddr(user)} deposited {formatAWP(amount)} · lock ends {tsToDate(lockEndTime)} · bscscan.com/tx/{shortTxHash}`
- `# SubnetRegistered · #{subnetId} "{name}" by {shortAddr(owner)} · bscscan.com/tx/{shortTxHash}`
- `# SkillsURIUpdated · #{subnetId} -> {skillsURI} · bscscan.com/tx/{shortTxHash}`
- `~ EpochSettled · Epoch {epoch} · {formatAWP(totalEmission)} to {recipientCount} recipients · bscscan.com/tx/{shortTxHash}`
- `@ AgentBound · {shortAddr(agent)} -> {shortAddr(principal)} · bscscan.com/tx/{shortTxHash}`

#### Example Output
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2025-12-01 | bscscan.com/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | bscscan.com/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | bscscan.com/tx/0x123...
```

### W2 · Emission Alert [DRAFT]

1. Subscribe: `EpochSettled` + `RecipientAWPDistributed` + `DAOMatchDistributed`
2. On EpochSettled: show summary + fetch `GET /emission/current`
3. On DAOMatchDistributed: capture DAO match
4. On RecipientAWPDistributed: accumulate per-recipient -> show top earners
5. **Polling fallback** (no WebSocket): `GET /emission/current` every 60s, compare epoch. recipientCount unavailable in polling.

#### Alert Format
> ~ Epoch {epoch} Settled
>   Total: {formatAWP(totalEmission)} · DAO: {formatAWP(daoAmount)} · Recipients: {recipientCount}
>   Top: 1. {shortAddr(addr)} — {formatAWP(amount)} ...

---

## Error Recovery

| Error | Fix |
|-------|-----|
| 400 Bad Request | Check address format (0x+40hex), amount > 0, subnetId > 0 |
| 404 Not Found | `GET /subnets` or `GET /agents/by-owner` to find valid IDs |
| 429 Rate Limit | Auto-retry: wait 60s then retry. If still 429, inform user of the 100/IP/1h limit. |
| "not registered" | Run S1: register() or bind(ownerAddress) |
| "insufficient balance" | Q2 to check -> S2 to deposit more AWP |
| "not subnet owner" | Check SubnetNFT ownership via `GET /subnets/{id}` owner field |
| PositionExpired | Cannot addToPosition — withdraw first, then create new position via S2 |
| Approve not confirmed | Wait for receipt — `awp-wallet tx-status --hash {hash} --chain bsc` |
| Session expired | `awp-wallet unlock --scope full --duration 3600` |
| Wallet not found | `awp-wallet init` then `awp-wallet unlock` |
| AWP Wallet missing | `claude skill install https://github.com/awp-core/awp-wallet` |
| WS connection refused | Wait 5s, check `GET /health`, retry. After 3 failures: switch to polling. |
| WS unexpected close | Reconnect with backoff (1s-30s), re-send subscribe message. |
| No WS events | Verify event names against preset lists above |
