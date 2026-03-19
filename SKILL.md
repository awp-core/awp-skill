---
name: awp
description: >
  Interact with the AWP (Agent Working Protocol) on Base/EVM. This skill handles
  ALL AWP operations: check staking balances and positions, stake/deposit AWP tokens,
  allocate stake to agents on subnets, register and manage subnets (gasless or on-chain),
  create DAO governance proposals, vote on proposals with position NFTs, query emission
  rates and epoch history, look up agent info, list subnets, install subnet skills,
  and monitor real-time blockchain events via WebSocket. Use this skill whenever the user
  mentions AWP, AWP staking, AWP balance, AWP deposit, AWP subnet, AWP emission,
  AWP governance, AWP proposal, AWP voting, AWP allocation, AWP mining (solo or delegated),
  AWP binding, AWP wallet, AWPRegistry, StakeNFT, SubnetNFT, alpha token, or any on-chain
  interaction with the AWP protocol — even if the user doesn't say "AWP skill" explicitly.
  Also trigger when users ask to watch, monitor, or subscribe to AWP events, check their
  staked positions, register as a miner, or set up delegated mining with cold/hot wallets.
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"],"skills":["AWP Wallet"]}}}
---

# AWP Registry

**Skill version: 1.9.0**

**IMPORTANT: Always show the user what you're doing.** Every query result, every transaction, every event — print it clearly. Never run API calls silently.

## On Skill Load (do this FIRST)

**Step 1 — Welcome screen** (first session only, skip if already shown):

```
╭──────────────╮
│              │
│  >       <   │
│      ~       │
│              │
╰──────────────╯

agent · work · protocol

welcome to awp.

one protocol. infinite jobs. nonstop earnings.

── quick start ──────────────────
"start working"    → register + join a subnet
"check my balance" → staking overview
"list subnets"     → browse active subnets
"watch events"     → real-time monitor
"awp help"         → all commands
──────────────────────────────────
```

**Step 2 — Session recovery**: Check if wallet is already unlocked and restore prior state:
```bash
awp-wallet receive 2>/dev/null
```
- If wallet unlocked, silently restore `wallet_addr`. Print: `[SESSION] wallet restored: <short_address>`
- If a previous WebSocket subscription was active (`subscribed_events` in session), ask: `[SESSION] Last time you were watching <preset> events. Resume? (y/n)`
- If wallet not found or locked, do nothing — setup happens on first write action.

**Step 3 — Version check** (silent if up to date):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
```
If remote version > 1.9.0:
```
[UPDATE] New version available (local: 1.9.0, latest: <version>).
         Download from: https://github.com/awp-core/awp-skill
```

**After any skill update**, contract addresses and wallet state from previous sessions are invalid:
- Fetch `GET /registry` fresh — addresses may have changed due to contract upgrades
- Re-check `GET /address/{addr}/check` — registration status may differ on new contracts
- Re-unlock wallet: `awp-wallet unlock --scope full --duration 3600`

**Step 4 — Route to action** using the Intent Routing table below.

## User Commands

The user may type these at any time:

**awp status**
```
── my agent ──────────────────────
address:        <short_address>
status:         <registered/unregistered>
role:           <solo / delegated agent / —>
bound to:       <short_address or "self">
total staked:   <amount> AWP
allocated:      <amount> AWP
unallocated:    <amount> AWP
positions:      <count>
subnets:        <list of allocated subnets>
──────────────────────────────────
```

**awp wallet**
```
── wallet ────────────────────────
address:    <address>
network:    Base
ETH:        <balance>
AWP:        <balance>
──────────────────────────────────
```

**awp subnets** — shortcut for Q5 (list active subnets)

**awp onboard** — trigger the Onboarding flow

**awp help**
```
── commands ──────────────────────
awp status       → your agent overview
awp wallet       → wallet address + balances
awp subnets      → browse active subnets
awp onboard      → guided setup
awp help         → this list

