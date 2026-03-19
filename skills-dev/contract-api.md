# AWP Smart Contract API Reference

## Chain Info
- **Network**: EVM chain (configured at deployment)
- **RPC**: Chain RPC endpoint (from `RPC_URL` env var)
- **Block time**: ~3 seconds
- **EVM version**: Cancun (supports transient storage)

---

## AWPRegistry — Unified Entry Point

> EIP-712 domain name: "AWPRegistry"

### Account System (V2)
```
register()                                                    // Optional; equivalent to setRecipient(msg.sender)
bind(address target)                                          // Tree-based binding with anti-cycle check
bindFor(address user, address target, uint256 deadline, uint8 v, bytes32 r, bytes32 s)  // Gasless EIP-712
setRecipient(address recipient)                               // Set reward recipient
setRecipientFor(address user, address recipient, uint256 deadline, uint8 v, bytes32 r, bytes32 s) // Gasless EIP-712
grantDelegate(address delegate)                               // Grant delegation to an address
revokeDelegate(address delegate)                              // Revoke delegation from an address
resolveRecipient(address addr) view                           // Walks boundTo chain to root
isRegistered(address addr) view                               // boundTo[addr] != 0 || recipient[addr] != 0
```

### Staking (Allocation Only — deposit/withdraw via StakeNFT)
```
allocate(address staker, address agent, uint256 subnetId, uint256 amount)      // Staker or delegate
deallocate(address staker, address agent, uint256 subnetId, uint256 amount)    // Staker or delegate
reallocate(address staker, address fromAgent, uint256 fromSubnetId, address toAgent, uint256 toSubnetId, uint256 amount) // Staker or delegate, immediate
```

### Subnet Lifecycle
```
registerSubnet(SubnetParams params) → uint256 subnetId         // Anyone (costs AWP). subnetManager=0 auto-deploys SubnetManager proxy.
registerSubnetFor(address user, SubnetParams params, uint256 deadline, uint8 v, bytes32 r, bytes32 s) // Gasless (requires prior AWP approve)
registerSubnetForWithPermit(user, params, deadline, permitV, permitR, permitS, registerV, registerR, registerS) // Fully gasless (ERC-2612 permit + EIP-712)
activateSubnet(uint256 subnetId)                               // NFT Owner: Pending → Active
pauseSubnet(uint256 subnetId)                                  // NFT Owner: Active → Paused
resumeSubnet(uint256 subnetId)                                 // NFT Owner: Paused → Active
```

### Governance (Timelock only)
```
banSubnet(uint256 subnetId)                                    // Active/Paused → Banned
unbanSubnet(uint256 subnetId)                                  // Banned → Active
deregisterSubnet(uint256 subnetId)                             // Delete (after 30-day immunity)
setInitialAlphaPrice(uint256 price)
setGuardian(address g)
setImmunityPeriod(uint256 p)                                   // Minimum 7 days
setAlphaTokenFactory(address factory)                          // Replace factory for new subnets
setSubnetManagerImpl(address impl)                              // Set/update auto-deploy impl
```

### View Functions
```
getSubnet(uint256 subnetId) → SubnetInfo                       // Lifecycle state only (lpPool, status, timestamps)
getSubnetFull(uint256 subnetId) → SubnetFullInfo               // Combined: AWPRegistry state + SubnetNFT identity
getActiveSubnetCount() → uint256
getActiveSubnetIdAt(uint256 index) → uint256
isSubnetActive(uint256 subnetId) → bool
nextSubnetId() → uint256
getAgentInfo(address agent, uint256 subnetId) → AgentInfo
getAgentsInfo(address[] agents, uint256 subnetId) → AgentInfo[]
getRegistry() → (awpToken, subnetNFT, alphaTokenFactory, awpEmission, lpManager, stakingVault, stakeNFT, treasury, guardian)
resolveRecipient(address addr) → address                       // Walks boundTo chain to root
isRegistered(address addr) → bool                              // boundTo[addr] != 0 || recipient[addr] != 0
boundTo(address addr) → address
recipient(address addr) → address
delegates(address user, address delegate) → bool
nonces(address) → uint256
```

