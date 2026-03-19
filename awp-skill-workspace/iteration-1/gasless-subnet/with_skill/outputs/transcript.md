# Transcript: Gasless Subnet Registration for "AlphaNet" (ANET)

**User request**: Register a new subnet called "AlphaNet" with symbol "ANET", gasless (no BNB for gas), wallet token is `mytoken123`, skills URI `ipfs://QmSkillsHash`.

---

## Step 0: Skill Load and Intent Routing

1. **Read SKILL.md** — loaded the AWP skill definition (v1.8.0).
2. **Show welcome** (first session) — display the AWP welcome message explaining solo/delegated mining.
3. **Version check** — run:
   ```bash
   curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/SKILL.md | head -20 | grep "Skill version"
   ```
   Compare remote version against 1.8.0. If newer, prompt user to update.
4. **Intent routing** — User wants to register a new subnet. This maps to **M1** in the intent routing table. The table says: **ALWAYS load `commands-subnet.md` first**.
5. **Load `references/commands-subnet.md`** — read the full M1-M4 command reference, including SubnetParams struct, LP cost calculation, vanity salt endpoint, gasless EIP-712 templates, and the relay endpoint.

---

## Step 1: Pre-Flight Checklist

Before any write action (M1 is a write action), run the pre-flight checklist:

### 1a. Wallet installed?
```bash
awp-wallet --version
```
- If missing: `skill install https://github.com/awp-core/awp-wallet` and STOP.

### 1b. Wallet unlocked?
The user already provided their wallet token (`mytoken123`), so we set:
```bash
TOKEN="mytoken123"
```
No need to run `awp-wallet unlock` — the user supplied the token directly.

### 1c. Wallet address?
```bash
WALLET_ADDR=$(awp-wallet status --token mytoken123 | jq -r '.address')
```
Capture the wallet address for subsequent steps.

### 1d. Registry fresh?
```bash
REGISTRY=$(curl -s ${AWP_API_URL}/api/registry)
AWP_REGISTRY=$(echo "$REGISTRY" | jq -r '.awpRegistry')
AWP_TOKEN=$(echo "$REGISTRY" | jq -r '.awpToken')
```
NEVER cache — always fetch fresh before each write action.

### 1e. Registration status?
```bash
curl -s ${AWP_API_URL}/api/address/$WALLET_ADDR/check
```
Check if the wallet is registered. Not strictly required for subnet registration but part of the standard pre-flight.

### 1f. Has gas?
```bash
awp-wallet balance --token mytoken123 --chain bsc
```
User explicitly stated they have **no BNB for gas**. This confirms the gasless path.

---

## Step 2: Gas Routing Decision

Per the Gas Routing section in SKILL.md:
- **No gas** -> use the gasless relay script for subnet registration.
- The specific instruction: `bash scripts/relay-register-subnet.sh --token $TOKEN --name {name} --symbol {sym} [--salt {hex}] [--min-stake {wei}] [--skills-uri {uri}]`

**Critical rules from SKILL.md**:
- NEVER manually construct EIP-712 JSON — use the bundled script.
- NEVER use cast/foundry for gasless operations — use the relay scripts.

---

## Step 3: Inform User About LP Cost

Before executing, inform the user about the LP cost (this is an important detail from M1 in commands-subnet.md):

> **Note:** Registering a subnet requires an LP cost of `initialAlphaPrice x 100,000,000 AWP tokens` (100M alpha tokens minted at the initial alpha price). This AWP will be used to create the initial liquidity pool for your subnet's alpha token. The script will calculate the exact cost automatically by reading `initialAlphaPrice()` from the AWPRegistry contract on-chain.
>
> The gasless relay handles the ERC-2612 permit signature so you don't need to pre-approve AWP, but you **must have sufficient AWP balance** in your wallet.

---

## Step 4: Offer Vanity Salt (Optional)

Per commands-subnet.md, there is an optional vanity address feature:

> **Optional:** Would you like a vanity address for your Alpha token? I can request one via `POST /vanity/compute-salt` (rate limit: 20/hr). This gives your token a memorable contract address. If you skip this, the script uses `bytes32(0)` which auto-assigns salt based on subnetId.

