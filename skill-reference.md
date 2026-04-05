# AWP Protocol — Skill Reference

> Verified against codebase commit bd95ff8 (2026-04-05). Every function signature, parameter, and address has been cross-referenced with the source code.

---

## 1. Protocol Overview

AWP is a multi-chain **agent mining protocol** deployed identically on 4 EVM chains:

| Chain | Chain ID | DEX |
|-------|----------|-----|
| Base | 8453 | Uniswap V4 |
| Ethereum | 1 | Uniswap V4 |
| Arbitrum One | 42161 | Uniswap V4 |
| BNB Smart Chain | 56 | PancakeSwap V4 |

All protocol contracts share the same addresses across all 4 chains (deployed via CREATE2). The only exception is WorknetManager implementation contracts, which differ per chain due to DEX integration. Users interact with proxies, so proxy addresses are identical.

### Core Concepts

- **AWP Token** (`AWPToken.sol`): ERC20 + ERC1363 + Permit. 10B MAX_SUPPLY. Per-chain independent mint via configurable INITIAL_MINT constructor param. `mintAndCall(to, amount, data)` triggers ERC1363 callback on the recipient contract.

- **Worknet**: An autonomous AI agent network. Each worknet has a dedicated WorknetToken (ERC20 deployed via CREATE2), a WorknetManager contract, and an LP pool on DEX V4.

- **AWPWorkNet** (`AWPWorkNet.sol`): ERC721 NFT representing worknet ownership. `tokenId = worknetId`. Stores on-chain identity: name, symbol, worknetManager, worknetToken, lpPool, skillsURI, minStake, imageURI, metadataURI. tokenURI resolution is 3-tier: per-token metadataURI, global baseURI, on-chain Base64 JSON.

- **veAWP** (`veAWP.sol`): ERC721 staking position NFT. Deposit AWP with a lock period to mint a position NFT containing (amount, lockEndTime, createdAt). Positions are transferable. Voting power = `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)`.

- **AWPAllocator** (`AWPAllocator.sol`): UUPS proxy. Allocation bookkeeping for (staker, agent, worknetId) triples. EIP-712 domain name "AWPAllocator", version "1". Supports gasless `allocateFor` / `deallocateFor` via EIP-712 signatures. Cross-chain allocate: worknetId from any chain, no on-chain status check.

- **AWPEmission** (`AWPEmission.sol`): UUPS upgradeable proxy. Guardian-only epoch-versioned weight submission. Exponential decay: `currentEmission *= 996844 / 1000000`. `settleEpoch(limit)` batch-mints AWP via `mintAndCall`. 100% emission to recipients; Guardian includes treasury in recipients for DAO share.

- **AWPRegistry** (`AWPRegistry.sol`): UUPS proxy. Unified entry for worknet lifecycle management and account system. EIP-712 domain name "AWPRegistry", version "1". Holds 8 immutable contract addresses set at initialization. No mandatory registration -- every address is implicitly a root. `register()` is optional (alias for `setRecipient(msg.sender)`).

- **WorknetId**: `(block.chainid << 64) | localCounter` -- globally unique across all chains. Extract chain with `extractChainId(worknetId)`.

- **Binding**: Tree-based via `bind(target)`. Anti-cycle check walks the chain (max depth 256) before binding. `resolveRecipient(addr)` walks the `boundTo` chain to root for reward distribution.

- **Delegation**: `grantDelegate(delegate)` / `revokeDelegate(delegate)` for gasless operations on behalf of stakers. Delegates can call allocate/deallocate on the staker's behalf via AWPAllocator.

- **WorknetManager** (`WorknetManagerBase.sol`): Default worknet contract deployed behind ERC1967Proxy via AWPRegistry when `worknetManager=address(0)`. UUPS upgradeable + AccessControl + ReentrancyGuard + IERC1363Receiver. Three roles: MERKLE_ROLE (submit Merkle roots), STRATEGY_ROLE (AWP handling), TRANSFER_ROLE (token transfers). AWP strategy options: Reserve, AddLiquidity, BuybackBurn. `onTransferReceived` auto-executes strategy on AWP receipt via `mintAndCall`. Merkle claim mints WorknetToken to users.

---

## 2. Contract Addresses

### Protocol Contracts (identical on all 4 chains)

