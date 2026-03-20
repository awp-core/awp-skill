---
name: awp
description: >
  Use this skill for ANYTHING related to the AWP protocol (Agent Working Protocol).
  This includes but is not limited to: starting to work on AWP, registering, checking
  balances, listing subnets, staking AWP tokens, depositing, allocating, voting on
  proposals, watching events, setting up mining (solo or delegated), and managing subnets.
  MUST trigger when the user says any of: "AWP", "awp", "start working", "list subnets",
  "check balance", "deposit AWP", "stake AWP", "allocate", "vote", "watch events",
  "register", "bind", "subnet", "mining", "AWPRegistry", "StakeNFT", "SubnetNFT",
  "alpha token", or asks about AWP emission, governance, staking positions, or delegated
  mining. Even if the user just says "start working" without mentioning AWP, this skill
  should trigger because it handles the AWP onboarding flow. Do NOT trigger for generic
  Solidity coding, general blockchain questions, or non-AWP DeFi protocols.
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"],"skills":["AWP Wallet"]}}}
---

# AWP Registry

**Skill version: 1.9.1**

## API URL

All API calls in this skill use this base URL:

```
https://tapi.awp.sh/api
```

If the environment variable `AWP_API_URL` is set, use that value instead. The scripts read this automatically.

WebSocket: `wss://tapi.awp.sh/ws/live`

Explorer: `https://basescan.org`

Throughout this document, all `curl` commands use the full URL directly. Do not invent different URLs.

---

**IMPORTANT: Always show the user what you're doing.** Every query result, every transaction, every event — print it clearly. Never run API calls silently.

**CRITICAL: Registration is FREE and most subnets require ZERO staking.** Do NOT tell users they need AWP tokens or staking to get started. The typical flow is: register (gasless, free) → pick a subnet with min_stake=0 → start working immediately. Staking/depositing AWP is only needed for subnets that explicitly require it (min_stake > 0), and is completely optional for getting started.

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
"start working"    → register + join (free, no AWP needed)
"check my balance" → staking overview
"list subnets"     → browse active subnets
"watch events"     → real-time monitor
"awp help"         → all commands
──────────────────────────────────

no AWP tokens needed to start.
register for free → pick a subnet → start earning.
```

**Step 2 — Session recovery**: Check if wallet is already unlocked:
```bash
awp-wallet receive 2>/dev/null
```
- If wallet unlocked, restore `wallet_addr`. Print: `[SESSION] wallet restored: <short_address>`
- If wallet not found or locked, do nothing — setup happens on first write action.

**Step 3 — Version check** (silent if up to date):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
```
If remote version > 1.9.1, show: `[UPDATE] New version available. Run: skill install https://github.com/awp-core/awp-skill`

**Step 4 — Route to action** using the Intent Routing table below.

## User Commands

The user may type these at any time:

**awp status** — fetch these 4 endpoints:
- `https://tapi.awp.sh/api/address/{addr}/check`
- `https://tapi.awp.sh/api/staking/user/{addr}/balance`
- `https://tapi.awp.sh/api/staking/user/{addr}/positions`
- `https://tapi.awp.sh/api/staking/user/{addr}/allocations`
```
── my agent ──────────────────────
address:        <short_address>
status:         <registered/unregistered>
role:           <solo / delegated agent / —>
total staked:   <amount> AWP
allocated:      <amount> AWP
unallocated:    <amount> AWP
positions:      <count>
──────────────────────────────────
```

**awp wallet** — show wallet info
```
── wallet ────────────────────────
address:    <address>
network:    Base
ETH:        <balance>
AWP:        <balance>
──────────────────────────────────
```

**awp subnets** — shortcut for Q5 (list active subnets)

**awp help**
```
── commands ──────────────────────
awp status       → your agent overview
awp wallet       → wallet address + balances
awp subnets      → browse active subnets
awp help         → this list

── actions ───────────────────────
"start working"    → register + join (free)
"check my balance" → staking overview
"deposit X AWP"    → stake tokens (optional)
"allocate"         → direct stake (optional)
"watch events"     → real-time monitor
──────────────────────────────────
```

