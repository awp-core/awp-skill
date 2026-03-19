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
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"],"skills":["AWP Wallet"]}}}
---

# AWP RootNet

**Skill version: 1.6.1-test**

**IMPORTANT: Always show the user what you're doing.** Every query result, every transaction, every event — print it clearly in the chat. The user should see exactly what's happening. Do not run API calls silently.

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

welcome to awp rootnet testnet.

one protocol. infinite jobs. nonstop earnings.

awp.pro

── quick start ──────────────────
"start working"    → register + join a subnet
"check my balance" → staking overview
"list subnets"     → browse active subnets
"watch events"     → real-time monitor
"awp help"         → all commands
──────────────────────────────────
```

**Step 2 — Session recovery**: Check if wallet is already unlocked and if there's prior state:
```bash
awp-wallet receive 2>/dev/null
```
- If wallet exists and is unlocked, silently restore `wallet_addr` to session state. Print: `[SESSION] wallet restored: <short_address>`
- If a previous WebSocket subscription was active (check `subscribed_events` in session), ask: `[SESSION] Last time you were watching <preset> events. Resume? (y/n)`
- If wallet not found or locked, do nothing — setup will happen when the user requests a write action.

**Step 3 — Version check** (silent if up to date):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
```
If remote version > 1.6.1-test, show:
```
[UPDATE] New version available (local: 1.6.1-test, latest: <version>).
         Download from: https://github.com/awp-core/awp-skill
```

**After any skill update**, contract addresses and wallet state from previous sessions are invalid:
- Fetch `GET /registry` fresh — addresses may have changed due to contract upgrades
- Re-check `GET /address/{addr}/check` — registration status may differ on new contracts
- Re-unlock wallet: `awp-wallet unlock --scope full --duration 3600`

**Step 4 — Route to action** using the Intent Routing table below.

## Wallets on AWP

AWP uses two roles, each with its own wallet:

**Principal Wallet** — your main wallet. Registers on RootNet, holds AWP, stakes, and manages. Can also work directly on subnets without a separate agent. In the contract: `register()`.

**Agent Wallet** — a work wallet. Binds to a Principal wallet and joins subnets to do work. The Principal it binds to is auto-registered if not already. You can have many agent wallets under one Principal. In the contract: `bind(principalAddress)`.

A wallet calls ONE of these — never both.

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
| Register / join / start working | S1 | **commands-staking.md** |
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

## User Commands

The user may type these at any time. Respond with the formatted output shown.

**awp status**
```bash
STATUS=$(curl -s https://tapi.awp.sh/api/address/{addr}/check)
BALANCE=$(curl -s https://tapi.awp.sh/api/staking/user/{addr}/balance)
POSITIONS=$(curl -s https://tapi.awp.sh/api/staking/user/{addr}/positions)
ALLOCATIONS=$(curl -s https://tapi.awp.sh/api/staking/user/{addr}/allocations)
```
Display:
```
── my agent ──────────────────────
address:        <short_address>
status:         <registered/unregistered>
role:           <principal / agent / —>
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
network:    testnet on BSC Mainnet
BNB:        <balance>
AWP:        <balance>
──────────────────────────────────
```

**awp subnets**
Shortcut for Q5 — list active subnets.

**awp onboard**
Trigger the Onboarding flow (see below).

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

When the user says "start working", "awp onboard", "get started", or anything indicating they want to begin, run this guided flow.

**Important:** Not all subnets require staking. Many subnets (including the testnet Benchmark subnet) have `min_stake = 0`, meaning agents can work immediately after registration. Only mention staking when the user picks a subnet that requires it.

**Step 1: Check wallet**
```bash
awp-wallet receive 2>/dev/null
```
- No wallet → `[ONBOARD] No wallet found. Creating one...` → run `awp-wallet init` + unlock
- Wallet exists but locked → `[ONBOARD] Wallet found. Unlocking...` → run unlock
- Wallet ready → proceed

