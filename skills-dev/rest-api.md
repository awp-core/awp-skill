# AWP REST API Reference

> Base URL: `https://api.awp.network/api` (configurable)

## System

### `GET /health`
```json
{"status": "ok"}
```

### `GET /registry`
Returns all 11 protocol contract addresses:
```json
{
  "rootNet": "0x...",
  "awpToken": "0x...",
  "awpEmission": "0x...",
  "stakingVault": "0x...",
  "stakeNFT": "0x...",
  "subnetNFT": "0x...",
  "accessManager": "0x...",
  "lpManager": "0x...",
  "alphaTokenFactory": "0x...",
  "dao": "0x...",
  "treasury": "0x..."
}
```

> **Note:** Per-subnet addresses (`subnet_contract`, `alpha_token`, `lp_pool`) are returned by `GET /subnets/{subnetId}`, not by `/registry`.

---

## Users

### `GET /users?page=1&limit=20`
Paginated user list.

### `GET /users/count`
```json
{"count": 1234}
```

### `GET /users/{address}`
```json
{
  "user": {"address": "0x...", "registered_at": 1710000000},
  "balance": {"user_address": "0x...", "total_staked": "5000000000000000000000", "total_allocated": "3000000000000000000000"},
  "rewardRecipient": {"user_address": "0x...", "recipient_address": "0x..."},
  "agents": [{"agent_address": "0x...", "owner_address": "0x...", "is_manager": false, "removed": false}]
}
```

### `GET /address/{address}/check`
```json
{
  "isRegisteredUser": true,
  "isRegisteredAgent": false,
  "ownerAddress": "",
  "isManager": false
}
```

---

## Agents

### `GET /agents/by-owner/{owner}`
```json
[{"agent_address": "0x...", "owner_address": "0x...", "is_manager": true, "removed": false}]
```

### `GET /agents/lookup/{agent}`
```json
{"ownerAddress": "0x..."}
```

### `POST /agents/batch-info`
**Request:**
```json
{"agents": ["0xagent1", "0xagent2"], "subnetId": 1}
```
**Response:**
```json
[
  {"agent": {"agent_address": "0x...", "owner_address": "0x..."}, "stake": "5000000000000000000000"},
  {"agent": {"agent_address": "0x...", "owner_address": "0x..."}, "stake": "3000000000000000000000"}
]
```
> Max 100 agents per request.

---

## Staking

### `GET /staking/user/{address}/balance`
```json
{
  "totalStaked": "10000000000000000000000",
  "totalAllocated": "5000000000000000000000",
  "unallocated": "5000000000000000000000"
}
```
> `totalStaked` is computed from StakeNFT positions. No `withdrawRequest` field.

### `GET /staking/user/{address}/positions`
StakeNFT position NFTs owned by the user:
```json
[
  {"token_id": 1, "amount": "5000000000000000000000", "lock_end_time": 1710604800, "created_at": 1710000000},
  {"token_id": 7, "amount": "5000000000000000000000", "lock_end_time": 1713196800, "created_at": 1710345600}
]
```

### `GET /staking/user/{address}/allocations?page=1&limit=20`
```json
[{"user_address": "0x...", "agent_address": "0x...", "subnet_id": 1, "amount": "5000000000000000000000", "frozen": false}]
```

### `GET /staking/agent/{agent}/subnet/{subnetId}`
```json
{"amount": "5000000000000000000000"}
```

### `GET /staking/agent/{agent}/subnets`
```json
[{"subnet_id": 1, "amount": "5000000000000000000000"}, {"subnet_id": 3, "amount": "2000000000000000000000"}]
```

### `GET /staking/subnet/{subnetId}/total`
```json
{"total": "50000000000000000000000"}
```

---

## Subnets

### `GET /subnets?status=Active&page=1&limit=20`
```json
[
  {
    "subnet_id": 1,
    "owner": "0x...",
    "name": "My Subnet",
    "symbol": "MSUB",
    "metadata_uri": "ipfs://...",
    "subnet_contract": "0x...",
    "coordinator_url": "https://...",
    "skills_uri": "ipfs://QmSkills...",
    "alpha_token": "0x...",
    "lp_pool": "0x...",
    "status": "Active",
    "created_at": 1710000000,
    "activated_at": 1710000100
  }
]
```
> `status` filter is optional. Values: `Pending`, `Active`, `Paused`, `Banned`.

### `GET /subnets/{subnetId}`
Single subnet detail (same fields as above).

### `GET /subnets/{subnetId}/earnings?page=1&limit=20`
```json
[{"epoch_id": 5, "recipient": "0x1234...", "awp_amount": "7900000000000000000000000"}]
```

