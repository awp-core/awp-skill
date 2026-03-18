# AWP Skill — API Reference (Index)

Quick index of read-only REST endpoints. For write operations, see the dedicated command files:
- **commands-staking.md** — S1 Register/Bind, S2 Deposit, S3 Allocate
- **commands-subnet.md** — M1 Register Subnet, M2 Lifecycle, M3-M5 Settings
- **commands-governance.md** — G1 Proposals, G2 Voting, G3/G4 Queries, Supplementary

**API Base URL**: `https://tapi.awp.sh/api` (or `AWP_API_URL` env var)

---

## Read-Only Endpoints

| Action | Endpoint | Notes |
|--------|----------|-------|
| Q1 Subnet | `GET /subnets/{subnetId}` | Full subnet object; fallback: `getSubnetFull(id)` |
| Q2 Balance | `GET /staking/user/{addr}/balance` | Also: `/positions`, `/allocations` |
| Q3 Emission | `GET /emission/current` | Also: `/schedule`, `/epochs` |
| Q4 Agent | `GET /subnets/{subnetId}/agents/{agent}` | Batch: `POST /agents/batch-info`; By owner: `/agents/by-owner/{owner}` |
| Q5 List | `GET /subnets?status={s}&page={p}&limit={n}` | Status: Pending, Active, Paused, Banned |
| Q6 Skills | `GET /subnets/{subnetId}/skills` | Returns skillsURI |
| Q7 Epochs | `GET /emission/epochs?page={p}&limit={n}` | Epoch history with emissions |

## Shared Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /registry` | All 11 contract addresses — never hardcode |
| `GET /address/{addr}/check` | Registration status check |
| `GET /health` | Service health |

For data structures, events, and constants, see **protocol.md**.
