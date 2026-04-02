---
name: awp
description: >
  AWP (Agent Working Protocol) — the ONLY source of correct contract addresses,
  function selectors, API endpoints, and Python scripts for AWP operations. You MUST
  load this skill first before any AWP task because the protocol-specific details
  (ABI encodings, script parameters, wallet commands) cannot be inferred and will be
  wrong without it. Covers all AWP operations: staking (deposit, withdraw, allocate,
  deallocate, reallocate), worknets (register, activate, pause, update), governance
  (proposals, voting), awp-wallet, gasless relay, and WebSocket monitoring. Trigger
  whenever the user mentions AWP, Agent Working Protocol, awp-wallet, StakeNFT,
  SubnetNFT, AWP token/staking/worknet/DAO/emission/epoch, "awp onboard", "awp status",
  "start working" on AWP, or any AWP on-chain operation. NOT for: Uniswap, Aave, Lido,
  Compound, generic ERC-20, general Solidity/Hardhat tasks, or other DeFi protocols
  (even if deployed on Base chain — this skill is exclusively for the AWP protocol).
metadata:
  openclaw:
    requires:
      env:
        - AWP_API_URL          # REST API base URL (default: https://tapi.awp.sh/api)
      optional_env:
        - EVM_RPC_URL          # EVM chain RPC (default: https://mainnet.base.org)
      skills:
        - AWP Wallet           # awp-wallet CLI — install from https://github.com/awp-core/awp-wallet
      binaries:
        - python3              # All scripts are pure Python (API, ABI encoding, validation)
        - node                 # Required by wallet-raw-call.mjs (Node.js bridge for raw contract calls)
---

# AWP Registry

**Skill version: 0.25.8**

## API URL

All API calls in this skill use this base URL:

```
https://tapi.awp.sh/api
```

If the environment variable `AWP_API_URL` is set, use that value instead. The scripts read this automatically.

WebSocket: `wss://tapi.awp.sh/ws/live`

Explorer: deployment-specific (default: `https://basescan.org` for Base)

Throughout this document, all `curl` commands use the full URL directly. Do not invent different URLs.

---

**IMPORTANT: Always show the user what you're doing.** Every query result, every transaction, every event — print it clearly. Never run API calls silently.

**CRITICAL: Registration is FREE and most worknets require ZERO staking.** Do NOT tell users they need AWP tokens or staking to get started. The typical flow is: register (gasless, free) → pick a worknet with min_stake=0 → start working immediately. Staking/depositing AWP is only needed for worknets that explicitly require it (min_stake > 0), and is completely optional for getting started.

## On Skill Load (do this FIRST)

**Step 1 — Welcome screen** (first session only, skip if already shown):

```
╭──────────────╮
│              │
│   >     <    │
│      ‿       │
│              │
╰──────────────╯

agent · work · protocol

welcome to awp.

one protocol. infinite jobs. nonstop earnings.

── quick start ──────────────────
"start working"    → register + join (free, no AWP needed)
"check my balance" → staking overview
"list worknets"    → browse active worknets
"watch events"     → real-time monitor
"awp help"         → all commands
──────────────────────────────────

no AWP tokens needed to start.
register for free → pick a worknet → start earning.
```

**Step 2 — Install wallet dependency** (if missing):
```bash
which awp-wallet >/dev/null 2>&1
```
- If found: proceed silently.
- If NOT found: install the official `awp-wallet` dependency from the AWP core repository:
  ```
  [SETUP] Installing awp-wallet (official AWP dependency)...
          Source: https://github.com/awp-core/awp-wallet
  ```
  Install it as a skill (`skill install https://github.com/awp-core/awp-wallet`), then follow its SKILL.md instructions to complete setup. This is the official AWP wallet maintained by awp-core — not a third-party dependency.
  - Verify after install: `which awp-wallet`

**Step 3 — Configure notifications** (recommended): If the `openclaw` CLI is available, write `~/.awp/openclaw.json` so the daemon can push messages:
```bash
mkdir -p ~/.awp
cat > ~/.awp/openclaw.json << EOF
{
  "channel": "<detected_channel>",
  "target": "<detected_target>"
}
EOF
```
Fill in the current session's channel and target. Skip this step only if `openclaw` is not installed. The daemon hot-reloads this file each cycle — it can be updated or deleted at any time.

