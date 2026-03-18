# AWP RootNet — Skills Development Context

You are developing **OpenClaw skills** for interacting with the AWP RootNet protocol. Skills should enable users to query protocol state, manage subnets, stake tokens, and monitor emissions — all via natural language.

## Protocol Overview

AWP RootNet is an **Agent Working protocol on BSC** (13 Solidity contracts) with these core components:

- **RootNet** — Unified entry: subnet management + staking allocation + gasless relay (registerFor, bindFor, registerSubnetFor). No deposit/withdraw (handled by StakeNFT).
- **StakeNFT** — ERC721 position NFT. Deposit AWP with lock period (timestamp-based, seconds). addToPosition blocked on expired locks (PositionExpired).
- **AWPEmission** — **[DRAFT]** UUPS proxy emission engine. settleEpoch(limit) uses mintAndCall to auto-trigger SubnetManager strategies.
- **StakingVault** — Pure allocation logic. Auto-enumerates agent subnets. allocate/reallocate reject subnetId=0.
- **LPManager** — PancakeSwap V4 CL pool (permanently locked LP).
- **AWPToken** — ERC20+ERC1363+Votes, 10B max. mintAndCall(to, amount, data) triggers ERC1363 callback.
- **AlphaToken** — Per-subnet ERC20 via CREATE2 (standalone). Factory replaceable via setAlphaTokenFactory (Timelock).
- **SubnetNFT** — ERC721 with on-chain identity (name, subnetManager, alphaToken) + owner-updatable (skillsURI via setSkillsURI, minStake via setMinStake). Status/lifecycle in RootNet.
- **SubnetManager** — Default subnet contract (auto-deployed via ERC1967Proxy). AccessControl + Merkle distribution + AWP strategies (Reserve/AddLiquidity/BuybackBurn) + IERC1363Receiver (auto-executes on mintAndCall).
- **AWPDAO** — NFT-based voting. createdAt >= propCreatedAt blocks same-block voting. totalVotingPower > 0 required. Two proposal types: proposeWithTokens + signalPropose.
- **Treasury** — TimelockController governance.

## Key Files in This Directory

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — context and instructions |
| `contract-api.md` | All smart contract function signatures, parameters, access control |
| `rest-api.md` | All HTTP endpoints with request/response examples |
| `abi/` | Contract ABI JSON files for ethers.js/viem integration |
| `examples.md` | Code examples for common operations (read + write) |
| `config.md` | Chain config, contract addresses, constants |
| `agent-skill-guide.md` | How agents discover subnets, fetch SKILL.md, and install skills via OpenClaw |

## Skills to Build

### Read-Only Skills (query state, no wallet needed)
1. **query-subnet** — Get subnet info by ID (status, owner, alpha token, LP pool, skills URI)
2. **query-balance** — Get user staking balance (totalStaked from positions, allocated, unallocated)
3. **query-emission** — Get current epoch, daily emission, total weight, decay projections
4. **query-agent** — Get agent info (owner, stake on subnet, reward recipient)
5. **list-subnets** — List active/all subnets with pagination
6. **query-skills** — Get subnet skills URI by ID
7. **query-epoch-history** — Get epoch settlement history with emission amounts

### Write Skills (require wallet/signer)
8. **register-user** — Register as a user on RootNet
9. **register-subnet** — Register a new subnet (deploy Alpha + LP)
10. **deposit-stake** — Deposit AWP via StakeNFT (mint position NFT with lock period)
11. **allocate-stake** — Allocate stake to (agent, subnet)
12. **manage-subnet** — Activate/pause/resume subnet, update skillsURI

### Monitoring Skills
13. **watch-events** — Subscribe to WebSocket events (emission, staking, subnet lifecycle)
14. **emission-alert** — Monitor epoch settlements and notify on distribution

## Implementation Notes

- **Chain**: BSC (Chain ID 56), RPC via QuickNode or public BSC RPC
- **Contract interaction**: Use `viem` or `ethers.js` for on-chain reads/writes
- **REST API**: Base URL `https://tapi.awp.sh/api`
- **WebSocket**: `wss://tapi.awp.sh/ws/live`
- **All token amounts are in wei** (18 decimals). Display as human-readable with proper formatting.
- **Addresses are lowercase** in the API but mixed-case (EIP-55) on-chain.