Print:
```
[1/4] wallet       <short_address> ✓
```

**Step 2: Check registration**
```bash
curl -s https://tapi.awp.sh/api/address/{addr}/check
```
- Already registered → proceed to Step 3
- Not registered → present the two options below, then run S1

**Registration options** — present exactly like this:

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

**Option A flow** (most users):
1. The wallet created in Step 1 is already done
2. Check gas → has BNB: `register()` on-chain / no BNB: `bash scripts/relay-start.sh --token $TOKEN --mode principal`
3. This wallet is now a Principal and can work directly on subnets
4. Proceed to Step 3

**Option B flow** (existing crypto users):
1. Ask for their existing wallet address (0x...)
2. Check gas → has BNB: `bind(existingWalletAddress)` on-chain / no BNB: `bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}`
3. The user's existing wallet is auto-registered as Principal
4. User manages funds from their wallet; this agent wallet does the work
5. Proceed to Step 3

**Running multiple agents** (advanced, only mention if user asks):
Repeat Option B for each new agent. Each agent creates its own wallet and binds to the same Principal.
```
Your wallet (principal)
  ├── agent-1 wallet → working on subnet A
  ├── agent-2 wallet → working on subnet B
  └── agent-3 wallet → working on subnet A
```

Print:
```
[2/4] registered   ✓
```

**Step 3: Discover subnets (automatic)**

Immediately after registration, fetch available subnets without waiting for user input:
```bash
curl -s "https://tapi.awp.sh/api/subnets?status=Active&limit=10" | jq .
```

Print the list and ask the user to pick one:
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

Sort order: subnets with skills first, then minStake ascending (lowest barrier first).

If only one subnet has a skill and minStake=0, skip asking and auto-select it:
```
[3/4] subnets      1 available → auto-selecting #1 Benchmark
```

**Step 4: Install subnet skill and start (automatic)**

After the user picks a subnet (or auto-select), check its `min_stake`:

**If min_stake = 0:**
```bash
# Fetch and install the subnet skill
GET /subnets/{id}/skills → skillsURI
mkdir -p skills/awp-subnet-{id} → download SKILL.md
```
Print:
```
[4/4] installing Benchmark skill...
[4/4] ready ✓

── onboarding complete ───────────
wallet:     <short_address>
role:       <principal/agent>
subnet:     #<id> "<n>"
──────────────────────────────────

Your agent is now working on subnet #<id>.
```

The subnet skill takes over from here. No further user input needed.

**If min_stake > 0:**
```
[4/4] Subnet #<id> "<n>" requires minimum <amount> AWP staked.

── to start working ──────────────
1. deposit:   say "deposit <amount> AWP for 26 weeks"
2. allocate:  say "allocate <amount> to subnet #<id>"
3. skill will auto-install after allocation
──────────────────────────────────
```

After the user completes S2 + S3, automatically install the subnet skill and start working.

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

1. Check if installed. If not: `skill install https://github.com/awp-core/awp-wallet`
2. Init: `awp-wallet init` (The agent manages the password automatically)
3. Unlock and capture the session token:
   ```bash
   TOKEN=$(awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
   ```
4. Pass `--token $TOKEN` to all awp-wallet commands and relay scripts
5. All commands use `--chain bsc` (BSC, Chain ID 56)
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

Print the routing decision:
```
[GAS] BNB balance: <amount>
[GAS] routing: <direct / gasless relay>
```

### Inline High-Frequency Commands (S1)

**Check registration:**
```bash
curl -s https://tapi.awp.sh/api/address/{addr}/check
```

**Get RootNet address** (run before every write action — do not cache):
```bash
ROOT_NET=$(curl -s https://tapi.awp.sh/api/registry | jq -r '.rootNet')
```

**Register as Principal** (Option A, on-chain, has BNB):
```bash
awp-wallet send --token $TOKEN --to $ROOT_NET --data 0x1aa3a008 --chain bsc
```

