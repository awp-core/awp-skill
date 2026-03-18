I'll set up a real-time WebSocket subscription for all subnet events. This uses action **W1 · Watch Events** with the **subnets** preset.

## Connection

**WebSocket URL:** `wss://tapi.awp.sh/ws/live`

## Subscribe Message

Send this JSON after connecting:

```json
{
  "action": "subscribe",
  "events": [
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

This is the **subnets** preset — **10 event types** covering the full subnet lifecycle. The events you specifically asked about are all included:

- **SubnetRegistered** — new subnet registrations
- **SkillsURIUpdated** — skills URI changes (emitted by `SubnetNFT.setSkillsURI`)
- **MinStakeUpdated** — minimum stake changes (emitted by `SubnetNFT.setMinStake`)

## What You'll See

Events will stream in this format:

```
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | bscscan.com/tx/0xdef...
# SkillsURIUpdated | #12 -> ipfs://QmABC...xyz | bscscan.com/tx/0x456...
# MinStakeUpdated | #12 -> 1,000.0000 AWP | bscscan.com/tx/0x789...
# SubnetActivated | #12 | bscscan.com/tx/0xabc...
# LPCreated | #12 pool created | bscscan.com/tx/0xfed...
```

All subnet events use the `#` emoji prefix.

## Reconnection

If the WebSocket disconnects, reconnect with exponential backoff (1s -> 2s -> 4s -> ... -> max 30s) and re-send the subscribe message above.

## Reference

- **27 total event types** across all categories (staking: 6, subnets: 10, emission: 6, users: 5)
- No wallet needed — this is a read-only subscription
- To narrow down to just your 3 events of interest, replace the events array with `["SubnetRegistered", "SkillsURIUpdated", "MinStakeUpdated"]`
