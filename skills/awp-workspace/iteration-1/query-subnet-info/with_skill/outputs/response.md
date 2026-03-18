# Query Subnet 5 — Execution Plan

## Task

User requests: "查一下 subnet 5 的详细信息，包括 skills URI 和 alpha token 价格"

This is a read-only query — no wallet required. It maps to **Q1 (Query Subnet)** plus **Q6 (Query Skills URI)** plus the supplementary **Alpha Token Price** endpoint.

---

## Step 1: Fetch Contract Registry

Before any API call, fetch dynamic contract addresses (per skill convention: never hardcode).

```
GET {AWP_API_URL}/registry
```

Expected response:
```json
{
  "rootNet": "0x...",
  "subnetNFT": "0x...",
  "stakeNFT": "0x...",
  "dao": "0x...",
  "awpToken": "0x...",
  "stakingVault": "0x...",
  "awpEmission": "0x...",
  "treasury": "0x..."
}
```

Store `rootNet` address for potential on-chain fallback.

---

## Step 2: Fetch Subnet Details, Skills URI, and Alpha Token Price (in parallel)

Three independent GET requests, issued concurrently:

### 2a. Subnet Info (Action Q1)

```
GET {AWP_API_URL}/subnets/5
```

Expected response:
```json
{
  "subnet_id": 5,
  "owner": "0x...",
  "name": "...",
  "symbol": "...",
  "metadata_uri": "ipfs://...",
  "subnet_contract": "0x...",
  "coordinator_url": "https://...",
  "skills_uri": "ipfs://Qm...",
  "alpha_token": "0x...",
  "lp_pool": "0x...",
  "status": "Active",
  "created_at": 1710000000,
  "activated_at": 1710000100
}
```

### 2b. Skills URI (Action Q6)

```
GET {AWP_API_URL}/subnets/5/skills
```

Expected response:
```json
{
  "subnetId": 5,
  "skillsURI": "ipfs://QmSkillsFile..."
}
```

Note: This is redundant with the `skills_uri` field in Q1, but serves as a dedicated endpoint and confirms the indexed value. If Q1 already returns `skills_uri`, this call provides cross-validation.

### 2c. Alpha Token Price (Supplementary Endpoint)

```
GET {AWP_API_URL}/tokens/alpha/5/price
```

Expected response:
```json
{
  "priceInAWP": "0.015",
  "reserve0": "...",
  "reserve1": "...",
  "updatedAt": "..."
}
```

---

## Step 3: Error Handling

- If any request returns **404 Not Found**: report "Subnet 5 does not exist" and suggest using Q5 (`GET /subnets?status=Active`) to list available subnets.
- If the REST API is unreachable (500 / timeout): fall back to on-chain read for subnet info only.

### On-Chain Fallback (if REST fails for subnet info)

Call `RootNet.getSubnet(5)` on BSC (Chain ID 56) using the `rootNet` address from `/registry`.

```solidity
function getSubnet(uint256 subnetId) view returns (SubnetInfo)
// Returns: (subnetContract, alphaToken, lpPool, status, createdAt, activatedAt)
```

**Limitation**: On-chain `SubnetInfo` does NOT include string fields (`name`, `symbol`, `metadata_uri`, `coordinator_url`, `skills_uri`). These are only available from the REST API (indexed off-chain from `SubnetRegistered` / `MetadataUpdated` events). If the API is down, inform the user that name, skills URI, and metadata are unavailable and only on-chain fields can be shown.

There is no on-chain fallback for alpha token price — that requires reading LP pool reserves directly, which is not covered by a simple view function in the skill.

---

## Step 4: Format and Display Output

Using the data from all three responses, format the output as follows:

```
Subnet #5 — {subnet.name} ({subnet.symbol})

  Status:          {subnet.status}
  Owner:           {shortAddr(subnet.owner)}
  Subnet Contract: {shortAddr(subnet.subnet_contract)}
  Coordinator:     {subnet.coordinator_url}
  Metadata URI:    {subnet.metadata_uri}
  Skills URI:      {subnet.skills_uri}
  Created:         {tsToDate(subnet.created_at)}
  Activated:       {tsToDate(subnet.activated_at)}

Alpha Token
  Address:         {shortAddr(subnet.alpha_token)}
  LP Pool:         {shortAddr(subnet.lp_pool)}
  Price:           {priceInAWP} AWP per Alpha
  Last Updated:    {updatedAt}
```

### Formatting Rules Applied

- **Amounts**: All wei values converted via `amount / 10^18`, displayed to 4 decimal places (`{formatAWP(amount)}`).
- **Addresses**: Shortened with `{shortAddr(addr)}` (e.g., `0x1234...abcd`) in display. Full addresses available on request.
- **Timestamps**: Converted from Unix epoch to human-readable date via `{tsToDate(ts)}`.
- **Price**: Shown as-is from the API response (already human-readable string).
- **BSCScan links**: Optionally linkable — `https://bscscan.com/address/{subnet.alpha_token}` for the alpha token contract.

---

## Summary of API Calls

| # | Method | Endpoint | Action ID | Purpose |
|---|--------|----------|-----------|---------|
| 1 | GET | `/registry` | — | Fetch contract addresses (for fallback) |
| 2 | GET | `/subnets/5` | Q1 | Full subnet details |
| 3 | GET | `/subnets/5/skills` | Q6 | Skills URI (cross-validation) |
| 4 | GET | `/tokens/alpha/5/price` | Supplementary | Alpha token price in AWP |

Calls 2, 3, and 4 are independent and execute in parallel. Call 1 can also run in parallel since its result is only needed for on-chain fallback.

Total: 4 REST calls, 0 on-chain calls (unless REST fails).
