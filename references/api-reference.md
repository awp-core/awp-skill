# AWP Skill — API Reference

Quick index of JSON-RPC 2.0 methods and relay endpoints. For write operations, see the dedicated command files:
- **commands-staking.md** — S1 Register/Bind, S2 Deposit, S3 Allocate
- **commands-worknet.md** — M1 Register Worknet, M2 Lifecycle, M3-M4 Settings
- **commands-governance.md** — G1 Proposals, G2 Voting, G3/G4 Queries, Supplementary

---

## API Transport

| Transport | URL | Notes |
|-----------|-----|-------|
| JSON-RPC 2.0 | `POST https://api.awp.sh/v2` | All read queries |
| Discovery | `GET https://api.awp.sh/v2` | Method listing |
| WebSocket | `wss://api.awp.sh/ws/live` | Real-time events |
| Batch | `POST https://api.awp.sh/v2` | Up to 20 requests per batch, executed concurrently |
| Health Check | `GET https://api.awp.sh/api/health` | REST health endpoint |

### Request/Response Format

```json
// Request
{"jsonrpc": "2.0", "method": "namespace.method", "params": {...}, "id": 1}

// Batch Request
[
  {"jsonrpc": "2.0", "method": "health.check", "params": {}, "id": 1},
  {"jsonrpc": "2.0", "method": "stats.global", "params": {}, "id": 2}
]

// Success
{"jsonrpc": "2.0", "result": {...}, "id": 1}

// Error
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "method not found"}, "id": 1}
```

### Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32001 | Resource not found |

### Common Parameters

- `address`: `string` — 0x-prefixed, 40 hex chars, case-insensitive
- `worknetId`: `string` — Globally unique: `chainId * 100_000_000 + localId`, passed as decimal string
- `chainId`: `integer` — Optional on most methods; omit for all-chain aggregation, specify for single-chain
- `page`: `integer` — 1-indexed (default 1)
- `limit`: `integer` — Items per page (default 20, max 100)
- `status`: `string` — Enum. Worknet: `"Pending"`, `"Active"`, `"Paused"`, `"Banned"`. Proposal: `"Active"`, `"Canceled"`, `"Defeated"`, `"Succeeded"`, `"Queued"`, `"Expired"`, `"Executed"`

---

## JSON-RPC Methods

### System

| Method | Params | Description |
|--------|--------|-------------|
| `stats.global` | — | Global protocol stats (users, worknets, staked, emitted, chains) |
| `registry.get` | `chainId?` | Contract addresses + EIP-712 domain for one chain. Omit chainId → single dict for the default chain |
| `registry.list` | — | Contract addresses for all chains (returns array of per-chain entries) |
| `health.check` | — | `{"status": "ok"}` |
| `health.detailed` | — | Per-chain indexer/keeper status |
| `chains.list` | — | Supported chains array |

### Users

| Method | Params | Description |
|--------|--------|-------------|
| `users.list` | `chainId?`, `page?`, `limit?` | Paginated user list |
| `users.listGlobal` | `page?`, `limit?` | Cross-chain deduplicated |
| `users.count` | `chainId?` | Total user count |
| `users.get` | `address` (required), `chainId?` | User details (balance, agents, recipient) |
| `users.getPortfolio` | `address` (required), `chainId?` | Full portfolio: identity + balance + positions + allocations + delegates |
| `users.getDelegates` | `address` (required), `chainId?` | Agents bound to user |

### Address & Nonce

| Method | Params | Description |
|--------|--------|-------------|
| `address.check` | `address` (required), `chainId?` | Registration, binding, recipient. **Omit chainId → returns all chains where registered**. See response formats below |
| `address.resolveRecipient` | `address` (required), `chainId?` | Walk bind chain to root, return recipient |
| `address.batchResolveRecipients` | `addresses[]` (required, max 500), `chainId?` | Batch resolve |
| `nonce.get` | `address` (required), `chainId?` | AWPRegistry EIP-712 nonce |
| `nonce.getStaking` | `address` (required), `chainId?` | AWPAllocator EIP-712 nonce |

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

### Agents

