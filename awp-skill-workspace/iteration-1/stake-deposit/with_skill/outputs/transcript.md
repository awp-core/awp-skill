# Transcript: Stake 5000 AWP for 90 Days (Agent WITH Skill)

## User Request

> "I want to stake 5000 AWP for 90 days. my wallet is already unlocked with token abc123. go ahead and do it"

---

## Step 0: Skill Load & Intent Routing

The agent recognizes "stake AWP" and loads the AWP skill (SKILL.md). Per the intent routing table, "Deposit / stake AWP" maps to **S2**. The skill says:

> S1-S3 -- ALWAYS load commands-staking.md first.

So the agent loads `references/commands-staking.md` before proceeding.

The skill also identifies the bundled script for S2:

> Use the script: `bash scripts/onchain-deposit.sh --token $TOKEN --amount {AWP} --lock-days {days}`

---

## Step 1: Pre-Flight Checklist

Per SKILL.md "Pre-Flight Checklist (run before ANY write action)", the agent runs all 6 checks. The user said wallet is already unlocked with token `abc123`, so the agent skips step 2 (unlock) but still verifies.

### 1a. Wallet installed?

```bash
awp-wallet --version
```
> Expected output: version string confirming awp-wallet is installed.

### 1b. Wallet unlocked? (user says yes, token = abc123)

The user provided the token `abc123` directly, so we use it. No need to run unlock again.

```
TOKEN=abc123
```

### 1c. Get wallet address

```bash
WALLET_ADDR=$(awp-wallet status --token abc123 | jq -r '.address')
```
> Expected output: e.g. `0x7A3b...9f2E` (the user's wallet address)

### 1d. Fetch fresh registry (NEVER cache)

```bash
REGISTRY=$(curl -s ${AWP_API_URL}/api/registry)
AWP_TOKEN=$(echo "$REGISTRY" | jq -r '.awpToken')
STAKE_NFT=$(echo "$REGISTRY" | jq -r '.stakeNFT')
```
> Expected output: contract addresses for AWP token and StakeNFT.

### 1e. Check registration status

```bash
curl -s ${AWP_API_URL}/api/address/$WALLET_ADDR/check
```
> Expected output: `{"isRegistered": true/false, "boundTo": "0x...", "recipient": "0x..."}`
>
> Note: Registration is not strictly required for depositing (S2). Deposit only requires gas and AWP tokens. But the skill says to run this check before ANY write action.

### 1f. Check gas (BNB balance)

```bash
awp-wallet balance --token abc123 --chain bsc
```
> Expected output: native BNB balance. Deposit ALWAYS requires gas (no gasless option), so the user must have BNB. If zero, STOP and tell user they need BNB for gas.

---

## Step 2: Check AWP Token Balance

Before depositing, verify the user actually has 5000 AWP available:

```bash
awp-wallet balance --token abc123 --chain bsc --asset $AWP_TOKEN
```
> Expected output: AWP token balance. Must be >= 5000. If not, STOP and inform user of insufficient AWP balance.

---

## Step 3: Execute Deposit Using the Bundled Script

The skill explicitly provides a bundled script for S2 deposits:

> Use the script: `bash scripts/onchain-deposit.sh --token $TOKEN --amount {AWP} --lock-days {days}`

The agent runs the bundled script (does NOT manually construct calldata):

```bash
bash scripts/onchain-deposit.sh --token abc123 --amount 5000 --lock-days 90
```

### What the script does internally (for reference):

1. **Validates inputs** -- confirms amount and lock-days are valid numbers
2. **Fetches wallet address** via `awp-wallet status --token abc123`
3. **Fetches fresh registry** via `curl -s ${AWP_API_URL}/api/registry`
4. **Computes wei amount**: `5000 * 10^18 = 5000000000000000000000`
5. **Computes lock seconds**: `90 * 86400 = 7776000`
6. **Step 1 - Approve**: `awp-wallet approve --token abc123 --asset $AWP_TOKEN --spender $STAKE_NFT --amount 5000 --chain bsc`
7. **Step 2 - Deposit**: Encodes `deposit(uint256,uint64)` with selector `0x7d552ea6` + ABI-encoded amount and lock duration, then sends via `awp-wallet send`

> Expected output from script:
> - Step "approve": `{"txHash": "0x...", "status": "confirmed"}`
> - Step "deposit": `{"txHash": "0x...", "status": "confirmed", "tokenId": ...}`

---

## Step 4: Confirm to User

After the script completes successfully, the agent would tell the user:

> **Deposit complete!**
>
> - **Amount**: 5,000.0000 AWP
> - **Lock duration**: 90 days
> - **Lock ends**: approximately 2026-06-17
> - **Position NFT**: #{tokenId} (from Deposited event)
> - **Tx hash**: 0x... (explorer link)
>
> Your AWP is now staked. You can allocate it to an agent + subnet to start earning emissions, or leave it unallocated. Say "allocate" when you're ready.

---

## Analysis Summary

| Criteria | Result |
|----------|--------|
| **Used bundled script?** | YES -- `bash scripts/onchain-deposit.sh --token abc123 --amount 5000 --lock-days 90` |
| **Ran pre-flight checks?** | YES -- all 6 checks from the Pre-Flight Checklist (wallet version, token, address, registry, registration status, gas balance) |
| **Loaded commands-staking.md?** | YES -- per skill instructions "S1-S3 -- ALWAYS load commands-staking.md first" |
| **Constructed calldata manually?** | NO -- the script handles approve + calldata encoding + deposit internally |
| **Fetched registry fresh?** | YES -- both the agent's pre-flight and the script itself fetch `/api/registry` (no caching) |
| **Checked gas?** | YES -- deposit always requires gas, verified BNB balance before proceeding |
| **Handled approve step?** | YES -- the script handles approve + deposit in sequence automatically |
| **Used correct parameters?** | YES -- `--amount 5000 --lock-days 90` maps to 5000 AWP for 90 days |
