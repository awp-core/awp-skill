# AWP Protocol Reference (V2)

Shared definitions for the AWP skill.

---

## Multi-Chain Deployment

AWP is deployed on **4 chains** with identical contract addresses (except LPManager and WorknetManager impls which differ per DEX):

| Chain | Chain ID |
|-------|----------|
| Base | 8453 |
| Ethereum | 1 |
| Arbitrum | 42161 |
| BSC | 56 |

### Contract Addresses (Same on all 4 chains)

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

### WorknetManager Implementations (differ per chain)

Default implementation contracts for auto-deployed WorknetManagers. Each worknet gets its own ERC1967Proxy pointing to the chain's implementation.

| Chain | WorknetManager Impl | DEX |
|-------|-------------------|-----|
| Base (8453) | `0x00945e7fd4110b9c56ab4a3c2f53b6fabe6485e5` | Uniswap V4 |
| Ethereum (1) | `0x0029aABD49BF9ec7a34CDbcf75486B19CFAC3Ea8` | Uniswap V4 |
| Arbitrum (42161) | `0x00c428DCa1678e41Ed17Cc5AE3cF14430e2085A0` | Uniswap V4 |
| BSC (56) | `0x00D87f2f81E20cB1583F46d94BC7a7ad8f2DAC78` | PancakeSwap V4 |

---

## Data Structures

### WorknetStatus Enum

| Value | Name | Description |
|-------|------|-------------|
| 0 | Pending | Registered but not yet activated |
| 1 | Active | Operational, receiving allocations |
| 2 | Paused | Temporarily halted by owner |
| 3 | Banned | Governance-banned via Timelock |

### WorknetInfo (on-chain struct)

Returned by `AWPRegistry.getWorknet(worknetId)`. AWPRegistry lifecycle state only — identity data lives in WorknetNFT.

| Field | Type | Notes |
|-------|------|-------|
| lpPool | bytes32 | PancakeSwap V4 PoolId |
| status | WorknetStatus | Enum (0-3), see WorknetStatus above |
| createdAt | uint64 | Unix timestamp when worknet was registered |
| activatedAt | uint64 | Unix timestamp when activated (0 if never activated) |

> **Important**: On-chain WorknetInfo does NOT include `name`, `symbol`, `skillsURI`, `worknetManager`, `alphaToken`, `minStake`, or `owner`. Use `getWorknetFull()` or the JSON-RPC API for those fields.

### WorknetFullInfo (on-chain struct)

Returned by `AWPRegistry.getWorknetFull(worknetId)`. Combined: AWPRegistry state + WorknetNFT identity.

| Field | Type | Notes |
|-------|------|-------|
| worknetManager | address | Worknet manager contract (Alpha minter) |
| alphaToken | address | Alpha token address |
| lpPool | bytes32 | PancakeSwap V4 PoolId |
| status | WorknetStatus | Enum (0-3) |
| createdAt | uint64 | Unix timestamp when worknet was registered |
| activatedAt | uint64 | Unix timestamp when activated (0 if never activated) |
| name | string | Alpha token name |
| symbol | string | Alpha token symbol |
| skillsURI | string | Skills file URI (set via WorknetNFT.setSkillsURI) |
| minStake | uint128 | Minimum stake for agents (0 = no minimum) |
| owner | address | WorknetNFT owner |

### WorknetParams (registration input)

Used in `AWPRegistry.registerWorknet(params)`.

| Field | Type | Constraints |
|-------|------|-------------|
| name | string | Alpha token name, 1-64 bytes, no `"` or `\` |
| symbol | string | Alpha token symbol, 1-16 bytes, no `"` or `\` |
| worknetManager | address | `address(0)` = auto-deploy WorknetManager proxy |
| salt | bytes32 | CREATE2 salt; `bytes32(0)` = use worknetId as salt |
| minStake | uint128 | Minimum stake for agents (0 = no minimum) |
| skillsURI | string | Skills file URI (IPFS/HTTPS) |

### Worknet Lifecycle (AWPRegistry)

```solidity
registerWorknet(WorknetParams params)   // -> Pending
activateWorknet(uint256 worknetId)      // Pending -> Active, owner only
cancelWorknet(uint256 worknetId)        // Pending -> None (full AWP refund), owner only
pauseWorknet(uint256 worknetId)         // Active -> Paused, owner only
resumeWorknet(uint256 worknetId)        // Paused -> Active, owner only
```

### AgentInfo (on-chain struct)

Returned by `AWPRegistry.getAgentInfo(agent, worknetId)`.

| Field | Type |
|-------|------|
| boundTo | address |
| isValid | bool |
| stake | uint256 |
| recipient | address |

### StakeNFT Position

Returned by `StakeNFT.positions(tokenId)`.

