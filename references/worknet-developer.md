# AWP WorkNet Protocol — LLM Agent Reference

> System prompt companion: feed this document to an LLM agent so it can answer any developer question about building, deploying, and operating a WorkNet on AWP.

---

## Protocol Overview

AWP is a multi-chain AI agent incentive protocol. **WorkNets** are autonomous AI agent networks that receive daily AWP emission and distribute rewards to participating agents.

Each WorkNet has:
- An **Alpha Token** (e.g., aMINE, aPRED) — per-worknet ERC-20, 10B max supply, minted by the WorkNet Manager
- A **WorkNet Manager** — UUPS proxy contract handling reward distribution, AWP strategy, and Merkle claims
- A **Uniswap V4 LP pool** bootstrapped at activation with 1M AWP + 1B Alpha tokens
- An **AWPWorkNet NFT** (ERC-721) — on-chain identity storing name, symbol, manager address, token address. LP pool ID is stored in `AWPRegistry.worknets[worknetId].lpPool`, not in AWPWorkNet.

**Chains**: Base (8453, primary), Ethereum (1), Arbitrum (42161), BSC (56). All addresses identical via CREATE2 except LPManager (DEX-specific).

---

## Contract Addresses (All Chains Unless Noted)

```
AWPRegistry:           0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A
AWPToken:              0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1
AWPWorkNet:            0x00000bfbdEf8533E5F3228c9C846522D906100A7
AWPAllocator:          0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA
veAWP:                 0x0000b534C63D78212f1BDCc315165852793A00A8
VeAWPHelper:           0x0000561EDE5C1Ba0b81cE585964050bEAE730001
AWPEmission:           0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9
Treasury:              0x82562023a053025F3201785160CaE6051efD759e
AWPDAO:                0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0
Guardian (Safe 3/5):   0x000002bEfa6A1C99A710862Feb6dB50525dF00A3
LPManager (Base):      varies per chain (Uniswap V4 on Base/ETH/ARB, PancakeSwap V4 on BSC)
```

## API Endpoints

```
REST:        https://api.awp.sh/api/...
JSON-RPC:    POST https://api.awp.sh/v2
WebSocket:   wss://api.awp.sh/ws/live
```

Rate limit: 100 req/IP/hour for relay endpoints. IP whitelist via Redis SET `ratelimit:whitelist`.

---

## WorkNet Lifecycle

```
Pending ──Guardian activateWorknet()──▶ Active ◀── Owner: resumeWorknet()
                                          │                  ↑
                                    Owner: pauseWorknet()    │
                                          │                  │
                                          ▼                  │
                                        Paused ──────────────┘
                                          
Active ──Guardian: deregisterWorknet()──▶ Deregistered (final, irreversible)
```

### Registration

**WorknetParams struct:**
```solidity
struct WorknetParams {
    string name;              // 1-64 bytes, no " or \ (JsonUnsafeCharacter error)
    string symbol;            // 1-16 bytes, no " or \
    address worknetManager;   // address(0) = auto-deploy default manager
    bytes32 salt;             // CREATE2 salt (bytes32(0) = use worknetId)
    uint128 minStake;         // Hint for frontends (not enforced on-chain)
    string skillsURI;         // URL to skill definition
}
```

**Escrow cost**: `initialAlphaMint × initialAlphaPrice / 1e18` AWP. Query on-chain:
```
AWPRegistry.initialAlphaMint() → uint256 (default 1e27 = 1B tokens)
AWPRegistry.initialAlphaPrice() → uint256 (default 1e15 = 0.001 AWP per token)
→ escrow ≈ 1,000,000 AWP
```

**WorknetId**: `block.chainid × 100_000_000 + localCounter`. Globally unique. Starts at #1. First assigned ID is 845300000001.

### Activation (Atomic, Guardian-only)