| Contract | Address |
|----------|---------|
| AWPRegistry | `0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A` |
| AWPToken | `0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1` |
| AWPEmission | `0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9` |
| AWPAllocator | `0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA` |
| veAWP | `0x0000b534C63D78212f1BDCc315165852793A00A8` |
| AWPWorkNet | `0x00000bfbdEf8533E5F3228c9C846522D906100A7` |
| LPManager | `0x00001961b9AcCD86b72DE19Be24FaD6f7c5b00A2` |
| WorknetTokenFactory | `0x0000D4996BDBb99c772e3fA9f0e94AB52AAFFAC7` |
| AWPDAO | `0x00006879f79f3Da189b5D0fF6e58ad0127Cc0DA0` |
| Treasury | `0x82562023a053025F3201785160CaE6051efD759e` |
| Guardian (Safe 3/5) | `0x000002bEfa6A1C99A710862Feb6dB50525dF00A3` |

### WorknetManager Implementation (DEX-specific, differs by chain)

| Chain | Address |
|-------|---------|
| Base (8453) | `0x000011EE4117c52dC0Eb146cBC844cb155B200A9` |
| Ethereum (1) | `0x0000DD4841bB4e66AF61A5E35204C1606b4a00A9` |
| Arbitrum (42161) | `0x000055Ca7d29e8dC7eDEF3892849347214a300A9` |
| BSC (56) | `0x0000269C10feF9B603A228b075F8C99BAE5b00A9` |

---

## 3. API — JSON-RPC 2.0

**Base URL:** `https://api.awp.sh/v2`

