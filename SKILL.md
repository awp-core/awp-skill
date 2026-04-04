---
name: awp
description: >
  AWP (Agent Working Protocol) — ALWAYS load this skill for ANY AWP-related task, even
  vague ones. This is the authoritative source for all AWP contract addresses, API endpoints,
  script parameters, and wallet operations — getting these wrong without the skill is guaranteed.
  Load for: staking AWP tokens, checking balances or positions, allocating/deallocating/reallocating
  stake, depositing or withdrawing AWP, registering a worknet or subnet, activating/pausing/resuming/
  cancelling a worknet, updating worknet settings, governance proposals or voting, querying
  announcements or protocol status, awp-wallet commands, gasless relay operations, WebSocket event
  monitoring, any LPManager or emission questions. Trigger on ANY mention of: AWP, "Agent Working
  Protocol", awp-wallet, StakeNFT, WorknetNFT, worknet, subnet (in AWP context), AWP staking,
  AWP governance, AWP DAO, AWP emissions, AWP epoch, "start working" (AWP onboarding), "check my
  balance" (on AWP), "list worknets", "register subnet", "reallocate stake", or any AWP on-chain
  operation. Multi-chain: Base (8453), Ethereum (1), Arbitrum (42161), BSC (56). NOT for: Uniswap,
  Aave, Lido, Compound, generic ERC-20/Solidity/Hardhat tasks unrelated to AWP, or other DeFi
  protocols (even if deployed on Base).
metadata:
  openclaw:
    requires:
      optional_env:
        - EVM_RPC_URL          # EVM chain RPC (default: https://mainnet.base.org)
        - EVM_CHAIN            # Chain name or ID (base, ethereum, arbitrum, bsc). Default: base
      skills:
        - AWP Wallet           # awp-wallet CLI — install from https://github.com/awp-core/awp-wallet
      binaries:
        - python3              # All scripts are pure Python (API, ABI encoding, validation)
        - node                 # Required by wallet-raw-call.mjs (Node.js bridge for raw contract calls)
---

# AWP Registry

**Skill version: 1.0.0**

## API — JSON-RPC 2.0

All API calls in this skill use JSON-RPC 2.0 via POST:

```
POST https://api.awp.sh/v2
Content-Type: application/json
```

Request: `{"jsonrpc":"2.0","method":"namespace.method","params":{...},"id":1}`
Discovery: `GET https://api.awp.sh/v2` | WebSocket: `wss://api.awp.sh/ws/live` | Batch: up to 20 per request.

Explorers: Base → `basescan.org` | Ethereum → `etherscan.io` | Arbitrum → `arbiscan.io` | BSC → `bscscan.com`

Throughout this document, all `curl` commands use JSON-RPC POST to `https://api.awp.sh/v2`. Do not use REST-style GET paths.

### API Method Reference

#### System

| Method | Params | Description |
|--------|--------|-------------|
| `stats.global` | none | Global protocol stats: total users, worknets, staked AWP, emitted AWP, active chains |
| `registry.get` | `chainId?` | All contract addresses + EIP-712 domain info. Omit chainId for array of all 4 chains. |
| `health.check` | none | Returns `{"status": "ok"}` if API is running |
| `health.detailed` | none | Per-chain health: indexer sync block, keeper status, RPC latency |
| `chains.list` | none | Array of `{chainId, name, status, explorer}` for all supported chains |

#### Users

| Method | Params | Description |
|--------|--------|-------------|
| `users.list` | `chainId?`, `page?`, `limit?` | Paginated user list for one chain |
| `users.listGlobal` | `page?`, `limit?` | Cross-chain deduplicated user list |
| `users.count` | `chainId?` | Total registered user count |
| `users.get` | `address` **(required)**, `chainId?` | User details: balance, bound agents, recipient, registration status |
| `users.getPortfolio` | `address` **(required)**, `chainId?` | Complete portfolio: identity + staking + NFT positions + allocations + delegates |
| `users.getDelegates` | `address` **(required)**, `chainId?` | List of addresses this user has authorized as delegates |

#### Address & Nonce