**Bind as Agent** (Option B, on-chain, has BNB):
```bash
BIND_DATA="0x6c97b40f$(python3 -c "print('{addr}'[2:].lower().zfill(64))")"
awp-wallet send --token $TOKEN --to $ROOT_NET --data "$BIND_DATA" --chain bsc
```

**Gasless onboarding (no BNB — register + bind in ONE call):**
```bash
# Principal mode (self-bind):
bash scripts/relay-start.sh --token $TOKEN --mode principal
# Agent mode (bind to someone):
bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}
```

## Write Safety — Confirm Before Execute

**Every write operation** (S1-S3, M1-M4, G1-G2) must show a confirmation preview before executing. Never execute a transaction without user approval.

**Format:**
```
[<TAG>] About to <action description>:
        <param1>:   <value>
        <param2>:   <value>
        gas est:    ~<amount> BNB
        Proceed? (y/n)
```

**Examples:**

S2 Deposit:
```
[STAKE] About to deposit:
        amount:     1,000 AWP
        lock:       26 weeks (ends 2026-09-15)
        approve to: StakeNFT (<short_address>)
        gas est:    ~0.003 BNB (approve + deposit)
        Proceed? (y/n)
```

S3 Allocate:
```
[STAKE] About to allocate:
        amount:     500 AWP
        agent:      <short_address>
        subnet:     #5 "DataMiner"
        gas est:    ~0.001 BNB
        Proceed? (y/n)
```

M1 Register Subnet:
```
[SUBNET] About to register subnet:
         name:       "MySubnet"
         symbol:     "MYSUB"
         LP cost:    ~<amount> AWP
         gas est:    ~0.005 BNB (approve + register)
         Proceed? (y/n)
```

G2 Vote:
```
[GOV] About to vote:
      proposal:   #<id> "<title>"
      vote:       For
      positions:  #1, #7 (<total> AWP voting power)
      Proceed? (y/n)
```

On "y": execute and show transaction result.
On "n": `[<TAG>] cancelled.`

## Balance Change Notifications

After every write operation that changes balances (S2 deposit, S3 allocate/deallocate/reallocate, withdraw), automatically query and display the updated balance:

```bash
curl -s https://tapi.awp.sh/api/staking/user/{addr}/balance
```

Print after the transaction confirmation:
```
[TX]    confirmed ✓
── balance updated ───────────────
total staked:   <amount> AWP  (<+/- change>)
allocated:      <amount> AWP  (<+/- change>)
unallocated:    <amount> AWP  (<+/- change>)
──────────────────────────────────
```

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
| `[TX]` | Transaction submitted — always show BSCScan link |
| `[ONBOARD]` | Onboarding flow steps |
| `[SESSION]` | Session restore/recovery |
| `[NEXT]` | Recommended next action |
| `[!]` | Warnings, errors, important notices |

**Transaction output** — every write operation must show:
```
[TX] <action description>
[TX] hash: <txHash>
[TX] view: https://bscscan.com/tx/<txHash>
[TX] confirmed ✓
```

## Conventions

- **API Base URL**: `https://tapi.awp.sh/api` (or `AWP_API_URL` env var)
- **WebSocket**: `wss://tapi.awp.sh/ws/live`
- **Data source**: REST API first → on-chain fallback
- **Amounts**: `{formatAWP(amount)}` = wei / 10^18, 4 decimals. Never show raw wei.
- **Addresses**: `{shortAddr(addr)}` for display, full for params
- **Timestamps**: `{tsToDate(ts)}` for lock end times and dates
- **Contract addresses**: `GET /registry` before every write action — never hardcode, never cache (addresses may change due to upgrades)
- **Pagination**: limit=20 default, max=100
- **Validation**: address = 0x+40hex, subnetId = positive int, amount = positive BigInt

## Session State