### Connection

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v2` | POST | JSON-RPC request (or batch, max 20) |
| `/v2` | GET | `rpc.discover` documentation |
| `/ws/live` | WS | WebSocket real-time events |
| `/api/health` | GET | Health check |

### Error Codes

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32001 | Not found |

### 3.1 System

| Method | Params | Description |
|--------|--------|-------------|
| `registry.get` | `chainId?: int64` | Contract addresses + EIP-712 domain for one chain (default: primary chain) |
| `registry.list` | -- | Contract addresses for all chains (returns array) |
| `health.check` | -- | Health check |
| `health.detailed` | -- | Detailed per-chain health status |
| `chains.list` | -- | List supported chains |
| `stats.global` | -- | Global protocol statistics |

### 3.2 Users

| Method | Params | Description |
|--------|--------|-------------|
| `users.list` | `page?, limit?` | List users (paginated) |
| `users.listGlobal` | `page?, limit?` | List users across all chains (deduplicated) |
| `users.count` | -- | Total user count |
| `users.get` | `address` | User details (balance + bindings) |
| `users.getPortfolio` | `address, chainId?` | Full portfolio (identity, balance, positions, allocations, delegates) |
| `users.getDelegates` | `address, chainId?` | Delegates for address |

### 3.3 Address & Nonce

| Method | Params | Description |
|--------|--------|-------------|
| `address.check` | `address` | Registration, binding, recipient status |
| `address.resolveRecipient` | `address, chainId?` | Walk bind chain to root, return recipient |
| `address.batchResolveRecipients` | `addresses[], chainId?` | Batch resolve (max 500) |
| `nonce.get` | `address` | AWPRegistry EIP-712 nonce (rate limited) |
| `nonce.getStaking` | `address` | AWPAllocator EIP-712 nonce (rate limited) |

### 3.4 Agents

| Method | Params | Description |
|--------|--------|-------------|
| `agents.getByOwner` | `owner` | Agents bound to owner |
| `agents.getDetail` | `agent` | Agent details |
| `agents.lookup` | `agent` | Look up agent owner |
| `agents.batchInfo` | `agents[], worknetId` | Batch agent info + stake (max 100, rate limited) |

### 3.5 Staking

| Method | Params | Description |
|--------|--------|-------------|
| `staking.getBalance` | `address` | AWP balance (staked/allocated/available) |
| `staking.getUserBalanceGlobal` | `address` | Balance across all chains |
| `staking.getPositions` | `address` | veAWP positions |
| `staking.getPositionsGlobal` | `address` | Positions across all chains |
| `staking.getAllocations` | `address, page?, limit?` | Stake allocations (paginated) |
| `staking.getFrozen` | `address` | Frozen allocations |
| `staking.getAgentSubnetStake` | `agent, worknetId` | Agent stake in worknet |
| `staking.getAgentSubnets` | `agent` | All worknets agent participates in |
| `staking.getSubnetTotalStake` | `worknetId` | Worknet total stake |

### 3.6 Worknets

| Method | Params | Description |
|--------|--------|-------------|
| `subnets.list` | `status?, chainId?, page?, limit?` | List worknets (optional status filter: Active/Pending/Paused/Banned) |
| `subnets.listRanked` | `chainId?, page?, limit?` | Worknets ranked by total stake |
| `subnets.get` | `worknetId` | Worknet details |
| `subnets.getSkills` | `worknetId` | Skills URI |
| `subnets.getEarnings` | `worknetId, page?, limit?` | AWP earnings history |
| `subnets.getAgentInfo` | `worknetId, agent` | Agent staking info in worknet |
| `subnets.listAgents` | `worknetId, chainId?, page?, limit?` | Agents in worknet (ranked by stake) |
| `subnets.search` | `query, chainId?, page?, limit?` | Search worknets by name/symbol |
| `subnets.getByOwner` | `owner, chainId?, page?, limit?` | Worknets owned by address |

### 3.7 Emission

| Method | Params | Description |
|--------|--------|-------------|
| `emission.getCurrent` | -- | Current emission data (epoch, daily emission, etc.) |
| `emission.getSchedule` | -- | Emission projections (30/90/365 days) |
| `emission.getGlobalSchedule` | -- | Global emission schedule across all chains |
| `emission.listEpochs` | `page?, limit?` | List settled epochs |
| `emission.getEpochDetail` | `epochId, chainId?` | Epoch detail with per-recipient distributions |

### 3.8 Tokens

| Method | Params | Description |
|--------|--------|-------------|
| `tokens.getAWP` | -- | AWP token info (supply, emission rate, etc.) |
| `tokens.getAWPGlobal` | -- | AWP info aggregated across all chains |
| `tokens.getWorknetTokenInfo` | `worknetId` | WorknetToken info (supply, minter, cap) |
| `tokens.getWorknetTokenPrice` | `worknetId` | WorknetToken price from LP pool |

### 3.9 Governance

| Method | Params | Description |
|--------|--------|-------------|
| `governance.listProposals` | `status?, page?, limit?` | List proposals |
| `governance.listAllProposals` | `status?, page?, limit?` | Proposals across all chains |
| `governance.getProposal` | `proposalId, chainId?` | Proposal details |
| `governance.getTreasury` | -- | Treasury address |

---

## 4. User-Facing Smart Contract Functions

### 4.1 AWPRegistry

EIP-712 domain: `name="AWPRegistry"`, `version="1"`

#### Account System

| Function | Access | Description |
|----------|--------|-------------|
| `bind(address target)` | Anyone | Tree-based bind. Anti-cycle check (max depth 256). |
| `unbind()` | Anyone | Remove binding, become root. |
| `setRecipient(address addr)` | Anyone | Set reward recipient (addr=0 clears). |
| `register()` | Anyone | Alias for `setRecipient(msg.sender)`. |
| `grantDelegate(address delegate)` | Anyone | Grant delegation for gasless ops. |
| `revokeDelegate(address delegate)` | Anyone | Revoke delegation. Cannot revoke self. |

#### Gasless (EIP-712)

| Function | Params | TypeHash |
|----------|--------|----------|
| `bindFor` | `agent, target, deadline, v, r, s` | `Bind(address agent,address target,uint256 nonce,uint256 deadline)` |
| `unbindFor` | `user, deadline, v, r, s` | `Unbind(address user,uint256 nonce,uint256 deadline)` |
| `setRecipientFor` | `user, recipient, deadline, v, r, s` | `SetRecipient(address user,address recipient,uint256 nonce,uint256 deadline)` |
| `grantDelegateFor` | `user, delegate, deadline, v, r, s` | `GrantDelegate(address user,address delegate,uint256 nonce,uint256 deadline)` |
| `revokeDelegateFor` | `user, delegate, deadline, v, r, s` | `RevokeDelegate(address user,address delegate,uint256 nonce,uint256 deadline)` |
| `registerWorknetFor` | `user, params, deadline, v, r, s` | `RegisterWorknet(address user,WorknetParams params,...)` |
| `registerWorknetForWithPermit` | `user, params, deadline, permitV/R/S, registerV/R/S` | Permit + RegisterWorknet in one tx |

#### Worknet Lifecycle

| Function | Access | Description |
|----------|--------|-------------|
| `registerWorknet(WorknetParams params) -> uint256` | Anyone | Register worknet. Deploys WorknetToken + LP. Returns worknetId. |
| `activateWorknet(uint256 worknetId)` | Guardian | Pending -> Active |
| `pauseWorknet(uint256 worknetId)` | NFT Owner | Active -> Paused |
| `resumeWorknet(uint256 worknetId)` | NFT Owner | Paused -> Active |
| `cancelWorknet(uint256 worknetId)` | NFT Owner | Pending -> refund AWP escrow |
| `rejectWorknet(uint256 worknetId)` | Guardian | Pending -> Rejected, refund AWP escrow |
| `banWorknet(uint256 worknetId)` | Guardian | Active/Paused -> Banned |
| `unbanWorknet(uint256 worknetId)` | Guardian | Banned -> Active (checks MAX_ACTIVE_WORKNETS) |

**WorknetParams struct:**

```solidity
struct WorknetParams {
    string name;             // 1-64 bytes, no " or \
    string symbol;           // 1-16 bytes, no " or \
    address worknetManager;  // 0x0 = auto-deploy default impl
    bytes32 salt;            // 0x0 = use worknetId; non-zero = vanity
    uint128 minStake;        // off-chain reference only
    string skillsURI;        // skills description URI
}
```

#### Guardian Admin

| Function | Access | Description |
|----------|--------|-------------|
| `setInitialAlphaPrice(uint256 price)` | Guardian | Set LP creation price (min 1e12, max 1e30) |
| `setInitialAlphaMint(uint256 amount)` | Guardian | Set initial WorknetToken mint amount for LP |
| `setGuardian(address g)` | Guardian | Transfer guardian role |
| `setWorknetManagerImpl(address impl)` | Guardian | Set default WorknetManager impl |
| `pause()` | Guardian | Emergency pause contract |
| `unpause()` | Guardian | Unpause contract |
| `rescueToken(address token, address to, uint256 amount)` | Guardian | Rescue stuck tokens |

#### View Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `getRegistry()` | `(address[9])` | awpToken, awpWorkNet, worknetTokenFactory, awpEmission, lpManager, awpAllocator, veAWP, treasury, guardian |
| `getWorknet(uint256 worknetId)` | `WorknetInfo` | lpPool, status, createdAt, activatedAt |
| `getWorknetFull(uint256 worknetId)` | `WorknetFullInfo` | Full info including name, symbol, owner, etc. |
| `resolveRecipient(address)` | `address` | Walk bind chain to root, return recipient |
| `batchResolveRecipients(address[])` | `address[]` | Batch resolve |
| `getAgentInfo(address agent, uint256 worknetId)` | `AgentInfo` | root, isValid, stake, rewardRecipient |
| `nonces(address)` | `uint256` | EIP-712 nonce |
| `nextWorknetId()` | `uint256` | Next worknet ID to be assigned |
| `extractChainId(uint256 worknetId)` | `uint256` | Extract chainId from worknetId |
| `boundTo(address)` | `address` | Binding target |
| `recipient(address)` | `address` | Reward recipient |
| `delegates(address, address)` | `bool` | Delegation status |
| `initialAlphaPrice()` | `uint256` | Current initial price |
| `initialAlphaMint()` | `uint256` | Current initial mint |
| `guardian()` | `address` | Guardian address |
| `reservedSalts(bytes32)` | `bool` | Whether a salt is reserved |

### 4.2 veAWP

| Function | Access | Description |
|----------|--------|-------------|
| `deposit(uint256 amount, uint64 lockDuration) -> uint256` | Anyone | Deposit AWP, mint position NFT. Returns tokenId. |
| `addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime)` | Token owner | Add AWP to existing position. Blocked if lock expired. |
| `withdraw(uint256 tokenId)` | Token owner | Withdraw full position (lock must be expired). |
| `partialWithdraw(uint256 tokenId, uint128 amount)` | Token owner | Withdraw partial (lock must be expired). |
| `batchWithdraw(uint256[] tokenIds)` | Token owner | Batch withdraw multiple positions. |
| `positions(uint256 tokenId)` | View | `(amount, lockEndTime, createdAt)` |
| `getUserTotalStaked(address user)` | View | Total AWP staked by user |
| `getVotingPower(uint256 tokenId)` | View | Voting power for one position |
| `getUserVotingPower(address, uint256[] tokenIds)` | View | Aggregate voting power |
| `remainingTime(uint256 tokenId)` | View | Seconds until lock expires |

### 4.3 AWPAllocator

EIP-712 domain: `name="AWPAllocator"`, `version="1"`

| Function | Access | Description |
|----------|--------|-------------|
| `allocate(address staker, address agent, uint256 worknetId, uint256 amount)` | Staker or delegate | Allocate stake. worknetId=0 rejected. |
| `deallocate(address staker, address agent, uint256 worknetId, uint256 amount)` | Staker or delegate | Remove allocation. |
| `deallocateAll(address staker, address agent, uint256 worknetId)` | Staker or delegate | Remove entire allocation. |
| `reallocate(staker, fromAgent, fromWorknetId, toAgent, toWorknetId, amount)` | Staker or delegate | Move allocation atomically. |
| `batchAllocate(staker, agents[], worknetIds[], amounts[])` | Staker or delegate | Batch allocate. |
| `batchDeallocate(staker, agents[], worknetIds[], amounts[])` | Staker or delegate | Batch deallocate. |
| `allocateFor(staker, agent, worknetId, amount, deadline, v, r, s)` | Anyone | Gasless allocate via EIP-712. |
| `deallocateFor(staker, agent, worknetId, amount, deadline, v, r, s)` | Anyone | Gasless deallocate via EIP-712. |
| `nonces(address)` | View | EIP-712 nonce |
| `userTotalAllocated(address)` | View | Total allocated by user |
| `getAgentStake(address staker, address agent, uint256 worknetId)` | View | Specific allocation |
| `getAgentWorknets(address staker, address agent)` | View | All worknets for agent |
| `getWorknetTotalStake(uint256 worknetId)` | View | Total stake for worknet |

### 4.4 AWPWorkNet

| Function | Access | Description |
|----------|--------|-------------|
| `setSkillsURI(uint256 tokenId, string uri)` | NFT Owner | Update skills URI |
| `setMinStake(uint256 tokenId, uint128 minStake)` | NFT Owner | Update minimum stake |
| `setMetadataURI(uint256 tokenId, string uri)` | NFT Owner | Override tokenURI |
| `setImageURI(uint256 tokenId, string uri)` | NFT Owner | Update image URI |
| `getWorknetData(uint256 tokenId)` | View | Full worknet data |
| `getWorknetIdentity(uint256 tokenId)` | View | name, symbol, manager, token, lpPool |
| `getWorknetMeta(uint256 tokenId)` | View | skillsURI, minStake, imageURI, metadataURI |
| `getWorknetManager(uint256 tokenId)` | View | Manager contract address |
| `getWorknetToken(uint256 tokenId)` | View | WorknetToken address |

### 4.5 AWPDAO

Timestamp-based clock (not block number). Quorum on raw staked amount. proposalThreshold 200K AWP.

| Function | Access | Description |
|----------|--------|-------------|
| `proposeWithTokens(targets[], values[], calldatas[], description, tokenIds[])` | Anyone with veAWP | Create executable proposal (requires tokenIds for voting power threshold). `propose()` is blocked. |
| `signalPropose(description, tokenIds[])` | Anyone with veAWP | Create signal-only proposal (vote-only, no execution). |
| `castVoteWithReasonAndParams(proposalId, support, reason, params)` | Anyone with veAWP | Vote. `params = abi.encode(uint256[] tokenIds)`. support: 0=Against, 1=For, 2=Abstain. |
| `queue(targets[], values[], calldatas[], descriptionHash)` | Anyone | Queue passed proposal to Treasury timelock. |
| `execute(targets[], values[], calldatas[], descriptionHash)` | Anyone | Execute matured proposal. |
| `guardianCancel(targets[], values[], calldatas[], descriptionHash)` | Guardian | Emergency cancel proposal. |
| `setQuorumPercent(uint256 newQuorumPercent)` | Guardian or Executor | Update quorum percentage. |

Voting power per token: `amount * sqrt(min(remainingTime, 54 weeks) / 7 days)`. Only NFTs with `createdAt < proposalCreatedAt` can vote. Per-tokenId double-vote prevention.

### 4.6 WorknetManager

| Function | Access | Description |
|----------|--------|-------------|
| `setMerkleRoot(uint32 epoch, bytes32 root)` | MERKLE_ROLE | Submit distribution root. |
| `claim(uint32 epoch, uint256 amount, bytes32[] proof)` | Anyone | Claim WorknetToken via Merkle proof. |
| `setStrategy(AWPStrategy strategy)` | STRATEGY_ROLE | Set AWP handling strategy (Reserve/AddLiquidity/BuybackBurn). |
| `executeStrategy(uint256 amount, uint256 minAmountOut)` | STRATEGY_ROLE | Execute strategy with MEV protection. |
| `transferToken(address token, address to, uint256 amount)` | TRANSFER_ROLE | Transfer any token. |
| `batchTransferToken(address token, address[] to, uint256[] amounts)` | TRANSFER_ROLE | Batch transfer. |
| `setSlippageTolerance(uint16 bps)` | DEFAULT_ADMIN | Set slippage (1-5000 bps). |
| `setStrategyPaused(bool paused)` | DEFAULT_ADMIN | Pause/unpause strategy. |
| `isClaimed(uint32 epoch, address account)` | View | Check if claimed. |

### 4.7 WorknetToken

Non-upgradeable ERC20 + ERC20Permit + ERC20Burnable + ERC1363. No constructor args (callback pattern from factory).

| Function | Access | Description |
|----------|--------|-------------|
| `mint(address to, uint256 amount)` | Minter only | Mint tokens (subject to time-based cap). |
| `setMinter(address newMinter)` | Admin | Permanently lock minter to worknet manager. |
| `burn(uint256 amount)` | Anyone | Burn own tokens. |
| `currentMintableLimit()` | View | Current mintable amount based on time. |
| `MAX_SUPPLY()` | View | 10B (1e28) |
| `worknetId()` | View | Associated worknet ID |
| `minter()` | View | Current minter address |

### 4.8 AWPEmission

| Function | Access | Description |
|----------|--------|-------------|
| `submitAllocations(uint256[] packed, uint256 totalWeight, uint256 effectiveEpoch)` | Guardian | Submit epoch weights. `packed = (weight << 160) \| address`. |
| `settleEpoch(uint256 limit)` | Anyone | Settle epoch in batches. Mints AWP via mintAndCall. |
| `pauseEpochUntil(uint64 resumeTime)` | Guardian | Pause emission until timestamp. 0 = resume immediately. |
| `currentEpoch()` | View | Current epoch number |
| `currentDailyEmission()` | View | Today's emission amount |

---

## 5. Gasless Relay Endpoints

Base URL: https://api.awp.sh

All relay endpoints: POST, JSON body, rate limited (100/IP/hour). Returns `{ "txHash": "0x..." }` on success, `{ "error": "message" }` on failure.

### Endpoints

| Endpoint | Body Fields | Contract Call |
|----------|-------------|---------------|
| POST /api/relay/register | chainId, user, deadline, signature | setRecipientFor(user, user, ...) — self-registration |
| POST /api/relay/bind | chainId, agent, target, deadline, signature | bindFor(agent, target, ...) |
| POST /api/relay/unbind | chainId, user, deadline, signature | unbindFor(user, ...) |
| POST /api/relay/set-recipient | chainId, user, recipient, deadline, signature | setRecipientFor(user, recipient, ...) |
| POST /api/relay/grant-delegate | chainId, user, delegate, deadline, signature | grantDelegateFor(user, delegate, ...) |
| POST /api/relay/revoke-delegate | chainId, user, delegate, deadline, signature | revokeDelegateFor(user, delegate, ...) |
| POST /api/relay/allocate | chainId, staker, agent, worknetId, amount, deadline, signature | allocateFor(staker, agent, worknetId, amount, ...) |
| POST /api/relay/deallocate | chainId, staker, agent, worknetId, amount, deadline, signature | deallocateFor(staker, agent, worknetId, amount, ...) |
| POST /api/relay/register-worknet | chainId, user, name, symbol, worknetManager, salt, minStake, skillsUri, deadline, permitSignature, registerSignature | registerWorknetForWithPermit — requires TWO signatures (ERC-2612 permit + EIP-712 register) |
| GET /api/relay/status/{txHash} | — | Query relay tx confirmation status |

### EIP-712 Domains

AWPRegistry domain (for bind, unbind, setRecipient, grantDelegate, revokeDelegate, registerWorknet):
```json
{
  "name": "AWPRegistry",
  "version": "1",
  "chainId": <chain_id>,
  "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
}
```

AWPAllocator domain (for allocate, deallocate):
```json
{
  "name": "AWPAllocator",
  "version": "1",
  "chainId": <chain_id>,
  "verifyingContract": "0x0000D6BB5e040E35081b3AaF59DD71b21C9800AA"
}
```

### EIP-712 Type Definitions

```
Bind(address agent,address target,uint256 nonce,uint256 deadline)
Unbind(address user,uint256 nonce,uint256 deadline)
SetRecipient(address user,address recipient,uint256 nonce,uint256 deadline)
GrantDelegate(address user,address delegate,uint256 nonce,uint256 deadline)
RevokeDelegate(address user,address delegate,uint256 nonce,uint256 deadline)
RegisterWorknet(address user,WorknetParams params,uint256 nonce,uint256 deadline)WorknetParams(string name,string symbol,address worknetManager,bytes32 salt,uint128 minStake,string skillsURI)
Allocate(address staker,address agent,uint256 worknetId,uint256 amount,uint256 nonce,uint256 deadline)
Deallocate(address staker,address agent,uint256 worknetId,uint256 amount,uint256 nonce,uint256 deadline)
```

### Nonce Workflow

1. Get nonce: `nonce.get` (AWPRegistry) or `nonce.getStaking` (AWPAllocator)
2. Sign EIP-712 typed data with nonce in message
3. Submit to relay endpoint (nonce not in request body — embedded in signature)
4. Contract uses `nonces[user]++` for verification (post-increment)
5. Failed verification does NOT increment nonce

---

## 6. Vanity Salt Endpoints

| Endpoint | Description |
|----------|-------------|
| GET /api/vanity/mining-params | Get bytecodeHash, vanityRule, factoryAddress for salt mining |
| POST /api/vanity/upload-salts | Upload pre-mined salts to pool (rate limited: 5/hour/IP) |
| GET /api/vanity/salts | List available salts from pool |
| GET /api/vanity/salts/count | Count available salts |
| POST /api/vanity/compute-salt | Mine a vanity salt server-side (rate limited: 20/hour/IP) |

---

## 7. WebSocket Real-Time Events

Endpoint: `wss://api.awp.sh/ws/live`