| Method | Params | Description |
|--------|--------|-------------|
| `address.check` | `address` **(required)**, `chainId?` | Check registration status, binding, recipient. See response format below. |
| `address.resolveRecipient` | `address` **(required)**, `chainId?` | Walk bind chain to root, return effective reward recipient |
| `address.batchResolveRecipients` | `addresses[]` **(required, max 500)**, `chainId?` | Batch resolve effective recipients (on-chain call) |
| `nonce.get` | `address` **(required)**, `chainId?` | AWPRegistry EIP-712 nonce (for bind/unbind/setRecipient/registerWorknet/activateWorknet/grantDelegate/revokeDelegate) |
| `nonce.getStaking` | `address` **(required)**, `chainId?` | StakingVault EIP-712 nonce (for allocate/deallocate) |

#### Agents

| Method | Params | Description |
|--------|--------|-------------|
| `agents.getByOwner` | `owner` **(required)**, `chainId?` | All agents (addresses) that have bound to this owner |
| `agents.getDetail` | `agent` **(required)**, `chainId?` | Agent details: owner, binding chain, delegated status |
| `agents.lookup` | `agent` **(required)**, `chainId?` | Quick lookup: returns `{"ownerAddress": "0x..."}` |
| `agents.batchInfo` | `agents[]` **(required, max 100)**, `worknetId` **(required)**, `chainId?` | Batch query: agent info + their stake in specified worknet |

#### Staking

| Method | Params | Description |
|--------|--------|-------------|
| `staking.getBalance` | `address` **(required)**, `chainId?` | Returns `{totalStaked, totalAllocated, unallocated}` in wei strings |
| `staking.getUserBalanceGlobal` | `address` **(required)** | Same as above but aggregated across ALL chains |
| `staking.getPositions` | `address` **(required)**, `chainId?` | Array of StakeNFT positions: `{tokenId, amount, lockEndTime, createdAt}` |
| `staking.getPositionsGlobal` | `address` **(required)** | Positions across all chains (includes chainId per position) |
| `staking.getAllocations` | `address` **(required)**, `chainId?`, `page?`, `limit?` | Paginated allocation records: `{agent, worknetId, amount}` |
| `staking.getFrozen` | `address` **(required)**, `chainId?` | Frozen allocations (from banned worknets) |
| `staking.getAgentSubnetStake` | `agent` **(required)**, `worknetId` **(required)** | Agent's total allocated stake in a specific worknet (cross-chain) |
| `staking.getAgentSubnets` | `agent` **(required)** | All worknetIds where this agent has non-zero allocations |
| `staking.getSubnetTotalStake` | `worknetId` **(required)** | Total AWP staked across all agents in a worknet |

#### Worknets

