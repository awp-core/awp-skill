# AWP Protocol — Skill Development Reference

> Complete reference for building Claude Code skills that interact with AWP (Agent Working Protocol). Covers smart contracts, JSON-RPC API, gasless relay, and WebSocket events. User-facing only — admin/guardian functions are not exposed.

---

## 1. Protocol Overview

AWP is a multi-chain **agent mining protocol** deployed identically on 4 EVM chains:

| Chain | Chain ID | Explorer |
|-------|----------|----------|
| Base | 8453 | basescan.org |
| Ethereum | 1 | etherscan.io |
| Arbitrum One | 42161 | arbiscan.io |
| BNB Smart Chain | 56 | bscscan.com |

All protocol contracts share the same addresses across all 4 chains (deployed via CREATE2). The only exceptions are LPManager implementation contracts and WorknetManager implementation contracts, which differ per chain because they integrate with chain-specific DEXes (Uniswap V4 on Base/ETH/ARB, PancakeSwap V4 on BSC). Users interact with proxies, not implementations, so the proxy addresses are identical.

### Core Concepts

- **AWP Token** (`0x0000A105...00A1`): ERC20 governance/utility token. 10B max supply. Emitted daily via AWPEmission and distributed to worknets. Used for staking, governance, and worknet registration.
- **Worknet**: An autonomous agent network. Each worknet has its own **Alpha token** (ERC20, 10B max per worknet) and a **liquidity pool** (AWP/Alpha pair). Worknets go through a lifecycle: `None -> Pending -> Active -> Paused/Banned`.
- **WorknetNFT** (`0xB9F035...5233`): ERC721 representing worknet ownership. tokenId = worknetId. Owner can pause/resume/cancel their worknet and update metadata.
- **StakeNFT** (`0x4E1195...ba2d`): ERC721 position NFT. Users deposit AWP with a lock period to mint a position. Each position stores (amount, lockEndTime, createdAt). Transferable. Lock must be active to add more AWP.
- **StakingVault** (`0xE8A204...f29b`): Manages stake allocations. Users allocate their staked AWP to (agent, worknetId) tuples. Supports gasless operations via EIP-712. Authorization: caller must be the staker or an authorized delegate.
- **AWPEmission** (`0x3C9cB7...EaA9`): Epoch-based emission engine. Guardian submits per-worknet weights each epoch; `settleEpoch()` mints AWP to recipients proportionally. Exponential decay reduces emission over time.
- **Binding**: Tree-based account linking. An agent calls `bind(owner)` to form a tree. Rewards flow upward to the tree root via `resolveRecipient()`. No mutual exclusion — any address can bind to any other (cycle detection prevents loops).
- **Delegation**: A user can `grantDelegate(delegate)` to allow the delegate to allocate/deallocate on their behalf without holding the user's private key.
- **WorknetId**: Globally unique 256-bit identifier: `(block.chainid << 64) | localCounter`. Passed as a decimal string in the API (e.g., `"36364510078353408001"`).

---

## 2. Contract Addresses

### Protocol Contracts (identical on all 4 chains)

| Contract | Address | Type | Description |
|----------|---------|------|-------------|
| AWPToken | `0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1` | ERC20 | Protocol token, 10B max supply |
| AWPRegistry | `0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A` | UUPS Proxy | Central registry: accounts, worknets, binding, delegation |
| AWPEmission | `0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9` | UUPS Proxy | Epoch-based AWP emission engine |
| StakingVault | `0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b` | UUPS Proxy | Stake allocation management |
| StakeNFT | `0x4E119560632698Bab67cFAB5d8EC0A373363ba2d` | ERC721 | AWP staking position NFT |
| WorknetNFT | `0xB9F03539BE496d09c4d7964921d674B8763f5233` | ERC721 | Worknet ownership NFT |
| LPManager | `0x386A54f22a8E7abE9D70443F8d5E6b36D1879d5C` | UUPS Proxy | LP pool creation and fee compounding |
| AlphaTokenFactory | `0xB2e4897eD77d0f5BFa3140B9989594de09a8037c` | Contract | CREATE2 factory for Alpha tokens |
| Treasury | `0x82562023a053025F3201785160CaE6051efD759e` | TimelockController | DAO treasury (2-day timelock) |
| AWPDAO | `0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004` | Governor | StakeNFT-based governance |

### WorknetManager Implementations (differ per chain due to DEX integration)

These are the default implementation contracts used when a new worknet is auto-deployed via `registerWorknet(worknetManager: 0x0)`. Each worknet gets its own ERC1967Proxy pointing to the chain's implementation.