### Subscription

Send JSON after connection:
```json
{
  "subscribe": ["WorknetActivated", "Allocated"],
  "watchAllocations": [
    { "agent": "0x...", "worknetId": "845300000002" }
  ],
  "watchAddresses": ["0x..."]
}
```

### Events

| Event | Source | Key Fields |
|-------|--------|------------|
| Allocated | AWPAllocator | staker, agent, worknetId, amount, operator |
| Deallocated | AWPAllocator | staker, agent, worknetId, amount, operator |
| Reallocated | AWPAllocator | staker, fromAgent, fromWorknetId, toAgent, toWorknetId, amount |
| Bound | AWPRegistry | addr, target |
| Unbound | AWPRegistry | addr |
| RecipientSet | AWPRegistry | addr, recipient |
| DelegateGranted | AWPRegistry | staker, delegate |
| DelegateRevoked | AWPRegistry | staker, delegate |
| WorknetRegistered | AWPRegistry | worknetId, owner, name, symbol |
| WorknetActivated | AWPRegistry | worknetId |
| WorknetPaused | AWPRegistry | worknetId |
| WorknetResumed | AWPRegistry | worknetId |
| WorknetBanned | AWPRegistry | worknetId |
| WorknetUnbanned | AWPRegistry | worknetId |
| WorknetRejected | AWPRegistry | worknetId |
| WorknetCancelled | AWPRegistry | worknetId |
| StakePositionCreated | veAWP | user, tokenId, amount, lockEndTime |
| StakePositionIncreased | veAWP | tokenId, addedAmount, newLockEndTime |
| StakePositionClosed | veAWP | user, tokenId, amount |
| EpochSettled | AWPEmission | epoch, totalEmission, recipientCount |
| AllocationsSubmitted | AWPEmission | epoch, totalWeight, recipients[], weights[] |
| GuardianUpdated | AWPRegistry | newGuardian |
| InitialAlphaPriceUpdated | AWPRegistry | newPrice |
| WorknetTokenFactoryUpdated | AWPRegistry | newFactory |
| WorknetNFTTransfer | AWPWorkNet | from, to, tokenId |

