# AWP Protocol — Skill Development Reference

> Complete reference for building Claude Code skills that interact with AWP (Agent Working Protocol). Covers smart contracts, JSON-RPC API, gasless relay, and WebSocket events. User-facing only — admin/guardian functions are excluded.

---

## 1. Protocol Overview

AWP is a multi-chain **agent mining protocol** deployed identically on 4 EVM chains:

| Chain | Chain ID | Explorer |
|-------|----------|----------|
| Base | 8453 | basescan.org |
| Ethereum | 1 | etherscan.io |
| Arbitrum One | 42161 | arbiscan.io |
| BNB Smart Chain | 56 | bscscan.com |

All protocol contracts share the same addresses across all 4 chains (deployed via CREATE2). The only exception is WorknetManager implementation contracts, which differ per chain due to DEX integration (Uniswap V4 on Base/ETH/ARB, PancakeSwap V4 on BSC). Users interact with proxies, so proxy addresses are identical.

### Core Concepts

- **AWP Token**: ERC20 governance/utility token. 10B max supply. Emitted daily via AWPEmission and distributed to worknets. Used for staking, governance, and worknet registration.
- **Worknet**: An autonomous agent network. Each worknet has its own **WorknetToken** (ERC20, 10B max per worknet) and a **liquidity pool** (AWP/WorknetToken pair). Lifecycle: `None -> Pending -> Active -> Paused/Banned`.
- **AWPWorkNet**: ERC721 representing worknet ownership. tokenId = worknetId. Owner can pause/resume/cancel their worknet and update metadata.
- **veAWP**: ERC721 position NFT. Users deposit AWP with a lock period to mint a position. Each position stores (amount, lockEndTime, createdAt). Transferable. Lock must be active to add more AWP.
- **AWPAllocator**: Manages stake allocations. Users allocate their staked AWP to (agent, worknetId) tuples. Supports gasless operations via EIP-712. Authorization: caller must be the staker or an authorized delegate. EIP-712 domain name "AWPAllocator".
- **AWPEmission**: Epoch-based emission engine. Guardian submits per-worknet weights each epoch; `settleEpoch()` mints AWP to recipients proportionally. Exponential decay reduces emission over time.
- **Binding**: Tree-based account linking. An agent calls `bind(owner)` to form a tree. Rewards flow upward to the tree root via `resolveRecipient()`. Cycle detection prevents loops.
- **Delegation**: A user can `grantDelegate(delegate)` to allow the delegate to allocate/deallocate on their behalf.
- **WorknetId**: Globally unique 256-bit identifier: `chainId * 100_000_000 + localId` (human-readable format). Passed as a decimal string in the API (e.g., `"845300000001"`).

---

## 2. Contract Addresses

### Protocol Contracts (identical on all 4 chains)

| Contract | Address | Type |
|----------|---------|------|
| AWPToken | `0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1` | ERC20 (non-upgradeable) |
| AWPRegistry (proxy) | `0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A` | UUPS Proxy |
| AWPEmission (proxy) | `0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9` | UUPS Proxy |
| AWPAllocator (proxy) | `0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA` | UUPS Proxy |
| veAWP | `0x0000b534C63D78212f1BDCc315165852793A00A8` | ERC721 (non-upgradeable) |
| AWPWorkNet (proxy) | `0x00000bfbdEf8533E5F3228c9C846522D906100A7` | UUPS Proxy ERC721 |
| LPManager (proxy) | `0x00001961b9AcCD86b72DE19Be24FaD6f7c5b00A2` | UUPS Proxy |
| WorknetTokenFactory | `0x0000D4996BDBb99c772e3fA9f0e94AB52AAFFAC7` | Non-upgradeable |
| AWPDAO (proxy) | `0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0` | UUPS Proxy Governor |
| Treasury | `0x82562023a053025F3201785160CaE6051efD759e` | TimelockController (2-day delay) |

### WorknetManager Implementations (differ per chain)

| Chain | Address | DEX |
|-------|---------|-----|
| Base (8453) | `0x000011EE4117c52dC0Eb146cBC844cb155B200A9` | Uniswap V4 |
| Ethereum (1) | `0x0000DD4841bB4e66AF61A5E35204C1606b4a00A9` | Uniswap V4 |
| Arbitrum (42161) | `0x000055Ca7d29e8dC7eDEF3892849347214a300A9` | Uniswap V4 |
| BSC (56) | `0x0000269C10feF9B603A228b075F8C99BAE5b00A9` | PancakeSwap V4 |

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
// Request
{"jsonrpc": "2.0", "method": "namespace.method", "params": {...}, "id": 1}