| Chain | WorknetManager Impl | DEX |
|-------|-------------------|-----|
| Base (8453) | `0x00945e7fd4110b9c56ab4a3c2f53b6fabe6485e5` | Uniswap V4 |
| Ethereum (1) | `0x0029aABD49BF9ec7a34CDbcf75486B19CFAC3Ea8` | Uniswap V4 |
| Arbitrum (42161) | `0x00c428DCa1678e41Ed17Cc5AE3cF14430e2085A0` | Uniswap V4 |
| BSC (56) | `0x00D87f2f81E20cB1583F46d94BC7a7ad8f2DAC78` | PancakeSwap V4 |

### Guardian (Safe Multisig)

| Role | Address | Type |
|------|---------|------|
| Guardian | `0x000002bEfa6A1C99A710862Feb6dB50525dF00A3` | Safe 3/5 multisig (all chains) |

---

## 3. API — JSON-RPC 2.0

### Connection

| Purpose | URL |
|---------|-----|
| JSON-RPC endpoint | `POST https://api.awp.sh/v2` |
| RPC discovery | `GET https://api.awp.sh/v2` (returns all available methods) |
| WebSocket (live events) | `wss://api.awp.sh/ws/live` |
| Health check | `GET https://api.awp.sh/api/health` |

**Batch requests**: Send an array of up to 20 JSON-RPC requests. They execute concurrently.

### Request/Response Format

```json
// Request (single)
{"jsonrpc": "2.0", "method": "namespace.method", "params": {...}, "id": 1}

// Request (batch)
[
  {"jsonrpc": "2.0", "method": "users.get", "params": {"address": "0x..."}, "id": 1},
  {"jsonrpc": "2.0", "method": "staking.getBalance", "params": {"address": "0x..."}, "id": 2}
]

// Success response
{"jsonrpc": "2.0", "result": {...}, "id": 1}

// Error response
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "method not found"}, "id": 1}
```

### Error Codes

| Code | Meaning | Typical Cause |
|------|---------|---------------|
| -32700 | Parse error | Malformed JSON |
| -32600 | Invalid request | Missing jsonrpc/method fields |
| -32601 | Method not found | Typo in method name |
| -32602 | Invalid params | Missing required param, bad address format |
| -32603 | Internal error | Server-side failure |
| -32001 | Resource not found | No data for given worknetId/address |

### Common Parameter Types

| Parameter | Type | Format | Notes |
|-----------|------|--------|-------|
| `address` | string | `"0x"` + 40 hex chars | Case-insensitive. Always 42 chars total. |
| `worknetId` | string | Decimal integer string | e.g., `"36364510078353408001"`. Globally unique: `(chainId << 64) \| localId` |
| `chainId` | integer | `1`, `56`, `8453`, `42161` | Optional on most methods. **Omit = all chains.** Specify = single chain. |
| `page` | integer | >= 1 | Default: 1. First page. |
| `limit` | integer | 1-100 | Default: 20. Items per page. |
| `status` | string | Enum | Worknet: `"Pending"`, `"Active"`, `"Paused"`, `"Banned"`. Proposal: `"Active"`, `"Canceled"`, `"Defeated"`, `"Succeeded"`, `"Queued"`, `"Expired"`, `"Executed"` |

**Important**: All token amounts in API responses are **wei strings** (18 decimals). For example, 100 AWP = `"100000000000000000000"`. Use BigInt/BigNumber for arithmetic.

---

### 3.1 System

| Method | Params | Description |
|--------|--------|-------------|
| `stats.global` | none | Global protocol stats: total users, worknets, staked AWP, emitted AWP, active chains |
| `registry.get` | `chainId?` | All contract addresses + EIP-712 domain info. **Omit chainId to get an array of all 4 chains.** With chainId: single object. |
| `health.check` | none | Returns `{"status": "ok"}` if API is running |
| `health.detailed` | none | Per-chain health: indexer sync block, keeper status, RPC latency |
| `chains.list` | none | Array of `{chainId, name, dex, explorer}` for all supported chains |

### 3.2 Users

| Method | Params | Description |
|--------|--------|-------------|
| `users.list` | `chainId?`, `page?`, `limit?` | Paginated user list for one chain |
| `users.listGlobal` | `page?`, `limit?` | Cross-chain deduplicated user list |
| `users.count` | `chainId?` | Total registered user count |
| `users.get` | `address` **(required)**, `chainId?` | User details: balance, bound agents, recipient, registration status |
| `users.getPortfolio` | `address` **(required)**, `chainId?` | Complete portfolio: identity + staking balance + NFT positions + allocations + delegates |
| `users.getDelegates` | `address` **(required)**, `chainId?` | List of addresses this user has authorized as delegates |

