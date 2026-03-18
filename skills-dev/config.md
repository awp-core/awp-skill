# Configuration Reference

## Chain Configuration

| Parameter | Value |
|-----------|-------|
| Network | BSC Mainnet |
| Chain ID | 56 |
| RPC URL | `https://bsc-dataseed.binance.org` |
| Block Time | ~3 seconds |
| Explorer | `https://bscscan.com` |

## Contract Addresses (fill after deployment)

| Contract | Address | Description |
|----------|---------|-------------|
| RootNet | `TBD` | Unified entry point |
| AWPToken | `TBD` | Main token (ERC20+Votes) |
| AWPEmission (Proxy) | `TBD` | Emission engine (UUPS proxy) |
| SubnetNFT | `TBD` | Subnet NFT (ERC721) |
| StakingVault | `TBD` | Pure allocation logic |
| StakeNFT | `TBD` | Position NFT (ERC721, deposit/withdraw AWP) |
| AccessManager | `TBD` | User/Agent registration |
| LPManager | `TBD` | PancakeSwap V4 LP |
| Treasury | `TBD` | Timelock governance |
| AWPDAO | `TBD` | Governor |
| AlphaTokenFactory | `TBD` | Alpha token deployer (CREATE2, vanity address support) |

## API Configuration

| Parameter | Value |
|-----------|-------|
| REST Base URL | `https://api.awp.network/api` |
| WebSocket URL | `wss://api.awp.network/ws/live` |
| HTTP Port | 8080 |

## Environment Variables (API Server)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `RPC_URL` | Yes | BSC RPC endpoint |
| `ROOTNET_ADDRESS` | Yes | RootNet contract address |
| `AWP_TOKEN_ADDRESS` | Yes | AWPToken contract address |
| `AWP_EMISSION_ADDRESS` | Yes | AWPEmission proxy address |
| `STAKING_VAULT_ADDRESS` | Yes | StakingVault contract address |
| `STAKE_NFT_ADDRESS` | Yes | StakeNFT contract address |
| `SUBNETNFT_ADDRESS` | Yes | SubnetNFT contract address |
| `ACCESS_MANAGER_ADDRESS` | Yes | AccessManager contract address |
| `LP_MANAGER_ADDRESS` | Yes | LPManager contract address |
| `ALPHA_FACTORY_ADDRESS` | Yes | AlphaTokenFactory address (also enables `/api/vanity/*`) |
| `DAO_ADDRESS` | Yes | AWPDAO contract address |
| `TREASURY_ADDRESS` | Yes | Treasury (TimelockController) address |
| `DEPLOY_BLOCK` | Yes | Block number at which contracts were deployed (indexer start) |
| `KEEPER_PRIVATE_KEY` | No | Private key for keeper service (epoch settlement) |
| `RELAYER_PRIVATE_KEY` | No | Private key for gasless relay (enables `/api/relay/*`) |
| `ALPHA_INITCODE_HASH` | No | `keccak256(AlphaToken.creationCode)` hex (enables vanity mining) |
| `VANITY_RULE` | No | `AlphaTokenFactory.vanityRule()` uint64 hex (e.g. `0x1001FFFF0C0A0F0E`) |

## PancakeSwap V4 (BSC Mainnet)

| Contract | Address |
|----------|---------|
| CLPoolManager | `0xa0FfB9c1CE1Fe56963B0321B32E7A0302114058b` |
| CLPositionManager | `0x55f4c8abA71A1e923edC303eb4fEfF14608cC226` |
| Permit2 | `0x31c2F6fcFf4F8759b3Bd5Bf0e1084A055615c768` |

## Protocol Constants

| Constant | Value | Description |
|----------|-------|-------------|
| AWP MAX_SUPPLY | 10B (10^28 wei) | Total AWP supply cap |
| Alpha MAX_SUPPLY | 10B per subnet | Independent per-subnet cap |
| INITIAL_DAILY_EMISSION | 15.8M AWP | First epoch daily emission |
| EPOCH_DURATION | 1 day (86400s) | Time between settlements (daily epochs, AWPEmission only) |
| DECAY_FACTOR | 0.996844 per epoch | ~0.3156% decay each epoch |
| EMISSION_SPLIT | 50/50 | Recipients vs DAO |
| MAX_ACTIVE_SUBNETS | 10,000 | RootNet active subnet limit |
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
| `chain_events` (Pub/Sub) | — | Indexer | Real-time event stream |