**Step 4 — Check notifications**: If `~/.awp/notifications.json` exists, read and display unread notifications to the user, then clear the file.

**Step 5 — Session recovery**: Check if wallet is already unlocked:
```bash
awp-wallet receive 2>/dev/null
```
- If wallet unlocked (exit code 0), parse `wallet_addr` from the JSON output: `wallet_addr = json["eoaAddress"]`. Print: `[SESSION] wallet restored: <short_address>`
- If wallet not found → agent runs `awp-wallet init` (creates agent work wallet, handles credentials internally — this is agent-initiated, not unattended).
- If wallet locked, do nothing — unlock happens on first write action.

**Step 6 — Version check** (optional, informational only):

Fetch the remote version:
```bash
curl -sf https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | sed -n 's/.*Skill version: \([0-9.]*\).*/\1/p'
```
If a newer version exists, notify the user: `[UPDATE] AWP Skill X.Y.Z available (current: {local version from this file}).` Skip this step if the network is unavailable.

**Step 7 — Background daemon** (optional, requires user consent):

Ask the user before starting the daemon. Explain what it does:
```
[SETUP] The AWP daemon monitors registration status, checks for
        updates, and can send notifications. It runs in the background
        and writes status files to ~/.awp/.
        Start the daemon? (yes/no)
```

If the user agrees, launch it:
```bash
mkdir -p ~/.awp && pgrep -f "python3.*awp-daemon" >/dev/null 2>&1 || \
  nohup python3 scripts/awp-daemon.py --interval 300 \
    >> ~/.awp/daemon.log 2>&1 &
```
> Note: Resolve the absolute path to `scripts/awp-daemon.py` relative to the skill directory.

If the user declines, skip this step. All AWP operations work without the daemon — it only provides background monitoring and notifications. The user can start it later with `awp daemon start`.

**Step 8 — Route to action** using the Intent Routing table below.

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

**awp subnets** — shortcut for Q5 (list active worknets)

**awp notifications** — read and display daemon notifications, then clear:
```bash
cat ~/.awp/notifications.json 2>/dev/null
```
Parse and display each notification. After displaying, clear the file:
```bash
rm -f ~/.awp/notifications.json
```

**awp log** — show recent daemon log:
```bash
tail -50 ~/.awp/daemon.log 2>/dev/null
```