// Batch
[
  {"jsonrpc": "2.0", "method": "users.get", "params": {"address": "0x..."}, "id": 1},
  {"jsonrpc": "2.0", "method": "staking.getBalance", "params": {"address": "0x..."}, "id": 2}
]

// Success
{"jsonrpc": "2.0", "result": {...}, "id": 1}

// Error
{"jsonrpc": "2.0", "error": {"code": -32601, "message": "method not found"}, "id": 1}
```

### Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error (malformed JSON) |
| -32600 | Invalid request (missing jsonrpc/method) |
| -32601 | Method not found |
| -32602 | Invalid params (missing required param, bad address) |
| -32603 | Internal error |
| -32001 | Resource not found |

### Common Parameter Types

| Parameter | Type | Format |
|-----------|------|--------|
| `address` | string | `"0x"` + 40 hex chars. Case-insensitive. |
| `worknetId` | string | Decimal integer string, e.g., `"845300000001"`. Format: `chainId * 100_000_000 + localId` |
| `chainId` | integer | `1`, `56`, `8453`, `42161`. Omit = all chains. |
| `page` | integer | >= 1. Default: 1 |
| `limit` | integer | 1-100. Default: 20 |
| `status` | string | Worknet: `"Pending"`, `"Active"`, `"Paused"`, `"Banned"`. Proposal: `"Active"`, `"Canceled"`, `"Defeated"`, `"Succeeded"`, `"Queued"`, `"Expired"`, `"Executed"` |

All token amounts in API responses are **wei strings** (18 decimals). Use BigInt for arithmetic.

---

### 3.1 System

| Method | Params | Description |
|--------|--------|-------------|
| `stats.global` | none | Global protocol stats: total users, worknets, staked AWP, emitted AWP |
| `registry.get` | `chainId?` | All contract addresses + EIP-712 domain info. Omit chainId = array of all 4 chains |
| `health.check` | none | Returns `{"status": "ok"}` |
| `health.detailed` | none | Per-chain health: indexer sync block, keeper status, RPC latency |
| `chains.list` | none | Array of `{chainId, name, status, explorer}` |

### 3.2 Users

| Method | Params | Description |
|--------|--------|-------------|
| `users.list` | `page?`, `limit?`, `chainId?` | Paginated user list |
| `users.listGlobal` | `page?`, `limit?` | Cross-chain deduplicated user list |
| `users.count` | `chainId?` | Total registered user count |
| `users.get` | `address` **(req)**, `chainId?` | User details: balance, bound agents, recipient |
| `users.getPortfolio` | `address` **(req)**, `chainId?` | Full portfolio: identity + staking + NFT positions + allocations + delegates |
| `users.getDelegates` | `address` **(req)**, `chainId?` | Delegates authorized by this user |

### 3.3 Address & Nonce

| Method | Params | Description |
|--------|--------|-------------|
| `address.check` | `address` **(req)**, `chainId?` | Registration status, binding, recipient |
| `address.resolveRecipient` | `address` **(req)**, `chainId?` | Walk bind chain to root, return effective recipient |
| `address.batchResolveRecipients` | `addresses[]` **(req, max 500)**, `chainId?` | Batch resolve recipients (on-chain call) |
| `nonce.get` | `address` **(req)**, `chainId?` | AWPRegistry EIP-712 nonce |
| `nonce.getStaking` | `address` **(req)**, `chainId?` | AWPAllocator EIP-712 nonce |

### 3.4 Agents

| Method | Params | Description |
|--------|--------|-------------|
| `agents.getByOwner` | `owner` **(req)**, `chainId?` | All agents bound to this owner |
| `agents.getDetail` | `agent` **(req)**, `chainId?` | Agent details: owner, binding chain |
| `agents.lookup` | `agent` **(req)**, `chainId?` | Quick lookup: `{"ownerAddress": "0x..."}` |
| `agents.batchInfo` | `agents[]` **(req, max 100)**, `worknetId` **(req)**, `chainId?` | Batch agent info + stake in worknet |

### 3.5 Staking

| Method | Params | Description |
|--------|--------|-------------|
| `staking.getBalance` | `address` **(req)**, `chainId?` | `{totalStaked, totalAllocated, available}` in wei |
| `staking.getUserBalanceGlobal` | `address` **(req)** | Same, aggregated across all chains |
| `staking.getPositions` | `address` **(req)**, `chainId?` | veAWP positions: `{tokenId, amount, lockEndTime, createdAt}` |
| `staking.getPositionsGlobal` | `address` **(req)** | Positions across all chains (includes chainId per position) |
| `staking.getAllocations` | `address` **(req)**, `chainId?`, `page?`, `limit?` | Allocation records: `{agent, worknetId, amount}` |
| `staking.getFrozen` | `address` **(req)**, `chainId?` | Frozen allocations (from banned worknets) |
| `staking.getPending` | none | Pending allocation changes (always empty) |
| `staking.getAgentSubnetStake` | `agent` **(req)**, `worknetId` **(req)** | Agent's total allocated stake in a worknet (cross-chain) |
| `staking.getAgentSubnets` | `agent` **(req)** | All worknetIds where agent has non-zero allocations |
| `staking.getSubnetTotalStake` | `worknetId` **(req)** | Total AWP staked in a worknet |

### 3.6 Worknets

| Method | Params | Description |
|--------|--------|-------------|
| `subnets.list` | `status?`, `chainId?`, `page?`, `limit?` | List worknets with optional status filter |
| `subnets.listRanked` | `chainId?`, `page?`, `limit?` | Worknets ranked by total stake |
| `subnets.search` | `query` **(req, 1-100 chars)**, `chainId?`, `page?`, `limit?` | Search by name or symbol (ILIKE) |
| `subnets.getByOwner` | `owner` **(req)**, `chainId?`, `page?`, `limit?` | Worknets owned by address |
| `subnets.get` | `worknetId` **(req)** | Full worknet details |
| `subnets.getSkills` | `worknetId` **(req)** | Skills URI |
| `subnets.getEarnings` | `worknetId` **(req)**, `page?`, `limit?` | AWP earnings by epoch |
| `subnets.getAgentInfo` | `worknetId` **(req)**, `agent` **(req)** | Agent info within worknet |
| `subnets.listAgents` | `worknetId` **(req)**, `chainId?`, `page?`, `limit?` | Agents in worknet ranked by stake |

### 3.7 Emission

| Method | Params | Description |
|--------|--------|-------------|
| `emission.getCurrent` | `chainId?` | Current epoch, daily emission, total weight, settled epoch |
| `emission.getSchedule` | `chainId?` | 30/90/365-day emission projections with decay |
| `emission.getGlobalSchedule` | none | Same, aggregated across all chains |
| `emission.listEpochs` | `chainId?`, `page?`, `limit?` | Settled epochs with totals |
| `emission.getEpochDetail` | `epochId` **(req)**, `chainId?` | Per-recipient distributions for an epoch |

### 3.8 Tokens

| Method | Params | Description |
|--------|--------|-------------|
| `tokens.getAWP` | `chainId?` | AWP totalSupply, maxSupply, circulatingSupply |
| `tokens.getAWPGlobal` | none | AWP info aggregated across all chains |
| `tokens.getWorknetTokenInfo` | `worknetId` **(req)** | WorknetToken info: address, name, symbol, totalSupply, minter |
| `tokens.getWorknetTokenPrice` | `worknetId` **(req)** | WorknetToken/AWP price from LP (cached 10min). Returns sqrtPriceX96 and human-readable price |

### 3.9 Governance

| Method | Params | Description |
|--------|--------|-------------|
| `governance.listProposals` | `status?`, `chainId?`, `page?`, `limit?` | List proposals with optional status filter |
| `governance.listAllProposals` | `status?`, `page?`, `limit?` | Cross-chain proposal list |
| `governance.getProposal` | `proposalId` **(req)**, `chainId?` | Proposal details: description, votes, state, targets |
| `governance.getTreasury` | none | Treasury contract address |

### 3.10 Announcements (REST-only)

| Endpoint | Description |
|----------|-------------|
| `GET /api/announcements` | List active announcements. Query: `chainId?`, `category?`, `limit?`, `offset?` |
| `GET /api/announcements/{id}` | Single announcement by ID |
| `GET /api/announcements/llm-context` | All active announcements as text block for LLM context. Query: `chainId?` |

---

## 4. User-Facing Smart Contract Functions

### 4.1 AWPRegistry (`0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A`)

```solidity
// ── Binding ──
function bind(address target) external;
function unbind() external;