| Field | Type | Notes |
|-------|------|-------|
| amount | uint128 | Staked AWP in wei |
| lockEndTime | uint64 | Unix timestamp when lock expires |
| createdAt | uint64 | Unix timestamp when position was created |

> **Important**: StakeNFT is NOT ERC721Enumerable. Token IDs cannot be iterated on-chain. Always retrieve position lists via `staking.getPositions(address)`.

---

## Event Field Table (19 types)

All events arrive via WebSocket (`wss://api.awp.sh/ws/live`) with envelope:
```json
{"type": "EventName", "blockNumber": 12345, "txHash": "0x...", "chainId": 8453, "data": {...}}
```

### User & Delegation Events

| Event | Source | Data Fields |
|-------|--------|-------------|
| UserRegistered | AWPRegistry | `{user, chainId}` |
| Bound | AWPRegistry | `{user, target, chainId}` |
| Unbound | AWPRegistry | `{user, chainId}` |
| RecipientSet | AWPRegistry | `{user, recipient, chainId}` |
| DelegateGranted | AWPRegistry | `{user, delegate, chainId}` |
| DelegateRevoked | AWPRegistry | `{user, delegate, chainId}` |

### Staking Events

| Event | Source | Data Fields | Pitfall |
|-------|--------|-------------|---------|
| Deposited | StakeNFT | `{user, tokenId, amount, lockEndTime, chainId}` | `lockEndTime` is **absolute** unix timestamp, NOT relative lock duration |
| Withdrawn | StakeNFT | `{user, tokenId, amount, chainId}` | — |
| Allocated | StakingVault | `{staker, agent, worknetId, amount, chainId}` | — |
| Deallocated | StakingVault | `{staker, agent, worknetId, amount, chainId}` | — |
| Reallocated | StakingVault | `{staker, fromAgent, fromWorknetId, toAgent, toWorknetId, amount, chainId}` | — |

### Worknet Events

| Event | Source | Data Fields |
|-------|--------|-------------|
| WorknetRegistered | AWPRegistry | `{worknetId, owner, name, symbol, chainId}` |
| WorknetActivated | AWPRegistry | `{worknetId, chainId}` |
| WorknetCancelled | AWPRegistry | `{worknetId, chainId}` |

### Emission Events

| Event | Source | Data Fields |
|-------|--------|-------------|
| EpochSettled | AWPEmission | `{epoch, totalEmission, recipientCount, chainId}` |
| RecipientAWPDistributed | AWPEmission | `{epoch, recipient, amount, chainId}` |
| AllocationsSubmitted | AWPEmission | `{epoch, totalWeight, recipients, weights, chainId}` |

### Protocol Events

| Event | Source | Data Fields |
|-------|--------|-------------|
| LPManagerUpdated | AWPRegistry | `{newLPManager, chainId}` |
| DefaultWorknetManagerImplUpdated | AWPRegistry | `{newImpl, chainId}` |

---

## EIP-712 Signing

### AWPRegistry Domain

Used for: bind, unbind, setRecipient, grantDelegate, revokeDelegate, registerWorknet, activateWorknet.

```json
{
  "name": "AWPRegistry",
  "version": "1",
  "chainId": <chainId>,
  "verifyingContract": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
}
```

Nonce: fetch via `nonce.get(address)`.

### StakingVault Domain

Used for: allocate, deallocate.

```json
{
  "name": "StakingVault",
  "version": "1",
  "chainId": <chainId>,
  "verifyingContract": "0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b"
}
```

Nonce: fetch via `nonce.getStaking(address)`.

### EIP-712 Type Definitions

```
Bind(address agent, address target, uint256 nonce, uint256 deadline)
Unbind(address user, uint256 nonce, uint256 deadline)
SetRecipient(address user, address recipient, uint256 nonce, uint256 deadline)
GrantDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
RevokeDelegate(address user, address delegate, uint256 nonce, uint256 deadline)
ActivateWorknet(address user, uint256 worknetId, uint256 nonce, uint256 deadline)
CancelWorknet(address user, uint256 worknetId, uint256 nonce, uint256 deadline)
RegisterWorknet(address user, WorknetParams params, uint256 nonce, uint256 deadline)
  with WorknetParams(string name, string symbol, address worknetManager, bytes32 salt, uint128 minStake, string skillsURI)
Allocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
Deallocate(address staker, address agent, uint256 worknetId, uint256 amount, uint256 nonce, uint256 deadline)
```

---

## StakeNFT — AWP Staking

```solidity
// Deposit AWP and mint a position NFT. lockDuration in seconds (min 1 day).
// Caller must approve StakeNFT to spend AWP first.
function deposit(uint256 amount, uint64 lockDuration) external returns (uint256 tokenId);

// Same as deposit but uses ERC-2612 permit (no prior approve needed — user signs a permit off-chain)
function depositWithPermit(uint256 amount, uint64 lockDuration, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external returns (uint256 tokenId);
```