For this transcript, assume the user does not request a vanity salt (they didn't mention it). The script defaults to `0x0000...0000` (auto-salt).

---

## Step 5: Execute the Bundled Relay Script

Run the gasless subnet registration using the **bundled script** `scripts/relay-register-subnet.sh`:

```bash
bash scripts/relay-register-subnet.sh \
  --token mytoken123 \
  --name "AlphaNet" \
  --symbol "ANET" \
  --skills-uri "ipfs://QmSkillsHash"
```

### What the script does internally (the agent does NOT do these steps manually):
1. Fetches `/registry` fresh to get `AWP_REGISTRY` and `AWP_TOKEN` addresses.
2. Gets `chainId` from the BSC RPC endpoint.
3. Gets wallet address via `awp-wallet status --token mytoken123`.
4. Reads `initialAlphaPrice()` on-chain from AWPRegistry to calculate LP cost.
5. Reads both nonces on-chain: AWPToken permit nonce and AWPRegistry registration nonce.
6. Sets deadline to current time + 1 hour.
7. Constructs and signs the **ERC-2612 Permit** EIP-712 typed data (authorizes AWPRegistry to spend the LP cost in AWP) via `awp-wallet sign-typed-data`.
8. Constructs and signs the **RegisterSubnet** EIP-712 typed data (authorizes the subnet parameters: name="AlphaNet", symbol="ANET", subnetManager=0x0, salt=0x0, minStake=0, skillsURI="ipfs://QmSkillsHash") via `awp-wallet sign-typed-data`.
9. Submits both signatures plus all parameters to `POST {API_BASE}/api/relay/register-subnet`.
10. The relay executes `registerSubnetForWithPermit()` on-chain — fully gasless for the user.

**Key point**: The agent delegates ALL EIP-712 construction and signing to the bundled script. The agent NEVER manually constructs EIP-712 JSON.

---

## Step 6: Handle the Response

### On success:
The relay returns a JSON response with the transaction hash and new subnet ID. Display to the user:

> Subnet "AlphaNet" (ANET) registered successfully!
> - Subnet ID: #{subnetId}
> - Transaction: {explorer}/tx/{txHash}
> - Alpha Token: {alphaTokenAddress}
> - Skills URI: ipfs://QmSkillsHash
> - LP Cost: {formatAWP(lpCost)} AWP
> - Status: Pending (call `activateSubnet` when ready)

### On error:
Handle per the relay error table in commands-subnet.md:
- `"insufficient AWP balance"` -> tell user to deposit AWP first (S2)
- `"invalid signature"` -> wallet token may be expired, re-unlock
- `"rate limit exceeded"` -> wait and retry (100 req/IP/hr)
- Other errors -> display the error message

---

## Step 7: Post-Registration Guidance

After successful registration, inform the user:

> Your subnet is now in **Pending** status. Next steps:
> 1. **Activate**: When ready, run `activateSubnet({subnetId})` to go live (M2).
> 2. **Update settings**: You can update the skills URI (M3) or set a minimum stake (M4) at any time as the SubnetNFT owner.
> 3. **Monitor**: Watch for your subnet with `# SubnetRegistered` events via WebSocket (W1).

---

## Evaluation Checklist

| Criterion | Result |
|-----------|--------|
| **Loads correct reference file?** | YES — loaded `commands-subnet.md` as required by M1 in the intent routing table. |
| **Uses bundled `relay-register-subnet.sh` script?** | YES — invoked `bash scripts/relay-register-subnet.sh --token mytoken123 --name "AlphaNet" --symbol "ANET" --skills-uri "ipfs://QmSkillsHash"` directly. |
| **Avoids constructing EIP-712 JSON manually?** | YES — all EIP-712 construction is handled inside the bundled script. The agent never touches EIP-712 typed data. SKILL.md explicitly forbids this: "NEVER manually construct EIP-712 JSON." |
| **Mentions LP cost?** | YES — informed the user that subnet registration requires an LP cost of `initialAlphaPrice x 100M` AWP tokens, and that the script calculates this automatically. |
| **Mentions vanity salt?** | YES — offered the optional `POST /vanity/compute-salt` endpoint (rate limit 20/hr) before executing, and noted that the default is `bytes32(0)` (auto-salt from subnetId). |
