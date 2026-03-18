# Configuration Reference

## Chain Configuration

| Parameter | Value |
|-----------|-------|
| Network | BSC Mainnet |
| Chain ID | 56 |
| RPC URL | `https://bsc-dataseed.binance.org` |
| Block Time | ~3 seconds |
| Explorer | `https://bscscan.com` |

## Contract Addresses (BSC Mainnet)

| Contract | Address | Description |
|----------|---------|-------------|
| RootNet | `0x190E0E3128764913D54aD570993b21a38D1411F7` | Unified entry point |
| AWPToken | `0x0000969dDC625E1c084ECE9079055Fbc50F400a1` | Main token (ERC20+Votes) |
| AWPEmission (Proxy) | `0xcc4fA866c0c49FE4763977C5302a6052C3f0d742` | Emission engine (UUPS proxy) |
| SubnetNFT | `0xbdfd26f499bd7972242bb765d8C3262d6d89fE63` | Subnet NFT (ERC721) |
| StakingVault | `0xbEe164bdE7F690E7bb73a0D84c1a87D1073545eE` | Pure allocation logic |
| StakeNFT | `0x3678463cd5EbA407b20CD1c296B6ECc58491C170` | Position NFT (ERC721, deposit/withdraw AWP) |
| AccessManager | `0xcEa146F15db74f8801Bc8fD152EE0E7e07eDB3fD` | User/Agent registration |
| LPManager | `0x5372b30E2D14599F90Cb623fc673692B48E83404` | PancakeSwap V4 LP |
| Treasury | `0x710975eC607617fB4623Db9b86B5C218a92E7C7d` | Timelock governance |
| AWPDAO | `0xe21097cB128b41611557356de7f55BCd25062579` | Governor |
| AlphaTokenFactory | `0x7E3B68cf196FD8a972115685ea171b763B677499` | Alpha token deployer (CREATE2, vanity address support) |
| SubnetManager (impl) | `0xE5771dC2a5a577CDFa6b939Af4F32Ad13CFc6D92` | Default subnet contract implementation |

## API Configuration

| Parameter | Value |
|-----------|-------|
| REST Base URL | `https://tapi.awp.sh/api` |
| WebSocket URL | `wss://tapi.awp.sh/ws/live` |
| HTTP Port | 8001 |

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
| `RELAY_RATE_LIMIT` | No | Max relay requests per IP per window (default: 100) |
| `RELAY_RATE_WINDOW` | No | Rate limit window in seconds (default: 3600) |
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
| INITIAL_DAILY_EMISSION | 15.8M AWP | **[DRAFT]** | First epoch daily emission |
| EPOCH_DURATION | 1 day (86400s) | **[DRAFT]** | Time between settlements (daily epochs, AWPEmission only) |
| DECAY_FACTOR | 0.996844 per epoch | **[DRAFT]** | ~0.3156% decay each epoch |
| EMISSION_SPLIT | 50/50 | **[DRAFT]** | Recipients vs DAO |
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
| `relay_ratelimit:{ip}` | 1h | Relay handler (Lua INCR+EXPIRE) | IP request counter |
| `chain_events` (Pub/Sub) | — | Indexer | Real-time event stream |
