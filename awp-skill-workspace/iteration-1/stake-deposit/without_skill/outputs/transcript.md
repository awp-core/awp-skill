# Transcript: Agent Without AWP Skill — Stake 5000 AWP for 90 Days

## User Request
> "I want to stake 5000 AWP for 90 days. My wallet is already unlocked with token abc123. Go ahead and do it."

---

## Agent Response (Turn 1)

I'd like to help you stake 5000 AWP for 90 days, but I need to be upfront: I don't have specific knowledge of the AWP protocol, its smart contracts, staking interface, or required transaction parameters. To proceed safely, I need several pieces of information that I currently lack:

1. **What is the AWP token?** I'm not familiar with a token called "AWP." Could you provide:
   - The chain it operates on (Ethereum, BSC, Polygon, Arbitrum, etc.)?
   - The token contract address?
   - A link to the project's official documentation or website?

2. **Staking contract details.** To submit a staking transaction, I would need:
   - The staking contract address.
   - The ABI or at least the function signature for the staking call (e.g., `stake(uint256 amount, uint256 duration)` or similar).
   - Whether an ERC-20 `approve()` call is required before staking (almost certainly yes, but I need the exact spender address).

3. **RPC endpoint.** Which RPC URL should I use to broadcast the transaction?

4. **Wallet context.** You mentioned your wallet is unlocked with token `abc123`. I don't know what wallet system or API this token corresponds to. Is this:
   - A local keystore with an HTTP API?
   - A custom wallet service with a REST interface?
   - A hardware wallet proxy?
   - Something else?

5. **Lock period encoding.** You said 90 days, but staking contracts encode durations in different ways — some use seconds (90 * 86400 = 7,776,000), some use a tier/index (e.g., tier 2 = 90 days), and some use block numbers. I need to know which format the AWP staking contract expects.

6. **Amount encoding.** I need to know the token's decimal precision (commonly 18 decimals, but not always) to encode 5000 AWP correctly (e.g., `5000 * 10^18`).

---

## What I Could Attempt (General Approach)

If I were to guess at a generic ERC-20 staking flow, the steps would be roughly:

### Step 1 — Look up token and staking contract addresses
```
# I would search for AWP token on block explorers or CoinGecko/CoinMarketCap
# PROBLEM: I cannot find verified AWP contract addresses without documentation
```

### Step 2 — Approve the staking contract to spend AWP tokens
```
# Generic ERC-20 approve call
data = encode_function("approve(address,uint256)", [STAKING_CONTRACT, 5000 * 10**DECIMALS])
tx = {
    "to": AWP_TOKEN_ADDRESS,   # UNKNOWN
    "data": data,
    "from": WALLET_ADDRESS,    # UNKNOWN
    "chainId": CHAIN_ID        # UNKNOWN
}
```

### Step 3 — Call the stake function
```
data = encode_function("stake(uint256,uint256)", [5000 * 10**DECIMALS, 90_DAYS_ENCODED])
tx = {
    "to": STAKING_CONTRACT,    # UNKNOWN
    "data": data,
    "from": WALLET_ADDRESS,    # UNKNOWN
    "chainId": CHAIN_ID        # UNKNOWN
}
```

### Step 4 — Sign and broadcast using the wallet token
```
# Use token abc123 to authenticate to wallet API
# PROBLEM: I don't know the wallet API endpoint or signing method
```

**Every step above contains critical unknowns that I cannot safely guess.**

---

## Why I Cannot Proceed

Executing a blockchain transaction with guessed or incorrect parameters carries serious risks:

- **Wrong contract address** — Funds could be sent to an unrelated or malicious contract and be permanently lost.
- **Wrong function selector or encoding** — The transaction would revert, wasting gas, or worse, trigger an unintended function.
- **Wrong chain** — Tokens could be sent on the wrong network.
- **Wrong decimal encoding** — Staking 5000 * 10^18 when the token uses 8 decimals would attempt to stake an astronomically larger amount (or fail).

I am not willing to fabricate contract addresses or function signatures for a protocol I don't have verified information about. Doing so would put your funds at risk.

---

## What I Need From You

Please provide any of the following so I can help:

1. The AWP project's official documentation URL or GitHub repository.
2. The blockchain network and token contract address.
3. The staking contract address and its ABI (or a link to it on a block explorer).
4. Details about the wallet API that the unlock token `abc123` corresponds to.

With that information, I can construct, sign, and broadcast the staking transaction for you.

---

## Outcome

**FAILED — Unable to execute.** The agent lacked all protocol-specific knowledge required to construct a valid staking transaction. No transaction was submitted. No funds were moved. The user's wallet token `abc123` was not used.