1. Deploy WorknetToken via CREATE2 (vanity `0xA100...CAFE`)
2. Transfer escrowed AWP to LPManager + mint Alpha → create V4 LP pool (full range, 0.1% fee, tick spacing 200)
3. Deploy WorknetManager proxy (if auto-deploy) with owner as DEFAULT_ADMIN_ROLE
4. Lock minter: `WorknetToken.setMinter(worknetManager)` — **irreversible**
5. Mint AWPWorkNet NFT (ERC-721) with identity data
6. State → Active

---

## WorkNet Manager

### Role System

| Role | Hash | Purpose |
|------|------|---------|
| DEFAULT_ADMIN_ROLE | `0x00...00` (32 zero bytes) | Grant/revoke all roles |
| MERKLE_ROLE | `keccak256("MERKLE_ROLE")` | Batch mint, set Merkle root |
| TRANSFER_ROLE | `keccak256("TRANSFER_ROLE")` | Batch transfer AWP/tokens |
| STRATEGY_ROLE | `keccak256("STRATEGY_ROLE")` | Change AWP strategy |
| CHECKPOINT_ROLE | `keccak256("CHECKPOINT_ROLE")` | Submit computation checkpoints |
| UPGRADER_ROLE | `keccak256("UPGRADER_ROLE")` | UUPS upgrade (can be permanently renounced) |

### AWP Strategy (3 options)

```solidity
enum AWPStrategy { Reserve, AddLiquidity, BuybackBurn }
```

| # | Name | Behavior on AWP receipt |
|---|------|----------------------|
| 0 | Reserve | Hold AWP in manager (distribute manually later via batchTransferTokenPacked) |
| 1 | AddLiquidity | Add AWP + mint Alpha → LP pool |
| 2 | BuybackBurn | Buy Alpha with AWP on DEX, burn it |

### All External Functions

```solidity
// ── Reward Distribution (MERKLE_ROLE) ──
batchMint(address[] recipients, uint256[] amounts)
batchMintPacked(uint256[] packed)              // packed[i] = (amount_uint96 << 160) | address_uint160
setMerkleRoot(uint32 epoch, bytes32 root)
claim(uint32 epoch, uint256 amount, bytes32[] proof)
isClaimed(uint32 epoch, address account) → bool

// ── Token Transfer (TRANSFER_ROLE) ──
transferToken(address token, address to, uint256 amount)
batchTransferToken(address token, address[] recipients, uint256[] amounts)
batchTransferTokenPacked(address token, uint256[] packed)

// ── Checkpoints (CHECKPOINT_ROLE) ──
submitCheckpoint(uint32 epoch, bytes32 root, string uri)
verifyCheckpoint(uint32 epoch, bytes32 leaf, bytes32[] proof) → bool

// ── Strategy (STRATEGY_ROLE) ──
setStrategy(AWPStrategy strategy)
executeStrategy(uint256 amount, uint256 minAmountOut)
setSlippageTolerance(uint16 bps)
setMinStrategyAmount(uint256 amount)

// ── Admin (DEFAULT_ADMIN_ROLE) ──
grantRole(bytes32 role, address account)
revokeRole(bytes32 role, address account)
setStrategyPaused(bool paused)           // requires DEFAULT_ADMIN_ROLE
renounceUpgradeability()                 // IRREVERSIBLE

// ── Upgrade (UPGRADER_ROLE) ──
upgradeToAndCall(address newImpl, bytes data)

// ── ERC1363 callback (receives AWP from emission) ──
onTransferReceived(address operator, address from, uint256 value, bytes data) → bytes4
```

### Packed Format

Every batch function uses the same packed encoding:
```
packed[i] = (amount_uint96 << 160) | address_uint160
```
- amount: uint96 max = 2^96 - 1 ≈ 79.2B tokens
- address: bottom 160 bits
- Gas: ~25k per recipient
- **Max batch size**: 350 recipients recommended (414 max, but cold storage writes for first-time recipients use ~2× gas)

---

## WorknetToken (Alpha Token)

```
MAX_SUPPLY = 10,000,000,000 × 1e18 (10B tokens)
Decimals = 18
```