Each event includes `type`, `chainId`, `blockNumber`, `txHash`, and event-specific `data` fields.

---

## 8. Key Protocol Parameters

| Parameter | Value | Location |
|-----------|-------|----------|
| AWP MAX_SUPPLY | 10,000,000,000 (1e28) | AWPToken |
| WorknetToken MAX_SUPPLY | 10,000,000,000 (1e28) per worknet | WorknetToken |
| Initial Alpha Price | 1e15 (0.001 AWP per token) | AWPRegistry.initialAlphaPrice |
| Initial Alpha Mint | 1,000,000,000 * 1e18 | AWPRegistry.initialAlphaMint |
| Epoch Duration | 86400 (1 day) | AWPEmission.epochDuration |
| Emission Decay Factor | 996844 / 1000000 per epoch | AWPEmission.decayFactor |
| MAX_ACTIVE_WORKNETS | 10,000 | AWPRegistry |
| Max Bind Depth | 256 | AWPRegistry |
| Max Recipients | 10,000 | AWPEmission.maxRecipients |
| Treasury Timelock | 172,800 seconds (2 days) | Treasury.getMinDelay() |
| AWPDAO Proposal Threshold | 200,000 AWP (raw staked) | AWPDAO.proposalThreshold() |
| AWPDAO Voting Period | Configured at initialization | AWPDAO.votingPeriod() |
| veAWP Voting Power | amount * sqrt(min(remaining, 54 weeks) / 7 days) | veAWP/AWPDAO |
| WorknetManager Slippage | 1-5000 bps | WorknetManagerBase |
| Relay Rate Limit | 100 requests/hour/IP | Redis-configurable |
| Vanity Compute Limit | 20 requests/hour/IP | Redis-configurable |

