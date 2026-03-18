# Monitoring All Staking Events in Real-Time

Following the **W1 (Watch Events)** workflow with the **staking** preset.

---

## Step 1: Connect to WebSocket

```
wss://api.awp.network/ws/live
```

Open a persistent WebSocket connection to the AWP RootNet live event stream.

---

## Step 2: Send Subscribe Message

Immediately after the connection opens, send the **staking preset** subscribe message:

```json
{"subscribe": ["Deposited", "Withdrawn", "PositionIncreased", "Allocated", "Deallocated", "Reallocated"]}
```

This covers all 6 staking-related event types.

---

## Step 3: Event Display Format

Each incoming event uses the format:

```
$ {type} · {key_fields} · bscscan.com/tx/{shortTxHash}
```

The `$` emoji prefix is used for all staking events per the preset table.

### Deposited

Incoming message:
```json
{
  "type": "Deposited",
  "blockNumber": 41923456,
  "txHash": "0xa1b2c3d4e5f6...1234567890abcdef",
  "data": {
    "user": "0x1234567890abcdef1234567890abcdef12345678",
    "tokenId": "42",
    "amount": "50000000000000000000000",
    "lockEndEpoch": "58"
  }
}
```

Display:
```
$ Deposited · 0x1234...5678 deposited 50,000.0000 AWP (token #42) · lock ends epoch 58 · bscscan.com/tx/0xa1b2...cdef
```

> Note: `lockEndEpoch` is an **absolute** epoch number, not a relative lock duration.

### Withdrawn

Incoming message:
```json
{
  "type": "Withdrawn",
  "blockNumber": 41923500,
  "txHash": "0xdeadbeef...abcdef1234567890",
  "data": {
    "user": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    "tokenId": "17",
    "amount": "10000000000000000000000"
  }
}
```

Display:
```
$ Withdrawn · 0xabcd...abcd withdrew 10,000.0000 AWP (token #17) · bscscan.com/tx/0xdead...7890
```

### PositionIncreased

Incoming message:
```json
{
  "type": "PositionIncreased",
  "blockNumber": 41923555,
  "txHash": "0x9876543210fedcba9876543210fedcba98765432",
  "data": {
    "tokenId": "42",
    "addedAmount": "25000000000000000000000",
    "newLockEndEpoch": "62"
  }
}
```

Display:
```
$ PositionIncreased · token #42 increased by 25,000.0000 AWP · new lock end epoch 62 · bscscan.com/tx/0x9876...5432
```

### Allocated

Incoming message:
```json
{
  "type": "Allocated",
  "blockNumber": 41923600,
  "txHash": "0xfedcba0987654321fedcba0987654321fedcba09",
  "data": {
    "user": "0x1234567890abcdef1234567890abcdef12345678",
    "agent": "0xaaaabbbbccccddddeeeeffffaaaabbbbccccdddd",
    "subnetId": "5",
    "amount": "30000000000000000000000",
    "operator": "0x1234567890abcdef1234567890abcdef12345678"
  }
}
```

Display:
```
$ Allocated · 0x1234...5678 allocated 30,000.0000 AWP to agent 0xaaaa...dddd on subnet #5 (operator: 0x1234...5678) · bscscan.com/tx/0xfedc...ba09
```

> Note: The `operator` field indicates who initiated the call. When operator = user, the user acted directly. When they differ, a manager acted on behalf of the user.

### Deallocated

Incoming message:
```json
{
  "type": "Deallocated",
  "blockNumber": 41923650,
  "txHash": "0x1111222233334444555566667777888899990000",
  "data": {
    "user": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    "agent": "0xeeeeffffeeeeffffeeeeffffeeeeffffeeeeffff",
    "subnetId": "3",
    "amount": "15000000000000000000000",
    "operator": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
  }
}
```

Display:
```
$ Deallocated · 0xabcd...abcd deallocated 15,000.0000 AWP from agent 0xeeee...ffff on subnet #3 (operator: 0xabcd...abcd) · bscscan.com/tx/0x1111...0000
```

### Reallocated

Incoming message:
```json
{
  "type": "Reallocated",
  "blockNumber": 41923700,
  "txHash": "0xaabbccddeeff00112233445566778899aabbccdd",
  "data": {
    "user": "0x1234567890abcdef1234567890abcdef12345678",
    "fromAgent": "0xaaaabbbbccccddddeeeeffffaaaabbbbccccdddd",
    "fromSubnet": "5",
    "toAgent": "0xeeeeffffeeeeffffeeeeffffeeeeffffeeeeffff",
    "toSubnet": "3",
    "amount": "20000000000000000000000",
    "operator": "0x1234567890abcdef1234567890abcdef12345678"
  }
}
```

Display:
```
$ Reallocated · 0x1234...5678 moved 20,000.0000 AWP from agent 0xaaaa...dddd (subnet #5) to agent 0xeeee...ffff (subnet #3) (operator: 0x1234...5678) · bscscan.com/tx/0xaabb...ccdd
```

> Note: Reallocate is immediate with no cooldown.

---

## Step 4: Reconnection Strategy

If the WebSocket connection drops:

| Parameter | Value |
|-----------|-------|
| Initial delay | 1 second |
| Backoff factor | 2x |
| Max delay | 30 seconds |
| Sequence | 1s, 2s, 4s, 8s, 16s, 30s, 30s, 30s... |

On each reconnect:
1. Re-establish connection to `wss://api.awp.network/ws/live`
2. Re-send the subscribe message: `{"subscribe": ["Deposited", "Withdrawn", "PositionIncreased", "Allocated", "Deallocated", "Reallocated"]}`
3. Once a valid event message is received, reset the backoff delay to 1 second

If the WebSocket remains unreachable, verify API health via `GET /health` (expect `{"status": "ok"}`). If the health endpoint also fails, the API is likely down -- continue retrying with the 30s max interval.

---

## Step 5: Amount Handling

All amounts in event data are **string-type wei** (18 decimals). Processing rules:

- Parse with `BigInt` -- never `Number` (precision loss above 2^53)
- Convert: `amount / 10^18`, display with 4 decimal places and thousands separators
- Example: `"50000000000000000000000"` displays as `50,000.0000 AWP`
- Addresses: `0x1234567890abcdef1234567890abcdef12345678` displays as `0x1234...5678`

---

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| WebSocket connection refused | API down or network issue | Retry with exponential backoff; check `GET /health` |
| WebSocket closed unexpectedly | Server restart or timeout | Auto-reconnect, re-subscribe |
| No events received | Wrong event type names or no staking activity | Verify event names match the 6 staking events listed above; staking events only fire when users stake/allocate |