### 3.3 Address & Nonce

| Method | Params | Description |
|--------|--------|-------------|
| `address.check` | `address` **(required)**, `chainId?` | Check registration status, binding, recipient. **See response format below.** |
| `address.resolveRecipient` | `address` **(required)**, `chainId?` | Walk bind chain to root, return effective reward recipient |
| `address.batchResolveRecipients` | `addresses[]` **(required, max 500)**, `chainId?` | Batch resolve effective recipients (on-chain call) |
| `nonce.get` | `address` **(required)**, `chainId?` | AWPRegistry EIP-712 nonce (for bind/unbind/setRecipient/registerWorknet/activateWorknet/grantDelegate/revokeDelegate) |
| `nonce.getStaking` | `address` **(required)**, `chainId?` | StakingVault EIP-712 nonce (for allocate/deallocate) |

#### `address.check` Response Formats

**With `chainId` specified** (single-chain query):
```json
{
  "isRegistered": true,
  "boundTo": "0xOwnerAddress...",
  "recipient": "0xRecipientAddress..."
}
```
- `isRegistered`: true if user has called `register()`, `setRecipient()`, or `bind()` on this chain
- `boundTo`: address this user is bound to (empty string if not bound)
- `recipient`: reward recipient address (empty string if not set; defaults to self)

**Without `chainId`** (all-chain query):
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

### 3.4 Agents

| Method | Params | Description |
|--------|--------|-------------|
| `agents.getByOwner` | `owner` **(required)**, `chainId?` | All agents (addresses) that have bound to this owner |
| `agents.getDetail` | `agent` **(required)**, `chainId?` | Agent details: owner, binding chain, delegated status |
| `agents.lookup` | `agent` **(required)**, `chainId?` | Quick lookup: returns `{"ownerAddress": "0x..."}` |
| `agents.batchInfo` | `agents[]` **(required, max 100)**, `worknetId` **(required)**, `chainId?` | Batch query: agent info + their stake in specified worknet |

### 3.5 Staking

| Method | Params | Description |
|--------|--------|-------------|
| `staking.getBalance` | `address` **(required)**, `chainId?` | Returns `{totalStaked, totalAllocated, unallocated}` in wei strings |
| `staking.getUserBalanceGlobal` | `address` **(required)** | Same as above but aggregated across ALL chains |
| `staking.getPositions` | `address` **(required)**, `chainId?` | Array of StakeNFT positions: `{tokenId, amount, lockEndTime, createdAt}` |
| `staking.getPositionsGlobal` | `address` **(required)** | Positions across all chains (includes chainId per position) |
| `staking.getAllocations` | `address` **(required)**, `chainId?`, `page?`, `limit?` | Paginated allocation records: `{agent, worknetId, amount}` |
| `staking.getFrozen` | `address` **(required)**, `chainId?` | Frozen allocations (from banned worknets) |
| `staking.getAgentSubnetStake` | `agent` **(required)**, `worknetId` **(required)** | Single value: agent's total allocated stake in a specific worknet (cross-chain) |
| `staking.getAgentSubnets` | `agent` **(required)** | All worknetIds where this agent has non-zero allocations |
| `staking.getSubnetTotalStake` | `worknetId` **(required)** | Total AWP staked across all agents in a worknet |

### 3.6 Worknets

