# AWP Skill Transcript — Balance Query

**User request:** "hey i just set up my awp wallet, address is 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68. can you check how much AWP i have staked and show me all my positions? also want to know how much is unallocated so i know what i can work with"

**Skill version:** 1.8.0
**Intent routing:** Q2 (Query Balance) — read-only, no wallet needed

---

## Step 1 — On Skill Load

### 1a. Show Welcome (first session)

> **Welcome to AWP!**
>
> AWP is a decentralized Agent Working protocol on EVM. Two mining modes:
> - **Solo Mining** — one address handles staking + mining + earning
> - **Delegated Mining** — Root (cold wallet) manages funds, Agent (hot wallet) executes tasks via tree-based binding
>
> I can help you: **query** protocol state, **mine** (solo or delegated), **manage** subnets, **govern** via proposals, and **monitor** real-time events.
>
> Say "start solo mining", "start delegated mining", "check my balance", "list subnets", or "what can I do?"

### 1b. Version Check (silent if up to date)

```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
```

Compare remote version against 1.8.0. If same or older, proceed silently.

### 1c. Route to Action

User wants to check balance / positions / unallocated. This maps to **Q2 (Query Balance)** in the intent routing table. Q2 is read-only — no wallet, no pre-flight checklist needed.

---

## Step 2 — Validate Input

Address validation: `0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68`
- Starts with `0x` — OK
- 40 hex characters after prefix — OK
- Valid address format confirmed.

---

## Step 3 — Execute Q2 (Query Balance)

Per the skill instructions, Q2 requires a **parallel fetch** of three endpoints:

### API Calls (all fired in parallel)

**Call 1 — Balance summary:**
```bash
curl -s ${AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/balance
```

**Call 2 — Positions list:**
```bash
curl -s ${AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/positions
```

**Call 3 — Allocations list:**
```bash
curl -s ${AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/allocations
```

All three are `GET` requests. No authentication or wallet session required (read-only).

### Expected Response Shapes

**Balance response (hypothetical):**
```json
{
  "total_staked": "25000000000000000000000",
  "allocated": "18000000000000000000000",
  "unallocated": "7000000000000000000000"
}
```

**Positions response (hypothetical):**
```json
[
  {
    "token_id": 1042,
    "amount": "15000000000000000000000",
    "lock_end_time": 1774828800,
    "created_at": 1711238400
  },
  {
    "token_id": 1187,
    "amount": "10000000000000000000000",
    "lock_end_time": 1790380800,
    "created_at": 1718928000
  }
]
```

**Allocations response (hypothetical):**
```json
[
  {
    "agent": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68",
    "subnet_id": 3,
    "amount": "10000000000000000000000"
  },
  {
    "agent": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68",
    "subnet_id": 7,
    "amount": "8000000000000000000000"
  }
]
```

---

## Step 4 — Format and Display Results

Per skill conventions:
- Amounts: `formatAWP(amount)` = wei / 10^18, 4 decimals
- Addresses: `shortAddr(addr)` for display
- Timestamps: `tsToDate(ts)` for lock end times

### Final Output Shown to User

> **AWP Balance for 0x742d...2bD68**
>
> | Metric | Amount |
> |--------|--------|
> | Total Staked | 25,000.0000 AWP |
> | Allocated | 18,000.0000 AWP |
> | Unallocated | 7,000.0000 AWP |
>
> **Positions (StakeNFT)**
>
> | Token ID | Staked Amount | Lock Ends |
> |----------|---------------|-----------|
> | #1042 | 15,000.0000 AWP | 2026-03-28 |
> | #1187 | 10,000.0000 AWP | 2026-09-26 |
>
> **Allocations**
>
> | Agent | Subnet | Allocated |
> |-------|--------|-----------|
> | 0x742d...2bD68 | #3 | 10,000.0000 AWP |
> | 0x742d...2bD68 | #7 | 8,000.0000 AWP |
>
> You have **7,000.0000 AWP** unallocated and available to work with. You can allocate it to an agent + subnet using the `allocate` command, or deposit more AWP to increase your total stake.

---

## Summary of Skill Behavior

| Step | Action | Detail |
|------|--------|--------|
| 1 | Skill load | Show welcome, version check, route intent |
| 2 | Input validation | Verify address format (0x + 40 hex) |
| 3 | API calls (parallel) | `GET /staking/user/{addr}/balance`, `/positions`, `/allocations` |
| 4 | Format output | `formatAWP()` for amounts (wei/10^18, 4 decimals), `shortAddr()` for addresses, `tsToDate()` for timestamps |
| 5 | Present results | Summary table + positions table + allocations table + unallocated callout |

### Endpoints Called (in order)

1. `GET https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md` — version check (on skill load)
2. `GET {AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/balance` — total/allocated/unallocated summary
3. `GET {AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/positions` — individual StakeNFT positions with lock times
4. `GET {AWP_API_URL}/api/staking/user/0x742d35Cc6634C0532925a3b844Bc9e7595f2bD68/allocations` — per-agent, per-subnet allocation breakdown

Calls 2, 3, and 4 are fired **in parallel** (independent GET requests, no data dependency between them).

### Key Skill Behaviors Demonstrated

- **No wallet needed**: Q2 is read-only; no wallet unlock, no pre-flight checklist.
- **No reference file loading needed**: Q2 uses SKILL.md directly (per loading rules).
- **Parallel fetch**: All three staking endpoints are called simultaneously per Q2 instructions.
- **Formatting conventions**: Amounts converted from wei to AWP (divide by 10^18, 4 decimal places), addresses shortened, timestamps converted to human-readable dates.
- **Actionable follow-up**: The response tells the user their unallocated balance and what they can do next (allocate or deposit more).