**Mint cap (immutable, post-lock):**
```
cap = (MAX_SUPPLY - supplyAtLock) × elapsed / 365 days
```
Where `supplyAtLock` is a snapshot taken at `setMinter()` time, `elapsed` is seconds since token creation. Minting capacity grows linearly — after 1 year, the full remaining supply is mintable. At max rate: ~27.4M tokens/day (assuming supplyAtLock ≈ 0).

**Key properties:**
- Minter locked to WorknetManager at activation — irreversible
- `minterPaused`: Guardian can pause minting without deregistering
- ERC-1363: supports `transferAndCall` / `approveAndCall`
- Vanity address pattern: `0xA100...CAFE` (enforced by factory)

---

## AWP Emission

**Epoch**: 24 hours (86400s). `currentEpoch = (block.timestamp - baseTime) / epochDuration`.

**Decay**: `currentDailyEmission *= 996844 / 1000000` per epoch (~0.32% decrease/day). Default value set at initialization; Guardian-configurable via `setDecayFactor()`.

**submitAllocations packed format:**
```
packed[i] = (weight_uint64 << 160) | recipient_address_uint160
```
`totalWeight` = sum of all weights. Each recipient gets `(weight / totalWeight) × currentDailyEmission`.

**Settlement**: Keeper calls `settleEpoch(limit)` → AWPToken `mintAndCall` to each recipient → triggers `onTransferReceived` on WorknetManager → strategy executes.

**Current emission split (epoch 8+):**
| Recipient | Weight | Share |
|-----------|--------|-------|
| Treasury | 500 | 50% |
| Mine WorkNet Manager | 350 | 35% |
| Predict WorkNet Manager | 150 | 15% |

---

## veAWP Staking

**Position struct:**
```solidity
struct Position { uint128 amount; uint64 lockEndTime; uint64 createdAt; }
```

**Functions:**
```solidity
deposit(uint256 amount, uint64 lockDuration) → uint256 tokenId
depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) → uint256 tokenId
addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime)  // reverts with PositionExpired if lock is expired and no lock extension is provided in the same call
withdraw(uint256 tokenId)   // only after lock expires; requires sufficient unallocated balance
partialWithdraw(uint256 tokenId, uint128 amount)
batchWithdraw(uint256[] calldata tokenIds)
```

**Voting power formula:**
```
power = amount × sqrt(min(remainingTime, 54 weeks) / 7 days)
```
- MAX_WEIGHT_DURATION = 54 weeks = 32,659,200s
- VOTE_WEIGHT_DIVISOR = 7 days = 604,800s
- MIN_LOCK_DURATION = 1 day = 86,400s
- Max multiplier ≈ 7.7× (at 54 weeks lock)

**Gasless staking**: `VeAWPHelper.depositFor(user, amount, lockDuration, deadline, v, r, s)` — user signs ERC-2612 Permit, relayer calls depositFor. API: `POST /api/relay/stake`.

**Option E (anti-flash-stake)**: Voting NFTs must have `lockEndTime >= proposalDeadline + 7 days`. Users who stake after a proposal can still vote, but must commit capital for ≥ 8 days.

---

## AWPAllocator

Users allocate their veAWP balance toward specific agents in specific worknets:

```solidity
allocate(address staker, address agent, uint256 worknetId, uint256 amount)
deallocate(address staker, address agent, uint256 worknetId, uint256 amount)
deallocateAll(address staker, address agent, uint256 worknetId)
reallocate(address staker, address fromAgent, uint256 fromWorknetId, address toAgent, uint256 toWorknetId, uint256 amount)
batchAllocate(address staker, address[] calldata agents, uint256[] calldata worknetIds, uint256[] calldata amounts)
batchDeallocate(address staker, address[] calldata agents, uint256[] calldata worknetIds, uint256[] calldata amounts)
```