| Method | Params | Description |
|--------|--------|-------------|
| `subnets.list` | `status?`, `chainId?`, `page?`, `limit?` | List worknets. Filter by status: `Pending`, `Active`, `Paused`, `Banned` |
| `subnets.listRanked` | `chainId?`, `page?`, `limit?` | Worknets ranked by total stake (highest first) |
| `subnets.search` | `query` **(required, 1-100 chars)**, `chainId?`, `page?`, `limit?` | Search by name or symbol (case-insensitive ILIKE) |
| `subnets.getByOwner` | `owner` **(required)**, `chainId?`, `page?`, `limit?` | Worknets owned by address |
| `subnets.get` | `worknetId` **(required)** | Full worknet details: name, symbol, status, alphaToken, LP pool, owner, stakes, etc. |
| `subnets.getSkills` | `worknetId` **(required)** | Skills URI (off-chain metadata describing the worknet's capabilities) |
| `subnets.getEarnings` | `worknetId` **(required)**, `page?`, `limit?` | Paginated AWP earnings history by epoch |
| `subnets.getAgentInfo` | `worknetId` **(required)**, `agent` **(required)** | Agent's info within a specific worknet: stake, validity, reward recipient |
| `subnets.listAgents` | `worknetId` **(required)**, `chainId?`, `page?`, `limit?` | Agents in worknet ranked by stake |

### 3.7 Emission

| Method | Params | Description |
|--------|--------|-------------|
| `emission.getCurrent` | `chainId?` | Current epoch number, daily emission amount, total weight, settled epoch |
| `emission.getSchedule` | `chainId?` | Emission projections: 30-day, 90-day, 365-day cumulative with decay applied |
| `emission.getGlobalSchedule` | none | Same projections but aggregated across all 4 chains |
| `emission.listEpochs` | `chainId?`, `page?`, `limit?` | Paginated list of settled epochs with emission totals |
| `emission.getEpochDetail` | `epochId?`, `chainId` **(required)** | Detailed breakdown: per-recipient AWP distributions for a specific epoch |

### 3.8 Tokens

| Method | Params | Description |
|--------|--------|-------------|
| `tokens.getAWP` | `chainId?` | AWP token info: totalSupply, maxSupply, circulatingSupply (per chain) |
| `tokens.getAWPGlobal` | none | AWP info aggregated across all chains |
| `tokens.getAlphaInfo` | `worknetId` **(required)** | Alpha token info: address, name, symbol, totalSupply, minter |
| `tokens.getAlphaPrice` | `worknetId` **(required)** | Alpha/AWP price from LP pool (cached 10min in Redis). Returns sqrtPriceX96 and human-readable price. |

### 3.9 Governance

| Method | Params | Description |
|--------|--------|-------------|
| `governance.listProposals` | `status?`, `chainId?`, `page?`, `limit?` | List proposals. Status filter: `Active`/`Canceled`/`Defeated`/`Succeeded`/`Queued`/`Expired`/`Executed` |
| `governance.listAllProposals` | `status?`, `page?`, `limit?` | Cross-chain proposal list |
| `governance.getProposal` | `proposalId` **(required)**, `chainId?` | Proposal details: description, votes (for/against/abstain), state, targets, calldatas |
| `governance.getTreasury` | none | Returns treasury contract address |

### 3.10 Announcements

Protocol announcements (maintenance, governance, emission updates, security alerts). REST-only endpoints — not available via JSON-RPC.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/announcements` | GET | List active announcements. Query params: `chainId?`, `category?`, `limit?` (default 20), `offset?` (default 0) |
| `GET /api/announcements/{id}` | GET | Get single announcement by numeric ID |
| `GET /api/announcements/llm-context` | GET | All active announcements formatted as a single text block for LLM context injection. Query: `chainId?` |

#### Announcement Object

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

## 4. User-Facing Smart Contract Functions

### 4.1 AWPRegistry (`0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A`) — Account System

```solidity
// ── Binding (tree-based account linking) ──
// Agent calls bind(owner) to join owner's tree. Rewards flow to root.
function bind(address target) external;
// Unbind from current target (become independent root again)
function unbind() external;

// ── Reward Recipient ──
// Set where your rewards go. Default: rewards go to self.
// register() is equivalent to setRecipient(msg.sender) — marks address as active.
function setRecipient(address addr) external;

// ── Delegation ──
// Authorize another address to allocate/deallocate on your behalf
function grantDelegate(address delegate) external;
// Revoke delegation
function revokeDelegate(address delegate) external;

// ── View Functions ──
// Walk bind chain from addr to root, return the root's recipient (or root itself if no recipient set)
function resolveRecipient(address addr) external view returns (address);
// Batch version (up to 500 addresses, single on-chain call)
function batchResolveRecipients(address[] calldata addrs) external view returns (address[] memory);
// True if address has ever called register/setRecipient/bind
function isRegistered(address addr) external view returns (bool);
// Direct storage reads
function boundTo(address) external view returns (address);      // who this address is bound to (0x0 if none)
function recipient(address) external view returns (address);    // explicit recipient (0x0 if not set)
function delegates(address user, address delegate) external view returns (bool); // delegation check
function nonces(address) external view returns (uint256);       // EIP-712 nonce (auto-increments)
```

### 4.2 AWPRegistry — Worknet Management

```solidity
// Registration parameters
struct WorknetParams {
    string name;              // Alpha Token name (1-64 chars, no double-quotes or backslash)
    string symbol;            // Alpha Token symbol (1-16 chars, same restrictions)
    address worknetManager;   // Custom manager contract, or address(0) to auto-deploy a default one
    bytes32 salt;             // CREATE2 salt for Alpha token (bytes32(0) = use worknetId as salt)
    uint128 minStake;         // Minimum stake hint for agents (stored on-chain but NOT enforced by contracts)
    string skillsURI;         // URI pointing to off-chain skills/capabilities description (IPFS, HTTPS, etc.)
}

// Register a new worknet. Costs initialAlphaMint * initialAlphaPrice AWP (currently 100,000 AWP).
// Caller must approve AWPRegistry to spend AWP BEFORE calling.
// Returns a globally unique worknetId. Initial status: Pending.
function registerWorknet(WorknetParams calldata params) external returns (uint256 worknetId);

// ── Lifecycle transitions (caller must own the WorknetNFT) ──
// Pending -> Active: deploys Alpha token, creates AWP/Alpha LP pool, mints Alpha to LP
function activateWorknet(uint256 worknetId) external;
// Pending -> None: cancels registration, returns ALL escrowed AWP to NFT owner
function cancelWorknet(uint256 worknetId) external;
// Active -> Paused: temporarily suspends the worknet (emission continues but can be excluded by Guardian)
function pauseWorknet(uint256 worknetId) external;
// Paused -> Active: resumes the worknet
function resumeWorknet(uint256 worknetId) external;

// ── View Functions ──
function getWorknet(uint256 worknetId) external view returns (WorknetInfo memory);
function getWorknetFull(uint256 worknetId) external view returns (WorknetFullInfo memory);
function getActiveWorknetCount() external view returns (uint256);
function isWorknetActive(uint256 worknetId) external view returns (bool);
function initialAlphaPrice() external view returns (uint256);   // Currently 1e15 (0.001 AWP per Alpha)
function initialAlphaMint() external view returns (uint256);    // Currently 100,000,000 (100M Alpha tokens)
```

### 4.3 StakeNFT (`0x4E119560632698Bab67cFAB5d8EC0A373363ba2d`) — AWP Staking

```solidity
// Deposit AWP and mint a position NFT. lockDuration in seconds (min 1 day).
// Caller must approve StakeNFT to spend AWP first.
function deposit(uint256 amount, uint64 lockDuration) external returns (uint256 tokenId);

// Same as deposit but uses ERC-2612 permit (no prior approve needed — user signs a permit off-chain)
function depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external returns (uint256 tokenId);

// Add more AWP to an existing position. Caller must own the NFT.
// BLOCKED if lock has expired (must withdraw and re-deposit). Can extend lock via newLockEndTime.
function addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime) external;