### Emergency
```
pause()     // Guardian only
unpause()   // Timelock only
```

---

## AWPEmission — Emission Engine (UUPS Proxy) [DRAFT]

> **This section describes a preliminary design. The emission mechanism has not been finalized.**

### Oracle Submission
```
submitAllocations(address[] recipients, uint96[] weights, bytes[] signatures, uint256 effectiveEpoch)
// Requires >= oracleThreshold valid EIP-712 oracle signatures
// effectiveEpoch must be > settledEpoch (future epoch)
// Full replacement: clears old allocations for that epoch, writes new ones
// Allowed during settlement (epoch-versioned design)
```

### Epoch Settlement
```
settleEpoch(uint256 limit)
// Anyone can call. Processes up to `limit` recipients per call.
// Phase 1 (first call): initialize epoch, snapshot weights, check settledEpoch < currentEpoch()
// Phase 2 (each call): mint AWP to recipients proportionally
// Phase 3 (final call): mint DAO share, advance settledEpoch
```

### Governance (Timelock only)
```
emergencySetWeight(uint256 epoch, uint256 index, address addr, uint96 weight)  // Overwrite entry at index; addr must not be address(0)
setOracleConfig(address[] oracles, uint256 threshold)
upgradeToAndCall(address newImpl, bytes data)                   // UUPS upgrade
```

### View Functions
```
currentEpoch() → uint256                                       // Time-based: (block.timestamp - genesisTime) / epochDuration (1 day)
genesisTime() → uint256                                        // Immutable, set at initialization
epochDuration() → uint256                                      // Immutable, 86400 (1 day)
settledEpoch() → uint256                                       // Number of epochs settled so far
activeEpoch() → uint256                                        // Most recently promoted weight epoch
currentDailyEmission() → uint256                               // Current epoch emission (wei)
settleProgress() → uint256                                     // 0=idle, >0=in progress
epochEmissionLocked() → uint256
oracleThreshold() → uint256
allocationNonce() → uint256
maxRecipients() → uint256
awpRegistry() → address
getOracleCount() → uint256
getRecipientCount() → uint256
getRecipient(uint256 index) → address
getWeight(address addr) → uint96                               // Active epoch weight (O(n) scan)
getTotalWeight() → uint256                                     // Active epoch total weight
getEpochRecipientCount(uint256 epoch) → uint256
getEpochWeight(uint256 epoch, address addr) → uint96
getEpochTotalWeight(uint256 epoch) → uint256
oracles(uint256 index) → address
```

---

## Data Structures

```solidity
enum SubnetStatus { Pending, Active, Paused, Banned }

// AWPRegistry lifecycle state only — identity data in SubnetNFT
struct SubnetInfo {
    bytes32 lpPool;            // PancakeSwap V4 PoolId
    SubnetStatus status;
    uint64 createdAt;
    uint64 activatedAt;
}

// Combined: AWPRegistry state + SubnetNFT identity
struct SubnetFullInfo {
    address subnetManager;     // Subnet manager contract (Alpha minter)
    address alphaToken;        // Alpha token address
    bytes32 lpPool;
    SubnetStatus status;
    uint64 createdAt;
    uint64 activatedAt;
    string name;
    string skillsURI;
    uint128 minStake;
    address owner;
}

struct SubnetParams {
    string name;               // Alpha token name (1-64 bytes)
    string symbol;             // Alpha token symbol (1-16 bytes)
    address subnetManager;     // address(0) = auto-deploy SubnetManager proxy
    bytes32 salt;              // CREATE2 salt; bytes32(0) = use subnetId as salt
    uint128 minStake;          // Minimum stake for agents (0 = no minimum)
    string skillsURI;          // Skills file URI (IPFS/HTTPS)
}

struct AgentInfo {
    address boundTo;
    bool isValid;
    uint256 stake;
    address recipient;
}
```

