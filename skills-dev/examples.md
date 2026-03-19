# Code Examples — AWP Protocol Interaction

## 1. REST API Examples (no wallet needed)

### Query subnet info
```javascript
const res = await fetch(`${API_BASE}/subnets/1`);
const subnet = await res.json();
console.log(subnet.name, subnet.status, subnet.skills_uri);
```

### Query user balance
```javascript
const res = await fetch(`${API_BASE}/staking/user/0x1234.../balance`);
const balance = await res.json();
// balance.totalStaked, balance.totalAllocated, balance.unallocated are in wei (string)
const totalAWP = Number(balance.totalStaked) / 1e18;
```

### Query user positions (StakeNFT)
```javascript
const res = await fetch(`${API_BASE}/staking/user/0x1234.../positions`);
const positions = await res.json();
// positions[0].token_id, positions[0].amount, positions[0].lock_end_time, positions[0].created_at
```

### Get emission info
```javascript
const res = await fetch(`${API_BASE}/emission/current`);
const emission = await res.json();
// emission.epoch, emission.dailyEmission, emission.totalWeight
```

### List active subnets
```javascript
const res = await fetch(`${API_BASE}/subnets?status=Active&page=1&limit=10`);
const subnets = await res.json();
```

### Get subnet skills
```javascript
const res = await fetch(`${API_BASE}/subnets/1/skills`);
const { skillsURI } = await res.json();
// skillsURI = "ipfs://QmSkillsFile..."
```

### Batch agent info (for coordinators)
```javascript
const res = await fetch(`${API_BASE}/agents/batch-info`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ agents: ['0xAgent1', '0xAgent2'], subnetId: 1 })
});
const agents = await res.json();
// agents[0].agent.owner_address, agents[0].stake
```

---

## 2. Contract Read Examples (viem)

### Setup
```javascript
import { createPublicClient, http, parseAbi } from 'viem';
// chain configured at deployment

const client = createPublicClient({
  chain: targetChain, // chain object configured at deployment
  transport: http(RPC_URL), // RPC endpoint from environment
});

const AWP_REGISTRY = '0x...'; // from deployment
const AWP_EMISSION = '0x...';
```

### Read subnet info (full — combines AWPRegistry state + SubnetNFT identity)
```javascript
const subnet = await client.readContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function getSubnetFull(uint256) view returns (address subnetManager, address alphaToken, bytes32 lpPool, uint8 status, uint64 createdAt, uint64 activatedAt, string name, string skillsURI, uint128 minStake, address owner)']),
  functionName: 'getSubnetFull',
  args: [1n],
});
// subnet.subnetManager, subnet.alphaToken, subnet.status (0=Pending, 1=Active, 2=Paused, 3=Banned)
```

### Read agent info
```javascript
const info = await client.readContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function getAgentInfo(address,uint256) view returns (address owner, bool isValid, uint256 stake, address rewardRecipient)']),
  functionName: 'getAgentInfo',
  args: ['0xAgentAddress', 1n],
});
// info.owner, info.stake (BigInt, wei)
```

### Read emission state
```javascript
const [currentEpoch, settledEpoch, dailyEmission, totalWeight, settleProgress] = await Promise.all([
  client.readContract({ address: AWP_EMISSION, abi: parseAbi(['function currentEpoch() view returns (uint256)']), functionName: 'currentEpoch' }),
  client.readContract({ address: AWP_EMISSION, abi: parseAbi(['function settledEpoch() view returns (uint256)']), functionName: 'settledEpoch' }),
  client.readContract({ address: AWP_EMISSION, abi: parseAbi(['function currentDailyEmission() view returns (uint256)']), functionName: 'currentDailyEmission' }),
  client.readContract({ address: AWP_EMISSION, abi: parseAbi(['function getTotalWeight() view returns (uint256)']), functionName: 'getTotalWeight' }),
  client.readContract({ address: AWP_EMISSION, abi: parseAbi(['function settleProgress() view returns (uint256)']), functionName: 'settleProgress' }),
]);
```

### Read recipient weight
```javascript
const weight = await client.readContract({
  address: AWP_EMISSION,
  abi: parseAbi(['function getWeight(address) view returns (uint96)']),
  functionName: 'getWeight',
  args: ['0xRecipientAddress'],
});
```

---

## 3. Contract Write Examples (viem + wallet)

### Register as user
```javascript
import { createWalletClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
// chain configured at deployment

const account = privateKeyToAccount('0x...');
const walletClient = createWalletClient({
  account,
  chain: targetChain, // chain object configured at deployment
  transport: http(RPC_URL), // RPC endpoint from environment
});

const hash = await walletClient.writeContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function register()']),
  functionName: 'register',
});
```

