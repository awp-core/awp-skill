# AWP Monitor — API Reference

For shared data structures and event field table, see `protocol.md`.

---

## WebSocket Protocol

### Connection

```
wss://tapi.awp.sh/ws/live
```

### Subscribe

Send a JSON message after connection is established:

```json
{
  "subscribe": ["EventName1", "EventName2", "..."]
}
```

### Incoming Message Format

```json
{
  "type": "EventName",
  "blockNumber": 12345678,
  "txHash": "0xabcdef...",
  "data": {
    // Event-specific fields — see protocol.md event field table
  }
}
```

---

## Presets

### Staking Preset

```json
{"subscribe": ["Deposited", "Withdrawn", "PositionIncreased", "Allocated", "Deallocated", "Reallocated"]}
```

| Event | Key Display Fields |
|-------|--------------------|
| Deposited | user, tokenId, amount, lockEndTime (absolute timestamp) |
| Withdrawn | user, tokenId, amount |
| PositionIncreased | tokenId, addedAmount, newLockEndTime |
| Allocated | user, agent, subnetId, amount, operator |
| Deallocated | user, agent, subnetId, amount, operator |
| Reallocated | user, fromAgent, fromSubnet, toAgent, toSubnet, amount, operator |

### Subnets Preset

```json
{"subscribe": ["SubnetRegistered", "SubnetActivated", "SubnetPaused", "SubnetResumed", "SubnetBanned", "SubnetUnbanned", "SubnetDeregistered", "MetadataUpdated", "LPCreated", "SkillsURIUpdated", "MinStakeUpdated"]}
```

| Event | Key Display Fields |
|-------|--------------------|
| SubnetRegistered | subnetId, owner, name, symbol, metadataURI, subnetManager, alphaToken, coordinatorURL |
| SubnetActivated / Paused / Resumed / Banned / Unbanned / Deregistered | subnetId |
| MetadataUpdated | subnetId, metadataURI, coordinatorURL |
| LPCreated | subnetId, poolId, awpAmount, alphaAmount |
| SkillsURIUpdated | subnetId, skillsURI |
| MinStakeUpdated | subnetId, minStake |

### Emission Preset

```json
{"subscribe": ["EpochSettled", "RecipientAWPDistributed", "DAOMatchDistributed", "GovernanceWeightUpdated", "AllocationsSubmitted", "OracleConfigUpdated"]}
```

| Event | Key Display Fields |
|-------|--------------------|
| EpochSettled | epoch, totalEmission, recipientCount |
| RecipientAWPDistributed | epoch, recipient, awpAmount |
| DAOMatchDistributed | epoch, amount |
| GovernanceWeightUpdated | addr, weight |
| AllocationsSubmitted | nonce, recipients, weights |
| OracleConfigUpdated | oracles, threshold |

### Users Preset

```json
{"subscribe": ["UserRegistered", "AgentBound", "AgentUnbound", "AgentRemoved", "DelegationUpdated"]}
```

| Event | Key Display Fields |
|-------|--------------------|
| UserRegistered | user |
| AgentBound | principal, agent, oldPrincipal |
| AgentUnbound | principal, agent |
| AgentRemoved | user, agent, operator |
| DelegationUpdated | user, agent, isManager, operator |

### All Preset

```json
{"subscribe": ["Deposited", "Withdrawn", "PositionIncreased", "Allocated", "Deallocated", "Reallocated", "SubnetRegistered", "SubnetActivated", "SubnetPaused", "SubnetResumed", "SubnetBanned", "SubnetUnbanned", "SubnetDeregistered", "MetadataUpdated", "LPCreated", "SkillsURIUpdated", "MinStakeUpdated", "EpochSettled", "RecipientAWPDistributed", "DAOMatchDistributed", "GovernanceWeightUpdated", "AllocationsSubmitted", "OracleConfigUpdated", "UserRegistered", "AgentBound", "AgentUnbound", "AgentRemoved", "DelegationUpdated"]}
```

All 28 event types from the four presets combined.

---

## Polling Fallback

When WebSocket is unavailable, use HTTP polling.

### Current Emission State

```
GET /emission/current
```
```json
{"epoch": "42", "dailyEmission": "15000000000000000000000000", "totalWeight": "5000"}
```

Poll every 60 seconds. Compare `epoch` value — if it increments, a new epoch has been settled.

### Epoch Details

```
GET /emission/epochs?page=1&limit=5
```
```json
[{"epoch_id": 42, "start_time": 1710000000, "daily_emission": "15000000000000000000000000", "dao_emission": "7500000000000000000000000"}]
```

Fetch after detecting epoch change to get settlement details.

> **Important**: The epochs endpoint returns `daily_emission` (per-day rate), not `totalEmission` (per-epoch total from the WebSocket `EpochSettled` event). Epoch duration is 1 day, so `daily_emission` and `totalEmission` are roughly equal, but `recipientCount` is not available from this endpoint — omit it from the display or show "N/A" when using the polling fallback.

---

## Reconnection Strategy

```
Initial delay:  1 second
Backoff factor: 2×
Max delay:      30 seconds
On reconnect:   re-send the subscribe message
Reset delay:    after successful message received
```