---

## StakeNFT — ERC721 Position NFT

```
deposit(uint256 amount, uint64 lockDuration) → uint256 tokenId   // Deposit AWP + mint position NFT; lockDuration in seconds
depositFor(address user, uint256 amount, uint64 lockDuration) → uint256 tokenId // onlyAWPRegistry
addToPosition(uint256 tokenId, uint256 amount, uint64 newLockEndTime) // Add AWP and/or extend lock; reverts PositionExpired if lock expired
withdraw(uint256 tokenId)                                        // Withdraw after lock expires (burns NFT)
```

### View Functions
```
positions(uint256 tokenId) → (uint128 amount, uint64 lockEndTime, uint64 createdAt)
getUserTotalStaked(address user) → uint256                       // O(1) total staked balance
getVotingPower(uint256 tokenId) → uint256                        // amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
getUserVotingPower(address user, uint256[] tokenIds) → uint256   // Sum voting power for given tokenIds
totalVotingPower() → uint256                                     // Upper-bound estimate
getPositionForVoting(uint256 tokenId) → (address owner, uint128 amount, uint64 lockEndTime, uint64 createdAt, uint64 remaining, uint256 votingPower)
remainingTime(uint256 tokenId) → uint64                          // Remaining lock time in seconds
```

---

## StakingVault — Pure Allocation Logic

```
setStakeNFT(address stakeNFT_)                                            // onlyAWPRegistry, one-time (called by initializeRegistry)
allocate(address staker, address agent, uint256 subnetId, uint256 amount)    // onlyAWPRegistry
deallocate(address staker, address agent, uint256 subnetId, uint256 amount)  // onlyAWPRegistry
reallocate(address staker, address fromAgent, uint256 fromSubnetId, address toAgent, uint256 toSubnetId, uint256 amount) // onlyAWPRegistry
freezeAgentAllocations(address staker, address agent)                        // onlyAWPRegistry; auto-enumerates subnets
```

### View Functions
```
userTotalAllocated(address staker) → uint256
getAgentStake(address staker, address agent, uint256 subnetId) → uint256
subnetTotalStake(uint256 subnetId) → uint256
getSubnetTotalStake(uint256 subnetId) → uint256
getAgentSubnets(address staker, address agent) → uint256[]
```

---

## SubnetNFT — ERC721 with On-Chain Identity

```
// AWPRegistry-only writes
mint(address to, uint256 tokenId, string name_, address subnetManager_, address alphaToken_, uint128 minStake_, string skillsURI_) // onlyAWPRegistry
burn(uint256 tokenId)                                          // onlyAWPRegistry
setBaseURI(string uri)                                         // onlyAWPRegistry

// Owner-updatable
setSkillsURI(uint256 tokenId, string skillsURI_)               // NFT owner only
setMinStake(uint256 tokenId, uint128 minStake_)                // NFT owner only
```

### View Functions
```
getSubnetData(uint256 tokenId) → SubnetData                    // Full identity + metadata
getSubnetManager(uint256 tokenId) → address
getAlphaToken(uint256 tokenId) → address
getMinStake(uint256 tokenId) → uint128
ownerOf(uint256 tokenId) → address                             // Standard ERC721
tokenURI(uint256 tokenId) → string                             // baseURI + tokenId
```

### Events
```
SkillsURIUpdated(uint256 indexed tokenId, string skillsURI)
MinStakeUpdated(uint256 indexed tokenId, uint128 minStake)
```

---

## AWPToken — ERC20 + ERC1363 + Votes

```
mint(address to, uint256 amount)                               // Authorized minters only
mintAndCall(address to, uint256 amount, bytes data)             // Mint + ERC1363 onTransferReceived callback
transferAndCall(address to, uint256 amount, bytes data)         // Transfer + ERC1363 callback
approveAndCall(address spender, uint256 amount, bytes data)     // Approve + ERC1363 callback
burn(uint256 amount)
```

---