// ── Reward Recipient ──
function setRecipient(address addr) external;

// ── Delegation ──
function grantDelegate(address delegate) external;
function revokeDelegate(address delegate) external;

// ── Worknet Registration ──
struct WorknetParams {
    string name;
    string symbol;
    address worknetManager;   // address(0) to auto-deploy default
    bytes32 salt;             // bytes32(0) = use worknetId as salt
    uint128 minStake;         // stored on-chain, NOT enforced by contracts
    string skillsURI;
}
function registerWorknet(WorknetParams calldata params) external returns (uint256 worknetId);

// ── Worknet Lifecycle (NFT owner only) ──
function cancelWorknet(uint256 worknetId) external;    // Pending -> None (AWP refunded)
function pauseWorknet(uint256 worknetId) external;     // Active -> Paused
function resumeWorknet(uint256 worknetId) external;    // Paused -> Active

// ── View ──
function resolveRecipient(address addr) external view returns (address);
function batchResolveRecipients(address[] calldata addrs) external view returns (address[] memory);
function getAgentInfo(address agent, uint256 worknetId) external view returns (AgentInfo memory);
function getWorknet(uint256 worknetId) external view returns (WorknetInfo memory);
function getWorknetFull(uint256 worknetId) external view returns (WorknetFullInfo memory);
function isRegistered(address addr) external view returns (bool);
function isWorknetActive(uint256 worknetId) external view returns (bool);
function nonces(address) external view returns (uint256);