| Method | Params | Description |
|--------|--------|-------------|
| `subnets.list` | `status?`, `chainId?`, `page?`, `limit?` | List worknets. Filter by status: `Pending`, `Active`, `Paused`, `Banned` |
| `subnets.listRanked` | `chainId?`, `page?`, `limit?` | Worknets ranked by total stake (highest first) |
| `subnets.search` | `query` **(required, 1-100 chars)**, `chainId?`, `page?`, `limit?` | Search by name or symbol (case-insensitive) |
| `subnets.getByOwner` | `owner` **(required)**, `chainId?`, `page?`, `limit?` | Worknets owned by address |
| `subnets.get` | `worknetId` **(required)** | Full worknet details: name, symbol, status, alphaToken, LP pool, owner, stakes |
| `subnets.getSkills` | `worknetId` **(required)** | Skills URI (off-chain metadata describing the worknet's capabilities) |
| `subnets.getEarnings` | `worknetId` **(required)**, `page?`, `limit?` | Paginated AWP earnings history by epoch |
| `subnets.getAgentInfo` | `worknetId` **(required)**, `agent` **(required)** | Agent's info within a specific worknet: stake, validity, reward recipient |
| `subnets.listAgents` | `worknetId` **(required)**, `chainId?`, `page?`, `limit?` | Agents in worknet ranked by stake |

#### Emission

| Method | Params | Description |
|--------|--------|-------------|
| `emission.getCurrent` | `chainId?` | Current epoch number, daily emission amount, total weight, settled epoch |
| `emission.getSchedule` | `chainId?` | Emission projections: 30-day, 90-day, 365-day cumulative with decay applied |
| `emission.getGlobalSchedule` | none | Same projections but aggregated across all 4 chains |
| `emission.listEpochs` | `chainId?`, `page?`, `limit?` | Paginated list of settled epochs with emission totals |
| `emission.getEpochDetail` | `epochId` **(required)**, `chainId?` | Detailed breakdown: per-recipient AWP distributions for a specific epoch |

#### Tokens

| Method | Params | Description |
|--------|--------|-------------|
| `tokens.getAWP` | `chainId?` | AWP token info: totalSupply, maxSupply, circulatingSupply (per chain) |
| `tokens.getAWPGlobal` | none | AWP info aggregated across all chains |
| `tokens.getAlphaInfo` | `worknetId` **(required)** | Alpha token info: address, name, symbol, totalSupply, minter |
| `tokens.getAlphaPrice` | `worknetId` **(required)** | Alpha/AWP price from LP pool (cached 10min). Returns sqrtPriceX96 and human-readable price. |

#### Governance

| Method | Params | Description |
|--------|--------|-------------|
| `governance.listProposals` | `status?`, `chainId?`, `page?`, `limit?` | List proposals. Status: `Active`/`Canceled`/`Defeated`/`Succeeded`/`Queued`/`Expired`/`Executed` |
| `governance.listAllProposals` | `status?`, `page?`, `limit?` | Cross-chain proposal list |
| `governance.getProposal` | `proposalId` **(required)**, `chainId?` | Proposal details: description, votes, state, targets, calldatas |
| `governance.getTreasury` | none | Returns treasury contract address |

---

**IMPORTANT: Always show the user what you're doing.** Every query result, every transaction, every event — print it clearly. Never run API calls silently.

**CRITICAL: Registration is FREE and most worknets require ZERO staking.** Do NOT tell users they need AWP tokens or staking to get started. The typical flow is: register (gasless, free) → pick a worknet with min_stake=0 → start working immediately. Staking/depositing AWP is only needed for worknets that explicitly require it (min_stake > 0), and is completely optional for getting started.

## Contract Addresses (same on all 4 chains)

```
AWPToken:           0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1
AWPRegistry:        0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A
AWPEmission:        0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9
StakingVault:       0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b
StakeNFT:           0x4E119560632698Bab67cFAB5d8EC0A373363ba2d
WorknetNFT:         0xB9F03539BE496d09c4d7964921d674B8763f5233
LPManager (proxy):  0x00001961b9AcCD86b72DE19Be24FaD6f7c5b00A2
AlphaTokenFactory:  0xB2e4897eD77d0f5BFa3140B9989594de09a8037c
Treasury:           0x82562023a053025F3201785160CaE6051efD759e
AWPDAO:             0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004
```

Supported chains: Base (8453), Ethereum (1), Arbitrum (42161), BSC (56). All addresses identical across all 4 chains (except LPManager and WorknetManager impls which differ per DEX).

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
- If NOT found: `skill install https://github.com/awp-core/awp-wallet`, then follow its SKILL.md. Verify: `which awp-wallet`

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

Ask: `[SETUP] Start the AWP daemon? It monitors status and sends notifications. (yes/no)`

If yes:
```bash
mkdir -p ~/.awp && pgrep -f "python3.*awp-daemon" >/dev/null 2>&1 || \
  nohup python3 scripts/awp-daemon.py --interval 300 >> ~/.awp/daemon.log 2>&1 &
```
Resolve the absolute path to `scripts/awp-daemon.py` relative to the skill directory. If declined, skip. The user can start later with `awp daemon start`.

**Step 8 — Route to action** using the Intent Routing table below.

## User Commands

The user may type these at any time:

**awp status** — fetch via JSON-RPC batch:
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '[
    {"jsonrpc":"2.0","method":"address.check","params":{"address":"'$WALLET_ADDR'"},"id":1},
    {"jsonrpc":"2.0","method":"staking.getBalance","params":{"address":"'$WALLET_ADDR'"},"id":2},
    {"jsonrpc":"2.0","method":"staking.getPositions","params":{"address":"'$WALLET_ADDR'"},"id":3},
    {"jsonrpc":"2.0","method":"staking.getAllocations","params":{"address":"'$WALLET_ADDR'"},"id":4}
  ]'
```
```
── my agent ──────────────────────
address:        <short_address>
status:         <registered/unregistered>
role:           <solo / delegated agent / —>
chain:          <current chain>
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
chains:     Base · Ethereum · Arbitrum · BSC
ETH:        <balance>
AWP:        <balance>
──────────────────────────────────
```

**awp announcements** — fetch and display protocol announcements:
```bash
curl -s https://api.awp.sh/api/announcements/llm-context
```
Display each announcement with its category, priority, and timestamp.

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

**awp daemon start** — start the background daemon (with user consent):
```bash
mkdir -p ~/.awp && pgrep -f "python3.*awp-daemon" >/dev/null 2>&1 || \
  nohup python3 scripts/awp-daemon.py --interval 300 \
    >> ~/.awp/daemon.log 2>&1 &
