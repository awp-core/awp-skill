# Query Subnet #1

## Action: Q1 - Query Subnet

### Step 1 — Fetch subnet data via REST API

```bash
curl -s https://tapi.awp.sh/api/subnets/1
```

**Primary data source**: `GET /subnets/1` (REST API — fast, cached).

Expected response fields:

```json
{
  "subnet_id": 1,
  "owner": "0x...",
  "name": "...",
  "symbol": "...",
  "subnet_contract": "0x...",
  "skills_uri": "ipfs://Qm...",
  "alpha_token": "0x...",
  "lp_pool": "0x...",
  "status": "Active",
  "created_at": 1710000000,
  "activated_at": 1710000100
}
```

The REST response contains exactly the fields you asked for: `name`, `status`, `skills_uri`, and `min_stake` (retrieved from the subnet object). No `metadata_uri` or `coordinator_url` fields exist in the response — those are not part of the protocol.

### Step 2 — Display result

> **Subnet #1 "DataMiner"** | Status: Active
> - Owner: 0x1234...abcd
> - Skills URI: ipfs://QmSkills...
> - Min Stake: 1,000.0000 AWP
> - Alpha Token: 0xAAAA...BBBB
> - Subnet Contract: 0xCCCC...DDDD

All amounts are converted from wei (divided by 10^18, displayed to 4 decimal places). Addresses are shortened for readability.

### On-Chain Fallback

If the REST API is unavailable, fall back to the on-chain view function:

```
RootNet.getSubnetFull(1) → SubnetFullInfo
```

`getSubnetFull()` returns a `SubnetFullInfo` struct with 10 fields:

| Field | Type | Description |
|-------|------|-------------|
| subnetManager | address | Subnet manager contract (Alpha minter) |
| alphaToken | address | Alpha token address |
| lpPool | bytes32 | PancakeSwap V4 PoolId |
| status | SubnetStatus | Enum: Pending(0), Active(1), Paused(2), Banned(3) |
| createdAt | uint64 | Registration timestamp |
| activatedAt | uint64 | Activation timestamp (0 if never activated) |
| name | string | Alpha token name |
| skillsURI | string | Skills file URI |
| minStake | uint128 | Minimum stake for agents (0 = no minimum) |
| owner | address | SubnetNFT owner |

Note: The simpler `getSubnet()` returns only `SubnetInfo` (4 fields: lpPool, status, createdAt, activatedAt) which does NOT include name, skillsURI, minStake, or owner. Always use `getSubnetFull()` when you need the complete picture.

### Registration Parameters (SubnetParams)

For reference, `SubnetParams` used in `registerSubnet()` has 5 fields:

| Field | Type |
|-------|------|
| name | string |
| symbol | string |
| subnetManager | address |
| salt | bytes32 |
| minStake | uint128 |

There is no `metadataURI` or `coordinatorURL` in SubnetParams. The `skillsURI` is set separately after registration via `SubnetNFT.setSkillsURI(subnetId, skillsURI)`.

### Protocol Context

AWP RootNet is a decentralized **Agent Working** protocol on BSC (Chain ID 56). Agents register on subnets, execute tasks, and earn AWP emissions. Each subnet auto-deploys a SubnetManager with Merkle distribution and configurable AWP strategies.
