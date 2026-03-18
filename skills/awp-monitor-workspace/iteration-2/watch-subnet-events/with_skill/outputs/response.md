# Monitoring All Subnet Events (Real-Time)

Using the **subnets** preset from W1 to subscribe to all 11 subnet-related events, including new registrations, skillsURI updates, and minStake changes.

---

## 1. Connect to WebSocket

```
ws://ec2-100-31-107-3.compute-1.amazonaws.com/ws/live
```

## 2. Subscribe — Subnets Preset (11 Events)

Send this JSON message immediately after connection:

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
    "MetadataUpdated",
    "LPCreated",
    "SkillsURIUpdated",
    "MinStakeUpdated"
  ]
}
```

## 3. Incoming Event Format

Every event arrives as:

```json
{
  "type": "EventName",
  "blockNumber": 12345678,
  "txHash": "0xabcdef...",
  "data": { /* event-specific fields */ }
}
```

## 4. Display Format (Real-Time Output)

Each event is displayed with the `#` emoji prefix (subnet category):

### SubnetRegistered — New subnet created
```
# SubnetRegistered · #7 "AlphaNet" by 0x1234...abcd · manager 0x5678...ef01 · bscscan.com/tx/0xabc1...
```
Key fields: `subnetId`, `owner`, `name`, `symbol`, `metadataURI`, `subnetManager`, `alphaToken`, `coordinatorURL`

### SubnetActivated / Paused / Resumed / Banned / Unbanned / Deregistered — Lifecycle transitions
```
# SubnetActivated · #7 · bscscan.com/tx/0xabc2...
# SubnetPaused · #7 · bscscan.com/tx/0xabc3...
# SubnetResumed · #7 · bscscan.com/tx/0xabc4...
# SubnetBanned · #7 · bscscan.com/tx/0xabc5...
# SubnetUnbanned · #7 · bscscan.com/tx/0xabc6...
# SubnetDeregistered · #7 · bscscan.com/tx/0xabc7...
```
Key fields: `subnetId` only

### MetadataUpdated — Metadata or coordinator URL changed
```
# MetadataUpdated · #7 metadata → ipfs://Qm... · coordinator → https://coord.example.com · bscscan.com/tx/0xabc8...
```
Key fields: `subnetId`, `metadataURI`, `coordinatorURL` (only 2 string fields; does NOT include skillsURI)

### LPCreated — Liquidity pool initialized
```
# LPCreated · #7 pool created · 1,000,000.0000 AWP + 100,000,000.0000 Alpha · bscscan.com/tx/0xabc9...
```
Key fields: `subnetId`, `poolId`, `awpAmount`, `alphaAmount`

### SkillsURIUpdated — Skills file URI changed
```
# SkillsURIUpdated · #7 skills → https://example.com/skills/subnet7/SKILL.md · bscscan.com/tx/0xabca...
```
Key fields: `subnetId`, `skillsURI`
> Note: Emitted by **SubnetNFT** contract (not RootNet). This is a separate event from MetadataUpdated.

### MinStakeUpdated — Minimum stake requirement changed
```
# MinStakeUpdated · #7 min stake → 5,000.0000 AWP · bscscan.com/tx/0xabcb...
```
Key fields: `subnetId`, `minStake`
> Note: Emitted by **SubnetNFT** contract (not RootNet). `minStake` is in wei — always convert via `formatAWP()` (divide by 10^18, show 4 decimal places).

## 5. Reconnection Strategy

If the WebSocket disconnects:

1. Reconnect with exponential backoff: 1s → 2s → 4s → ... → max 30s
2. Re-send the subscribe message after reconnecting
3. Reset backoff delay after first successful message received
4. If connection is persistently refused, check `GET /health` endpoint

## 6. Important Notes

- **Amount handling**: All amounts (e.g., `minStake`, `awpAmount`, `alphaAmount`) are string-type wei. Always convert with `BigInt` and display as `amount / 10^18` with 4 decimal places.
- **Address display**: Use `shortAddr()` format — `0x1234...abcd` (first 6 + last 4 hex chars).
- **On-chain SubnetInfo** does NOT include `name`, `symbol`, `skillsURI`, `minStake`, or `owner`. These fields are only available via the REST API or `getSubnetFull()`.
- **SkillsURIUpdated** and **MinStakeUpdated** are emitted by the SubnetNFT contract, not RootNet — but they are delivered through the same WebSocket stream.
- **SubnetRegistered** event does NOT include `skillsURI` — it must be set separately after registration via `SubnetNFT.setSkillsURI()`.