```

**awp daemon stop** — stop the background daemon:
```bash
kill $(cat ~/.awp/daemon.pid 2>/dev/null) 2>/dev/null && rm -f ~/.awp/daemon.pid
```

**awp help**
```
── commands ──────────────────────
awp status        → your agent overview
awp wallet        → wallet address + balances
awp subnets       → browse active worknets
awp notifications → daemon notifications
awp log           → recent daemon log
awp daemon start  → start background daemon
awp daemon stop   → stop background daemon
awp announcements → protocol announcements
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
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"address.check","params":{"address":"'$WALLET_ADDR'"},"id":1}'
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
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"subnets.list","params":{"status":"Active","limit":10},"id":1}'
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
| View emission / epoch info | Q3 | None |
| Look up agent info | Q4 | None |
| Browse worknets | Q5 | None |
| Find / install worknet skill | Q6 | None |
| View epoch history | Q7 | None |
| Search worknets by name | Q8 | None |
| View ranked worknets | Q9 | None |
| Portfolio overview | Q10 | None |
| Cross-chain balance | Q11 | None |
| Global stats | Q12 | None |
| Set recipient / bind / unbind / start mining | S1 | **references/commands-staking.md** |
| Deposit / stake AWP | S2 | **references/commands-staking.md** |
| Allocate / deallocate / reallocate | S3 | **references/commands-staking.md** |
| Register a new worknet | M1 | **references/commands-subnet.md** |
| Activate / pause / resume worknet | M2 | **references/commands-subnet.md** |
| Update skills URI | M3 | **references/commands-subnet.md** |
| Set minimum stake | M4 | **references/commands-subnet.md** |
| Create governance proposal | G1 | **references/commands-governance.md** |
| Vote on proposal | G2 | **references/commands-governance.md** |
| Query proposals | G3 | None |
| Check treasury | G4 | None |
| Watch / monitor events | W1 | None (presets below) |
| Emission settlement alerts | W2 | None (workflow below) |
| Check announcements | ANNOUNCEMENTS | None |
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
| `[TX]` | Transaction — always show chain-appropriate explorer link |
| `[NEXT]` | Recommended next action |
| `[SETUP]` | Install / setup operations |
| `[!]` | Warnings and errors |

**Transaction output** (use chain-appropriate explorer):
```
[TX] hash: <txHash>
[TX] view: https://basescan.org/tx/<txHash>
[TX] confirmed ✓
```

## Agent Wallet & Transaction Safety

**This is an agent work wallet — do NOT store personal assets in it.** The wallet created by this skill is for executing AWP protocol tasks only. Keep only the minimum ETH needed for gas. Do not transfer personal funds or valuable tokens into this wallet.

Before executing any on-chain transaction, show a summary and ask for explicit confirmation:
```
[TX] deposit 1,000 AWP → new position (lock: 90 days)
     contract: StakeNFT (0x4E11...ba2d) | chain: Base (8453) | gas: ~0.001 ETH
     Proceed? (yes/no)
```
After confirmation and completion:
```
[TX] deposited 1,000 AWP → position #3 | lock ends 2026-06-19
[TX] hash: 0xabc... | https://basescan.org/tx/0xabc... | confirmed ✓
```

**Never execute a transaction without user confirmation.** Exception: gasless registration via relay (free, reversible).

## Rules

