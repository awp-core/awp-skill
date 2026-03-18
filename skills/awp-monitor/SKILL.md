---
name: awp-monitor
description: >
  Real-time monitoring and alerting for AWP RootNet protocol events via
  WebSocket. Sets up persistent subscriptions to watch staking, subnet
  lifecycle, emission settlements, agent bindings, and governance updates.
  ALWAYS use when the user wants to monitor, watch, subscribe, track, or
  get alerts for AWP events in real-time — even without saying "monitor".
metadata: {"openclaw":{"requires":{"env":["AWP_API_URL"]}}}
---

# AWP Monitor

**Skill version: 1.3.0**

## On Skill Load (do this FIRST)

**Step 1 — Show welcome** (first session only):
> **Welcome to AWP Monitor!**
>
> Real-time monitoring of AWP RootNet events via WebSocket — 28 event types across staking, subnets, emissions, and agents.
>
> Say: "watch staking events", "alert on epoch settlements", "monitor subnet 5", or "watch everything"

**Step 2 — Version check** (silent if current):
```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp-monitor/SKILL.md | head -20 | grep "Skill version"
```
If remote > 1.3.0: "Update: `openclaw skill install https://github.com/awp-core/awp-skill/tree/main/skills/awp-monitor`"

**Step 3 — Route**: W1 (watch events) or W2 (emission alert).

## Reference Files

- **api-reference.md** — WebSocket protocol, preset JSON, polling fallback
  Local: `references/api-reference.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp-monitor/references/api-reference.md`
- **protocol.md** — 28 event types with field definitions
  Local: `references/protocol.md` | Remote: `https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp-monitor/references/protocol.md`

**Loading rule**: For preset subscriptions, this SKILL.md has the event lists. Fetch api-reference.md only if you need the exact subscribe JSON or polling endpoint details.

## Conventions

- **API**: `https://tapi.awp.sh/api` (or `AWP_API_URL`)
- **WebSocket**: `wss://tapi.awp.sh/ws/live`
- **Amounts**: `{formatAWP(amount)}` — never raw wei
- **Addresses**: `{shortAddr(addr)}`
- **Timestamps**: `{tsToDate(ts)}`
- **Reconnect**: 1s → 2s → 4s → ... → max 30s, re-subscribe on reconnect

## Session State

Track across conversation:
- `ws_connected`: true after successful WebSocket connection — don't reconnect unless disconnected
- `subscribed_events`: list of currently subscribed event types — re-use for reconnection
- `last_epoch`: last seen epoch number from EpochSettled — detect new settlements

---

## W1 · Watch Events

1. Connect to WebSocket URL above
2. Send subscribe JSON with event types (preset or custom)
3. Format each event: `{emoji} {type} · {fields} · bscscan.com/tx/{shortTxHash}`
4. On disconnect: reconnect with backoff, re-send subscribe

### Presets (28 events = 6 + 11 + 6 + 5)

| Preset | Events | Emoji |
|--------|--------|-------|
| staking | Deposited, Withdrawn, PositionIncreased, Allocated, Deallocated, Reallocated | `$` |
| subnets | SubnetRegistered, SubnetActivated, SubnetPaused, SubnetResumed, SubnetBanned, SubnetUnbanned, SubnetDeregistered, MetadataUpdated, LPCreated, SkillsURIUpdated, MinStakeUpdated | `#` |
| emission | EpochSettled, RecipientAWPDistributed, DAOMatchDistributed, GovernanceWeightUpdated, AllocationsSubmitted, OracleConfigUpdated | `~` |
| users | UserRegistered, AgentBound, AgentUnbound, AgentRemoved, DelegationUpdated | `@` |
| all | All 28 | (by category) |

### Display Examples
- `$ Deposited · {shortAddr(user)} deposited {formatAWP(amount)} · lock ends {tsToDate(lockEndTime)} · bscscan.com/tx/{shortTxHash}`
- `# SubnetRegistered · #{subnetId} "{name}" by {shortAddr(owner)} · bscscan.com/tx/{shortTxHash}`
- `# SkillsURIUpdated · #{subnetId} → {skillsURI} · bscscan.com/tx/{shortTxHash}`
- `# MinStakeUpdated · #{subnetId} min stake → {formatAWP(minStake)} · bscscan.com/tx/{shortTxHash}`
- `~ EpochSettled · Epoch {epoch} · {formatAWP(totalEmission)} to {recipientCount} recipients · bscscan.com/tx/{shortTxHash}`
- `@ AgentBound · {shortAddr(agent)} → {shortAddr(principal)} · bscscan.com/tx/{shortTxHash}`

### Example W1 Output

```
$ Deposited | 0x1234...abcd deposited 5,000.0000 AWP | lock ends 2025-12-01 | bscscan.com/tx/0xabc...
# SubnetRegistered | #12 "DataMiner" by 0x5678...efgh | bscscan.com/tx/0xdef...
~ EpochSettled | Epoch 42 | 15,800,000.0000 AWP to 150 recipients | bscscan.com/tx/0x123...
```

---

## W2 · Emission Alert

1. Subscribe: `EpochSettled` + `RecipientAWPDistributed` + `DAOMatchDistributed`
2. On EpochSettled: show summary + fetch `GET /emission/current`
3. On DAOMatchDistributed: capture DAO match
4. On RecipientAWPDistributed: accumulate per-recipient → show top earners
5. **Polling fallback** (no WebSocket): `GET /emission/current` every 60s, compare epoch. recipientCount unavailable in polling.

### Alert Format
> ~ Epoch {epoch} Settled
>   Total: {formatAWP(totalEmission)} · DAO: {formatAWP(daoAmount)} · Recipients: {recipientCount}
>   Top: 1. {shortAddr(addr)} — {formatAWP(amount)} ...

---

## Error Recovery

| Error | Fix |
|-------|-----|
| Connection refused | Wait 5s, check `GET /health`, retry. After 3 failures: switch to polling mode. |
| Unexpected close | Immediate reconnect (backoff 1s-30s). Re-send subscribe message on reconnect. |
| No events received | Verify event names against preset lists above |
| No epoch change (polling) | Normal — keep polling at 60s |
| 500 on /emission | Retry after 30s |