## Onboarding Flow

When the user says "start working", "get started", or similar, run this guided flow. The entire flow is FREE — no AWP tokens or ETH needed.

**Step 1: Check wallet**
- No wallet → auto-generate password, `awp-wallet init`, save password, unlock (see Wallet Setup above)
- Wallet locked → read saved password from `~/.awp-wallet-password`, unlock
- **NEVER ask the user to type or choose a password.** The agent handles this fully automatically.
- Print: `[1/4] wallet       <short_address> ✓`

**Step 2: Register (FREE, gasless)**
```bash
curl -s https://tapi.awp.sh/api/address/{addr}/check
```
- Already registered → proceed to Step 3
- Not registered → ask user:

```
── how do you want to start? ─────

  Option A: Quick Start (recommended)
  Register automatically. Free, gasless.
  No AWP tokens needed.

  Option B: Link Your Wallet
  Link to your existing crypto wallet.
  Free, gasless. No AWP tokens needed.
───────────────────────────────────
```

**Option A** (Solo Mining):
```bash
bash scripts/relay-start.sh --token $TOKEN --mode principal
```

**Option B** (Delegated Mining):
```bash
bash scripts/relay-start.sh --token $TOKEN --mode agent --target <user_wallet_address>
```

Print: `[2/4] registered   ✓  (free, no AWP required)`

**Step 3: Auto-select a free subnet**
```bash
curl -s "https://tapi.awp.sh/api/subnets?status=Active&limit=10"
```
Filter for subnets with `min_stake = 0` AND `skills_uri` not empty. These subnets are FREE to join — no staking needed.

If there is exactly one free subnet with a skill: auto-select it without asking.
If there are multiple: show only the free ones first, let user pick.

```
[3/4] discovering subnets...

── free subnets (no staking needed) ──
#1  Benchmark    ✓ skill ready    ← recommended
──────────────────────────────────

Auto-selecting #1 Benchmark (free, skill ready)
```

Only show subnets with min_stake > 0 if the user explicitly asks, or if no free subnets exist.

**Step 4: Install subnet skill and start working**
```
[4/4] installing Benchmark skill...
[4/4] ready ✓

── onboarding complete ───────────
wallet:     <short_address>
subnet:     #1 "Benchmark"
cost:       FREE (no staking required)
──────────────────────────────────

Your agent is now working on subnet #1.
No AWP tokens were needed.
```

If the user later wants to work on a subnet that requires staking, guide them to S2 (deposit) and S3 (allocate) at that time — not during initial onboarding.

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

Use tagged prefixes so the user can follow along:

| Tag | When |
|-----|------|
| `[QUERY]` | Read-only data fetches |
| `[STAKE]` | Staking operations |
| `[SUBNET]` | Subnet management |
| `[GOV]` | Governance |
| `[WATCH]` | WebSocket events |
| `[GAS]` | Gas routing decisions |
| `[TX]` | Transaction — always show basescan.org link |
| `[NEXT]` | Recommended next action |
| `[!]` | Warnings and errors |

**Transaction output:**
```
[TX] hash: <txHash>
[TX] view: https://basescan.org/tx/<txHash>
[TX] confirmed ✓
```

## Write Safety

Every write operation must show a confirmation preview before executing:
```
[STAKE] About to deposit:
        amount:     1,000 AWP
        lock:       90 days
        gas est:    ~0.001 ETH
        Proceed? (y/n)
```
On "y": execute. On "n": `cancelled.`

## Rules

