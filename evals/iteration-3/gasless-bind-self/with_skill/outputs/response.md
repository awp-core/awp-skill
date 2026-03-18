# Gasless Agent Bind to Principal 0xABCD1234567890ABCD1234567890ABCD12345678

Since you're already registered and need to bind without BNB for gas, we'll use the **gasless relay** path. This submits an EIP-712 signed message to the relay server, which executes the `bindFor()` transaction on your behalf.

## Complete Flow

### Step 1 — Ensure wallet is unlocked

```bash
awp-wallet unlock --scope full --duration 3600
```

### Step 2 — Run the gasless bind script

```bash
bash scripts/relay-bind.sh --principal 0xABCD1234567890ABCD1234567890ABCD12345678
```

This single command handles the entire flow:

1. **Fetches RootNet address** from `GET /registry` (never hardcoded)
2. **Gets your wallet address** (the agent) via `awp-wallet status`
3. **Reads the agent's nonce** from the RootNet contract — `nonces(address)` called with **your (agent) address**, not the principal's
4. **Sets deadline** to 1 hour from now
5. **Constructs and signs EIP-712 typed data** with the following structure:
   - **Domain**: `name: "AWPRootNet"`, `version: "1"`, `chainId: 56`, `verifyingContract: <RootNet address>`
   - **Primary type**: `Bind`
   - **Field order**: `agent`, `principal`, `nonce`, `deadline`
   - The `agent` field is your wallet address; `principal` is `0xABCD1234567890ABCD1234567890ABCD12345678`
6. **Submits to relay**: `POST /relay/bind` with `{agent, principal, deadline, signature}`

### Step 3 — Verify the binding

On success the script outputs `{"txHash": "0x..."}`. Confirm it:

```bash
curl -s https://tapi.awp.sh/api/address/{your_wallet_address}/check
```

Expected response:

```json
{
  "isRegisteredUser": true,
  "isRegisteredAgent": true,
  "ownerAddress": "0xABCD1234567890ABCD1234567890ABCD12345678",
  "isManager": false
}
```

You can also view the transaction on BscScan: `https://bscscan.com/tx/{txHash}`

## What Happens Under the Hood

The relay server calls `RootNet.bindFor(agent, principal, deadline, v, r, s)` using its own gas. The EIP-712 signature proves you (the agent) authorized this binding. Key details:

- **Nonce source**: The contract uses the **agent's** nonce (your nonce), not the principal's. This prevents replay attacks.
- **EIP-712 Bind field order**: `agent -> principal -> nonce -> deadline` (must be exact for signature verification)
- **Domain name**: `AWPRootNet` (not "RootNet" or "AWP")
- **Auto-registers principal**: If `0xABCD...5678` is not yet registered, `bindFor` automatically registers them too
- **Rate limit**: 100 relay requests per IP per hour (shared across all relay endpoints)

## After Binding

You are now bound as an agent to principal `0xABCD...5678`. Next steps:

- **Principal** deposits AWP (S2) and allocates stake to you on a subnet (S3)
- **You** install the subnet's skill (`GET /subnets/{id}/skills`) and start working
- **Unbind** anytime with: `awp-wallet send --token {T} --to $ROOT_NET --data $(cast calldata "unbind()") --chain bsc` (requires BNB)
- **Rebind** to a different principal by calling `bind(newPrincipal)` directly — no need to unbind first
