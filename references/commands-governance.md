# AWP Governance Commands

**API Endpoint**: `POST https://api.awp.sh/v2` (JSON-RPC 2.0)

> **IMPORTANT**: Always use the bundled `scripts/*.py` files for write operations — they handle ABI encoding natively in Python, require only python3, and work without Foundry or curl/jq.
> The `cast calldata` examples below are for reference only; do NOT run them directly.

## Setup (reference only — bundled scripts handle this automatically)

```bash
# Reference only — actual operations are handled automatically by scripts/*.py
# Contract addresses (same on all chains)
AWP_REGISTRY="0x0000F34Ed3594F54faABbCb2Ec45738DDD1c001A"
AWP_TOKEN="0x0000A1050AcF9DEA8af9c2E74f0D7CF43f1000A1"
STAKE_NFT="0x4E119560632698Bab67cFAB5d8EC0A373363ba2d"
WORKNET_NFT="0xB9F03539BE496d09c4d7964921d674B8763f5233"
DAO_ADDR="0x6a074aC9823c47f86EE4Fc7F62e4217Bc9C76004"
TREASURY="0x82562023a053025F3201785160CaE6051efD759e"

WALLET_ADDR=$(awp-wallet receive | jq -r '.eoaAddress')
```

---

## G1 · Create Proposal

### Contract Calls

```solidity
// Executable proposal (via Timelock)
function proposeWithTokens(
    address[] targets, uint256[] values, bytes[] calldatas,
    string description, uint256[] tokenIds
) returns (uint256 proposalId)
// Requires >= 1,000,000 AWP voting power across tokenIds

// Signal-only proposal (no execution, no Timelock)
function signalPropose(string description, uint256[] tokenIds) returns (uint256 proposalId)

// Check proposal type
function isSignalProposal(uint256 proposalId) view returns (bool)
```

---

## G2 · Vote

### Contract Call

```solidity
function castVoteWithReasonAndParams(
    uint256 proposalId, uint8 support, string reason, bytes params
)
// support: 0=Against, 1=For, 2=Abstain
// params = encodeAbiParameters([{type:'uint256[]'}], [tokenIds])
// DO NOT use encodePacked — use encodeAbiParameters
//
// BLOCKED: castVote() and castVoteWithReason() revert — MUST use params variant
//
// Voting power: amount * sqrt(min(remainingTime, 54 weeks) / 7 days)
// Anti-manipulation: NFTs with createdAt >= proposalCreatedAt CANNOT vote
//   (only positions created strictly before the proposal timestamp are eligible)
// Per-tokenId double-vote prevention
```

### Supporting View Functions

```solidity
function hasVotedWithToken(uint256 proposalId, uint256 tokenId) view returns (bool)
function proposalCreatedAt(uint256 proposalId) view returns (uint64)   // Timestamp when proposal was created
```

### Complete Command Template

```bash
# The bundled script handles position filtering, ABI encoding, and raw call automatically:
python3 scripts/onchain-vote.py --token {T} --proposal {proposalId} --support 1 --reason "I support this"
# support: 0=Against, 1=For, 2=Abstain
```

---

## G3 · Query Proposals

### JSON-RPC

```json
// List proposals (with optional status filter)
{"jsonrpc": "2.0", "method": "governance.listProposals", "params": {"status": "Active", "page": 1, "limit": 20}, "id": 1}

// List all proposals cross-chain
{"jsonrpc": "2.0", "method": "governance.listAllProposals", "params": {"status": "Active", "page": 1, "limit": 20}, "id": 1}

// Get specific proposal
{"jsonrpc": "2.0", "method": "governance.getProposal", "params": {"proposalId": "123"}, "id": 1}
```

Proposal status values: `Active`, `Canceled`, `Defeated`, `Succeeded`, `Queued`, `Expired`, `Executed`.

### On-Chain Enrichment

```solidity
function proposalVotes(uint256 proposalId) view returns (uint256 againstVotes, uint256 forVotes, uint256 abstainVotes)
function isSignalProposal(uint256 proposalId) view returns (bool)
function proposalCreatedAt(uint256 proposalId) view returns (uint64)
function quorum(uint256) view returns (uint256)
function proposalThreshold() view returns (uint256)   // 1,000,000 AWP
```

---

## G4 · Query Treasury

### JSON-RPC

```json
{"jsonrpc": "2.0", "method": "governance.getTreasury", "params": {}, "id": 1}
```

Treasury address: `0x82562023a053025F3201785160CaE6051efD759e`

### On-Chain (optional balance check)

```solidity
function balanceOf(address account) view returns (uint256)   // on AWPToken
```

---

## Supplementary Endpoints

### AWP Token Info

```json
// Single chain
{"jsonrpc": "2.0", "method": "tokens.getAWP", "params": {}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {"totalSupply": "5015800000000000000000000000", "maxSupply": "10000000000000000000000000000"}, "id": 1}

// Aggregated across all chains
{"jsonrpc": "2.0", "method": "tokens.getAWPGlobal", "params": {}, "id": 1}
```

### Alpha Token Info

```json
{"jsonrpc": "2.0", "method": "tokens.getAlphaInfo", "params": {"worknetId": "1"}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {"worknetId": "1", "name": "My Worknet Alpha", "symbol": "MWALPHA", "alphaToken": "0x..."}, "id": 1}
```

### Alpha Token Price

```json
{"jsonrpc": "2.0", "method": "tokens.getAlphaPrice", "params": {"worknetId": "1"}, "id": 1}

// Response (cached 10min)
{"jsonrpc": "2.0", "result": {"priceInAWP": "0.015", "reserve0": "...", "reserve1": "...", "updatedAt": "..."}, "id": 1}
```

### User Profile

```json
{"jsonrpc": "2.0", "method": "users.get", "params": {"address": "0x..."}, "id": 1}

// Response
{"jsonrpc": "2.0", "result": {
  "user": {"address": "0x...", "boundTo": "0x...", "recipient": "0x...", "registeredAt": 1710000000},
  "balance": {"totalStaked": "5000000000000000000000", "totalAllocated": "3000000000000000000000"}
}, "id": 1}

// Full portfolio (identity + balance + positions + allocations + delegates)
{"jsonrpc": "2.0", "method": "users.getPortfolio", "params": {"address": "0x..."}, "id": 1}
```

### Staking Details

```json
// Agent stake in worknet
{"jsonrpc": "2.0", "method": "staking.getAgentSubnetStake", "params": {"agent": "0x...", "worknetId": "1"}, "id": 1}

// All worknets agent participates in
{"jsonrpc": "2.0", "method": "staking.getAgentSubnets", "params": {"agent": "0x..."}, "id": 1}

// Total stake in worknet
{"jsonrpc": "2.0", "method": "staking.getSubnetTotalStake", "params": {"worknetId": "1"}, "id": 1}
```

### Worknet Earnings

```json
{"jsonrpc": "2.0", "method": "subnets.getEarnings", "params": {"worknetId": "1", "page": 1, "limit": 20}, "id": 1}
```