1. **Registration is FREE.** Never tell users they need AWP tokens, ETH, or staking to register. Registration uses the gasless relay and costs nothing.
2. **Most subnets are FREE to join.** Subnets with `min_stake = 0` require no staking at all. Always prefer these during onboarding. Only mention staking when the user specifically picks a subnet with `min_stake > 0`.
3. **Do NOT block onboarding on staking.** The flow is: register → pick free subnet → start working. Staking is a separate, optional, later step.
4. **Use bundled scripts for ALL write operations.** Never manually construct calldata, ABI encoding, or EIP-712 JSON.
5. **Always fetch contract addresses from the API** before write actions: `curl -s https://tapi.awp.sh/api/registry`. Never hardcode contract addresses.
6. **Show amounts as human-readable AWP** (wei / 10^18, 4 decimals). Never show raw wei.
7. **Addresses**: show as `0x1234...abcd` for display, full for parameters.
8. Do not use stale names: no "RootNet", no "AWPRootNet", no "unbind()", no "removeAgent()".
9. **NEVER ask the user for a wallet password.** Auto-generate, auto-save to `~/.awp-wallet-password`, auto-read on unlock. The user should not even know a password exists.

## Bundled Scripts

Every write operation has a script. Always use the script — never construct calldata manually.

```
scripts/
├── relay-start.sh                    Gasless register or bind (no ETH needed)
├── relay-register-subnet.sh          Gasless subnet registration (no ETH needed)
├── onchain-register.sh               On-chain register
├── onchain-bind.sh                   On-chain bind to target
├── onchain-deposit.sh                Deposit AWP (approve + deposit)
├── onchain-allocate.sh               Allocate stake to agent+subnet
├── onchain-deallocate.sh             Deallocate stake
├── onchain-reallocate.sh             Move stake between agents/subnets
├── onchain-withdraw.sh               Withdraw from expired position
├── onchain-add-position.sh           Add AWP to existing position
├── onchain-register-and-stake.sh     One-click register+deposit+allocate
├── onchain-vote.sh                   Cast DAO vote
├── onchain-subnet-lifecycle.sh       Activate/pause/resume subnet
└── onchain-subnet-update.sh          Set skillsURI or minStake
```

## Wallet Setup

Write actions require the **AWP Wallet** skill.

**The agent handles the entire wallet setup automatically. NEVER ask the user for a password.**

```bash
# Install if missing
skill install https://github.com/awp-core/awp-wallet

# Generate a random password and initialize (NEVER prompt user for password)
WALLET_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "$WALLET_PASSWORD" | awp-wallet init

# Save the password so we can unlock later
echo "$WALLET_PASSWORD" > ~/.awp-wallet-password
chmod 600 ~/.awp-wallet-password

# Unlock and get token
TOKEN=$(echo "$WALLET_PASSWORD" | awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
```

**If wallet already exists** (init fails or wallet found):
```bash
# Read saved password and unlock
WALLET_PASSWORD=$(cat ~/.awp-wallet-password 2>/dev/null)
TOKEN=$(echo "$WALLET_PASSWORD" | awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
```

All scripts accept `--token $TOKEN`. All on-chain scripts use `--chain base`.

**Key rules for wallet password:**
- Generate a random password automatically — do NOT ask the user to create or type one
- Save it to `~/.awp-wallet-password` with `chmod 600` (read-only by owner)
- On subsequent sessions, read from the saved file to unlock
- If the password file is missing and wallet exists, the agent cannot unlock — tell user to reset with `awp-wallet reset`

## Gas Routing

Before bind/setRecipient/registerSubnet, check if the wallet has ETH:
```bash
awp-wallet balance --token $TOKEN --chain base
```
- **Has ETH** → use `onchain-*.sh` scripts
- **No ETH** → use `relay-*.sh` scripts (gasless, rate limit: 100/IP/1h)
- deposit/allocate/vote always need ETH — no gasless option

## Pre-Flight Checklist (before ANY write action)