1. **Registration is FREE.** Never tell users they need AWP tokens, ETH, or staking to register. Registration uses the gasless relay and costs nothing.
2. **Most worknets are FREE to join.** Worknets with `min_stake = 0` require no staking at all. Always prefer these during onboarding. Only mention staking when the user specifically picks a worknet with `min_stake > 0`.
3. **Do NOT block onboarding on staking.** The flow is: register → pick free worknet → start working. Staking is a separate, optional, later step.
4. **Use bundled scripts for ALL write operations.** Never manually construct calldata, ABI encoding, or EIP-712 JSON.
5. **Always fetch contract addresses from the API** before write actions — the bundled scripts handle this automatically via `registry.get`. Never hardcode contract addresses.
6. **Show amounts as human-readable AWP** (wei / 10^18, 4 decimals). Never show raw wei.
7. **Addresses**: show as `0x1234...abcd` for display, full for parameters.
8. Do not use stale V1 names: no `removeAgent()`. Binding changes use `bind(newTarget)` or `unbind()`.
9. **Wallet handles credentials internally.** Just run `awp-wallet init` + `awp-wallet unlock`. No password generation, no password files, no user prompts.
10. **This is an agent work wallet.** Always confirm with the user before executing any on-chain transaction — show the action, target contract, chain, and estimated cost, then wait for explicit approval. Exception: gasless registration via relay (free, no gas cost) does not require confirmation. Remind the user on first setup: do NOT store personal assets in this wallet.
11. **Worknet skill install (Q6):** Install `awp-core` skills directly. For third-party sources (not `github.com/awp-core/*`), show a warning and require user confirmation before installing.
12. **Onboarding requires user choice.** Always present Option A (Solo) and Option B (Delegated) and WAIT for the user to choose. Never auto-select an option.
13. **Bind already sets the reward path.** After `bind(target)`, rewards resolve to the target via the bind chain. Do NOT call `setRecipient()` after a successful bind — it's redundant.
14. **Multi-chain awareness.** Use chain-appropriate explorer links. Include `chainId` in API params when the user specifies a chain. Default to Base (8453) when unspecified.

## Bundled Scripts

Every write operation has a script. Always use the script — never construct calldata manually.

```
scripts/
├── awp-daemon.py                     Background daemon (opt-in): monitors status/updates, writes PID to ~/.awp/daemon.pid, stops on Ctrl+C or kill
├── awp_lib.py                        Shared library (API, wallet, ABI encoding, validation)
├── wallet-raw-call.mjs               Node.js bridge: contract calls restricted to /registry allowlist only
├── relay-start.py                    Gasless register or bind: --mode principal (solo) | --mode agent --target <addr> (delegated)
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

**Contract allowlist**: `wallet-raw-call.mjs` fetches the AWP contract registry (`registry.get`) on every invocation and rejects any `--to` address not present in the registry. This prevents calls to arbitrary contracts — only known AWP protocol contracts (AWPRegistry, StakeNFT, WorknetNFT, StakingVault, AWPDAO, AWPToken, etc.) are permitted.

**Transaction confirmation**: All on-chain operations require explicit user confirmation before execution.

**Daemon lifecycle**: Opt-in only (Step 7). PID in `~/.awp/daemon.pid`. Stop via `kill $(cat ~/.awp/daemon.pid)`. Never auto-installs, never executes transactions — only monitors and notifies.

**Local files** (`~/.awp/`): `openclaw.json`, `daemon.pid`, `daemon.log`, `notifications.json`, `status.json` — all written only with user consent or explicit actions.

**Third-party skill installs**: Worknet skills from non-`awp-core` sources require explicit user confirmation.

## Vanity Salt Endpoints

For offline mining of vanity Alpha token CREATE2 addresses:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/vanity/mining-params` | GET | Returns `{factoryAddress, initCodeHash, vanityRule}` needed for offline salt mining |
| `POST /api/vanity/upload-salts` | POST | Upload pre-mined `{salts: [{salt, address}, ...]}`. Rate limited: 5/hr/IP |
| `GET /api/vanity/salts/count` | GET | Number of available (unused) salts in the pool |
| `POST /api/vanity/compute-salt` | POST | Server-side computation. Returns `{salt, address, source: "pool"\|"mined", elapsed}` |

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

Before bind/unbind/setRecipient/registerWorknet, check if the wallet has ETH:
```bash
awp-wallet balance --token $TOKEN
```
- **Has ETH** → use `onchain-*.py` scripts
- **No ETH** → use `relay-*.py` scripts (gasless, rate limit: 100/IP/1h)
- deposit/vote/cancelWorknet always need ETH — no gasless option

Gasless relay endpoints (REST, NOT JSON-RPC): `POST https://api.awp.sh/api/relay/*`