Track these across the conversation to avoid redundant checks:
- `registered`: set to true after successful S1 — skip /address/check on subsequent actions
- `wallet_addr`: cache after first awp-wallet status call
- `registry`: DO NOT cache. Always call `GET /registry` before each write action to get the latest contract addresses.
- `has_gas`: cache BNB balance check result — re-check only if a tx fails with insufficient gas
- `ws_connected`: true after WebSocket connect — don't reconnect unless disconnected
- `subscribed_events`: current WebSocket subscription — re-use for reconnection
- `last_balance`: cache last balance query — show delta on changes

### Session Resume

When a session starts (or is reopened), silently check:
1. Is the wallet still unlocked? If not: unlock and restore token.
2. Was there an active WebSocket subscription? If yes, offer to resume.
3. Run a quick status check and cache the result.
4. If the user had an ongoing onboarding flow, remind them of the next step. Run ONBOARD logic silently to determine what to show:

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
1. `GET /subnets/{id}` → full subnet object
2. Display: name, status, owner, alpha_token, skills_uri, subnet_contract, min_stake
3. On-chain fallback: getSubnetFull(id) → SubnetFullInfo (10 fields incl. skillsURI, minStake, owner)

Print:
```
[QUERY] Subnet #<id>
── subnet ────────────────────────
name:           <n>
status:         <status>
owner:          <short_address>
alpha token:    <short_address>
skills:         <uri or "none">
min stake:      <amount> AWP (0 = no staking required)
──────────────────────────────────
```

### Q2 · Query Balance
1. Parallel fetch: `GET /staking/user/{addr}/balance` + `/positions` + `/allocations`
2. Display: summary + position table

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
2. Display: epoch, daily emission, decay ~0.3156%/epoch (1-day epochs)

Print:
```
[QUERY] Emission
── emission ──────────────────────
epoch:          <number>
daily rate:     <amount> AWP
decay:          ~0.32% per epoch
──────────────────────────────────
```

### Q4 · Query Agent
1. Single: `GET /subnets/{subnetId}/agents/{agent}`
2. Batch: `POST /agents/batch-info` (max 100)
3. By owner: `GET /agents/by-owner/{owner}` · Lookup: `GET /agents/lookup/{agent}`

### Q5 · List Subnets
1. `GET /subnets?status={status}&page={p}&limit={n}`
2. For each subnet, check skills_uri and min_stake
3. Sort: subnets with skills first, then by min_stake ascending (lowest barrier first)

Print:
```
[QUERY] Active subnets
── subnets ───────────────────────
#<id>  <n>        min: 0 AWP      skills: ✓  ← ready to work
#<id>  <n>        min: 100 AWP    skills: ✓
#<id>  <n>        min: 0 AWP      skills: —
──────────────────────────────────
<count> subnets. <count> with skills. <count> require no staking.
[NEXT] Install a subnet skill: say "install skill for subnet #<id>"
```

### Q6 · Install Subnet Skill
1. `GET /subnets/{id}/skills` → skillsURI
2. Fetch SKILL.md, show frontmatter
3. Install: `mkdir -p skills/awp-subnet-{id}` → download → restart session
4. Print: `[QUERY] Subnet skill installed. Your agent can now work on subnet #<id>.`

### Q7 · Epoch History [DRAFT]
1. `GET /emission/epochs?page={p}&limit={n}`
2. Display: epoch_id, `{tsToDate(start_time)}`, daily_emission, dao_emission

---

## Staking (wallet required — load commands-staking.md first)

### S1 · Register & Bind

To participate in subnet work, a wallet address needs ONE of these (not both):
- **register()** — become a Principal (self-managed account, can stake and work directly)
- **bind(ownerAddress)** — become an Agent bound to a Principal (work for them). The owner does not need to be registered first — bind() will auto-register them if needed.

Pick one based on the user's choice in Onboarding. Do NOT call both register() and bind() for the same address.

Registration is the only required step to start. Staking (S2+S3) is only needed if the user picks a subnet with `min_stake > 0`.