---

## 9. Common User Workflows

### 9.1 Stake AWP
1. Approve AWP to veAWP contract
2. Call `veAWP.deposit(amount, lockDuration)` → receive position NFT (tokenId)
3. Position: amount locked until `block.timestamp + lockDuration`

### 9.2 Allocate Stake to Worknet
1. Must have veAWP position with sufficient unallocated balance
2. Call `AWPAllocator.allocate(staker, agent, worknetId, amount)`
3. Or gasless: sign EIP-712 → POST /api/relay/allocate

### 9.3 Register a Worknet
1. Approve AWP to AWPRegistry (amount = initialAlphaPrice * initialAlphaMint / 1e18)
2. Optionally mine vanity salt via /api/vanity/compute-salt
3. Call `AWPRegistry.registerWorknet(params)` → returns worknetId
4. Worknet starts in Pending status. Guardian calls activateWorknet to make it Active.
5. Or gasless: sign permit + registerWorknet → POST /api/relay/register-worknet

### 9.4 Bind Agent to Owner
1. Agent calls `AWPRegistry.bind(ownerAddress)`
2. Or gasless: sign EIP-712 → POST /api/relay/bind
3. Owner can resolve agent's rewards via `resolveRecipient(agent)`

### 9.5 Set Reward Recipient
1. Call `AWPRegistry.setRecipient(recipientAddress)`
2. Or gasless: POST /api/relay/set-recipient
3. All rewards for this address and its bound agents go to recipient

### 9.6 Delegate Operations
1. Staker calls `AWPRegistry.grantDelegate(delegateAddress)`
2. Delegate can now call allocate/deallocate on behalf of staker
3. Revoke: `AWPRegistry.revokeDelegate(delegateAddress)`

### 9.7 Vote on Proposal
1. Must have veAWP position with createdAt < proposal creation time
2. Call `AWPDAO.castVoteWithReasonAndParams(proposalId, support, reason, abi.encode(tokenIds))`
3. support: 0=Against, 1=For, 2=Abstain

### 9.8 Gasless Registration (for skills/agents)
1. Call `registry.get` RPC to get EIP-712 domain
2. Call `nonce.get` RPC with wallet address
3. Construct SetRecipient typed data: user=wallet, recipient=wallet, nonce, deadline
4. Sign with wallet private key
5. POST /api/relay/set-recipient with {chainId, user, recipient, deadline, signature}

### 9.9 Claim WorknetToken Rewards
1. Worknet operator submits Merkle root via `WorknetManager.setMerkleRoot(epoch, root)`
2. User calls `WorknetManager.claim(epoch, amount, proof)` to mint WorknetToken