| Endpoint | Description | EIP-712 Domain |
|----------|-------------|----------------|
| `POST /api/relay/register` | Register (= setRecipient to self) | AWPRegistry |
| `POST /api/relay/bind` | Bind agent to target | AWPRegistry |
| `POST /api/relay/unbind` | Unbind from tree | AWPRegistry |
| `POST /api/relay/set-recipient` | Set reward recipient | AWPRegistry |
| `POST /api/relay/grant-delegate` | Authorize a delegate | AWPRegistry |
| `POST /api/relay/revoke-delegate` | Revoke a delegate | AWPRegistry |
| `POST /api/relay/activate-subnet` | Activate a pending worknet | AWPRegistry |
| `POST /api/relay/register-subnet` | Register worknet (with AWP permit) | AWPRegistry |
| `POST /api/relay/allocate` | Allocate stake to agent | StakingVault |
| `POST /api/relay/deallocate` | Deallocate stake | StakingVault |
| `GET /api/relay/status/{txHash}` | Check relay tx status | -- |

Relay request format uses **v, r, s** signature components (not a combined signature hex):
```json
{
  "chainId": 8453,
  "user": "0xUserAddress...",
  "deadline": 1712345678,
  "v": 27,
  "r": "0x...(32 bytes hex)...",
  "s": "0x...(32 bytes hex)..."
}
```
Response: `{"txHash": "0x..."}` | Error: `{"error": "invalid EIP-712 signature"}`

### EIP-712 Domains

**AWPRegistry domain** (bind, unbind, setRecipient, grantDelegate, revokeDelegate, registerWorknet, activateWorknet):
```json
{"name": "AWPRegistry", "version": "1", "chainId": 8453, "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"}
```

**StakingVault domain** (allocate, deallocate):
```json
{"name": "StakingVault", "version": "1", "chainId": 8453, "verifyingContract": "0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b"}
```

### EIP-712 Type Definitions

```
Bind(address agent, address target, uint256 nonce, uint256 deadline)
Unbind(address user, uint256 nonce, uint256 deadline)
SetRecipient(address user, address recipient, uint256 nonce, uint256 deadline)
GrantDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
RevokeDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
ActivateWorknet(address user, uint256 worknetId, uint256 nonce, uint256 deadline)
RegisterWorknet(address user, WorknetParams params, uint256 nonce, uint256 deadline)
  WorknetParams(string name, string symbol, address worknetManager, bytes32 salt, uint128 minStake, string skillsURI)
Allocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
Deallocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
```

**Nonce workflow**: Always fetch the current nonce via `nonce.get` (AWPRegistry) or `nonce.getStaking` (StakingVault) immediately before signing. Nonces auto-increment after each successful relay. Using a stale nonce causes `InvalidSignature` error.

## Pre-Flight Checklist (before ANY write action)

```
1. Wallet unlocked?     → TOKEN=$(awp-wallet unlock --duration 3600 --scope transfer | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
2. Wallet address?      → WALLET_ADDR=$(awp-wallet receive | python3 -c "import sys,json; print(json.load(sys.stdin)['eoaAddress'])")
3. Registration status? → curl -s -X POST https://api.awp.sh/v2 -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"address.check","params":{"address":"'$WALLET_ADDR'"},"id":1}'
4. Has gas?             → awp-wallet balance --token $TOKEN
```

### `address.check` Response Format

With `chainId` specified → single-chain result:
```json
{"isRegistered": true, "boundTo": "0x...", "recipient": "0x..."}
```
- `isRegistered`: true if user has called `register()`, `setRecipient()`, or `bind()` on this chain
- `boundTo`: address this user is bound to (empty string if not bound)
- `recipient`: reward recipient address (empty string if not set; defaults to self)

Without `chainId` (omit) → all chains where registered:
```json
{
  "isRegistered": true,
  "chains": [
    {"chainId": 1, "isRegistered": true, "recipient": "0x..."},
    {"chainId": 8453, "isRegistered": true, "boundTo": "0x...", "recipient": "0x..."}
  ]
}
```
- `isRegistered`: true if registered on ANY chain
- `chains`: array of per-chain registration info (only chains where user is registered)

---

## Query (read-only, no wallet needed)

### Q1 · Query Worknet
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"subnets.get","params":{"worknetId":"ID"},"id":1}'
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
chain:          <chain name>
──────────────────────────────────
```

### Q2 · Query Balance
Fetch via JSON-RPC batch:
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '[
    {"jsonrpc":"2.0","method":"staking.getBalance","params":{"address":"ADDR"},"id":1},
    {"jsonrpc":"2.0","method":"staking.getPositions","params":{"address":"ADDR"},"id":2},
    {"jsonrpc":"2.0","method":"staking.getAllocations","params":{"address":"ADDR"},"id":3}
  ]'
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

### Q3 · Query Emission
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '[
    {"jsonrpc":"2.0","method":"emission.getCurrent","params":{},"id":1},
    {"jsonrpc":"2.0","method":"emission.getSchedule","params":{},"id":2}
  ]'
```
Print:
```
[QUERY] Emission
── emission ──────────────────────
epoch:          <number>
daily rate:     31,600,000 AWP (per chain)
decay:          ~0.3156% per epoch
──────────────────────────────────
```