## StakingVault — Allocation

```solidity
// Atomic move: deallocate from one (agent, worknet) and allocate to another in a single tx.
function reallocate(
    address staker,
    address fromAgent, uint256 fromWorknetId,
    address toAgent, uint256 toWorknetId,
    uint256 amount
) external;
```

---

## WorknetManager — Per-Worknet Operations

```solidity
// Merkle claim (any user with valid proof)
function claim(uint32 epoch, uint256 amount, bytes32[] calldata proof) external;
function isClaimed(uint32 epoch, address account) external view returns (bool);

// View
function alphaToken() external view returns (address);
function poolId() external view returns (bytes32);
function currentStrategy() external view returns (uint8); // 0=Reserve, 1=AddLiquidity, 2=BuybackBurn
function slippageBps() external view returns (uint256);     // Slippage tolerance in basis points
function strategyPaused() external view returns (bool);     // Whether auto-strategy is paused
```

---

## AWPDAO (`0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004`) — Governance

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

## Shared Endpoints (JSON-RPC)

### `registry.get`

Returns all protocol contract addresses + EIP-712 domain info. Fetch dynamically — contract addresses are the same on all chains but domain includes chainId.

```json
// Request
{"jsonrpc": "2.0", "method": "registry.get", "params": {}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {
  "chainId": 8453,
  "awpRegistry": "0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A",
  "awpToken": "0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1",
  "awpEmission": "0x3C9cB73f8B81083882c5308Cce4F31f93600EaA9",
  "stakingVault": "0xE8A204fD9c94C7E28bE11Af02fc4A4AC294Df29b",
  "stakeNFT": "0x4E119560632698Bab67cFAB5d8EC0A373363ba2d",
  "worknetNFT": "0xB9F03539BE496d09c4d7964921d674B8763f5233",
  "alphaTokenFactory": "0xB2e4897eD77d0f5BFa3140B9989594de09a8037c",
  "dao": "0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004",
  "treasury": "0x82562023a053025F3201785160CaE6051efD759e"
}, "id": 1}
```

### `address.check`

Check registration status for any address.

```json
// Request
{"jsonrpc": "2.0", "method": "address.check", "params": {"address": "0x..."}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {
  "isRegistered": true,
  "boundTo": "0x...",
  "recipient": "0x..."
}, "id": 1}
```

> `isRegistered` = `boundTo != 0x0 || recipient != 0x0`.

### `health.check`

```json
// Request
{"jsonrpc": "2.0", "method": "health.check", "params": {}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 1}
```

---

## Protocol Constants

| Constant | Value |
|----------|-------|
| Chains | Base (8453), Ethereum (1), Arbitrum (42161), BSC (56) |
| Epoch Duration | 1 day (86,400 seconds) |
| Initial Daily Emission | 31,600,000 AWP per chain |
| Decay Factor | 0.996844 per epoch (~0.3156% daily decay) |
| Emission Split | 50% recipients / 50% DAO |
| Max Active Worknets | 10,000 |
| Max Recipients | 10,000 |
| Max Weight Seconds | 54 weeks (32,659,200 seconds) — voting power sqrt cap |
| AWP Max Supply | 10,000,000,000 AWP (10^28 wei) |
| Alpha Max Supply | 10,000,000,000 per worknet (10^28 wei) |
| Token Decimals | 18 (all tokens) |
| Proposal Threshold | 1,000,000 AWP voting power |
| Worknet Registration Cost | 100,000 AWP (initialAlphaMint x initialAlphaPrice) |
| Alpha Mint per Worknet | 100,000,000 |
| WorknetId Format | `(chainId << 64) \| localCounter` — globally unique |
| Min Lock Duration (StakeNFT) | 1 day |
| Immunity Period | 30 days |
| Timelock Delay | 2 days |
| LP Pool Fee | 1% (PancakeSwap V4 CL) |
| LP Tick Spacing | 200 |
| Oracle Threshold | DAO-configured (initially 3/5 recommended) |

### Voting Power Formula

```
votingPower = amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
```

- `remainingTime` = `lockEndTime - block.timestamp` (in seconds)
- `54 weeks` = 32,659,200 seconds (MAX_WEIGHT_SECONDS)
- `7 days` = 604,800 seconds (base unit for sqrt)
- Time-based calculation using unix timestamps, not epoch numbers

---

## Amount Handling

All amounts in API responses and contract calls are **string-type wei** (18 decimals).

- Process with `BigInt`, never `Number` (precision loss above 2^53)
- Display as human-readable: `amount / 10^18`, show 4 decimal places
- Format helper: `{formatAWP(amount)}` -> e.g. "15,800,000.0000 AWP"
- Short address: `{shortAddr(addr)}` -> e.g. "0x1234...abcd"