### Deposit AWP (via StakeNFT)
```javascript
const STAKENFT = '0x...'; // from deployment

// 1. Approve AWP transfer to StakeNFT
const awpAmount = 10000n * 10n**18n; // 10,000 AWP
await walletClient.writeContract({
  address: AWP_TOKEN,
  abi: parseAbi(['function approve(address,uint256) returns (bool)']),
  functionName: 'approve',
  args: [STAKENFT, awpAmount],
});

// 2. Deposit with lock period (e.g., ~182 days in seconds)
const hash = await walletClient.writeContract({
  address: STAKENFT,
  abi: parseAbi(['function deposit(uint256,uint64) returns (uint256)']),
  functionName: 'deposit',
  args: [awpAmount, 15724800n], // 182 days × 86400 seconds
});
// Returns tokenId of the minted position NFT
```

### Vote with position NFTs (AWPDAO)
```javascript
const AWPDAO = '0x...'; // from deployment

// Vote with multiple position NFTs
await walletClient.writeContract({
  address: AWPDAO,
  abi: parseAbi(['function castVoteWithReasonAndParams(uint256,uint8,string,bytes)']),
  functionName: 'castVoteWithReasonAndParams',
  args: [proposalId, 1, '', encodeAbiParameters([{ type: 'uint256[]' }], [[tokenId1, tokenId2]])], // 1 = For
  // Voting power = sum(amount_i * sqrt(min(remainingTime_i, 54 weeks) / 7 days))
});
```

### Allocate stake
```javascript
await walletClient.writeContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function allocate(address,uint256,uint256)']),
  functionName: 'allocate',
  args: ['0xAgentAddress', 1n, 5000n * 10n**18n], // agent, subnetId, amount
});
```

### Register subnet
```javascript
// 1. Calculate LP cost
const initialAlphaPrice = await client.readContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function initialAlphaPrice() view returns (uint256)']),
  functionName: 'initialAlphaPrice',
});
const INITIAL_ALPHA_MINT = 100_000_000n * 10n**18n;
const lpCost = INITIAL_ALPHA_MINT * initialAlphaPrice / 10n**18n;

// 2. Approve AWP
await walletClient.writeContract({
  address: AWP_TOKEN,
  abi: parseAbi(['function approve(address,uint256) returns (bool)']),
  functionName: 'approve',
  args: [AWP_REGISTRY, lpCost],
});

// 3a. (Optional) Compute a vanity salt via the API — pattern determined by factory's vanityRule
const vanityRes = await fetch(`${API_BASE}/vanity/compute-salt`, {
  method: 'POST',
});
const { salt: vanitySalt, address: predictedAddr } = await vanityRes.json();
// vanitySalt = "0x530c11...", predictedAddr = "0xA1b275...cafe"

// 3b. Register subnet (salt=0x00..00 uses subnetId as CREATE2 salt; or pass vanitySalt for vanity address)
const hash = await walletClient.writeContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function registerSubnet((string,string,address,bytes32,uint128)) returns (uint256)']),
  functionName: 'registerSubnet',
  args: [{
    name: "My Subnet Alpha",
    symbol: "MSALPHA",
    subnetManager: "0x0000000000000000000000000000000000000000", // address(0) = auto-deploy SubnetManager
    salt: vanitySalt ?? "0x0000000000000000000000000000000000000000000000000000000000000000",
    minStake: 0n,
  }],
});
```

### Activate subnet
```javascript
await walletClient.writeContract({
  address: AWP_REGISTRY,
  abi: parseAbi(['function activateSubnet(uint256)']),
  functionName: 'activateSubnet',
  args: [1n], // subnetId
});
```

---

## 4. WebSocket Example

```javascript
const ws = new WebSocket(`wss://<API_HOST>/ws/live`);

ws.onopen = () => {
  // Subscribe to events relevant for a subnet coordinator
  ws.send(JSON.stringify({
    subscribe: [
      'Allocated', 'Deallocated', 'Reallocated', 'AgentRegistered', 'AgentRemoved',
      'Deposited', 'Withdrawn', 'RecipientAWPDistributed', 'EpochSettled'
    ]
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'Allocated':
      console.log(`User ${msg.data.user} allocated ${msg.data.amount} to agent ${msg.data.agent} subnet ${msg.data.subnetId}`);
      break;
    case 'RecipientAWPDistributed':
      console.log(`Epoch ${msg.data.epoch}: ${msg.data.recipient} received ${msg.data.awpAmount} AWP`);
      break;
    case 'EpochSettled':
      console.log(`Epoch ${msg.data.epoch} settled. Total emission: ${msg.data.totalEmission}`);
      break;
  }
};
```

---

## 5. Utility: Format Wei to Human-Readable

```javascript
function formatAWP(wei) {
  if (typeof wei === 'string') wei = BigInt(wei);
  const whole = wei / 10n**18n;
  const frac = wei % 10n**18n;
  const fracStr = frac.toString().padStart(18, '0').slice(0, 4);
  return `${whole.toLocaleString()}.${fracStr} AWP`;
}

// formatAWP("15800000000000000000000000") → "15,800,000.0000 AWP"
```