- Auth: staker themselves or delegate (via AWPRegistry.delegates mapping)
- worknetId=0 always rejected
- Cross-chain: staker on chain A can allocate to worknetId from chain B (globally unique IDs)
- Balance check: `userTotalAllocated(staker) + amount <= veAWP.getUserTotalStaked(staker)`
- Withdraw veAWP blocked if allocated amount would exceed remaining staked

**Gasless variants:**
```
allocateFor(staker, agent, worknetId, amount, deadline, v, r, s)
deallocateFor(staker, agent, worknetId, amount, deadline, v, r, s)
```

---

## Account System (AWPRegistry)

Tree-based identity + reward routing:

```solidity
bind(address target)           // bind to parent (tree; anti-cycle; max depth enforced)
setRecipient(address addr)     // set reward destination (default = self)
grantDelegate(address delegate) // let delegate act on your behalf (allocate, etc.)
revokeDelegate(address delegate)
resolveRecipient(address addr)  // walk boundTo chain to root's recipient
```

All have gasless `*For(user, ..., deadline, v, r, s)` variants.

---

## EIP-712 Domains & TypeHashes

### AWPRegistry Domain
```json
{"name": "AWPRegistry", "version": "1", "chainId": <chainId>, "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"}
```

| Operation | TypeHash String |
|-----------|----------------|
| Bind | `"Bind(address agent,address target,uint256 nonce,uint256 deadline)"` |
| SetRecipient | `"SetRecipient(address user,address recipient,uint256 nonce,uint256 deadline)"` |
| GrantDelegate | `"GrantDelegate(address user,address delegate,uint256 nonce,uint256 deadline)"` |
| RevokeDelegate | `"RevokeDelegate(address user,address delegate,uint256 nonce,uint256 deadline)"` |
| Unbind | `"Unbind(address user,uint256 nonce,uint256 deadline)"` |
| RegisterWorknet | `"RegisterWorknet(address user,WorknetParams params,uint256 nonce,uint256 deadline)WorknetParams(string name,string symbol,address worknetManager,bytes32 salt,uint128 minStake,string skillsURI)"` |

Nonce: `AWPRegistry.nonces(address)` — shared across all Registry operations.

### AWPAllocator Domain
```json
{"name": "AWPAllocator", "version": "1", "chainId": <chainId>, "verifyingContract": "0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA"}
```

| Operation | TypeHash String |
|-----------|----------------|
| Allocate | `"Allocate(address staker,address agent,uint256 worknetId,uint256 amount,uint256 nonce,uint256 deadline)"` |
| Deallocate | `"Deallocate(address staker,address agent,uint256 worknetId,uint256 amount,uint256 nonce,uint256 deadline)"` |

Nonce: `AWPAllocator.nonces(address)` — shared across allocate/deallocate.

### AWPToken Domain (ERC-2612 Permit)
```json
{"name": "AWP Token", "version": "1", "chainId": <chainId>, "verifyingContract": "0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1"}
```

Standard Permit: `"Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)"`.
Nonce: `AWPToken.nonces(address)`.

### AWPDAO Domain
```json
{"name": "AWPDAO", "version": "1", "chainId": <chainId>, "verifyingContract": "0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0"}
```

| Operation | TypeHash String |
|-----------|----------------|
| Vote | `"ExtendedBallot(uint256 proposalId,uint8 support,address voter,uint256 nonce,string reason,bytes params)"` |
| Propose | `"Propose(address proposer,address[] targets,uint256[] values,bytes[] calldatas,string description,uint256[] tokenIds,uint256 nonce,uint256 deadline)"` |
| SignalPropose | `"SignalPropose(address proposer,string description,uint256[] tokenIds,uint256 nonce,uint256 deadline)"` |

Nonce: `AWPDAO.nonces(address)` — shared across vote/propose/signal.

---

## DAO Governance

**Parameters:**
| Param | Value |
|-------|-------|
| votingDelay | 1 hour (3600s) |
| votingPeriod | 24 hours (86400s) |
| quorumPercent | 4% of total staked AWP |
| proposalThreshold | 200,000 AWP staked (waived for approvedProposer) |