// Withdraw all AWP and burn the NFT. Only after lock expires.
// REVERTS if any allocations are still active (must deallocate first).
function withdraw(uint256 tokenId) external;

// ── View Functions ──
function getUserTotalStaked(address user) external view returns (uint256); // O(1) total across all positions
function getVotingPower(uint256 tokenId) external view returns (uint256); // amount * sqrt(remainingLockTime)
function remainingTime(uint256 tokenId) external view returns (uint64);   // seconds until lock expires
```

### 4.4 StakingVault (`0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b`) — Allocation

```solidity
// Allocate staked AWP to an agent in a worknet.
// Authorization: msg.sender must be staker OR an authorized delegate of staker.
// worknetId must be non-zero. amount must not exceed available (staked - allocated).
// The worknet does NOT need to be on the same chain — worknetId is globally unique.
function allocate(address staker, address agent, uint256 worknetId, uint256 amount) external;

// Deallocate (reverse of allocate). Same authorization rules.
function deallocate(address staker, address agent, uint256 worknetId, uint256 amount) external;

// Atomic move: deallocate from one (agent, worknet) and allocate to another in a single tx.
function reallocate(
    address staker,
    address fromAgent, uint256 fromWorknetId,
    address toAgent, uint256 toWorknetId,
    uint256 amount
) external;