// ── Gasless (EIP-712, domain: AWPRegistry/1) ──
function bindFor(address agent, address target, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function unbindFor(address user, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function setRecipientFor(address user, address recipient, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function grantDelegateFor(address user, address delegate, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function revokeDelegateFor(address user, address delegate, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function registerWorknetFor(address user, WorknetParams calldata params, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external returns (uint256);
function registerWorknetForWithPermit(...) external returns (uint256); // fully gasless with ERC-2612 permit
```

### 4.2 veAWP (`0x0000b534C63D78212f1BDCc315165852793A00A8`)

```solidity
function deposit(uint256 amount, uint64 lockDuration) external returns (uint256 tokenId);
function depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external returns (uint256 tokenId);
function addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime) external; // BLOCKED if lock expired
function withdraw(uint256 tokenId) external;              // full withdraw + burn NFT (lock must be expired, all deallocated)
function partialWithdraw(uint256 tokenId, uint128 amount) external;
function batchWithdraw(uint256[] calldata tokenIds) external;

// ── View ──
function positions(uint256 tokenId) external view returns (uint128 amount, uint64 lockEndTime, uint64 createdAt);
function getVotingPower(uint256 tokenId) external view returns (uint256);
function getUserVotingPower(address user, uint256[] calldata tokenIds) external view returns (uint256);
function getUserTotalStaked(address user) external view returns (uint256);
function totalVotingPower() external view returns (uint256);
function remainingTime(uint256 tokenId) external view returns (uint64);

// Constants
// MAX_WEIGHT_DURATION = 54 weeks
// MIN_LOCK_DURATION = 1 day (86400 seconds)
// VOTE_WEIGHT_DIVISOR = 7 days
// Voting power = amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
```

### 4.3 AWPAllocator (`0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA`)

```solidity
// Auth: msg.sender must be staker OR authorized delegate (via AWPRegistry.delegates)
function allocate(address staker, address agent, uint256 worknetId, uint256 amount) external;
function deallocate(address staker, address agent, uint256 worknetId, uint256 amount) external;
function deallocateAll(address staker, address agent, uint256 worknetId) external;
function reallocate(
    address staker, address fromAgent, uint256 fromWorknetId,
    address toAgent, uint256 toWorknetId, uint256 amount
) external;
function batchAllocate(address staker, address[] calldata agents, uint256[] calldata worknetIds, uint256[] calldata amounts) external;
function batchDeallocate(address staker, address[] calldata agents, uint256[] calldata worknetIds, uint256[] calldata amounts) external;

// Gasless (EIP-712, domain: AWPAllocator/1)
function allocateFor(address staker, address agent, uint256 worknetId, uint256 amount, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
function deallocateFor(address staker, address agent, uint256 worknetId, uint256 amount, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;

// ── View ──
function getAgentStake(address staker, address agent, uint256 worknetId) external view returns (uint256);
function userTotalAllocated(address staker) external view returns (uint256);
function worknetTotalStake(uint256 worknetId) external view returns (uint256);
function nonces(address) external view returns (uint256);
```

### 4.4 AWPWorkNet (`0x00000bfbdEf8533E5F3228c9C846522D906100A7`)

```solidity
// Owner or delegate of the worknet NFT
function setSkillsURI(uint256 worknetId, string calldata skillsURI) external;
function setMinStake(uint256 worknetId, uint128 minStake) external;
function setImageURI(uint256 worknetId, string calldata imageURI) external;
function setMetadataURI(uint256 worknetId, string calldata metadataURI) external;

// ── View ──
function getWorknetData(uint256 worknetId) external view returns (WorknetData memory);
function tokenURI(uint256 tokenId) external view returns (string memory);
// tokenURI 3-tier: per-token metadataURI -> global baseURI -> on-chain Base64 JSON
```

### 4.5 AWPDAO (`0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0`)

```solidity
function proposeWithTokens(
    address[] memory targets, uint256[] memory values, bytes[] memory calldatas,
    string memory description, uint256[] memory tokenIds
) external returns (uint256 proposalId);

function signalPropose(string memory description, uint256[] memory tokenIds) external returns (uint256);

// params = abi.encode(uint256[] tokenIds). support: 0=Against, 1=For, 2=Abstain
function castVoteWithReasonAndParams(
    uint256 proposalId, uint8 support, string calldata reason, bytes memory params
) external returns (uint256 weight);

// Gasless voting
function castVoteWithReasonAndParamsBySig(
    uint256 proposalId, uint8 support, string calldata reason, bytes memory params,
    uint8 v, bytes32 r, bytes32 s
) external returns (uint256 weight);

function queue(address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash) external returns (uint256);
function execute(address[] memory targets, uint256[] memory values, bytes[] memory calldatas, bytes32 descriptionHash) external returns (uint256);

// ── View ──
function proposalVotes(uint256 proposalId) external view returns (uint256 against, uint256 forVotes, uint256 abstain);
function quorum(uint256 proposalId) external view returns (uint256);

// Clock: mode=timestamp, votingDelay=1 day, votingPeriod=7 days, proposalThreshold=200K AWP staked
```

### 4.6 WorknetManager (per-worknet proxy)

Each active worknet has its own WorknetManager proxy. Address returned by `subnets.get`.

```solidity
function claim(uint32 epoch, uint256 amount, bytes32[] calldata proof) external; // merkle claim for worknet tokens
function isClaimed(uint32 epoch, address account) external view returns (bool);
```

### 4.7 WorknetToken (per-worknet, deployed by WorknetTokenFactory)

```solidity
// ERC20 + ERC20Permit + ERC1363 + ERC20Burnable
// No constructor args — reads from factory callback (pending params pattern)
function currentMintableLimit() external view returns (uint256); // remaining mintable headroom
function initialized() external view returns (bool);
```

---

## 5. Gasless Relay Endpoints

Users sign EIP-712 typed data off-chain; the relayer submits the transaction and pays gas. Rate limited to 100 requests per IP per hour.

### Endpoints

| Endpoint | Description | EIP-712 Domain |
|----------|-------------|----------------|
| `POST /api/relay/bind` | Bind agent to target | AWPRegistry |
| `POST /api/relay/unbind` | Unbind from tree | AWPRegistry |
| `POST /api/relay/set-recipient` | Set reward recipient | AWPRegistry |
| `POST /api/relay/grant-delegate` | Authorize a delegate | AWPRegistry |
| `POST /api/relay/revoke-delegate` | Revoke a delegate | AWPRegistry |
| `POST /api/relay/register-worknet` | Register worknet (with AWP permit) | AWPRegistry |
| `POST /api/relay/allocate` | Allocate stake to agent | AWPAllocator |
| `POST /api/relay/deallocate` | Deallocate stake | AWPAllocator |
| `GET /api/relay/status/{txHash}` | Check relay tx status | — |

### Request Examples

```json
// Bind
POST /api/relay/bind
{
  "chainId": 8453,
  "agent": "0xAgentAddress...",
  "target": "0xOwnerAddress...",
  "deadline": 1712345678,
  "v": 27, "r": "0x...", "s": "0x..."
}

// Allocate
POST /api/relay/allocate
{
  "chainId": 8453,
  "staker": "0x...",
  "agent": "0x...",
  "worknetId": "845300000001",
  "amount": "1000000000000000000000",
  "deadline": 1712345678,
  "v": 27, "r": "0x...", "s": "0x..."
}

// Success response (all relay endpoints)
{"txHash": "0x..."}

// Error response
{"error": "invalid EIP-712 signature"}
```

### EIP-712 Domains

```json
// AWPRegistry (bind, unbind, setRecipient, grantDelegate, revokeDelegate, registerWorknet)
{"name": "AWPRegistry", "version": "1", "chainId": 8453, "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"}

// AWPAllocator (allocate, deallocate)
{"name": "AWPAllocator", "version": "1", "chainId": 8453, "verifyingContract": "0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA"}
```

### EIP-712 Type Definitions

```
Bind(address agent, address target, uint256 nonce, uint256 deadline)
Unbind(address user, uint256 nonce, uint256 deadline)
SetRecipient(address user, address recipient, uint256 nonce, uint256 deadline)
GrantDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
RevokeDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
RegisterWorknet(address user, WorknetParams params, uint256 nonce, uint256 deadline)
  WorknetParams(string name, string symbol, address worknetManager, bytes32 salt, uint128 minStake, string skillsURI)
Allocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
Deallocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
```

**Nonce workflow**: Fetch current nonce via `nonce.get` (AWPRegistry) or `nonce.getStaking` (AWPAllocator) immediately before signing. Nonces auto-increment after each relay. Stale nonce = `InvalidSignature` error.

---

## 6. Vanity Salt Endpoints

For offline mining of vanity WorknetToken CREATE2 addresses:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/vanity/mining-params` | GET | Returns `{factoryAddress, initCodeHash, vanityRule}` |
| `POST /api/vanity/upload-salts` | POST | Upload pre-mined `{salts: [{salt, address}, ...]}`. Rate: 5/hr/IP |
| `GET /api/vanity/salts` | GET | List available salts |
| `GET /api/vanity/salts/count` | GET | Available (unused) salt count |

---

## 7. WebSocket Real-Time Events

**Endpoint**: `wss://api.awp.sh/ws/live`

Connect via standard WebSocket. All events for all chains are broadcast (no subscription filtering).

| Event | Key Fields | Description |
|-------|------------|-------------|
| `UserRegistered` | `user`, `chainId` | First-time registration |
| `Bound` | `user`, `target`, `chainId` | Agent bound to target |
| `Unbound` | `user`, `chainId` | Agent unbound |
| `RecipientSet` | `user`, `recipient`, `chainId` | Reward recipient changed |
| `DelegateGranted` | `user`, `delegate`, `chainId` | Delegate authorized |
| `DelegateRevoked` | `user`, `delegate`, `chainId` | Delegate revoked |
| `Deposited` | `user`, `tokenId`, `amount`, `lockEndTime`, `chainId` | AWP deposited to veAWP |
| `Withdrawn` | `user`, `tokenId`, `amount`, `chainId` | AWP withdrawn from veAWP |
| `Allocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` | Stake allocated |
| `Deallocated` | `staker`, `agent`, `worknetId`, `amount`, `chainId` | Stake deallocated |
| `Reallocated` | `staker`, `fromAgent`, `fromWorknetId`, `toAgent`, `toWorknetId`, `amount`, `chainId` | Atomic reallocation |
| `WorknetRegistered` | `worknetId`, `owner`, `name`, `symbol`, `chainId` | New worknet (Pending) |
| `WorknetActivated` | `worknetId`, `chainId` | Worknet activated (LP created) |
| `WorknetCancelled` | `worknetId`, `chainId` | Worknet cancelled (AWP refunded) |
| `EpochSettled` | `epoch`, `totalEmission`, `recipientCount`, `chainId` | Emission epoch settled |

---

## 8. Key Protocol Parameters

| Parameter | Value |
|-----------|-------|
| AWP Max Supply | 10,000,000,000 (10B) per chain |
| Initial Daily Emission | 31,600,000 AWP per chain per epoch |
| Decay Factor | 996844 / 1,000,000 (~0.3156% per epoch) |
| Epoch Duration | 1 day (86,400 seconds) |
| Worknet Registration Cost | 100,000 AWP |
| WorknetTokens per Worknet | 100,000,000 (100M) |
| Initial WorknetToken Price | 0.001 AWP per token (1e15 wei) |
| Min Lock Duration (veAWP) | 1 day (86,400 seconds) |
| Max Voting Weight Duration | 54 weeks |
| Timelock Delay (Treasury) | 2 days |
| LP Pool Fee | 10,000 bps (1%) |
| Max Active Worknets | 10,000 per chain |
| Max Emission Recipients | 10,000 per chain per epoch |
| WorknetId Format | `chainId * 100_000_000 + localCounter` |
| Proposal Threshold (AWPDAO) | 200,000 AWP staked |
| Voting Delay (AWPDAO) | 1 day |
| Voting Period (AWPDAO) | 7 days |

---

## 9. Common User Workflows

### 9.1 Stake AWP and Earn Voting Power
1. `AWPToken.approve(veAWP, amount)` — or skip if using `depositWithPermit`
2. `veAWP.deposit(amount, lockDurationInSeconds)` — returns `tokenId`
3. Verify: `staking.getPositions({address: "0x..."})`
4. Withdraw after lock: `veAWP.withdraw(tokenId)` — must deallocate all first

### 9.2 Allocate Stake to an Agent
1. Check available: `staking.getBalance({address: "0x..."})` — `available = totalStaked - totalAllocated`
2. `AWPAllocator.allocate(staker, agent, worknetId, amount)`
3. Verify: `staking.getAgentSubnetStake({agent: "0x...", worknetId: "845300000001"})`

### 9.3 Register a Worknet
1. `AWPToken.approve(AWPRegistry, 100000e18)`
2. `AWPRegistry.registerWorknet({name, symbol, worknetManager: address(0), salt: bytes32(0), minStake: 0, skillsURI: "https://..."})` — returns `worknetId`, status = Pending
3. Verify: `subnets.get({worknetId: "..."})` — status should be `"Active"` after activation
4. Cancel instead: `AWPRegistry.cancelWorknet(worknetId)` — full AWP refund

### 9.4 Bind an Agent
1. Agent calls: `AWPRegistry.bind(ownerAddress)`
2. Verify: `address.check({address: agentAddress})` — `boundTo` shows owner
3. Unbind: `AWPRegistry.unbind()`

### 9.5 Set Reward Recipient
1. `AWPRegistry.setRecipient(recipientAddress)`
2. Verify: `address.resolveRecipient({address: "0x..."})` — returns recipient
3. Reset to self: `AWPRegistry.setRecipient(yourOwnAddress)`

### 9.6 Delegate Staking Operations
1. `AWPRegistry.grantDelegate(delegateAddress)`
2. Delegate calls: `AWPAllocator.allocate(yourAddress, agent, worknetId, amount)`
3. Revoke: `AWPRegistry.revokeDelegate(delegateAddress)`

### 9.7 Vote on a DAO Proposal
1. Must hold veAWP positions minted BEFORE the proposal was created
2. `AWPDAO.castVoteWithReasonAndParams(proposalId, 1, "reason", abi.encode([tokenId1, tokenId2]))`
3. Check: `governance.getProposal({proposalId: "..."})`

### 9.8 Gasless Registration (via Relay)
1. Fetch nonce: `nonce.get({address: "0x...", chainId: 8453})`
2. Sign EIP-712 `SetRecipient` with AWPRegistry domain
3. Submit: `POST /api/relay/set-recipient` with `{chainId, user, recipient, deadline, v, r, s}`
4. Poll: `GET /api/relay/status/{txHash}`

### 9.9 Gasless Allocation (via Relay)
1. Fetch nonce: `nonce.getStaking({address: "0x...", chainId: 8453})`
2. Sign EIP-712 `Allocate` with AWPAllocator domain
3. Submit: `POST /api/relay/allocate` with all fields + signature
4. Verify: `staking.getAgentSubnetStake({agent, worknetId})`