Note: DAO params are Guardian-configurable — always fetch from `registry.get → daoParams`.

**Proposal lifecycle**: create → 1h delay → 24h voting → Succeeded/Defeated → 2-day Timelock → execute.

**ProposalId format**: `0x` + 64 hex chars (bytes32 form of uint256). API accepts both hex and decimal, always returns hex.

**Vote support**: 0 = Against, 1 = For, 2 = Abstain. Quorum = For + Abstain votes ≥ 4% of total staked.

---

## Common Error Selectors

| Error | Selector | Meaning |
|-------|----------|---------|
| InvalidSignature() | 0x8baa579f | EIP-712 signature doesn't match expected signer (usually stale nonce) |
| ExpiredSignature() | 0xdf4cc36d | block.timestamp > deadline |
| SaltAlreadyUsed() | 0x0ced3043 | CREATE2 salt already consumed |
| InvalidWorknetName() | 0x33b4f8bf | Name empty, >64 bytes, or contains " or \ |
| InvalidWorknetSymbol() | 0xa581811c | Symbol empty, >16 bytes, or contains " or \ |
| NotAuthorized() | 0x4b6c2125 | Caller is not staker or delegate |
| InsufficientAllocation() | 0xdf2d4774 | Trying to deallocate more than allocated |
| InsufficientUnallocated() | 0xd247d121 | veAWP withdraw blocked — too much allocated |
| ZeroAmount() | 0x1f2a2005 | Amount parameter is 0 |
| ZeroWorknetId() | 0xd76d9a3d | worknetId is 0 |
| NotOwner() | 0x30cd7471 | Caller doesn't own the worknet NFT |
| MaxActiveWorknetsReached() | 0xfb05c4fa | 10,000 active worknet limit hit |
| LockTooShort() | (varies) | veAWP lock doesn't extend 7 days past voting deadline (Option E) |
| LockExpired() | (varies) | veAWP position lock has expired |
| TokenAlreadyVoted() | (varies) | This veAWP tokenId already voted on this proposal |
| ZeroTotalVotingPower() | (varies) | No veAWP staked on this chain (can't create proposals) |

---

## REST API Quick Reference

### Gasless Relay Endpoints (POST)

| Endpoint | Purpose |
|----------|---------|
| `/api/relay/register` | Gasless register (= setRecipientFor(user, user)) |
| `/api/relay/register-worknet/prepare` | Get EIP-712 typed data for worknet registration |
| `/api/relay/register-worknet` | Submit gasless worknet registration |
| `/api/relay/set-recipient` | Set reward recipient (gasless registration) |
| `/api/relay/bind` | Bind agent to target |
| `/api/relay/unbind` | Unbind from target |
| `/api/relay/grant-delegate` | Grant delegate |
| `/api/relay/revoke-delegate` | Revoke delegate |
| `/api/relay/stake` | Stake AWP → veAWP via permit |
| `/api/relay/stake/prepare` | Get EIP-712 typed data for staking |
| `/api/relay/allocate` | Allocate veAWP to (agent, worknet) |
| `/api/relay/deallocate` | Remove allocation |
| `/api/relay/vote/prepare` | Get EIP-712 typed data for voting |
| `/api/relay/vote` | Submit gasless vote |
| `/api/relay/signal-propose/prepare` | Get typed data for signal proposal |
| `/api/relay/signal-propose` | Submit signal proposal (with optional `url` field) |
| `/api/relay/propose/prepare` | Get typed data for executable proposal |
| `/api/relay/propose` | Submit executable proposal |

### Read Endpoints (GET)

| Endpoint | Returns |
|----------|---------|
| `/api/registry?chainId=N` | All contract addresses + DAO params + EIP-712 domains |
| `/api/worknets?chainId=N` | List all worknets |
| `/api/worknets/{id}?chainId=N` | Worknet detail |
| `/api/worknets/{id}/skills` | Skills URI + metadata |
| `/api/worknets/{id}/earnings` | Historical AWP earnings |
| `/api/worknets/ranked` | Worknets ranked by total stake |
| `/api/worknets/by-owner/{addr}` | Worknets owned by address |
| `/api/staking/agent/{addr}/worknet/{id}` | Agent allocation in worknet |
| `/api/staking/agent/{addr}/worknets` | All worknets agent allocated to |
| `/api/staking/worknet/{id}/total` | Total stake in worknet |
| `/api/governance/proposals?chainId=N` | List proposals |
| `/api/governance/proposals/{id}?chainId=N` | Proposal detail (enriched) |
| `/api/governance/eligible-tokens?address=X&proposalId=Y` | Voter NFT eligibility |
| `/api/governance/voting-power?address=X` | Aggregate voting power |
| `/api/nonce/{address}?chainId=N` | AWPRegistry EIP-712 nonce |
| `/api/staking-nonce/{address}?chainId=N` | AWPAllocator EIP-712 nonce |

### JSON-RPC Methods (POST /v2)

**Registration**: `address.check`, `address.resolveRecipient`, `nonce.get`, `nonce.getStaking`
**Users**: `users.get`, `users.getPortfolio`, `users.list`, `users.count`
**Staking**: `staking.getBalance`, `staking.getPositions`, `staking.getAllocations`
**WorkNets**: `worknets.list`, `worknets.get`, `worknets.getSkills`, `worknets.getEarnings`, `worknets.listRanked`, `worknets.search`, `worknets.listAgents`, `worknets.getByOwner`, `worknets.getAgentInfo`
**Emission**: `emission.getCurrent`, `emission.getSchedule`, `emission.listEpochs`
**Governance**: `governance.listProposals`, `governance.getProposal`, `governance.getEligibleTokens`, `governance.getVotingPower`, `governance.getQuorumProgress`, `governance.getStats`
**Tokens**: `tokens.getAWP`, `tokens.getWorknetTokenInfo`, `tokens.getWorknetTokenPrice`
**Health**: `health.check`, `health.detailed`, `registry.get`, `chains.list`

---

## Existing WorkNets (Reference)

### Mine WorkNet (#845300000002)
- Manager: `0xAB41eE5C44D4568aD802D104A6dAB1Fe09C590D1`
- Token: `0xA1008600D8A5dc0334105eeecA3f1f478A63CAFE` (aMINE)
- Operator: `0x61F73D4F5Fd574DB95226A618fe5DD787333ab81`
- Strategy: Reserve → manual batchTransferTokenPacked
- SkillsURI: `https://github.com/awp-worknet/mine-skill`

### Predict WorkNet (#845300000003)
- Manager: `0x809715a3bbadbde56ff23e4385adc2b42308f48c`
- Token: `0xa1009389ec6ed23c33262f1e02e1ebbd9ad5cafe` (aPRED)
- Owner: `0x5829f06b43e854a11e2a3d95191185e2e8e82bd1`
- SkillsURI: `https://github.com/awp-worknet/prediction-skill`

---

## Acceptance Criteria (Non-Negotiable)

### 1. Genuine AI Utility
- Core tasks must require LLM inference/reasoning (not simple scripts)
- Anti-sybil mechanism required (Merkle checkpoints, validator cross-checking, stake-weighted scoring)
- Work output must be independently valuable (trained models, curated data, verified predictions)

### 2. Security & Auditability
- Custom managers must be audited (or use the default manager)
- All contracts must be verified on block explorers
- Scoring algorithms must be open-source and deterministic

### 3. Openness & Fairness
- All reward distributions on-chain (Transfer events)
- Scoring criteria published and version-controlled
- Epoch reward CSVs published alongside checkpoint Merkle roots
- Non-discriminatory: any eligible agent can participate

**Violation consequences**: community flag → Guardian investigation → emission reduction → deregistration.

---

## Operational Playbook

### Daily Reward Distribution

```bash
# Pure Python script (no external deps beyond eth-account + requests)
python3 scripts/admin-tools/distribute-rewards.py epoch_rewards.csv --batch-size 350

# Pipeline:
# 1. Load CSV (address,reward), dedup
# 2. Pack: uint256[] where packed[i] = (amount<<160)|address
# 3. Split into batches of 350
# 4. Phase 1: batchMintPacked (Alpha) per batch, serial, wait receipt
# 5. Phase 2: batchTransferTokenPacked (AWP, proportional to Alpha) per batch
# 6. Verify on-chain: supply delta == expected
```

**Gas**: ~0.001 ETH for 1000 recipients on Base (~0.006 gwei gas price).

### Gasless Staking Flow
1. Frontend reads the AWP token's permit nonce: `AWPToken.nonces(user)` (NOT the AWPRegistry nonce from `nonce.get`). The relay prepare endpoint `/api/relay/stake/prepare` returns the correct nonce automatically.
2. User signs ERC-2612 Permit(user, VeAWPHelper, amount, nonce, deadline)
3. Frontend POSTs to `/api/relay/stake` with {user, amount, lockDuration, deadline, signature}
4. Relayer calls `VeAWPHelper.depositFor(...)` paying gas
5. veAWP NFT minted to user

### Signal Proposal (ERP) Flow
1. `POST /api/relay/signal-propose/prepare` → get EIP-712 typed data + nonce
2. Proposer signs the typed data
3. `POST /api/relay/signal-propose` with {title, body, url, tokenIds, signature}
4. On-chain: `AWPDAO.signalProposeBySig(...)` — title+contentHash on-chain, full body in DB
5. 12h delay → 48h voting → result

---

## FAQ (Common Developer Questions)

**Q: Do users need ETH to interact?**
A: No. All user operations (register, bind, setRecipient, stake, allocate, vote, propose) have gasless relay variants. The protocol relayer pays gas.

**Q: How do I get my WorkNet into the emission?**
A: Submit an ERP (signal proposal) via AWPDAO. Community votes weekly to set emission weights.

**Q: What happens to AWP when it arrives at my Manager?**
A: The `onTransferReceived` callback auto-executes your current strategy (Reserve/AddLiquidity/BuybackBurn). With Reserve (default), AWP sits in the manager until you distribute it via `batchTransferTokenPacked`.

**Q: Can I change the Alpha token minter?**
A: No. `setMinter()` is irreversible. To change minting logic, upgrade the WorknetManager via UUPS (requires UPGRADER_ROLE).

**Q: What's the maximum I can mint per day?**
A: `(MAX_SUPPLY - supplyAtLock) × elapsed / 365 days` — the budget grows linearly over time. At max rate ~27.4M tokens/day (assuming supplyAtLock ≈ 0). Bursty patterns must be spread across days.

**Q: How does cross-chain allocation work?**
A: worknetId is globally unique. A user on Ethereum can allocate veAWP to a Base worknet. Allocation is local per chain but worknetId references any chain.

**Q: What's the EIP-712 nonce for?**
A: Replay protection for gasless signatures. Each successful relay tx increments `nonces[user]`. Always fetch fresh nonce before signing. Different contracts have different nonce counters (AWPRegistry, AWPAllocator, AWPDAO, AWPToken).

**Q: Why did my relay tx fail with InvalidSignature?**
A: Most likely stale nonce. The user signed with nonce N, but a previous tx already consumed it (nonce is now N+1). Re-fetch nonce and re-sign.

**Q: What batch size should I use for batchMintPacked?**
A: 350 recipients max. With many first-time recipients (cold SSTORE), 414 can exceed the 14M gas limit. 350 is safe for all cases.

**Q: How do I verify my reward distribution is correct?**
A: `submitCheckpoint(epoch, keccak256(rewardCSV), uri)` before minting. Anyone can verify `verifyCheckpoint(epoch, leaf, proof)` against the committed root.