| Method | Params | Description |
|--------|--------|-------------|
| `agents.getByOwner` | `owner` (required), `chainId?` | All agents bound to owner |
| `agents.getDetail` | `agent` (required), `chainId?` | Agent details |
| `agents.lookup` | `agent` (required), `chainId?` | Returns `{"ownerAddress": "0x..."}` |
| `agents.batchInfo` | `agents[]` (required, max 100), `worknetId` (required), `chainId?` | Batch agent info + stake |

### Staking

| Method | Params | Description |
|--------|--------|-------------|
| `staking.getBalance` | `address` (required), `chainId?` | Returns `{totalStaked, totalAllocated, unallocated}` in wei strings |
| `staking.getUserBalanceGlobal` | `address` (required) | Aggregated across all chains |
| `staking.getPositions` | `address` (required), `chainId?` | veAWP positions |
| `staking.getPositionsGlobal` | `address` (required) | Positions across all chains (includes `chainId` per position) |
| `staking.getAllocations` | `address` (required), `chainId?`, `page?`, `limit?` | Allocation records |
| `staking.getAgentWorknetStake` | `agent` (required), `worknetId` (required) | Agent's stake in worknet (cross-chain) |
| `staking.getAgentWorknets` | `agent` (required) | All worknets agent participates in |
| `staking.getWorknetTotalStake` | `worknetId` (required) | Total stake in worknet |
| `staking.getFrozen` | `address` (required), `chainId?` | Frozen allocations |

### Worknets (worknets.*)

| Method | Params | Description |
|--------|--------|-------------|
| `subnets.list` | `status?`, `chainId?`, `page?`, `limit?` | Filter: `Pending`/`Active`/`Paused`/`Banned` |
| `subnets.listRanked` | `chainId?`, `page?`, `limit?` | Ranked by total stake |
| `subnets.search` | `query` (required, 1-100 chars), `chainId?`, `page?`, `limit?` | Name/symbol search |
| `subnets.getByOwner` | `owner` (required), `chainId?`, `page?`, `limit?` | Worknets owned by address |
| `subnets.get` | `worknetId` (required) | Worknet details |
| `subnets.getSkills` | `worknetId` (required) | Skills URI |
| `subnets.getEarnings` | `worknetId` (required), `page?`, `limit?` | AWP earnings history |
| `subnets.getAgentInfo` | `worknetId` (required), `agent` (required) | Agent info in worknet |
| `subnets.listAgents` | `worknetId` (required), `chainId?`, `page?`, `limit?` | Agents ranked by stake |

### Emission

| Method | Params | Description |
|--------|--------|-------------|
| `emission.getCurrent` | `chainId?` | Current epoch, daily emission, total weight |
| `emission.getSchedule` | `chainId?` | 30/90/365 day projections with decay |
| `emission.getGlobalSchedule` | — | Aggregated across all chains |
| `emission.listEpochs` | `chainId?`, `page?`, `limit?` | Settled epochs |
| `emission.getEpochDetail` | `epochId` (required), `chainId?` | Per-recipient distributions |

### Tokens

| Method | Params | Description |
|--------|--------|-------------|
| `tokens.getAWP` | `chainId?` | AWP supply, max supply |
| `tokens.getAWPGlobal` | — | Aggregated across chains |
| `tokens.getWorknetTokenInfo` | `worknetId` (required) | Alpha token info |
| `tokens.getWorknetTokenPrice` | `worknetId` (required) | Price from LP pool (cached 10min) |

### Governance

| Method | Params | Description |
|--------|--------|-------------|
| `governance.listProposals` | `status?`, `chainId?`, `page?`, `limit?` | Filter: `Active`/`Canceled`/`Defeated`/`Succeeded`/`Queued`/`Expired`/`Executed` |
| `governance.listAllProposals` | `status?`, `page?`, `limit?` | Cross-chain |
| `governance.getProposal` | `proposalId` (required), `chainId?` | Proposal details |
| `governance.getTreasury` | — | Treasury address |

### Announcements (REST)