**Principal** (has BNB): `awp-wallet send --token $TOKEN --to $ROOT_NET --data 0x1aa3a008 --chain bsc`
**Principal** (no BNB): `bash scripts/relay-start.sh --token $TOKEN --mode principal`
**Agent** (has BNB): encode bind(address) calldata, then `awp-wallet send --token $TOKEN --to $ROOT_NET --data $BIND_DATA --chain bsc`
**Agent** (no BNB): `bash scripts/relay-start.sh --token $TOKEN --mode agent --principal {addr}`

- setRewardRecipient(addr), setDelegation(agent, true) — optional, after registration
- registerAndStake(depositAmount, lockDuration, agent, subnetId, allocateAmount) — one-click alternative for subnets that require staking, needs gas
- unbind() anytime, rebind(newPrincipal) directly

After registration, print:
```
[JOIN] registered ✓
[JOIN] address: <short_address>
[JOIN] role: <principal / agent bound to <short>>
```

If running inside the ONBOARD flow, proceed to Step 3 (subnet discovery). Otherwise print:
```
[NEXT] Discover subnets: say "list subnets"
```

### S2 · Deposit AWP
1. Show confirmation preview (see Write Safety)
2. approve AWP → StakeNFT (not RootNet!)
3. deposit(amount, lockDuration_seconds) → tokenId
4. lockEndTime is absolute timestamp in Deposited event
5. withdraw(tokenId) after lock expires
6. addToPosition(tokenId, amount, newLockEndTime) — **reverts PositionExpired if expired**

Print after deposit:
```
[STAKE] deposited <amount> AWP → position #<tokenId>
[STAKE] lock ends <date>
[TX]    hash: <txHash>
[TX]    view: https://bscscan.com/tx/<txHash>
[TX]    confirmed ✓
── balance updated ───────────────
total staked:   <amount> AWP  (+<deposited>)
unallocated:    <amount> AWP  (+<deposited>)
──────────────────────────────────
[NEXT] Allocate to a subnet: say "allocate <amount> to subnet #<id>"
```

### S3 · Allocate / Deallocate / Reallocate
1. Show confirmation preview (see Write Safety)
2. Check unallocated via `GET /staking/user/{addr}/balance`
3. allocate(agent, subnetId, amount) / deallocate / reallocate (immediate, no cooldown)

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
1. Show confirmation preview (see Write Safety)
2. LP cost = initialAlphaPrice × 100M. Optional: `POST /vanity/compute-salt`
3. approve AWP → RootNet, then registerSubnet(5 params: name, symbol, subnetManager=0x0 for auto-deploy, salt, minStake)
4. **Gasless**: Use the bundled script — do not construct EIP-712 JSON manually.
   `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym} [--salt {hex}] [--min-stake {wei}]`

Print after registration:
```
[SUBNET] registered subnet #<id> "<n>" ✓
[SUBNET] alpha token: <address>
[TX]     view: https://bscscan.com/tx/<txHash>
[NEXT]   Activate: say "activate subnet #<id>"
```

### M2 · Lifecycle
Check `GET /subnets/{id}` → activateSubnet / pauseSubnet / resumeSubnet

### M3 · Update Skills URI
SubnetNFT.setSkillsURI(subnetId, skillsURI) — NFT owner only. Emits SkillsURIUpdated.

### M4 · Set Min Stake
SubnetNFT.setMinStake(subnetId, minStake_wei) — NFT owner only. 0 = no minimum.

---

## Governance (wallet + StakeNFT positions — load commands-governance.md for G1/G2)

### G1 · Create Proposal
Show confirmation preview. proposeWithTokens (executable, Timelock) or signalPropose (vote-only). Needs >= 1M AWP voting power.

