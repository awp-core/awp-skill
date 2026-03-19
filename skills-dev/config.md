# Configuration Reference

## Chain Configuration

| Parameter | Value |
|-----------|-------|
| Network | Configured at deployment |
| Chain ID | From `CHAIN_ID` env var |
| RPC URL | From `RPC_URL` env var |
| Block Time | Chain-dependent |
| Explorer | Chain-dependent |

## Contract Addresses

> Contract addresses are deployment-specific. Retrieve them from the API:
> `GET /api/registry` returns all protocol contract addresses + chainId.

## API Configuration

| Parameter | Value |
|-----------|-------|
| REST Base URL | Deployment-specific (e.g. `https://<api-host>/api`) |
| WebSocket URL | Deployment-specific (e.g. `wss://<api-host>/ws/live`) |
| HTTP Port | 8001 |

## Environment Variables (API Server)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `RPC_URL` | Yes | Chain RPC endpoint |
| `AWP_REGISTRY_ADDRESS` | Yes | AWPRegistry contract address |
| `AWP_TOKEN_ADDRESS` | Yes | AWPToken contract address |
| `AWP_EMISSION_ADDRESS` | Yes | AWPEmission proxy address |
| `STAKING_VAULT_ADDRESS` | Yes | StakingVault contract address |
| `STAKE_NFT_ADDRESS` | Yes | StakeNFT contract address |
| `SUBNETNFT_ADDRESS` | Yes | SubnetNFT contract address |
| `LP_MANAGER_ADDRESS` | Yes | LPManager contract address |
| `ALPHA_FACTORY_ADDRESS` | Yes | AlphaTokenFactory address (also enables `/api/vanity/*`) |
| `DAO_ADDRESS` | Yes | AWPDAO contract address |
| `TREASURY_ADDRESS` | Yes | Treasury (TimelockController) address |
| `DEPLOY_BLOCK` | Yes | Block number at which contracts were deployed (indexer start) |
| `KEEPER_PRIVATE_KEY` | No | Private key for keeper service (epoch settlement) |
| `RELAYER_PRIVATE_KEY` | No | Private key for gasless relay (enables `/api/relay/*`) |
| `ALPHA_INITCODE_HASH` | No | `keccak256(AlphaToken.creationCode)` hex (enables vanity mining) |
| `VANITY_RULE` | No | `AlphaTokenFactory.vanityRule()` uint64 hex (e.g. `0x1001FFFF0C0A0F0E`) |

## DEX Integration

> DEX addresses (CLPoolManager, CLPositionManager, Permit2, CLSwapRouter) are chain-specific
> and configured via environment variables at deployment. See `contracts/.env.example`.

## Protocol Constants

| Constant | Value | Description |
|----------|-------|-------------|
| AWP MAX_SUPPLY | 10B (10^28 wei) | Total AWP supply cap |
| Alpha MAX_SUPPLY | 10B per subnet | Independent per-subnet cap |
| INITIAL_DAILY_EMISSION | 15.8M AWP | **[DRAFT]** | First epoch daily emission |
| EPOCH_DURATION | 1 day (86400s) | **[DRAFT]** | Time between settlements (daily epochs, AWPEmission only) |
| DECAY_FACTOR | 0.996844 per epoch | **[DRAFT]** | ~0.3156% decay each epoch |
| EMISSION_SPLIT | 50/50 | **[DRAFT]** | Recipients vs DAO |
| MAX_ACTIVE_SUBNETS | 10,000 | AWPRegistry active subnet limit |
| maxRecipients | 10,000 | AWPEmission recipient limit |
| MAX_WEIGHT_SECONDS | 54 weeks (32,659,200s) | Max time for voting power sqrt |
| Immunity Period | 30 days | Deregister protection |
| Timelock Delay | 2 days | Governance execution delay |
| Pool Fee | 1% | PancakeSwap V4 CL fee |
| Oracle Threshold | DAO-configured | Initially 3/5 recommended |
| AlphaTokenFactory.vanityRule | uint64, immutable | 0 = no validation; non-zero = 8-position EIP-55 pattern |

## Token Decimals

All tokens use **18 decimals**. Amounts in the API and contracts are in **wei** (smallest unit).

```
1 AWP = 1,000,000,000,000,000,000 wei = 10^18 wei
1 Alpha = 10^18 wei
```

## Redis Keys (internal)

| Key | TTL | Updated By | Content |
|-----|-----|------------|---------|
| `emission_current` | 30s | Keeper (25s interval) | `{epoch, dailyEmission, totalWeight}` |
| `awp_info` | 1m | Keeper (25s interval) | `{totalSupply, maxSupply}` |
| `alpha_price:{subnetId}` | 10m | External | `{priceInAWP, reserve0, reserve1, updatedAt}` |
| `ratelimit:config` | — | admin.sh / Redis CLI | Rate limit configs (hash: name → "limit:window_seconds") |
| `rl:relay:{ip}` | 1h | Relay handler | Relay IP request counter |
| `rl:upload_salts:{ip}` | 1h | Salt handler | Upload salts IP counter |
| `rl:compute_salt:{ip}` | 1h | Vanity handler | Compute salt IP counter |
| `chain_events` (Pub/Sub) | — | Indexer | Real-time event stream |

> Rate limits are configured via Redis hash `ratelimit:config` (hot-updatable, no restart). Defaults compiled into the ratelimit package. Use `scripts/admin.sh` to manage.