| Endpoint | Description |
|----------|-------------|
| `GET /api/announcements` | List active announcements. Query: `chainId?`, `category?`, `limit?` (default 20), `offset?` (default 0) |
| `GET /api/announcements/{id}` | Get single announcement by ID |
| `GET /api/announcements/llm-context` | Formatted for LLM consumption. Query: `chainId?` |

Categories: `general`, `maintenance`, `governance`, `emission`, `security`. Priority: 0=info, 1=warning, 2=critical.

---

## Gasless Relay Endpoints (REST)

Relay endpoints use REST (not JSON-RPC). Users sign EIP-712 messages off-chain; the relayer submits the transaction and pays gas.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/relay/bind` | RelayBind | Gasless bind |
| `POST /api/relay/unbind` | RelayUnbind | Gasless unbind |
| `POST /api/relay/set-recipient` | RelaySetRecipient | Gasless setRecipient |
| `POST /api/relay/register` | RelayRegister | Gasless register (= setRecipientFor to self) |
| `POST /api/relay/allocate` | RelayAllocate | Gasless allocate |
| `POST /api/relay/deallocate` | RelayDeallocate | Gasless deallocate |
| `POST /api/relay/activate-worknet` | RelayActivateWorknet | Gasless activate worknet |
| `POST /api/relay/register-worknet` | RelayRegisterWorknet | Gasless register worknet (with permit) |
| `POST /api/relay/grant-delegate` | RelayGrantDelegate | Gasless grant delegate |
| `POST /api/relay/revoke-delegate` | RelayRevokeDelegate | Gasless revoke delegate |
| `GET /api/relay/status/{txHash}` | GetRelayStatus | Check relay tx status |

### Relay Request Format Examples

**Register** (simplest — user registers themselves):
```json
POST /api/relay/register
{
  "chainId": 8453,
  "user": "0xUserAddress...",
  "deadline": 1712345678,
  "signature": "0x...(65 bytes hex)..."
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
  "signature": "0x...(65 bytes hex)..."
}
```

**Allocate:**
```json
POST /api/relay/allocate
{
  "chainId": 8453,
  "staker": "0x...",
  "agent": "0x...",
  "worknetId": "845300000001",
  "amount": "1000000000000000000000",
  "deadline": 1712345678,
  "signature": "0x...(65 bytes hex)..."
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

### Relay Status Check

```
GET /api/relay/status/{txHash}
```

Returns the current status of a relay transaction by its hash.

> Rate limit: 100 requests per IP per 1 hour (shared across all relay endpoints).

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

**Nonce workflow**: Always fetch the current nonce via `nonce.get` (AWPRegistry) or `nonce.getStaking` (AWPAllocator) immediately before signing. Nonces auto-increment after each successful relay. Using a stale nonce causes `InvalidSignature` error.

---

## Contract Quick Reference

### AWPRegistry — Account System

```solidity
// Binding
bind(address target)                          // Tree-based binding with anti-cycle check
unbind()                                       // Unbind from current target

// Recipient
setRecipient(address recipient)               // Set reward recipient

// Delegation
grantDelegate(address delegate)               // Grant delegation
revokeDelegate(address delegate)              // Revoke delegation

// View
resolveRecipient(address addr) view           // Walk boundTo chain to root
batchResolveRecipients(address[] addrs) view  // Batch resolve
isRegistered(address addr) view               // boundTo[addr] != 0 || recipient[addr] != 0
boundTo(address) view                         // Direct binding target
recipient(address) view                       // Reward recipient
delegates(address user, address delegate) view // Delegation check
nonces(address) view                          // EIP-712 nonce
```
> EIP-712 domain name: `"AWPRegistry"`.
> `unbind()` is available — unbinds msg.sender from current target.

### AWPRegistry — Worknet Management

```solidity
struct WorknetParams {
    string name;              // Alpha Token name (1-64 chars, no " or \)
    string symbol;            // Alpha Token symbol (1-16 chars, no " or \)
    address worknetManager;   // 0x0 = auto-deploy WorknetManager proxy
    bytes32 salt;             // CREATE2 salt (0x0 = use worknetId)
    uint128 minStake;         // Min stake for agents (reference only)
    string skillsURI;         // Skills description URI
}

registerWorknet(WorknetParams params) returns (uint256 worknetId)  // Costs ~1,000,000 AWP (dynamic)
activateWorknet(uint256 worknetId)    // Pending -> Active, Guardian only
pauseWorknet(uint256 worknetId)       // Active -> Paused, AWPWorkNet owner only
resumeWorknet(uint256 worknetId)      // Paused -> Active, AWPWorkNet owner only
cancelWorknet(uint256 worknetId)      // Pending -> None (full AWP refund), AWPWorkNet owner only

// View
getWorknet(uint256 worknetId) view
getWorknetFull(uint256 worknetId) view
getActiveWorknetCount() view
isWorknetActive(uint256 worknetId) view
initialAlphaPrice() view
initialAlphaMint() view
```

### veAWP — AWP Staking

```solidity
deposit(uint256 amount, uint64 lockDuration) returns (uint256 tokenId)  // User must approve veAWP
depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) returns (uint256 tokenId)
addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime)
withdraw(uint256 tokenId)                     // After lock expires, burns NFT

// View
getUserTotalStaked(address user) view returns (uint256)
getVotingPower(uint256 tokenId) view returns (uint256)
remainingTime(uint256 tokenId) view returns (uint64)
```

### AWPAllocator — Allocation

```solidity
// Caller must be staker or staker's delegate (NOT onlyAWPRegistry)
allocate(address staker, address agent, uint256 worknetId, uint256 amount)
deallocate(address staker, address agent, uint256 worknetId, uint256 amount)
reallocate(address staker, address fromAgent, uint256 fromWorknetId, address toAgent, uint256 toWorknetId, uint256 amount)

// View
userTotalAllocated(address user) view returns (uint256)
getAgentStake(address user, address agent, uint256 worknetId) view returns (uint256)
getAgentWorknets(address user, address agent) view returns (uint256[])
nonces(address) view returns (uint256)        // AWPAllocator EIP-712 nonce (separate from AWPRegistry)
```
> AWPAllocator has its own EIP-712 domain (`"AWPAllocator"`, verifyingContract: `0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA`).

### WorknetManager — Per-Worknet Operations

```solidity
// Merkle claim (any user with valid proof)
claim(uint32 epoch, uint256 amount, bytes32[] calldata proof)
isClaimed(uint32 epoch, address account) view returns (bool)

// View
alphaToken() view returns (address)
poolId() view returns (bytes32)
currentStrategy() view returns (uint8)    // 0=Reserve, 1=AddLiquidity, 2=BuybackBurn
slippageBps() view returns (uint256)      // Slippage tolerance in basis points
strategyPaused() view returns (bool)      // Whether auto-strategy is paused
```

---

## WebSocket Events

**Endpoint**: `wss://api.awp.sh/ws/live`

Events pushed as JSON messages with envelope:
```json
{"type": "EventName", "blockNumber": 12345, "txHash": "0x...", "data": {...}}
```

| Event | Source | Key Fields | Description |
|-------|--------|------------|-------------|
| `Bound` | AWPRegistry | `addr`, `target` | Agent bound to target |
| `Unbound` | AWPRegistry | `addr` | Agent unbound |
| `RecipientSet` | AWPRegistry | `addr`, `recipient` | Recipient changed |
| `DelegateGranted` | AWPRegistry | `staker`, `delegate` | Delegate granted |
| `DelegateRevoked` | AWPRegistry | `staker`, `delegate` | Delegate revoked |
| `StakePositionCreated` | veAWP | `user`, `tokenId`, `amount`, `lockEndTime` | AWP staked (new position) |
| `StakePositionIncreased` | veAWP | `tokenId`, `addedAmount`, `newLockEndTime` | AWP added to position |
| `StakePositionClosed` | veAWP | `user`, `tokenId`, `amount` | Position withdrawn |
| `Allocated` | AWPAllocator | `staker`, `agent`, `worknetId`, `amount`, `operator` | Stake allocated |
| `Deallocated` | AWPAllocator | `staker`, `agent`, `worknetId`, `amount`, `operator` | Stake deallocated |
| `Reallocated` | AWPAllocator | `staker`, `fromAgent`, `fromWorknetId`, `toAgent`, `toWorknetId`, `amount` | Reallocation |
| `WorknetRegistered` | AWPRegistry | `worknetId`, `owner`, `name`, `symbol` | New worknet |
| `WorknetActivated` | AWPRegistry | `worknetId` | Worknet activated |
| `WorknetPaused` | AWPRegistry | `worknetId` | Worknet paused |
| `WorknetResumed` | AWPRegistry | `worknetId` | Worknet resumed |
| `WorknetBanned` | AWPRegistry | `worknetId` | Worknet banned |
| `WorknetUnbanned` | AWPRegistry | `worknetId` | Worknet unbanned |
| `WorknetRejected` | AWPRegistry | `worknetId` | Worknet rejected |
| `WorknetCancelled` | AWPRegistry | `worknetId` | Worknet cancelled |
| `WorknetNFTTransfer` | AWPWorkNet | `from`, `to`, `tokenId` | Worknet NFT transferred |
| `EpochSettled` | AWPEmission | `epoch`, `totalEmission`, `recipientCount` | Epoch settled |
| `AllocationsSubmitted` | AWPEmission | `epoch`, `totalWeight`, `recipients[]`, `weights[]` | Weights submitted |
| `GuardianUpdated` | AWPRegistry | `newGuardian` | Guardian changed |
| `InitialAlphaPriceUpdated` | AWPRegistry | `newPrice` | Initial price changed |
| `WorknetTokenFactoryUpdated` | AWPRegistry | `newFactory` | Factory changed |

All 25 events include `chainId`, `blockNumber`, `txHash` alongside their event-specific fields.

For data structures, events, and constants, see **protocol.md**.

---

## Vanity Salt Endpoints

For offline mining of vanity Alpha token CREATE2 addresses:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/vanity/mining-params` | GET | Returns `{factoryAddress, initCodeHash, vanityRule}` needed for offline salt mining |
| `POST /api/vanity/upload-salts` | POST | Upload pre-mined `{salts: [{salt, address}, ...]}`. Rate limited: 5/hr/IP |
| `GET /api/vanity/salts/count` | GET | Number of available (unused) salts in the pool |
| `POST /api/vanity/compute-salt` | POST | Server-side computation. Returns `{salt, address, source: "pool"\|"mined", elapsed}` |

---

## Key Protocol Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| AWP Max Supply | 10,000,000,000 (10B) | Hard cap across all chains. Each chain has independent mint. |
| Initial Daily Emission | 31,600,000 AWP | Per chain per epoch. Subject to decay. |
| Decay Factor | 996844 / 1,000,000 | ~0.3156% reduction per epoch. Formula: `emission *= 996844 / 1000000` |
| Epoch Duration | 1 day (86,400 seconds) | Each epoch = 1 calendar day |
| Worknet Registration Cost | ~1,000,000 AWP | `initialAlphaMint (1B) × initialAlphaPrice (0.001) ÷ 1e18`. Guardian-adjustable. Escrowed until activation or refunded on cancel. |
| WorknetTokens per Worknet | 1,000,000,000 (1B) | Minted to LP pool on activation (Guardian-adjustable via setInitialAlphaMint) |
| Initial Alpha Price | 0.001 AWP per Alpha | `1e15 wei`. Determines AWP escrow and LP ratio. |
| Min Lock Duration (veAWP) | 1 day (86,400 seconds) | Minimum lock when depositing |
| Max Voting Weight Duration | 54 weeks | Voting power formula: `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)` |
| Timelock Delay (Treasury) | 2 days (172,800 seconds) | DAO proposals require 2-day waiting period before execution |
| LP Pool Fee | 10,000 bps (1%) | Uniswap V4 / PancakeSwap V4 pool fee tier |
| LP Tick Spacing | 200 | Determines price granularity in LP pools |
| Max Active Worknets | 10,000 | Per chain. Hard limit in AWPRegistry. |
| Max Emission Recipients | 10,000 | Per chain per epoch. Hard limit in AWPEmission. |
| WorknetId Format | `chainId * 100_000_000 + localCounter` | 256-bit globally unique identifier |
