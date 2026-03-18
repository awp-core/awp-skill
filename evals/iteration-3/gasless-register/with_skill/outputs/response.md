**Welcome to AWP RootNet!**

AWP RootNet is a decentralized Agent Working protocol on BSC. Agents register on subnets, execute tasks, and earn AWP emissions. Each subnet auto-deploys a SubnetManager with Merkle distribution and AWP strategies.

I can help you: **query** protocol state, **mine** (register + stake + work), **manage** subnets, **govern** via proposals, and **monitor** real-time events via WebSocket.

Say "start mining", "check my balance", "list subnets", "watch staking events", or "what can I do?"

---

## Gasless Registration Flow

Since you have no BNB for gas, we'll use the **gasless relay** to register you on AWP RootNet. The relay covers the gas cost and submits the transaction on your behalf. Here's the complete flow:

### Step 1 — Set up your wallet

```bash
# Install the AWP Wallet skill if not already installed
openclaw skill install https://github.com/awp-core/awp-wallet

# Initialize wallet (auto-generates password)
awp-wallet init

# Unlock wallet for this session
awp-wallet unlock --scope full --duration 3600
```

Save the session token `{T}` returned by `unlock` — you'll need it for all subsequent commands.

### Step 2 — Check current registration status

```bash
WALLET_ADDR=$(awp-wallet status --token {T} | jq -r '.address')
curl -s https://tapi.awp.sh/api/address/$WALLET_ADDR/check
```

Expected response for a new user:
```json
{
  "isRegisteredUser": false,
  "isRegisteredAgent": false,
  "ownerAddress": "",
  "isManager": false
}
```

### Step 3 — Confirm no BNB (gas routing check)

```bash
awp-wallet balance --token {T} --chain bsc
```

Since the balance is 0 BNB, we proceed with the gasless relay path.

### Step 4 — Register via gasless relay script

The relay script handles all the EIP-712 signing and relay submission automatically — no need to manually construct the typed data JSON:

```bash
bash scripts/relay-register.sh --token {T}
```

This script internally performs the following (you don't need to do any of this manually):

1. **Fetches `/registry` fresh** (never cached — addresses may change due to upgrades):
   ```
   ROOT_NET=$(curl -s https://tapi.awp.sh/api/registry | jq -r '.rootNet')
   ```

2. **Gets the on-chain nonce** for EIP-712 replay protection:
   ```
   NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
   ```

3. **Sets deadline** to 1 hour from now.

4. **Signs EIP-712 typed data** with the following structure:
   - **Domain name**: `AWPRootNet` (version `"1"`, chainId `56`, verifyingContract = RootNet address)
   - **Primary type**: `Register`
   - **Field order**: `user` (address), `nonce` (uint256), `deadline` (uint256)

5. **Submits to the relay endpoint**:
   ```
   POST https://tapi.awp.sh/api/relay/register
   {"user": "0xYourAddr...", "deadline": 1742400000, "signature": "0x...130 hex chars"}
   ```

6. **Returns the transaction hash** on success:
   ```json
   {"txHash": "0xabc123..."}
   ```

### Step 5 — Verify registration

```bash
# Check tx on BSCScan
echo "https://bscscan.com/tx/{txHash}"

# Confirm registration status
curl -s https://tapi.awp.sh/api/address/$WALLET_ADDR/check
```

Expected response after successful registration:
```json
{
  "isRegisteredUser": true,
  "isRegisteredAgent": false,
  "ownerAddress": "",
  "isManager": false
}
```

---

## Important Notes

- **Rate limit**: The gasless relay allows **100 requests per IP per hour** (shared across all relay endpoints: register, bind, subnet). If you hit a 429 error, wait 60 seconds and retry.
- **No caching of `/registry`**: The script fetches contract addresses fresh from `GET /registry` before every write action. Never cache these — addresses may change due to contract upgrades.
- **What's next**: You're now registered but not yet staking. To start earning, you'll need BNB for the next steps (deposit and allocate have no gasless option):
  1. **Bind** as a principal: `bash scripts/relay-bind.sh --token {T} --principal $WALLET_ADDR` (also gasless)
  2. **Deposit AWP**: Requires BNB for gas — `S2` deposit flow
  3. **Allocate to an agent/subnet**: Requires BNB for gas — `S3` allocate flow