// ── View Functions ──
function userTotalAllocated(address user) external view returns (uint256);
function getAgentStake(address user, address agent, uint256 worknetId) external view returns (uint256);
function getAgentWorknets(address user, address agent) external view returns (uint256[] memory); // all worknetIds
function nonces(address) external view returns (uint256); // EIP-712 nonce for StakingVault domain
```

### 4.5 WorknetManager — Per-Worknet Operations

Each active worknet has its own WorknetManager proxy. The address is stored in WorknetNFT and returned by `subnets.get`.

```solidity
// ── Merkle Claim (any user with a valid proof can claim Alpha tokens) ──
// The worknet admin submits Merkle roots per epoch; users claim with proof.
function claim(uint32 epoch, uint256 amount, bytes32[] calldata proof) external;
function isClaimed(uint32 epoch, address account) external view returns (bool);

// ── View Functions ──
function alphaToken() external view returns (address);      // This worknet's Alpha token
function poolId() external view returns (bytes32);          // LP pool ID (for DEX queries)
function currentStrategy() external view returns (uint8);   // 0=Reserve, 1=AddLiquidity, 2=BuybackBurn
function slippageBps() external view returns (uint256);     // Slippage tolerance in basis points
function strategyPaused() external view returns (bool);     // Whether auto-strategy is paused
```

### 4.6 AWPDAO (`0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004`) — Governance

```solidity
// ── Propose (caller must hold StakeNFT positions with sufficient voting power) ──
// Submit an executable proposal (targets + calldatas executed via Treasury timelock)
function proposeWithTokens(
    address[] memory targets, uint256[] memory values, bytes[] memory calldatas,
    string memory description, uint256[] memory tokenIds
) external returns (uint256 proposalId);

// Signal-only proposal (no on-chain execution, for off-chain governance signals)
function signalPropose(string memory description, uint256[] memory tokenIds) external returns (uint256);

// ── Vote ──
// tokenIds are passed in params: params = abi.encode(uint256[] tokenIds)
// Each tokenId can only vote once per proposal. Anti-manipulation: tokenId.createdAt must be < proposal creation time.
// support: 0=Against, 1=For, 2=Abstain
function castVoteWithReasonAndParams(
    uint256 proposalId, uint8 support, string calldata reason, bytes memory params
) external returns (uint256 weight);

// ── View Functions ──
function state(uint256 proposalId) external view returns (uint8);
// States: 0=Pending, 1=Active, 2=Canceled, 3=Defeated, 4=Succeeded, 5=Queued, 6=Expired, 7=Executed
function proposalVotes(uint256 proposalId) external view returns (uint256 against, uint256 forVotes, uint256 abstain);
function votingDelay() external view returns (uint256);     // Blocks before voting starts
function votingPeriod() external view returns (uint256);    // Blocks voting is open
function proposalThreshold() external view returns (uint256); // Min voting power to propose
```

---

## 5. Gasless Relay Endpoints

Users sign EIP-712 typed data off-chain; the relayer submits the transaction on-chain and pays gas. Rate limited to 100 requests per IP per hour.

### Endpoints

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
| `GET /api/relay/status/{txHash}` | Check relay tx status | — |

### Request Format Examples

**Register (simplest — user registers themselves):**
```json
POST /api/relay/register
{
  "chainId": 8453,
  "user": "0xUserAddress...",
  "deadline": 1712345678,
  "v": 27,
  "r": "0x...(32 bytes hex)...",
  "s": "0x...(32 bytes hex)..."
}
```

**Bind:**
```json
POST /api/relay/bind
{
  "chainId": 8453,
  "agent": "0xAgentAddress...",
  "target": "0xOwnerAddress...",
  "deadline": 1712345678,
  "v": 27, "r": "0x...", "s": "0x..."
}
```

**Allocate:**
```json
POST /api/relay/allocate
{
  "chainId": 8453,
  "staker": "0x...",
  "agent": "0x...",
  "worknetId": "36364510078353408001",
  "amount": "1000000000000000000000",
  "deadline": 1712345678,
  "v": 27, "r": "0x...", "s": "0x..."
}
```

**Response (all relay endpoints):**
```json
{"txHash": "0x..."}
```

**Error response:**
```json
{"error": "invalid EIP-712 signature"}
```

### EIP-712 Domains

**AWPRegistry domain** (bind, unbind, setRecipient, grantDelegate, revokeDelegate, registerWorknet, activateWorknet):
```json
{
  "name": "AWPRegistry",
  "version": "1",
  "chainId": 8453,
  "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
}
```

**StakingVault domain** (allocate, deallocate):
```json
{
  "name": "StakingVault",
  "version": "1",
  "chainId": 8453,
  "verifyingContract": "0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b"
}
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

---

## 6. Vanity Salt Endpoints