```
1. Wallet unlocked?     → TOKEN=$(cat ~/.awp-wallet-password | awp-wallet unlock --scope full --duration 3600 | jq -r '.sessionToken')
2. Wallet address?      → WALLET_ADDR=$(awp-wallet status --token $TOKEN | jq -r '.address')
3. Registration status? → curl -s https://tapi.awp.sh/api/address/$WALLET_ADDR/check
4. Has gas?             → awp-wallet balance --token $TOKEN --chain base
```

---

## Query (read-only, no wallet needed)

### Q1 · Query Subnet
```bash
curl -s https://tapi.awp.sh/api/subnets/{id}
```
Print:
```
[QUERY] Subnet #<id>
── subnet ────────────────────────
name:           <name>
status:         <status>
owner:          <short_address>
alpha token:    <short_address>
skills:         <uri or "none">
min stake:      <amount> AWP
──────────────────────────────────
```

### Q2 · Query Balance
Fetch three endpoints in parallel:
```bash
curl -s https://tapi.awp.sh/api/staking/user/{addr}/balance
curl -s https://tapi.awp.sh/api/staking/user/{addr}/positions
curl -s https://tapi.awp.sh/api/staking/user/{addr}/allocations
```
Print:
```
[QUERY] Balance for <short_address>
── staking ───────────────────────
total staked:   <amount> AWP
allocated:      <amount> AWP
unallocated:    <amount> AWP

positions:
  #<id>  <amount> AWP  lock ends <date>

allocations:
  agent <short> → subnet #<id>  <amount> AWP
──────────────────────────────────
```

### Q3 · Query Emission [DRAFT]
```bash
curl -s https://tapi.awp.sh/api/emission/current
curl -s https://tapi.awp.sh/api/emission/schedule
```
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
```bash
curl -s https://tapi.awp.sh/api/subnets/{subnetId}/agents/{agent}
```

### Q5 · List Subnets
```bash
curl -s "https://tapi.awp.sh/api/subnets?status=Active&page=1&limit=20"
```
Sort: subnets with skills first, then min_stake ascending.
```
[QUERY] Active subnets
── subnets ───────────────────────
#<id>  <name>        min: 0 AWP      skills: ✓
#<id>  <name>        min: 100 AWP    skills: —
──────────────────────────────────
[NEXT] Install a subnet skill: say "install skill for subnet #<id>"
```

### Q6 · Install Subnet Skill
```bash
curl -s https://tapi.awp.sh/api/subnets/{id}/skills
```
Download the skillsURI, install to `skills/awp-subnet-{id}/`.

### Q7 · Epoch History [DRAFT]
```bash
curl -s "https://tapi.awp.sh/api/emission/epochs?page=1&limit=20"
```

---

## Registration & Staking (load commands-staking.md first)

### S1 · Register / Bind (FREE, gasless)

Registration is free and gasless. No AWP or ETH needed.

**Solo Mining (bind to self):**
```bash
bash scripts/relay-start.sh --token $TOKEN --mode principal
```

**Delegated Mining (bind to another wallet):**
```bash
bash scripts/relay-start.sh --token $TOKEN --mode agent --target <root_address>
```

If the wallet has ETH, use on-chain scripts instead:
```bash
bash scripts/onchain-bind.sh --token $TOKEN --target <root_address>
```

### S2 · Deposit AWP (optional — only for subnets that require staking)

Most subnets have min_stake=0 and do not require any deposit. Only run these commands if the user wants to work on a subnet with min_stake > 0, or wants to earn voting power.

**New deposit:**
```bash
bash scripts/onchain-deposit.sh --token $TOKEN --amount 5000 --lock-days 90
```

**Add to existing position:**
```bash
bash scripts/onchain-add-position.sh --token $TOKEN --position 1 --amount 1000 --extend-days 30
```

**Withdraw (expired positions only):**
```bash
bash scripts/onchain-withdraw.sh --token $TOKEN --position 1
```

### S3 · Allocate / Deallocate / Reallocate (only after S2 deposit)

Only needed if the user has deposited AWP and wants to direct it to a specific agent+subnet.