### `GET /subnets/{subnetId}/skills`
```json
{"subnetId": 1, "skillsURI": "ipfs://QmSkillsFile..."}
```

### `GET /subnets/{subnetId}/agents/{agent}`
```json
{"agent": "0x...", "subnetId": 1, "stake": "5000000000000000000000"}
```

---

## Emission

### `GET /emission/current`
From Redis cache (TTL 30s, refreshed every 25s by Keeper):
```json
{"epoch": "42", "dailyEmission": "15000000000000000000000000", "totalWeight": "5000"}
```

### `GET /emission/schedule`
Projected emission for 30/90/365 days:
```json
{
  "currentDailyEmission": "15800000000000000000000000",
  "projections": [
    {"days": 30, "totalEmission": "452000000000000000000000000", "finalDailyRate": "14300000000000000000000000"},
    {"days": 90, "totalEmission": "1200000000000000000000000000", "finalDailyRate": "12000000000000000000000000"},
    {"days": 365, "totalEmission": "3500000000000000000000000000", "finalDailyRate": "5000000000000000000000000"}
  ]
}
```

### `GET /emission/epochs?page=1&limit=20`
```json
[{"epoch_id": 42, "start_time": 1710000000, "daily_emission": "15000000000000000000000000", "dao_emission": "7500000000000000000000000"}]
```

---

## Tokens

### `GET /tokens/awp`
From Redis cache (TTL 1m):
```json
{"totalSupply": "5015800000000000000000000000", "maxSupply": "10000000000000000000000000000"}
```

### `GET /tokens/alpha/{subnetId}`
```json
{"subnetId": 1, "name": "My Subnet Alpha", "symbol": "MSALPHA", "alphaToken": "0x..."}
```

### `GET /tokens/alpha/{subnetId}/price`
From Redis cache (TTL 10m):
```json
{"priceInAWP": "0.015", "reserve0": "...", "reserve1": "...", "updatedAt": "..."}
```

---

## Governance

### `GET /governance/proposals?status=Active&page=1&limit=20`
### `GET /governance/proposals/{proposalId}`
### `GET /governance/treasury`
```json
{"treasuryAddress": "0x..."}
```

---

## WebSocket

### `WS /ws/live`

```javascript
const ws = new WebSocket('wss://api.awp.network/ws/live');

// Subscribe to specific event types
ws.send(JSON.stringify({
  subscribe: ["RecipientAWPDistributed", "EpochSettled", "Allocated", "Deallocated"]
}));

// Receive events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { type: "RecipientAWPDistributed", blockNumber: 12345, txHash: "0x...", data: { epoch, recipient, awpAmount } }
};
```

### Event Types

| Event | Data Fields | Source |
|-------|-------------|--------|
| `UserRegistered` | `{user}` | RootNet |
| `AgentBound` | `{principal, agent, oldPrincipal}` | RootNet |
| `AgentUnbound` | `{principal, agent}` | RootNet |
| `AgentRemoved` | `{user, agent, operator}` | RootNet |
| `DelegationUpdated` | `{user, agent, isManager, operator}` | RootNet |
| `Deposited` | `{user, tokenId, amount, lockEndTime}` | StakeNFT |
| `PositionIncreased` | `{tokenId, addedAmount, newLockEndTime}` | StakeNFT |
| `Withdrawn` | `{user, tokenId, amount}` | StakeNFT |
| `Allocated` | `{user, agent, subnetId, amount, operator}` | RootNet |
| `Deallocated` | `{user, agent, subnetId, amount, operator}` | RootNet |
| `Reallocated` | `{user, fromAgent, fromSubnet, toAgent, toSubnet, amount, operator}` | RootNet |
| `SubnetRegistered` | `{subnetId, owner, name, symbol, metadataURI, subnetManager, alphaToken, coordinatorURL}` | RootNet |
| `LPCreated` | `{subnetId, poolId, awpAmount, alphaAmount}` | RootNet |
| `MetadataUpdated` | `{subnetId, metadataURI, coordinatorURL}` | RootNet |
| `SkillsURIUpdated` | `{subnetId, skillsURI}` | SubnetNFT |
| `MinStakeUpdated` | `{subnetId, minStake}` | SubnetNFT |
| `SubnetActivated` | `{subnetId}` | RootNet |
| `SubnetPaused` | `{subnetId}` | RootNet |
| `SubnetResumed` | `{subnetId}` | RootNet |
| `SubnetBanned` | `{subnetId}` | RootNet |
| `SubnetUnbanned` | `{subnetId}` | RootNet |
| `SubnetDeregistered` | `{subnetId}` | RootNet |
| `GovernanceWeightUpdated` | `{addr, weight}` | AWPEmission |
| `RecipientAWPDistributed` | `{epoch, recipient, awpAmount}` | AWPEmission |
| `DAOMatchDistributed` | `{epoch, amount}` | AWPEmission |
| `EpochSettled` | `{epoch, totalEmission, recipientCount}` | AWPEmission |
| `AllocationsSubmitted` | `{nonce, recipients, weights}` | AWPEmission |
| `OracleConfigUpdated` | `{oracles, threshold}` | AWPEmission |