── actions ───────────────────────
"start working"    → register + join
"check my balance" → staking overview
"list subnets"     → browse + install skills
"watch events"     → real-time monitor
"deposit X AWP"    → stake tokens
"allocate"         → direct stake to subnet
──────────────────────────────────
```

## Onboarding Flow (ONBOARD)

When the user says "start working", "awp onboard", "get started", or similar, run this guided flow.

Not all subnets require staking. Many subnets have `min_stake = 0`, meaning agents can work immediately after setup. Only mention staking when the user picks a subnet that requires it.

**Step 1: Check wallet**
- No wallet → `[ONBOARD] No wallet found. Creating one...` → `awp-wallet init` + unlock
- Wallet locked → `[ONBOARD] Wallet found. Unlocking...` → unlock
- Wallet ready → proceed

Print:
```
[1/4] wallet       <short_address> ✓
```

**Step 2: Check registration**
```bash
curl -s {API_BASE}/api/address/{addr}/check
```
- Already registered → proceed to Step 3
- Not registered → present options:

```
── how do you want to start? ─────

  Option A: Quick Start (recommended)

  No wallet? No problem.
  The skill creates one for you and
  registers automatically. You can
  start working right away. Gasless.

  ────────────────────────────────────

  Option B: Link Your Wallet

  Already have a crypto wallet?
  The skill creates a work wallet and
  links it to your existing address.
  You manage funds, the agent works.
  Gasless.

───────────────────────────────────
```

**Option A** (Solo Mining):
1. Wallet created in Step 1
2. Check gas → has ETH: on-chain `setRecipient(self)` / no ETH: `bash scripts/relay-start.sh --token $TOKEN --mode principal`
3. Proceed to Step 3

**Option B** (Delegated Mining):
1. Ask for their existing wallet address (0x...)
2. Check gas → has ETH: on-chain `bind(existingWalletAddr)` / no ETH: `bash scripts/relay-start.sh --token $TOKEN --mode agent --target {addr}`
3. Proceed to Step 3

Print: `[2/4] registered   ✓`

**Step 3: Discover subnets (automatic)**
```bash
curl -s "{API_BASE}/api/subnets?status=Active&limit=10"
```
Sort: subnets with skills first, then minStake ascending.

```
[3/4] discovering subnets...

── available subnets ─────────────
#1  Benchmark    min: 0 AWP    ✓ skill ready
#3  DataMiner    min: 500 AWP  ✓ skill ready
#5  CodeReview   min: 0 AWP    — no skill yet
──────────────────────────────────