For offline mining of vanity Alpha token CREATE2 addresses:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/vanity/mining-params` | GET | Returns `{factoryAddress, initCodeHash, vanityRule}` needed for offline salt mining |
| `POST /api/vanity/upload-salts` | POST | Upload pre-mined `{salts: [{salt, address}, ...]}`. Rate limited: 5/hr/IP |
| `GET /api/vanity/salts/count` | GET | Number of available (unused) salts in the pool |
| `POST /api/vanity/compute-salt` | POST | Server-side computation. Returns `{salt, address, source: "pool"\|"mined", elapsed}` |

---

## 7. WebSocket Real-Time Events

**Endpoint**: `wss://api.awp.sh/ws/live`

Connect via standard WebSocket. Events are pushed as JSON messages. No subscription filtering — all events for all chains are broadcast.

| Event | Key Fields | Description |
|-------|------------|-------------|
| `UserRegistered` | `user`, `chainId` | Address called register() or setRecipient() for the first time |
| `Bound` | `user`, `target`, `chainId` | Agent bound to target |
| `Unbound` | `user`, `chainId` | Agent unbound from tree |
| `RecipientSet` | `user`, `recipient`, `chainId` | Reward recipient changed |
| `DelegateGranted` | `user`, `delegate`, `chainId` | Delegate authorized |
| `DelegateRevoked` | `user`, `delegate`, `chainId` | Delegate revoked |
| `Deposited` | `user`, `tokenId`, `amount`, `lockEndTime`, `chainId` | AWP deposited to StakeNFT |
| `Withdrawn` | `user`, `tokenId`, `amount`, `chainId` | AWP withdrawn from StakeNFT |
| `Allocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` | Stake allocated to agent in worknet |
| `Deallocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` | Stake deallocated |
| `Reallocated` | `staker`, `fromAgent`, `fromWorknetId`, `toAgent`, `toWorknetId`, `amount`, `chainId` | Atomic reallocation |
| `WorknetRegistered` | `worknetId`, `owner`, `name`, `symbol`, `chainId` | New worknet created (Pending) |
| `WorknetActivated` | `worknetId`, `chainId` | Worknet activated (LP created) |
| `WorknetCancelled` | `worknetId`, `chainId` | Worknet cancelled (AWP refunded) |
| `EpochSettled` | `epoch`, `totalEmission`, `recipientCount`, `chainId` | Emission epoch settled |
| `RecipientAWPDistributed` | `epoch`, `recipient`, `amount`, `chainId` | AWP minted to worknet |
| `AllocationsSubmitted` | `epoch`, `totalWeight`, `recipients`, `weights`, `chainId` | Guardian submitted weights |
| `LPManagerUpdated` | `newLPManager`, `chainId` | LPManager address updated |
| `DefaultWorknetManagerImplUpdated` | `newImpl`, `chainId` | WorknetManager implementation updated |

---

## 8. Key Protocol Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| AWP Max Supply | 10,000,000,000 (10B) | Hard cap across all chains. Each chain has independent mint. |
| Initial Daily Emission | 31,600,000 AWP | Per chain per epoch. Subject to decay. |
| Decay Factor | 996844 / 1,000,000 | ~0.3156% reduction per epoch. Formula: `emission *= 996844 / 1000000` |
| Epoch Duration | 1 day (86,400 seconds) | Each epoch = 1 calendar day |
| Worknet Registration Cost | 100,000 AWP | `initialAlphaMint (100M) * initialAlphaPrice (0.001)`. Escrowed until activation or refunded on cancel. |
| Alpha Tokens per Worknet | 100,000,000 (100M) | Minted to LP pool on activation |
| Initial Alpha Price | 0.001 AWP per Alpha | `1e15 wei`. Determines AWP escrow and LP ratio. |
| Min Lock Duration (StakeNFT) | 1 day (86,400 seconds) | Minimum lock when depositing |
| Max Voting Weight Duration | 54 weeks | Voting power formula: `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)` |
| Timelock Delay (Treasury) | 2 days (172,800 seconds) | DAO proposals require 2-day waiting period before execution |
| LP Pool Fee | 10,000 bps (1%) | Uniswap V4 / PancakeSwap V4 pool fee tier |
| LP Tick Spacing | 200 | Determines price granularity in LP pools |
| Max Active Worknets | 10,000 | Per chain. Hard limit in AWPRegistry. |
| Max Emission Recipients | 10,000 | Per chain per epoch. Hard limit in AWPEmission. |
| WorknetId Format | `(chainId << 64) \| localCounter` | 256-bit globally unique identifier |