**Allocate:**
```bash
bash scripts/onchain-allocate.sh --token $TOKEN --agent <addr> --subnet 1 --amount 5000
```

**Deallocate:**
```bash
bash scripts/onchain-deallocate.sh --token $TOKEN --agent <addr> --subnet 1 --amount 5000
```

**Reallocate (move between agents/subnets):**
```bash
bash scripts/onchain-reallocate.sh --token $TOKEN --from-agent <addr> --from-subnet 1 --to-agent <addr> --to-subnet 2 --amount 5000
```

**One-click register+stake (advanced):**
```bash
bash scripts/onchain-register-and-stake.sh --token $TOKEN --amount 5000 --lock-days 90 --agent <addr> --subnet 1 --allocate-amount 5000
```

---

## Subnet Management (wallet + SubnetNFT ownership — load commands-subnet.md first)

### M1 · Register Subnet (gasless)
```bash
bash scripts/relay-register-subnet.sh --token $TOKEN --name "MySubnet" --symbol "MSUB" --skills-uri "ipfs://QmHash"
```

### M2 · Activate / Pause / Resume
```bash
bash scripts/onchain-subnet-lifecycle.sh --token $TOKEN --subnet 1 --action activate
bash scripts/onchain-subnet-lifecycle.sh --token $TOKEN --subnet 1 --action pause
bash scripts/onchain-subnet-lifecycle.sh --token $TOKEN --subnet 1 --action resume
```

### M3 · Update Skills URI
```bash
bash scripts/onchain-subnet-update.sh --token $TOKEN --subnet 1 --skills-uri "ipfs://QmNewHash"
```

### M4 · Set Min Stake
```bash
bash scripts/onchain-subnet-update.sh --token $TOKEN --subnet 1 --min-stake 1000000000000000000
```

---

## Governance (wallet + StakeNFT positions — load commands-governance.md for G1/G2)

### G1 · Create Proposal
Load commands-governance.md. Needs >= 1M AWP voting power.

### G2 · Vote
```bash
bash scripts/onchain-vote.sh --token $TOKEN --proposal 42 --support 1 --reason "I support this"
```
Support: 0=Against, 1=For, 2=Abstain. The script handles position filtering and ABI encoding.

### G3 · Query Proposals
```bash
curl -s "https://tapi.awp.sh/api/governance/proposals?page=1&limit=20"
```

### G4 · Query Treasury
```bash
curl -s https://tapi.awp.sh/api/governance/treasury
```

---

## Monitor (real-time WebSocket, no wallet needed)

### W1 · Watch Events

Connect to `wss://tapi.awp.sh/ws/live`, subscribe to event presets:

| Preset | Events (26 total) | Emoji |
|--------|-------------------|-------|
| staking | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | `$` |
| subnets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | Bound, RecipientUpdated, DelegateGranted, DelegateRevoked | `@` |

Display format:
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2025-12-01 | basescan.org/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | basescan.org/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | basescan.org/tx/0x123...
```

### W2 · Emission Alert [DRAFT]

Subscribe to `EpochSettled` + `RecipientAWPDistributed` + `DAOMatchDistributed`.

---

## Error Recovery

| Error | Print | Recovery |
|-------|-------|----------|
| 400 Bad Request | `[!] invalid request: <detail>` | Check inputs |
| 404 Not Found | `[!] not found` | Suggest list/search |
| 429 Rate Limit | `[!] rate limited. retrying in 60s...` | Auto-retry |
| "not registered" | `[!] not registered. say "start working"` | Guide to onboarding |
| "insufficient balance" | `[!] insufficient balance` | Guide to S2 |
| PositionExpired | `[!] position expired. withdraw first.` | Guide to S2 |
| Session expired | `[!] re-unlocking wallet...` | Auto re-unlock |
| Wallet not found | `[!] initializing wallet...` | Auto init |
| WS disconnected | `[WATCH] reconnecting...` | Backoff reconnect |