Which subnet do you want to work on?
(enter # or name)
```

If only one subnet has a skill and minStake=0, auto-select it.

**Step 4: Install subnet skill and start**

If min_stake = 0:
```
[4/4] installing <name> skill...
[4/4] ready ✓

── onboarding complete ───────────
wallet:     <short_address>
role:       <solo / delegated agent>
subnet:     #<id> "<name>"
──────────────────────────────────

Your agent is now working on subnet #<id>.
```

If min_stake > 0:
```
[4/4] Subnet #<id> "<name>" requires minimum <amount> AWP staked.

── to start working ──────────────
1. deposit:   say "deposit <amount> AWP for 26 weeks"
2. allocate:  say "allocate <amount> to subnet #<id>"
3. skill will auto-install after allocation
──────────────────────────────────
```

## Intent Routing

| User wants to... | Action | Reference file to load |
|-------------------|--------|------------------------|
| Start / onboard / setup | ONBOARD | **commands-staking.md** |
| Query subnet info | Q1 | None |
| Check balance / positions | Q2 | None |
| View emission / epoch info | Q3 [DRAFT] | None |
| Look up agent info | Q4 | None |
| Browse subnets | Q5 | None |
| Find / install subnet skill | Q6 | None |
| View epoch history | Q7 [DRAFT] | None |
| Set recipient / bind / start mining | S1 | **commands-staking.md** |
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

## Output Format

Use tagged prefixes for all operations so the user can follow along:

| Tag | When |
|-----|------|
| `[QUERY]` | Read-only data fetches (Q1-Q7) |
| `[STAKE]` | Staking operations (S1-S3) |
| `[SUBNET]` | Subnet management (M1-M4) |
| `[GOV]` | Governance (G1-G4) |
| `[WATCH]` | WebSocket events (W1-W2) |
| `[GAS]` | Gas routing decisions |
| `[TX]` | Transaction submitted — always show explorer link |
| `[ONBOARD]` | Onboarding flow steps |
| `[SESSION]` | Session restore/recovery |
| `[NEXT]` | Recommended next action |
| `[!]` | Warnings, errors, important notices |

**Transaction output** — every write operation:
```
[TX] <action description>
[TX] hash: <txHash>
[TX] view: https://basescan.org/tx/<txHash>
[TX] confirmed ✓
```

## Write Safety — Confirm Before Execute

Every write operation (S1-S3, M1-M4, G1-G2) must show a confirmation preview before executing:

```
[<TAG>] About to <action description>:
        <param1>:   <value>
        <param2>:   <value>
        gas est:    ~<amount> ETH
        Proceed? (y/n)
```

On "y": execute and show transaction result. On "n": `[<TAG>] cancelled.`

## Balance Change Notifications

After every write operation that changes balances (S2/S3/withdraw), auto-query and display:
```
[TX]    confirmed ✓
── balance updated ───────────────
total staked:   <amount> AWP  (<+/- change>)
allocated:      <amount> AWP  (<+/- change>)
unallocated:    <amount> AWP  (<+/- change>)
──────────────────────────────────
```

## Bundled Files

```
awp-skill/
├── SKILL.md                          ← you are here
├── references/                       ← documentation (load on demand)
│   ├── api-reference.md                Q1-Q7 REST endpoint index
│   ├── commands-staking.md             S1-S3 command templates + EIP-712
│   ├── commands-subnet.md              M1-M4 command templates + gasless
│   ├── commands-governance.md          G1-G4 commands + supplementary endpoints
│   └── protocol.md                     Data structures, 26 events, constants
└── scripts/                          ← executable bash scripts (run directly)
    ├── relay-start.sh                    Gasless onboarding (bind or set-recipient)
    ├── relay-register-subnet.sh          Gasless subnet registration (dual signature)
    ├── onchain-register.sh               On-chain register (optional, has gas)
    ├── onchain-bind.sh                   On-chain bind (has gas)
    ├── onchain-deposit.sh                On-chain deposit AWP (has gas)
    ├── onchain-allocate.sh               On-chain allocate stake (has gas)
    ├── onchain-deallocate.sh             On-chain deallocate stake (has gas)
    ├── onchain-reallocate.sh             On-chain reallocate stake (has gas, 6 params)
    ├── onchain-withdraw.sh              On-chain withdraw from expired position (has gas)
    ├── onchain-add-position.sh           Add AWP to existing position (has gas)
    ├── onchain-register-and-stake.sh     One-click register+deposit+allocate (has gas)
    ├── onchain-vote.sh                   Cast DAO vote with position NFTs (has gas)
    ├── onchain-subnet-lifecycle.sh       Activate/pause/resume subnet (has gas)
    └── onchain-subnet-update.sh          Set skillsURI or minStake on SubnetNFT (has gas)
```

**Loading rules**:
- Q1-Q7, G3, G4, W1, W2 — this SKILL.md has enough info.
- S1-S3 — ALWAYS load commands-staking.md first.
- M1-M4 — ALWAYS load commands-subnet.md first.
- G1-G2 — ALWAYS load commands-governance.md first.
- Gasless bind — use `scripts/relay-start.sh --mode agent --target {addr}`.
- Gasless set recipient — use `scripts/relay-start.sh --mode principal`.
- Gasless subnet — use `scripts/relay-register-subnet.sh`.
- NEVER manually construct EIP-712 JSON. NEVER call setRecipient() and bind() as two separate steps when one suffices.

## Wallet Dependency

Write actions (S/M/G sections) require the **AWP Wallet** skill.

1. Check if installed. If not: `skill install https://github.com/awp-core/awp-wallet`
2. Init: `awp-wallet init` (The agent manages the password automatically)
3. Unlock and capture the session token:
   ```bash
   TOKEN=$(awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
   ```
4. Pass `--token $TOKEN` to all awp-wallet commands and relay scripts
5. All commands use `--chain base`.
6. Read-only Q/W actions do not need the wallet.

When setting up the wallet for the first time, print progress:
```
[1/3] wallet       initializing...
[1/3] wallet       <short_address> ✓
[2/3] tools        curl, jq ✓
[3/3] api          connected ✓

Ready.
```

## Gas Routing (for S1 and M1)

Before bind/setRecipient/registerSubnet, check native balance:
```bash
awp-wallet balance --token $TOKEN --chain base
```

Print the routing decision:
```
[GAS] ETH balance: <amount>
[GAS] routing: <direct / gasless relay>
```

- **Has gas** — direct on-chain tx via awp-wallet
- **No gas** — use the gasless relay scripts:
  - Bind: `bash scripts/relay-start.sh --token $TOKEN --mode agent --target {addr}`
  - Set recipient: `bash scripts/relay-start.sh --token $TOKEN --mode principal`
  - Subnet registration: `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym} [--skills-uri {uri}]`
  - Rate limit: 100/IP/1h
- deposit/allocate always need gas — no gasless option

### Inline High-Frequency Commands (S1)

**Check registration:**
```bash
curl -s {API_BASE}/api/address/{addr}/check
```
V2 response: `{"isRegistered": true, "boundTo": "0x...", "recipient": "0x..."}`
V1 response: `{"isRegisteredUser": false, "isRegisteredAgent": false, "isManager": false}`
> Scripts handle both formats automatically. V2: `isRegistered` = `boundTo != 0x0 || recipient != 0x0`.

**Get registry** (run before every write action — do not cache):
```bash
REGISTRY=$(curl -s {API_BASE}/api/registry)
AWP_REGISTRY=$(echo "$REGISTRY" | jq -r '.awpRegistry // .rootNet')
# V1 API returns .rootNet; V2 returns .awpRegistry — the // operator handles both
```

**Bind (on-chain, has gas):**
```bash
# bind(address target) — selector 0x81bac14f
TARGET_ADDR={addr}
BIND_DATA="0x81bac14f$(python3 -c "print('${TARGET_ADDR#0x}'.lower().zfill(64))")"
awp-wallet send --token $TOKEN --to $AWP_REGISTRY --data "$BIND_DATA" --chain base
```

**Set recipient (on-chain, has gas):**
```bash
# setRecipient(address) — selector 0x3bbed4a0
RECIPIENT={addr}
SET_DATA="0x3bbed4a0$(python3 -c "print('${RECIPIENT#0x}'.lower().zfill(64))")"
awp-wallet send --token $TOKEN --to $AWP_REGISTRY --data "$SET_DATA" --chain base
```

**Gasless bind / set recipient (no gas):**
```bash
bash scripts/relay-start.sh --token $TOKEN --mode agent --target {addr}
bash scripts/relay-start.sh --token $TOKEN --mode principal
```

## Conventions

- **API Base URL**: `{API_BASE}/api` (from `AWP_API_URL` env var — deployment-specific, do not hardcode)
- **WebSocket**: `wss://{API_HOST}/ws/live` (deployment-specific)
- **WebSocket limit**: 10 connections per IP
- **Data source**: REST API first -> on-chain fallback
- **Amounts**: `{formatAWP(amount)}` = wei / 10^18, 4 decimals. Never show raw wei.
- **Addresses**: `{shortAddr(addr)}` for display, full for params
- **Timestamps**: `{tsToDate(ts)}` for lock end times and dates
- **Contract addresses**: `GET /registry` before every write action — never hardcode, never cache
- **Pagination**: limit=20 default, max=100
- **Validation**: address = 0x+40hex, subnetId = positive int, amount = positive BigInt

## Common Mistakes (DO NOT do these)

- DO NOT cache /registry addresses — fetch fresh before every write action
- DO NOT construct EIP-712 JSON manually — use bundled scripts
- DO NOT use ethers.js or write custom signing code — use awp-wallet CLI + scripts
- DO NOT hardcode contract addresses, chainId, or API URLs — always from /registry and env vars
- DO NOT assume the user is registered — always check /address/{addr}/check first
- DO NOT use cast/foundry for gasless operations — use the relay scripts
- DO NOT invent steps not described in this skill — follow the exact flows
- DO NOT use stale terms: no "RootNet", no "AWPRootNet", no "unbind()", no "removeAgent()", no "setDelegation()". Exception: `--mode principal` in relay-start.sh is a valid flag name.
- DO NOT hardcode API URLs like `tapi.awp.sh` — use `{API_BASE}` from env var
- DO NOT execute write operations without showing the confirmation preview first

## Pre-Flight Checklist (run before ANY write action)

```
1. Wallet installed?    → awp-wallet --version (if missing: skill install awp-wallet)
2. Wallet unlocked?     → TOKEN=$(awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
3. Wallet address?      → WALLET_ADDR=$(awp-wallet status --token $TOKEN | jq -r '.address')
4. Registry fresh?      → REGISTRY=$(curl -s {API_BASE}/api/registry)
5. Registration status? → curl -s {API_BASE}/api/address/$WALLET_ADDR/check
6. Has gas?             → awp-wallet balance --token $TOKEN --chain base
```

## Session State

Track these across the conversation:
- `registered`: set to true after successful S1 — Pre-Flight step 5 can be skipped if true
- `wallet_addr`: cache after first awp-wallet status call
- `registry`: DO NOT cache. Always call `GET /registry` before each write action.
- `has_gas`: cache ETH balance — re-check only if a tx fails with insufficient gas
- `ws_connected`: true after WebSocket connect — don't reconnect unless disconnected
- `subscribed_events`: current WebSocket subscription — re-use for reconnection
- `last_balance`: cache last balance query — show delta on changes

### Session Resume

When a session starts (or is reopened), silently check:
1. Is the wallet still unlocked? If not: unlock and restore token.
2. Was there an active WebSocket subscription? Offer to resume.
3. If the user had an ongoing onboarding flow, remind them:
```
── welcome back ──────────────────
You registered last time but haven't
joined a subnet yet.

→ Next step: say "list subnets"
──────────────────────────────────
```

---

## Query (read-only, no wallet needed)

### Q1 · Query Subnet
1. `GET /subnets/{id}` -> full subnet object
2. On-chain fallback: getSubnetFull(id) -> SubnetFullInfo

Print:
```
[QUERY] Subnet #<id>
── subnet ────────────────────────
name:           <name>
status:         <status>
owner:          <short_address>
alpha token:    <short_address>
skills:         <uri or "none">
min stake:      <amount> AWP (0 = no staking required)
──────────────────────────────────
```

### Q2 · Query Balance
1. Parallel fetch: `GET /staking/user/{addr}/balance` + `/positions` + `/allocations`

Print:
```
[QUERY] Balance for <short_address>
── staking ───────────────────────
total staked:   <amount> AWP
allocated:      <amount> AWP
unallocated:    <amount> AWP

positions:
  #<id>  <amount> AWP  lock ends <date>
  #<id>  <amount> AWP  lock ends <date>

allocations:
  agent <short> → subnet #<id>  <amount> AWP
──────────────────────────────────
```

### Q3 · Query Emission [DRAFT]
1. Parallel fetch: `GET /emission/current` + `/schedule` + `/epochs`

Print:
```
[QUERY] Emission
── emission ──────────────────────
epoch:          <number>
daily rate:     <amount> AWP
decay:          ~0.3156% per epoch
──────────────────────────────────
```

### Q4 · Query Agent
1. Single: `GET /subnets/{subnetId}/agents/{agent}`
2. Display: agent address, subnetId, stake amount

### Q5 · List Subnets
1. `GET /subnets?status={status}&page={p}&limit={n}`
2. Sort: subnets with skills first, then by min_stake ascending

Print:
```
[QUERY] Active subnets
── subnets ───────────────────────
#<id>  <name>        min: 0 AWP      skills: ✓  ← ready to work
#<id>  <name>        min: 100 AWP    skills: ✓
#<id>  <name>        min: 0 AWP      skills: —
──────────────────────────────────
<count> subnets. <count> with skills. <count> require no staking.
[NEXT] Install a subnet skill: say "install skill for subnet #<id>"
```

### Q6 · Install Subnet Skill
1. `GET /subnets/{id}/skills` -> skillsURI
2. Fetch SKILL.md, show frontmatter
3. Install: `mkdir -p skills/awp-subnet-{id}` -> download -> restart session
4. Print: `[QUERY] Subnet skill installed. Your agent can now work on subnet #<id>.`

### Q7 · Epoch History [DRAFT]
1. `GET /emission/epochs?page={p}&limit={n}`
2. Display: epoch_id, date, daily_emission, dao_emission

---

## Staking (wallet required — load commands-staking.md first)

### S1 · Bind & Set Recipient

No mandatory registration — every address is implicitly a root. Choose based on mining mode:
- **Solo Mining** → `setRecipient(addr)` — optional, only if you want rewards elsewhere
- **Delegated Mining** → `bind(target)` — tree-based binding with anti-cycle check

**Bind (has gas):** `bash scripts/onchain-bind.sh --token $TOKEN --target {rootAddress}`
**Bind (no gas):** `bash scripts/relay-start.sh --token $TOKEN --mode agent --target {rootAddress}`
**Set recipient (has gas):** on-chain via awp-wallet (selector 0x3bbed4a0)
**Set recipient (no gas):** `bash scripts/relay-start.sh --token $TOKEN --mode principal`

After registration, print:
```
[STAKE] registered ✓
[STAKE] address: <short_address>
[STAKE] role: <solo / delegated agent bound to <short>>
[NEXT]  Discover subnets: say "list subnets"
```

- grantDelegate(delegate), revokeDelegate(delegate) — manage delegation after binding
- resolveRecipient(addr) — walks bound chain to root
- registerAndStake(depositAmount, lockDuration, agent, subnetId, allocateAmount) — one-click alternative, needs gas

### S2 · Deposit AWP

1. Show confirmation preview (see Write Safety)
2. **New deposit**: `bash scripts/onchain-deposit.sh --token $TOKEN --amount {AWP} --lock-days {days}`
3. **Add to existing position**: `bash scripts/onchain-add-position.sh --token $TOKEN --position {id} --amount {AWP} [--extend-days {days}]`
4. **Withdraw (expired only)**: `bash scripts/onchain-withdraw.sh --token $TOKEN --position {id}`

Print after deposit:
```
[STAKE] deposited <amount> AWP → position #<tokenId>
[STAKE] lock ends <date>
[TX]    hash: <txHash>
[TX]    view: https://basescan.org/tx/<txHash>
[TX]    confirmed ✓
── balance updated ───────────────
total staked:   <amount> AWP  (+<deposited>)
unallocated:    <amount> AWP  (+<deposited>)
──────────────────────────────────
[NEXT] Allocate to a subnet: say "allocate <amount> to subnet #<id>"
```

### S3 · Allocate / Deallocate / Reallocate

1. Show confirmation preview
2. **Allocate**: `bash scripts/onchain-allocate.sh --token $TOKEN --agent {addr} --subnet {id} --amount {AWP}`
3. **Deallocate**: `bash scripts/onchain-deallocate.sh --token $TOKEN --agent {addr} --subnet {id} --amount {AWP}`
4. **Reallocate**: `bash scripts/onchain-reallocate.sh --token $TOKEN --from-agent {addr} --from-subnet {id} --to-agent {addr} --to-subnet {id} --amount {AWP}`
5. **One-click register+stake**: `bash scripts/onchain-register-and-stake.sh --token $TOKEN --amount {AWP} --lock-days {days} --agent {addr} --subnet {id} --allocate-amount {AWP}`

Print after allocate:
```
[STAKE] allocated <amount> AWP → agent <short> on subnet #<id>
[TX]    confirmed ✓
── balance updated ───────────────
allocated:      <amount> AWP  (+<amount>)
unallocated:    <amount> AWP  (-<amount>)
──────────────────────────────────
```

---

## Subnet Management (wallet + SubnetNFT ownership — load commands-subnet.md first)

### M1 · Register Subnet
1. Show confirmation preview
2. LP cost = initialAlphaPrice x 100M. Optional: `POST /vanity/compute-salt` (rate limit: 20/hr)
3. **Gasless**: `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym} [--salt {hex}] [--min-stake {wei}] [--skills-uri {uri}]`

Print after registration:
```
[SUBNET] registered subnet #<id> "<name>" ✓
[SUBNET] alpha token: <address>
[TX]     view: https://basescan.org/tx/<txHash>
[NEXT]   Activate: say "activate subnet #<id>"
```

### M2 · Lifecycle
Use script: `bash scripts/onchain-subnet-lifecycle.sh --token $TOKEN --subnet {id} --action <activate|pause|resume>`
The script pre-checks current status and prevents invalid transitions.

### M3 · Update Skills URI
Use script: `bash scripts/onchain-subnet-update.sh --token $TOKEN --subnet {id} --skills-uri {uri}`
Targets SubnetNFT (not AWPRegistry). NFT owner only.

### M4 · Set Min Stake
Use script: `bash scripts/onchain-subnet-update.sh --token $TOKEN --subnet {id} --min-stake {wei}`
Targets SubnetNFT (not AWPRegistry). NFT owner only. 0 = no minimum.

---

## Governance (wallet + StakeNFT positions — load commands-governance.md for G1/G2)

### G1 · Create Proposal
Show confirmation preview. proposeWithTokens (executable) or signalPropose (vote-only). Needs >= 1M AWP voting power.

### G2 · Vote
1. Show confirmation preview
2. Use script: `bash scripts/onchain-vote.sh --token $TOKEN --proposal {id} --support {0|1|2} [--reason "text"]`
   The script handles: position fetching, createdAt filtering, ABI encoding of tokenIds, and sends to DAO_ADDR (not AWPRegistry).

Print after vote:
```
[GOV] voted <For/Against/Abstain> on proposal #<id>
[GOV] voting power used: <amount>
[TX]  confirmed ✓
```

### G3 · Query Proposals
`GET /governance/proposals?status={status}&page={p}&limit={n}` + on-chain proposalVotes()

### G4 · Query Treasury
`GET /governance/treasury` -> optional AWPToken.balanceOf(treasury)

---

## Monitor (real-time WebSocket, no wallet needed)

### W1 · Watch Events

1. Connect: `wss://{API_HOST}/ws/live` (10 connections per IP max)
2. Send subscribe JSON with event types (preset or custom)
3. On disconnect: reconnect with exponential backoff (1s-30s), re-subscribe

Print on connect:
```
[WATCH] connected to wss://<host>/ws/live
[WATCH] subscribed to <preset> (<count> event types)
[WATCH] listening...
```

#### Presets (26 events = 6 + 10 + 6 + 4)

| Preset | Events | Emoji |
|--------|--------|-------|
| staking | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | `$` |
| subnets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | Bound, RecipientUpdated, DelegateGranted, DelegateRevoked | `@` |
| all | All 26 | (by category) |

#### Display Examples
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2025-12-01 | basescan.org/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | basescan.org/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | basescan.org/tx/0x123...
```

#### Monitor Statistics

Every 5 minutes during active monitoring, print:
```
[WATCH] ── 5 min summary ────────
         staking:  12 events
         subnets:   3 events
         emission:  1 event
         users:     5 events
         total:    21 events
         ─────────────────────────
```

### W2 · Emission Alert [DRAFT]

1. Subscribe: `EpochSettled` + `RecipientAWPDistributed` + `DAOMatchDistributed`
2. On EpochSettled: show summary + fetch `GET /emission/current`

```
[WATCH] ~ Epoch <epoch> Settled
        Total: <amount> AWP · DAO: <amount> AWP · Recipients: <count>
        Top: 1. <short_addr> — <amount> AWP
             2. <short_addr> — <amount> AWP
```

---

## Error Recovery

| Error | Print | Recovery |
|-------|-------|----------|
| 400 Bad Request | `[!] invalid request: <detail>` | Check inputs, retry |
| 404 Not Found | `[!] not found: <resource>` | Suggest list/search command |
| 429 Rate Limit | `[!] rate limited (100/IP/1h). retrying in 60s...` | Auto-retry after 60s |
| "not registered" | `[!] not registered. say "start working" to begin.` | Guide to onboarding |
| "cycle detected" | `[!] binding would create a cycle — choose a different target.` | — |
| "insufficient balance" | `[!] insufficient balance. <current> AWP available.` | Guide to S2 |
| PositionExpired | `[!] position expired. withdraw first, then create new.` | Guide to S2 |
| Session expired | `[!] wallet session expired. re-unlocking...` | Auto re-unlock |
| Wallet not found | `[!] wallet not found. initializing...` | Auto init + unlock |
| WS disconnected | `[WATCH] disconnected. reconnecting...` | Backoff reconnect |
| Relay 500 | `[!] relay server error. try again, or fund wallet with ETH for direct tx.` | Suggest alternative |