## SubnetManager — Default Subnet Contract (Proxy)

> Auto-deployed by AWPRegistry when `subnetManager = address(0)`. Uses AccessControl (OZ).

### Roles
```
DEFAULT_ADMIN_ROLE = 0x00                       // Grant/revoke roles; assigned to subnet registrant
MERKLE_ROLE = keccak256("MERKLE_ROLE")          // Submit Merkle roots
STRATEGY_ROLE = keccak256("STRATEGY_ROLE")      // Set/execute AWP strategy
TRANSFER_ROLE = keccak256("TRANSFER_ROLE")      // Transfer tokens out
```

### Merkle Distribution (MERKLE_ROLE)
```
setMerkleRoot(uint32 epoch, bytes32 root)                      // Submit Merkle root for an epoch
claim(uint32 epoch, uint256 amount, bytes32[] proof)           // Public; mints Alpha to msg.sender
isClaimed(uint32 epoch, address account) → bool
```
> Leaf = `keccak256(keccak256(abi.encode(account, amount)))`

### AWP Strategy (STRATEGY_ROLE)
```
setStrategy(AWPStrategy strategy)                              // 0=Reserve, 1=AddLiquidity, 2=BuybackBurn
executeStrategy(uint256 amount)                                // Manually execute on held AWP
```

### ERC1363 Receiver (auto-trigger)
```
onTransferReceived(operator, from, amount, data) → bytes4      // Called by AWPToken.mintAndCall; auto-executes strategy
```

### Token Transfer (TRANSFER_ROLE)
```
transferToken(address token, address to, uint256 amount)
```

### View Functions
```
alphaToken() → address
awpToken() → address
poolId() → bytes32
currentStrategy() → AWPStrategy
merkleRoots(uint32 epoch) → bytes32
```

---

## AWPDAO — Custom NFT-Based Voting

```
proposeWithTokens(address[] targets, uint256[] values, bytes[] calldatas, string description, uint256[] tokenIds) → uint256 proposalId
signalPropose(string description, uint256[] tokenIds) → uint256 proposalId
// Signal-only: no on-chain execution, skips Timelock. Vote result recorded on-chain.
// After vote succeeds, call execute(targets=[address(dao)], values=[0], calldatas=[""], descriptionHash) to finalize.
castVoteWithReasonAndParams(uint256 proposalId, uint8 support, string reason, bytes params)
// params = abi.encode(uint256[] tokenIds)
// Voting power = amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
// Anti-manipulation: only NFTs with createdAt < proposalCreatedAt can vote (timestamp-based)
// Per-tokenId double-vote prevention
// castVote() and castVoteWithReason() are blocked — must use params variant
```

### View Functions
```
proposalVotes(uint256 proposalId) → (uint256 againstVotes, uint256 forVotes, uint256 abstainVotes)
hasVotedWithToken(uint256 proposalId, uint256 tokenId) → bool
isSignalProposal(uint256 proposalId) → bool
proposalCreatedAt(uint256 proposalId) → uint64                  // Timestamp when proposal was created
quorum(uint256) → uint256                                       // totalVotingPower * quorumPercent / 100
proposalThreshold() → uint256                                   // 1,000,000 AWP
```

---

## Constants

| Constant | Value |
|----------|-------|
| AWP MAX_SUPPLY | 10,000,000,000 × 10^18 |
| Alpha MAX_SUPPLY | 10,000,000,000 × 10^18 (per subnet) |
| INITIAL_DAILY_EMISSION | 15,800,000 × 10^18 |
| EPOCH_DURATION | 86,400 (1 day), immutable on AWPEmission |
| DECAY_FACTOR | 996844 / 1000000 per epoch |
| EMISSION_SPLIT | 50% recipients / 50% DAO |
| MAX_ACTIVE_SUBNETS | 10,000 |
| maxRecipients | 10,000 |
| MAX_WEIGHT_SECONDS | 54 weeks (32,659,200s) |
| Default immunity | 30 days |