### Q4 · Query Agent
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"subnets.getAgentInfo","params":{"worknetId":"ID","agent":"0x..."},"id":1}'
```

### Q5 · List Worknets
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"subnets.list","params":{"status":"Active","page":1,"limit":20},"id":1}'
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
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"subnets.getSkills","params":{"worknetId":"ID"},"id":1}'
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
If the user confirms, install to `skills/awp-subnet-{id}/`. If the user declines, print `[SETUP] Cancelled.` and return to the worknet list.

### Q7 · Epoch History
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"emission.listEpochs","params":{"page":1,"limit":20},"id":1}'
```

### Q8–Q12 · Additional Queries

| Query | Method | Key Params |
|-------|--------|------------|
| **Q8** Search worknets | `subnets.search` | `{"query":"NAME"}` |
| **Q9** Ranked worknets | `subnets.listRanked` | `{"page":1,"limit":20}` |
| **Q10** Portfolio overview | `users.getPortfolio` | `{"address":"ADDR"}` |
| **Q11** Cross-chain balance | `staking.getUserBalanceGlobal` | `{"address":"ADDR"}` |
| **Q11b** Cross-chain positions | `staking.getPositionsGlobal` | `{"address":"ADDR"}` |
| **Q12** Global stats | `stats.global` | `{}` |

Additional cross-chain methods: `tokens.getAWPGlobal`, `emission.getGlobalSchedule`, `health.detailed`.

All use the same JSON-RPC format: `POST https://api.awp.sh/v2` with `{"jsonrpc":"2.0","method":"...","params":{...},"id":1}`.

### Q13 · Announcements
Protocol announcements via REST (not JSON-RPC):
```bash
# List active announcements
curl -s https://api.awp.sh/api/announcements

# LLM-friendly format
curl -s https://api.awp.sh/api/announcements/llm-context

# Filter by chain or category
curl -s "https://api.awp.sh/api/announcements?chainId=8453&category=emission"
```
Announcement Object:
```json
{
  "id": 1,
  "chainId": 0,
  "title": "Emission schedule update",
  "content": "Daily emission reduced to 31.6M AWP per chain starting epoch 5.",
  "category": "emission",
  "priority": 1,
  "active": true,
  "createdAt": "2026-04-02T00:00:00Z",
  "expiresAt": "2026-04-10T00:00:00Z",
  "metadata": {"epochId": 5, "newEmission": "31600000"}
}
```

| Field | Type | Description |
|-------|------|-------------|
| `chainId` | integer | 0 = applies to all chains; otherwise specific chainId |
| `category` | string | `general`, `maintenance`, `governance`, `emission`, `security` |
| `priority` | integer | 0 = info, 1 = warning, 2 = critical |
| `expiresAt` | string/null | ISO 8601 timestamp; null = never expires |
| `metadata` | object/null | Arbitrary JSON for structured data |

---

## Registration & Staking (load commands-staking.md first)

### S1 · Register / Bind / Unbind (FREE, gasless)

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

**Unbind (detach from current target):**
```bash
python3 scripts/onchain-bind.py --token $TOKEN --unbind
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

**Reallocate (move between agents/worknets):**
```bash
python3 scripts/onchain-reallocate.py --token $TOKEN --from-agent <addr> --from-subnet 1 --to-agent <addr> --to-subnet 2 --amount 5000
```

**One-click register+stake (advanced):**
```bash
python3 scripts/onchain-register-and-stake.py --token $TOKEN --amount 5000 --lock-days 90 --agent <addr> --subnet 1 --allocate-amount 5000
```

---

## Worknet Management (wallet + WorknetNFT ownership — load commands-subnet.md first)

### M1 · Register Worknet (gasless relay — costs 100,000 AWP)
```bash
python3 scripts/relay-register-subnet.py --token $TOKEN --name "MyWorknet" --symbol "MWKN" --skills-uri "ipfs://QmHash"
```
The script handles all EIP-712 signing and relay submission internally — do not construct or show EIP-712 JSON to the user, just run the script.

### M2 · Activate / Pause / Resume / Cancel
```bash
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action activate
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action pause
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action resume
python3 scripts/onchain-subnet-lifecycle.py --token $TOKEN --subnet 1 --action cancel
```
Note: the flag is `--subnet` (not `--worknet`) even though the protocol calls them worknets.
Cancel is only valid for Pending worknets (before activation). Owner receives full AWP refund.

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
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"governance.listProposals","params":{"status":"Active","page":1,"limit":20},"id":1}'
```