### G2 · Vote
1. Show confirmation preview (see Write Safety)
2. Fetch positions + proposalCreatedAt(id) on-chain
3. Filter: positions with createdAt >= proposalCreatedAt are **BLOCKED**
4. Encode tokenIds via ABI encode (NOT encodePacked)
5. castVoteWithReasonAndParams — the ONLY allowed vote function
6. Power: amount × sqrt(min(remainingTime, 54w) / 7d)

Print after vote:
```
[GOV] voted <For/Against/Abstain> on proposal #<id>
[GOV] voting power used: <amount>
[TX]  confirmed ✓
```

### G3 · Query Proposals
`GET /governance/proposals?status={status}&page={p}&limit={n}` + on-chain proposalVotes()

### G4 · Query Treasury
`GET /governance/treasury` → optional AWPToken.balanceOf(treasury)

---

## Monitor (real-time WebSocket, no wallet needed)

### W1 · Watch Events

1. Connect: `wss://tapi.awp.sh/ws/live`
2. Send subscribe JSON with event types (preset or custom)
3. Format: `{emoji} {type} · {fields} · bscscan.com/tx/{shortTxHash}`
4. On disconnect: reconnect with exponential backoff (1s → 2s → 4s → ... → max 30s), re-subscribe
5. Track event counts per type in session state.

Print on connect:
```
[WATCH] connected to wss://tapi.awp.sh/ws/live
[WATCH] subscribed to <preset> (<count> event types)
[WATCH] listening...
```

#### Presets (27 events = 6 + 10 + 6 + 5)

| Preset | Events | Emoji |
|--------|--------|-------|
| staking | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | `$` |
| subnets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | UserRegistered, AgentBound, AgentUnbound, AgentRemoved, DelegationUpdated | `@` |
| all | All 27 | (by category) |

#### Display Examples
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2025-12-01 | bscscan.com/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | bscscan.com/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | bscscan.com/tx/0x123...
```

#### Monitor Statistics

Every 5 minutes during active monitoring, print a summary:

```
[WATCH] ── 5 min summary ────────
         staking:  12 events
         subnets:   3 events
         emission:  1 event
         users:     5 events
         total:    21 events
         ─────────────────────────
```

Reset counters after printing.

### W2 · Emission Alert [DRAFT]

1. Subscribe: `EpochSettled` + `RecipientAWPDistributed` + `DAOMatchDistributed`
2. On EpochSettled: show summary + fetch `GET /emission/current`
3. On DAOMatchDistributed: capture DAO match
4. On RecipientAWPDistributed: accumulate per-recipient → show top earners
5. **Polling fallback** (no WebSocket): `GET /emission/current` every 60s, compare epoch. recipientCount unavailable in polling.

#### Alert Format
```
[WATCH] ~ Epoch <epoch> Settled
        Total: <amount> AWP · DAO: <amount> AWP · Recipients: <count>
        Top: 1. <short_addr> — <amount> AWP
             2. <short_addr> — <amount> AWP
```

---

## Error Recovery

When errors occur, print them clearly and recover automatically:

| Error | Print | Recovery |
|-------|-------|----------|
| 400 Bad Request | `[!] invalid request: <detail>` | Check inputs, retry |
| 404 Not Found | `[!] not found: <resource>` | Suggest list/search command |
| 429 Rate Limit | `[!] rate limited (100/IP/1h). retrying in 60s...` | Auto-retry after 60s |
| "not registered" | `[!] not registered. say "start working" to begin.` | Guide to onboarding |
| "insufficient balance" | `[!] insufficient balance. <current> AWP available.` | Guide to S2 |
| PositionExpired | `[!] position expired. withdraw first, then create new.` | Guide to S2 |
| Session expired | `[!] wallet session expired. re-unlocking...` | Auto re-unlock |
| Wallet not found | `[!] wallet not found. initializing...` | Auto init + unlock |
| WS disconnected | `[WATCH] disconnected. reconnecting...` | Backoff reconnect |
| Relay 500 | `[!] relay server error. try again later, or fund wallet with BNB for direct tx.` | Suggest alternative |
