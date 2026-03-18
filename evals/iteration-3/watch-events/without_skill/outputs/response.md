I can walk you through setting up a real-time WebSocket subscription for subnet events on AWP RootNet. No wallet is needed — this is read-only.

## WebSocket Connection

Connect to the AWP live event stream:

```
wss://tapi.awp.sh/ws/live
```

## Subscribe to Subnet Events

After the WebSocket connection opens, send this subscribe message to filter for the three event types you want:

```json
{
  "subscribe": [
    "SubnetRegistered",
    "SkillsURIUpdated",
    "MinStakeUpdated"
  ]
}
```

These map directly to your requirements:

| Your Request | Event Type | Data Fields |
|-------------|------------|-------------|
| New registrations | `SubnetRegistered` | `{subnetId, owner, name, symbol, subnetManager, alphaToken}` |
| Skills URI updates | `SkillsURIUpdated` | `{subnetId, skillsURI}` |
| Min stake changes | `MinStakeUpdated` | `{subnetId, minStake}` |

- `SubnetRegistered` is emitted by the RootNet contract when `registerSubnet()` is called.
- `SkillsURIUpdated` is emitted by SubnetNFT when the subnet owner calls `setSkillsURI()`.
- `MinStakeUpdated` is emitted by SubnetNFT when the subnet owner calls `setMinStake()`.

## Event Message Format

Each incoming message has this structure:

```json
{
  "type": "SubnetRegistered",
  "blockNumber": 12345678,
  "txHash": "0xabc...",
  "data": {
    "subnetId": 12,
    "owner": "0x5678...efgh",
    "name": "DataMiner",
    "symbol": "DM",
    "subnetManager": "0x...",
    "alphaToken": "0x..."
  }
}
```

You can link to the transaction on BSCScan: `https://bscscan.com/tx/{txHash}`

Note that `minStake` in the `MinStakeUpdated` event is in wei (18 decimals). To display it as a human-readable number, divide by 10^18.

## JavaScript Example

```javascript
const ws = new WebSocket('wss://tapi.awp.sh/ws/live');

ws.onopen = () => {
  ws.send(JSON.stringify({
    subscribe: ['SubnetRegistered', 'SkillsURIUpdated', 'MinStakeUpdated']
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'SubnetRegistered':
      console.log(`New subnet #${msg.data.subnetId} "${msg.data.name}" registered by ${msg.data.owner}`);
      break;
    case 'SkillsURIUpdated':
      console.log(`Subnet #${msg.data.subnetId} skills URI updated to ${msg.data.skillsURI}`);
      break;
    case 'MinStakeUpdated': {
      const minStakeAWP = Number(BigInt(msg.data.minStake)) / 1e18;
      console.log(`Subnet #${msg.data.subnetId} min stake changed to ${minStakeAWP.toFixed(4)} AWP`);
      break;
    }
  }
};

ws.onclose = () => {
  // Reconnect with exponential backoff
  // 1s -> 2s -> 4s -> ... -> max 30s
};
```

## Broadening the Subscription

If you later want to see the full subnet lifecycle (activations, pauses, bans, LP creation, etc.), you can subscribe to all subnet-related events:

```json
{
  "subscribe": [
    "SubnetRegistered",
    "SubnetActivated",
    "SubnetPaused",
    "SubnetResumed",
    "SubnetBanned",
    "SubnetUnbanned",
    "SubnetDeregistered",
    "LPCreated",
    "SkillsURIUpdated",
    "MinStakeUpdated"
  ]
}
```

## Reconnection

WebSocket connections can drop. Implement automatic reconnection with exponential backoff (1s, 2s, 4s, ... capped at 30s) and re-send the subscribe message after each reconnect.

## Polling Fallback

If WebSocket is unavailable, you can poll `GET https://tapi.awp.sh/api/subnets?status=Active&page=1&limit=100` periodically and diff against the previous response. However, this will not catch `SkillsURIUpdated` or `MinStakeUpdated` changes — only the WebSocket stream provides those events in real time.