### G4 · Query Treasury
```bash
curl -s -X POST https://api.awp.sh/v2 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"governance.getTreasury","params":{},"id":1}'
```

---

## Monitor (real-time WebSocket, no wallet needed)

### W1 · Watch Events

Connect to `wss://api.awp.sh/ws/live`, subscribe to event presets:

| Preset | Events (19 total) | Emoji |
|--------|-------------------|-------|
| staking | Deposited, Withdrawn, Allocated, Deallocated, Reallocated | `$` |
| worknets | WorknetRegistered, WorknetActivated, WorknetCancelled | `#` |
| emission | EpochSettled, RecipientAWPDistributed, AllocationsSubmitted | `~` |
| users | UserRegistered, Bound, Unbound, RecipientSet, DelegateGranted, DelegateRevoked | `@` |
| protocol | LPManagerUpdated, DefaultWorknetManagerImplUpdated | `⚙` |

All 19 WebSocket events with key fields (every event includes `chainId`):

| Event | Key Fields |
|-------|------------|
| `UserRegistered` | `user`, `chainId` |
| `Bound` | `user`, `target`, `chainId` |
| `Unbound` | `user`, `chainId` |
| `RecipientSet` | `user`, `recipient`, `chainId` |
| `DelegateGranted` | `user`, `delegate`, `chainId` |
| `DelegateRevoked` | `user`, `delegate`, `chainId` |
| `Deposited` | `user`, `tokenId`, `amount`, `lockEndTime`, `chainId` |
| `Withdrawn` | `user`, `tokenId`, `amount`, `chainId` |
| `Allocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` |
| `Deallocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` |
| `Reallocated` | `staker`, `fromAgent`, `fromWorknetId`, `toAgent`, `toWorknetId`, `amount`, `chainId` |
| `WorknetRegistered` | `worknetId`, `owner`, `name`, `symbol`, `chainId` |
| `WorknetActivated` | `worknetId`, `chainId` |
| `WorknetCancelled` | `worknetId`, `chainId` |
| `EpochSettled` | `epoch`, `totalEmission`, `recipientCount`, `chainId` |
| `RecipientAWPDistributed` | `epoch`, `recipient`, `amount`, `chainId` |
| `AllocationsSubmitted` | `epoch`, `totalWeight`, `recipients`, `weights`, `chainId` |
| `LPManagerUpdated` | `newLPManager`, `chainId` |
| `DefaultWorknetManagerImplUpdated` | `newImpl`, `chainId` |

Display format:
```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2026-12-01 | https://basescan.org/tx/0xabc...
# WorknetRegistered | #12 "DataMiner" by 0x5678...efgh | https://basescan.org/tx/0xdef...
~ EpochSettled | Epoch 42 | 31,600,000.0000 AWP to 150 recipients | https://basescan.org/tx/0x123...
```

### W2 · Emission Alert

Subscribe to `EpochSettled` + `RecipientAWPDistributed`.

---

## Error Recovery

| Error | Print | Recovery |
|-------|-------|----------|
| JSON-RPC -32600 | `[!] invalid request: <detail>` | Check inputs |
| JSON-RPC -32601 | `[!] method not found` | Check method name |
| JSON-RPC -32001 | `[!] not found` | Suggest list/search |
| 429 Rate Limit | `[!] rate limited. retrying in 60s...` | Auto-retry |
| "not registered" | `[!] not registered. say "start working"` | Guide to onboarding |
| "insufficient balance" | `[!] insufficient balance` | Guide to S2 |
| PositionExpired | `[!] position expired. withdraw first.` | Guide to S2 |
| Session expired | `[!] re-unlocking wallet...` | Auto re-unlock |
| Wallet not found | `[!] initializing wallet...` | Agent runs `awp-wallet init` |
| WS disconnected | `[WATCH] reconnecting...` | Backoff reconnect |