---

## Relay (Gasless Transactions)

> Rate limit: 5 requests per IP per 4 hours (shared across both endpoints).
> Requires `RELAYER_PRIVATE_KEY` configured on the API server.

### `POST /relay/register`
Gasless user registration — relayer submits `registerFor()` on behalf of the user.

**Request:**
```json
{"user": "0x1234...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```

**Response:**
```json
{"txHash": "0x..."}
```

### `POST /relay/bind`
Gasless agent bind — relayer submits `bindFor()` on behalf of the agent.

**Request:**
```json
{"agent": "0xAgent...", "principal": "0xPrincipal...", "deadline": 1742400000, "signature": "0x...65 bytes hex (130 chars)"}
```

**Response:**
```json
{"txHash": "0x..."}
```

### `POST /relay/register-subnet`
Fully gasless subnet registration via `registerSubnetForWithPermit()`. User signs two off-chain messages (ERC-2612 permit for AWP + EIP-712 registerSubnet), relayer pays all gas. SubnetNFT + SubnetManager admin go to user.

**Request:**
```json
{
  "user": "0x...", "name": "EVO Alpha", "symbol": "EVO",
  "metadataURI": "ipfs://...", "subnetManager": "0x0000...0000",
  "coordinatorURL": "https://...", "salt": "0x...",
  "minStake": "0", "deadline": 1742400000,
  "permitSignature": "0x...65 bytes (ERC-2612 AWP permit)",
  "registerSignature": "0x...65 bytes (EIP-712 registerSubnet)"
}
```

**Response:**
```json
{"txHash": "0x..."}
```

**Two signatures required:**
- `permitSignature`: ERC-2612 permit — authorizes RootNet to spend user's AWP (no prior approve tx needed)
- `registerSignature`: EIP-712 — authorizes subnet registration parameters

Both are standard 65-byte signatures (r[32] + s[32] + v[1]), hex-encoded with `0x` prefix.

**Error responses:**
| Code | Body | Meaning |
|------|------|---------|
| 400 | `{"error": "..."}` | Invalid params, expired deadline, bad signature format |
| 429 | `{"error": "rate limit exceeded: max 5 requests per 4 hours"}` | IP rate limit exceeded |
| 500 | `{"error": "relay transaction failed"}` | On-chain transaction submission failed |

---

## Vanity Address (Salt Pool + Mining)

> Salt pool: pre-mined salts stored in DB, claimed atomically on demand.
> Fallback: if pool is empty, `cast create2` mines in real-time (max 2 concurrent, 120s timeout).

### `GET /vanity/mining-params`
Returns parameters needed by external tools to mine salts offline.
```json
{"factoryAddress": "0xAe8E...", "initCodeHash": "0xec76...", "vanityRule": "0x0A01FFFF0C0A0F0E"}
```

### `POST /vanity/upload-salts`
Batch upload pre-mined salts (max 1000/request). Each salt is verified: CREATE2 address correctness + vanityRule compliance.
```json
// Request
{"salts": [{"salt": "0x1234...", "address": "0xa1...cafe"}, ...]}
// Response
{"inserted": 98, "rejected": 2}
```

### `GET /vanity/salts`
List available (unclaimed) salts. Supports `?limit=` pagination.

### `GET /vanity/salts/count`
```json
{"available": 42}
```

### `POST /vanity/compute-salt`
Get a salt: tries DB pool first (O(1) atomic claim), falls back to `cast create2` if pool is empty.

**Response:**
```json
{"salt": "0x530c...", "address": "0xa1...cafe", "source": "pool", "elapsed": "1ms"}
```
`source` is `"pool"` or `"mined"`.

**Error responses:**
| Code | Body | Meaning |
|------|------|---------|
| 408 | `{"error": "search timed out..."}` | No match found within 120s timeout |
| 500 | `{"error": "..."}` | Mining engine error |

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Resource not found |
| 429 | Rate limit exceeded (relay endpoints) |
| 500 | Internal server error |

## Pagination

All paginated endpoints accept `page` (1-based) and `limit` (default 20, max 100).