**awp help**
```
── commands ──────────────────────
awp status        → your agent overview
awp wallet        → wallet address + balances
awp subnets       → browse active worknets
awp notifications → daemon notifications
awp log           → recent daemon log
awp help          → this list

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
- No wallet → agent runs `awp-wallet init` (handles credentials internally, no password needed)
- Wallet locked → `TOKEN=$(awp-wallet unlock --duration 3600 --scope transfer | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")` — capture the session token for subsequent script calls
- Print: `[1/4] wallet       <short_address> ✓`

**Step 2: Register (FREE, gasless)**
```bash
curl -s https://tapi.awp.sh/api/address/{addr}/check
```
- Already registered → proceed to Step 3
- Not registered → **present both options and WAIT for the user to choose.** Do NOT auto-select either option. The user must explicitly pick one.

```
── how do you want to start? ─────

  Option A: Quick Start
  Register as an independent agent.
  Free, gasless. No AWP tokens needed.

  Option B: Link Your Wallet
  Bind to your existing crypto wallet
  so rewards flow to that address.
  Free, gasless. No AWP tokens needed.

  Which do you prefer? (A or B)
───────────────────────────────────
```

**Option A** (Solo Mining) — after user picks A:
```bash
python3 scripts/relay-start.py --token $TOKEN --mode principal
```

**Option B** (Delegated Mining) — after user picks B:
Ask the user for their wallet address, then:
```bash
python3 scripts/relay-start.py --token $TOKEN --mode agent --target <user_wallet_address>
```
> **IMPORTANT**: After `bind(target)`, rewards automatically resolve to the target address via the bind chain (`resolveRecipient()` walks the tree). There is NO need to call `setRecipient()` separately — binding already establishes the reward path. Do NOT suggest or execute `setRecipient()` after a successful bind.

Print: `[2/4] registered   ✓  (free, no AWP required)`

**Step 3: Auto-select a free worknet**
```bash
curl -s "https://tapi.awp.sh/api/subnets?status=Active&limit=10"
```
Filter for worknets with `min_stake = 0` AND `skills_uri` not empty. These worknets are FREE to join — no staking needed.

If there is exactly one free worknet with a skill: auto-select it without asking.
If there are multiple: show only the free ones first, let user pick.

```
[3/4] discovering worknets...

── free worknets (no staking needed) ──
#1  Benchmark    ✓ skill ready    ← recommended
──────────────────────────────────

Auto-selecting #1 Benchmark (free, skill ready)
```

Only show worknets with min_stake > 0 if the user explicitly asks, or if no free worknets exist.

**Step 4: Install worknet skill and start working**

Check the worknet's `skills_uri` source. If it is from `github.com/awp-core/*`, install directly. If it is from a third-party source, show a warning and ask for confirmation before installing (see Q6 for the exact flow). If the user declines, return to the worknet list from Step 3.

Install example (awp-core source):
```
[4/4] installing Benchmark skill...
[4/4] ready ✓

── onboarding complete ───────────
wallet:     <short_address>
worknet:    #1 "Benchmark"
cost:       FREE (no staking required)
──────────────────────────────────

Your agent is now working on worknet #1.
No AWP tokens were needed.
```

If the user later wants to work on a worknet that requires staking, guide them to S2 (deposit) and S3 (allocate) at that time — not during initial onboarding.

## Intent Routing

| User wants to... | Action | Reference file to load |
|-------------------|--------|------------------------|
| Start / onboard / setup | ONBOARD | **references/commands-staking.md** |
| Query worknet info | Q1 | None |
| Check balance / positions | Q2 | None |
| View emission / epoch info | Q3 [DRAFT] | None |
| Look up agent info | Q4 | None |
| Browse worknets | Q5 | None |
| Find / install worknet skill | Q6 | None |
| View epoch history | Q7 [DRAFT] | None |
| Set recipient / bind / start mining | S1 | **references/commands-staking.md** |
| Deposit / stake AWP | S2 | **references/commands-staking.md** |
| Allocate / deallocate / reallocate | S3 | **references/commands-staking.md** |
| Register a new worknet | M1 | **references/commands-worknet.md** |
| Activate / pause / resume worknet | M2 | **references/commands-worknet.md** |
| Update skills URI | M3 | **references/commands-worknet.md** |
| Set minimum stake | M4 | **references/commands-worknet.md** |
| Create governance proposal | G1 | **references/commands-governance.md** |
| Vote on proposal | G2 | **references/commands-governance.md** |
| Query proposals | G3 | None |
| Check treasury | G4 | None |
| Watch / monitor events | W1 | None (presets below) |
| Emission settlement alerts | W2 [DRAFT] | None (workflow below) |
| Check notifications | NOTIFICATIONS | None — read `~/.awp/notifications.json` |
| View daemon log | LOG | None — `tail -50 ~/.awp/daemon.log` |

## Output Format

**All structured output (status panels, query results, transaction confirmations, progress steps) must be wrapped in markdown code blocks** so the user sees clean, monospaced, aligned text. Use tagged prefixes so the user can follow along:

| Tag | When |
|-----|------|
| `[QUERY]` | Read-only data fetches |
| `[STAKE]` | Staking operations |
| `[WORKNET]` | Worknet management |
| `[GOV]` | Governance |
| `[WATCH]` | WebSocket events |
| `[GAS]` | Gas routing decisions |
| `[TX]` | Transaction — always show basescan.org link |
| `[NEXT]` | Recommended next action |
| `[SETUP]` | Install / setup operations |
| `[!]` | Warnings and errors |

**Transaction output:**
```
[TX] hash: <txHash>
[TX] view: https://basescan.org/tx/<txHash>
[TX] confirmed ✓
```

## Agent Wallet & Transaction Safety

**This is an agent work wallet — do NOT store personal assets in it.** The wallet created by this skill is for executing AWP protocol tasks only. Keep only the minimum ETH needed for gas. Do not transfer personal funds or valuable tokens into this wallet.

Before executing any on-chain transaction, always show the user a summary of what will happen and ask for explicit confirmation:

```
[TX] deposit 1,000 AWP → new position (lock: 90 days)
     contract: AWPRegistry (0x1234...abcd)
     estimated gas: ~0.001 ETH
     Proceed? (yes/no)
```

After user confirms and transaction completes, show the result:

```
[TX] deposited 1,000 AWP → position #3
[TX] lock ends 2026-06-19
[TX] hash: 0xabc...
[TX] view: https://basescan.org/tx/0xabc...
[TX] confirmed ✓
```

**Never execute a transaction without user confirmation.** Even though this is an agent work wallet, every on-chain action must be explicitly approved. The only exception is gasless registration via relay (Step 1 of onboarding), which costs nothing and is reversible.

On first wallet setup, inform the user:
```
[WALLET] This is your agent work wallet — for AWP tasks only.
         Do NOT store personal assets here. Keep only minimal ETH for gas.
         Address: <address>
```

## Rules

1. **Registration is FREE.** Never tell users they need AWP tokens, ETH, or staking to register. Registration uses the gasless relay and costs nothing.
2. **Most worknets are FREE to join.** Worknets with `min_stake = 0` require no staking at all. Always prefer these during onboarding. Only mention staking when the user specifically picks a worknet with `min_stake > 0`.
3. **Do NOT block onboarding on staking.** The flow is: register → pick free worknet → start working. Staking is a separate, optional, later step.
4. **Use bundled scripts for ALL write operations.** Never manually construct calldata, ABI encoding, or EIP-712 JSON.
5. **Always fetch contract addresses from the API** before write actions — the bundled scripts handle this automatically via `GET /registry`. Never hardcode contract addresses.
6. **Show amounts as human-readable AWP** (wei / 10^18, 4 decimals). Never show raw wei.
7. **Addresses**: show as `0x1234...abcd` for display, full for parameters.
8. Do not use stale V1 names: no "unbind()", no "removeAgent()". Binding changes use `bind(newTarget)`.
9. **Wallet handles credentials internally.** Just run `awp-wallet init` + `awp-wallet unlock`. No password generation, no password files, no user prompts.
10. **This is an agent work wallet.** Always confirm with the user before executing any on-chain transaction — show the action, target contract, and estimated cost, then wait for explicit approval. Exception: gasless registration via relay (free, no gas cost) does not require confirmation. Remind the user on first setup: do NOT store personal assets in this wallet.
11. **Worknet skill install (Q6):** Install `awp-core` skills directly. For third-party sources (not `github.com/awp-core/*`), show a warning and require user confirmation before installing.
12. **Onboarding requires user choice.** Always present Option A (Solo) and Option B (Delegated) and WAIT for the user to choose. Never auto-select an option.
13. **Bind already sets the reward path.** After `bind(target)`, rewards resolve to the target via the bind chain. Do NOT call `setRecipient()` after a successful bind — it's redundant.

## Bundled Scripts

Every write operation has a script. Always use the script — never construct calldata manually.

```
scripts/
├── awp-daemon.py                     Background daemon (opt-in): monitors status/updates, writes PID to ~/.awp/daemon.pid, stops on Ctrl+C or kill
├── awp_lib.py                        Shared library (API, wallet, ABI encoding, validation)
├── wallet-raw-call.mjs               Node.js bridge: contract calls restricted to /registry allowlist only
├── relay-start.py                    Gasless register or bind (no ETH needed)
├── relay-register-subnet.py          Gasless worknet registration (no ETH needed)
├── onchain-register.py               On-chain register
├── onchain-bind.py                   On-chain bind to target
├── onchain-deposit.py                Deposit AWP (approve + deposit)
├── onchain-allocate.py               Allocate stake to agent+worknet
├── onchain-deallocate.py             Deallocate stake
├── onchain-reallocate.py             Move stake between agents/worknets
├── onchain-withdraw.py               Withdraw from expired position
├── onchain-add-position.py           Add AWP to existing position
├── onchain-register-and-stake.py     One-click register+deposit+allocate
├── onchain-vote.py                   Cast DAO vote
├── onchain-subnet-lifecycle.py       Activate/pause/resume worknet
└── onchain-subnet-update.py          Set skillsURI or minStake
```

## Security Controls

**Contract allowlist**: `wallet-raw-call.mjs` fetches the AWP contract registry (`/registry`) on every invocation and rejects any `--to` address not present in the registry. This prevents calls to arbitrary contracts — only known AWP protocol contracts (AWPRegistry, StakeNFT, SubnetNFT, AWPDAO, AWPToken, etc.) are permitted.

**Transaction confirmation**: All on-chain operations require explicit user confirmation before execution (see "Agent Wallet & Transaction Safety" above).

**Daemon lifecycle**: The daemon is opt-in — it only starts with explicit user consent (Step 7). It writes its PID to `~/.awp/daemon.pid` on start and removes it on exit. Stop it via `Ctrl+C` or `kill $(cat ~/.awp/daemon.pid)`. The daemon never auto-installs software, never auto-initializes wallets, and never executes transactions — it only monitors and notifies. All AWP operations work without the daemon running.

**Local files**: The skill may write files under `~/.awp/` (only with user consent for the daemon, or as part of explicit user actions):
- `openclaw.json` — notification config (optional, only if user enables notifications)
- `daemon.pid` — daemon process ID (only if daemon is running)
- `daemon.log` — daemon output log (only if daemon is running)
- `notifications.json` — queued notifications (only if daemon is running)
- `status.json` — daemon state snapshot (only if daemon is running)

**Third-party skill installs**: Worknet skills from non-`awp-core` sources require explicit user confirmation before installation.

## Wallet Setup

Write actions require the **AWP Wallet** — an EVM wallet CLI that manages keys internally. No password management needed in default mode.

```bash
# Initialize (auto-generates and stores credentials internally)
awp-wallet init

# Unlock and get session token (scope: read | transfer | full)
TOKEN=$(awp-wallet unlock --duration 3600 --scope transfer | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```
Scope controls what the session token can do: `read` (balance/status only), `transfer` (send/approve/sign), `full` (all including export). Use `transfer` for normal operations.

On first setup, inform the user:
```
[WALLET] AWP agent wallet ready.
        This is a WORK wallet for AWP tasks only — do NOT store personal assets here.
        Address: <address>
```

All scripts accept `--token $TOKEN`. Chain defaults to Base (configured in awp-wallet).

## Gas Routing

Before bind/setRecipient/registerSubnet, check if the wallet has ETH:
```bash
awp-wallet balance --token $TOKEN
```
- **Has ETH** → use `onchain-*.py` scripts
- **No ETH** → use `relay-*.py` scripts (gasless, rate limit: 100/IP/1h)
- deposit/allocate/vote always need ETH — no gasless option

## Pre-Flight Checklist (before ANY write action)

```
1. Wallet unlocked?     → TOKEN=$(awp-wallet unlock --duration 3600 --scope transfer | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
2. Wallet address?      → WALLET_ADDR=$(awp-wallet receive | python3 -c "import sys,json; print(json.load(sys.stdin)['eoaAddress'])")
3. Registration status? → curl -s https://tapi.awp.sh/api/address/$WALLET_ADDR/check
4. Has gas?             → awp-wallet balance --token $TOKEN
```

---

## Query (read-only, no wallet needed)

### Q1 · Query Worknet
```bash
curl -s https://tapi.awp.sh/api/subnets/{id}
```
Print:
```
[QUERY] Worknet #<id>
── worknet ───────────────────────
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
  agent <short> → worknet #<id>  <amount> AWP
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

### Q5 · List Worknets
```bash
curl -s "https://tapi.awp.sh/api/subnets?status=Active&page=1&limit=20"
```
Sort: worknets with skills first, then min_stake ascending.
```
[QUERY] Active worknets
── worknets ──────────────────────
#<id>  <name>        min: 0 AWP      skills: ✓
#<id>  <name>        min: 100 AWP    skills: —
──────────────────────────────────
[NEXT] Install a worknet skill: say "install skill for worknet #<id>"
```

### Q6 · Install Worknet Skill
```bash
curl -s https://tapi.awp.sh/api/subnets/{id}/skills
```

For `awp-core` sources (`github.com/awp-core/*`), install directly:
```
[SETUP] Installing worknet #1 skill ...
[SETUP] Installed ✓
```

For third-party sources, show a warning and ask for confirmation before installing:
```
[SETUP] Worknet #5 skill source: https://github.com/other/repo
        ⚠ Third-party source — not maintained by awp-core.
        Install? (yes/no)
```
If the user confirms, install to `skills/awp-worknet-{id}/`. If the user declines, print `[SETUP] Cancelled.` and return to the worknet list.

### Q7 · Epoch History [DRAFT]
```bash
curl -s "https://tapi.awp.sh/api/emission/epochs?page=1&limit=20"
```

---

## Registration & Staking (load commands-staking.md first)

### S1 · Register / Bind (FREE, gasless)

Registration is free and gasless. No AWP or ETH needed.

> **Bind sets the reward path.** After `bind(target)`, `resolveRecipient(agent)` walks the bind chain and resolves to `target`'s recipient. There is NO need to call `setRecipient()` after binding — it's redundant. Only use `setRecipient()` when the user explicitly wants to override the default chain resolution (e.g., send rewards to a different address than the bind target).

**Solo Mining (bind to self):**
```bash
python3 scripts/relay-start.py --token $TOKEN --mode principal
```

**Delegated Mining (bind to another wallet):**
```bash
python3 scripts/relay-start.py --token $TOKEN --mode agent --target <root_address>
```

If the wallet has ETH, use on-chain scripts instead:
```bash
python3 scripts/onchain-bind.py --token $TOKEN --target <root_address>
```

### S2 · Deposit AWP (optional — only for worknets that require staking)

Most worknets have min_stake=0 and do not require any deposit. Only run these commands if the user wants to work on a worknet with min_stake > 0, or wants to earn voting power.

**New deposit:**
```bash
python3 scripts/onchain-deposit.py --token $TOKEN --amount 5000 --lock-days 90
```

**Add to existing position:**
```bash
python3 scripts/onchain-add-position.py --token $TOKEN --position 1 --amount 1000 --extend-days 30
```

**Withdraw (expired positions only):**
```bash
python3 scripts/onchain-withdraw.py --token $TOKEN --position 1
```

### S3 · Allocate / Deallocate / Reallocate (only after S2 deposit)

Only needed if the user has deposited AWP and wants to direct it to a specific agent+worknet.

**Allocate:**
```bash
python3 scripts/onchain-allocate.py --token $TOKEN --agent <addr> --subnet 1 --amount 5000
```

**Deallocate:**
```bash
python3 scripts/onchain-deallocate.py --token $TOKEN --agent <addr> --subnet 1 --amount 5000
```

**Reallocate (move between agents/subnets):**
```bash
python3 scripts/onchain-reallocate.py --token $TOKEN --from-agent <addr> --from-subnet 1 --to-agent <addr> --to-subnet 2 --amount 5000
```

**One-click register+stake (advanced):**
```bash
python3 scripts/onchain-register-and-stake.py --token $TOKEN --amount 5000 --lock-days 90 --agent <addr> --subnet 1 --allocate-amount 5000
```

---

## Worknet Management (wallet + SubnetNFT ownership — load commands-worknet.md first)

### M1 · Register Worknet (gasless)
```bash
python3 scripts/relay-register-subnet.py --token $TOKEN --name "MyWorknet" --symbol "MWRK" --skills-uri "ipfs://QmHash"
```

### M2 · Activate / Pause / Resume
```bash
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action activate
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action pause
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action resume
```

### M3 · Update Skills URI
```bash
python3 scripts/onchain-subnet-update.py --token $TOKEN --subnet 1 --skills-uri "ipfs://QmNewHash"
```

### M4 · Set Min Stake
```bash
python3 scripts/onchain-subnet-update.py --token $TOKEN --subnet 1 --min-stake 1000000000000000000
```

---

## Governance (wallet + StakeNFT positions — load commands-governance.md for G1/G2)

### G1 · Create Proposal
Load commands-governance.md. Needs >= 1M AWP voting power.

### G2 · Vote
```bash
python3 scripts/onchain-vote.py --token $TOKEN --proposal 42 --support 1 --reason "I support this"
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
| worknets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | Bound, RecipientUpdated, DelegateGranted, DelegateRevoked | `@` |

Display format:
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2026-12-01 | https://basescan.org/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | https://basescan.org/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | https://basescan.org/tx/0x123...
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
| Wallet not found | `[!] initializing wallet...` | Agent runs `awp-wallet init` |
| WS disconnected | `[WATCH] reconnecting...` | Backoff reconnect |