---

## 9. Common User Workflows

### 9.1 Stake AWP and Earn Voting Power
1. **Approve**: `AWPToken.approve(StakeNFT, amount)` — or skip if using `depositWithPermit`
2. **Deposit**: `StakeNFT.deposit(amount, lockDurationInSeconds)` — returns `tokenId`
   - Example: lock 1000 AWP for 30 days: `deposit(1000e18, 2592000)`
3. **Verify**: Call `staking.getBalance(address)` or `staking.getPositions(address)`
4. **Withdraw** (after lock expires): `StakeNFT.withdraw(tokenId)` — must deallocate all first

### 9.2 Allocate Stake to an Agent in a Worknet
1. **Check available**: `staking.getBalance(address)` — `available = totalStaked - totalAllocated`
2. **Allocate**: `StakingVault.allocate(staker, agent, worknetId, amount)`
   - `staker` = the address whose stake to use (must be msg.sender or msg.sender is their delegate)
   - `agent` = the agent address receiving the allocation
   - `worknetId` = target worknet (decimal string, e.g., `36364510078353408001`)
3. **Verify**: `staking.getAllocations(address)` or `staking.getAgentSubnetStake(agent, worknetId)`

### 9.3 Register and Activate a Worknet
1. **Approve AWP**: `AWPToken.approve(AWPRegistry, 100000e18)` (100,000 AWP registration cost)
2. **Register**: `AWPRegistry.registerWorknet({name: "MyNet", symbol: "MNT", worknetManager: address(0), salt: bytes32(0), minStake: 0, skillsURI: "https://..."})` — returns `worknetId`, status = `Pending`
3. **Activate**: `AWPRegistry.activateWorknet(worknetId)` — deploys Alpha token, creates LP pool, status = `Active`
4. **Verify**: `subnets.get(worknetId)` — should show `status: "Active"`
5. **Cancel instead** (optional): `AWPRegistry.cancelWorknet(worknetId)` — full AWP refund, status = `None`

### 9.4 Bind an Agent to an Owner
1. **Agent calls**: `AWPRegistry.bind(ownerAddress)` — agent binds to owner's tree
2. **Verify**: `address.check(agentAddress)` — `boundTo` shows the owner
3. **Unbind**: `AWPRegistry.unbind()` — agent becomes independent root again

### 9.5 Set a Reward Recipient
1. **Set**: `AWPRegistry.setRecipient(recipientAddress)` — rewards flow to this address
2. **Verify**: `address.resolveRecipient(yourAddress)` — should return `recipientAddress`
3. **Reset to self**: `AWPRegistry.setRecipient(yourOwnAddress)`

### 9.6 Delegate Staking Operations
1. **Grant**: `AWPRegistry.grantDelegate(delegateAddress)` — delegate can now allocate/deallocate on your behalf
2. **Delegate acts**: `StakingVault.allocate(yourAddress, agent, worknetId, amount)` — called by delegate
3. **Revoke**: `AWPRegistry.revokeDelegate(delegateAddress)`

### 9.7 Vote on a DAO Proposal
1. **Requirements**: Hold StakeNFT positions minted BEFORE the proposal was created
2. **Vote**: `AWPDAO.castVoteWithReasonAndParams(proposalId, 1, "I support this", abi.encode([tokenId1, tokenId2]))`
   - support: 0=Against, 1=For, 2=Abstain
3. **Check**: `governance.getProposal(proposalId)` — see vote tallies and state

### 9.8 Gasless Registration (via Relay)
1. **Fetch nonce**: `nonce.get({address: "0x...", chainId: 8453})`
2. **Sign EIP-712**: Sign `SetRecipient(user=0x..., recipient=0x..., nonce=N, deadline=T)` with AWPRegistry domain for chainId 8453
3. **Submit**: `POST /api/relay/register` with `{chainId: 8453, user: "0x...", deadline: T, v, r, s}`
4. **Check**: Poll `GET /api/relay/status/{txHash}` until confirmed, then `address.check({address: "0x...", chainId: 8453})`

### 9.9 Gasless Stake Allocation (via Relay)
1. **Fetch nonce**: `nonce.getStaking({address: "0x...", chainId: 8453})`
2. **Sign EIP-712**: Sign `Allocate(staker, agent, worknetId, amount, nonce, deadline)` with StakingVault domain
3. **Submit**: `POST /api/relay/allocate` with all fields + signature
4. **Check**: `staking.getAgentSubnetStake({agent, worknetId})`
