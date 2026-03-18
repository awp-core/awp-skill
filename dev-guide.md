# Claude Code Prompt Playbook

Place `CLAUDE.md` at the repository root (Claude Code reads it automatically), then follow these steps.

---

## Step 1: Read docs and build context

```
Read the following 6 files to understand the full AWP RootNet protocol spec:

1. skills-dev/CLAUDE.md — protocol architecture and component responsibilities
2. skills-dev/contract-api.md — all contract function signatures, data structures, access control
3. skills-dev/rest-api.md — all HTTP endpoints, response schemas, WebSocket events
4. skills-dev/examples.md — working code examples (REST, viem read/write, WebSocket)
5. skills-dev/config.md — chain configuration and constants
6. skills-dev/agent-skill-guide.md — how agents discover and install skills

After reading, summarize in your own words:
- What RootNet, StakeNFT, AWPEmission, and AWPDAO each do
- What actions the awp skill covers across its 4 sections (use Q/S/M/G IDs)
- Why awp-monitor is a separate skill (different interaction mode)
- Write-action safety rules (confirm → execute → link)
- The 3 most common pitfalls (lockEndEpoch, castVote, approve target)
```

---

## Step 2: Create references/protocol.md (shared definitions)

```
Create references/protocol.md containing definitions shared by both skills:

1. Data structures (extract from contract-api.md):
   - SubnetStatus enum (0–3 mapping)
   - SubnetInfo struct (note: on-chain struct does NOT include name/symbol/skills_uri)
   - SubnetParams struct (all 7 fields)
   - AgentInfo struct

2. Complete event field table (extract from rest-api.md WebSocket section, all 25 event types):
   - Group by category: Staking / Subnet / User & Agent / Emission
   - Mark error-prone fields: lockEndEpoch (absolute, not relative), operator field,
     SubnetRegistered full string fields

3. Shared endpoints:
   - GET /registry → contract addresses
   - GET /address/{addr}/check → registration status
   - GET /health

This file will be copied into both skills (self-contained requirement).
```

---

## Step 3: Create the awp skill

```
Create skills/awp/SKILL.md covering 19 actions across 4 sections.

SKILL.md requirements:
- YAML frontmatter: name=awp, description ~100 words covering trigger keywords, user-invocable=true
- Reference lines at top pointing to references/api-reference.md and references/protocol.md
- Write safety rules (apply to all S/M/G actions)
- Each action in 3–8 lines: intent + steps + key caveats
- No code blocks (code belongs in api-reference.md)
- Unified error-handling table at the end
- Target ~130 lines total

4 sections:

Query (Q1–Q7):
- Q1 Subnet Info: GET /subnets/{id}, on-chain fallback getSubnet() (no string fields)
- Q2 Balance: parallel fetch balance + positions + allocations
- Q3 Emission: current + schedule + epochs, decay ~0.3156%/epoch
- Q4 Agent: batch-info (POST, max 100), by-owner, lookup
- Q5 List Subnets: pagination + status filter, flag subnets with skills_uri
- Q6 Skills URI: fetch and optionally display SKILL.md frontmatter
- Q7 Epoch History: epochs endpoint with pagination

Staking (S1–S3):
- S1 Register: check /address/check first; registerAndStake approve target is RootNet
- S2 Deposit: approve(stakeNFT) → deposit → return tokenId; note lockEndEpoch is absolute
- S3 Allocate: check balance for unallocated; reallocate has no cooldown

Subnet Management (M1–M3):
- M1 Register Subnet: calculate LP cost → approve(rootNet) → registerSubnet
- M2 Lifecycle: check current status → activate/pause/resume
- M3 Update Metadata: all three strings required every call, GET current values first then merge

Governance (G1–G4):
- G1 Propose: proposeWithTokens or signalPropose (no execution)
- G2 Vote: must use castVoteWithReasonAndParams + encodeAbiParameters; castVote is blocked
- G3 Query Proposals: REST + on-chain proposalVotes/quorum/isSignalProposal
- G4 Treasury: treasuryAddress + optional balance check

After writing, verify every action against contract-api.md and rest-api.md.
```

---

## Step 4: Create the awp api-reference.md

```
Create skills/awp/references/api-reference.md.

Requirements:
- Organized by action ID (Q1, Q2, ..., S1, S2, ..., M1, ..., G1, ...)
- Each action groups together: REST endpoint (with response JSON example) + contract signature (Solidity format)
- For shared definitions (structs, events), write "see protocol.md" — do not duplicate
- Extract contract signatures from contract-api.md, keep only functions relevant to that action
- Extract response JSON from rest-api.md, preserve exact field names (snake_case)
- Include supplementary endpoints: tokens/awp, tokens/alpha/{id}/price, users/{addr}

Cross-check against rest-api.md:
□ Every endpoint path exactly correct?
□ Response field names are snake_case? (subnet_id not subnetId, except skillsURI)
□ POST /agents/batch-info request body format correct?
□ Pagination parameters documented?
```

---

## Step 5: Create the awp-monitor skill

```
Create skills/awp-monitor/SKILL.md + references/api-reference.md.

SKILL.md (~50 lines):
- Frontmatter: name=awp-monitor, description covering "watch/monitor/subscribe/alert/real-time"
- Action 1 Watch Events: connect → subscribe → format output → reconnect on disconnect
  - 5 preset groups: staking / subnets / emission / users / all
  - Display: emoji + event type + key fields (amounts as AWP, addresses shortened) + tx link
- Action 2 Emission Alert: subscribe to EpochSettled events → settlement notification + top recipients
  - Polling fallback: GET /emission/current every 60s, compare epoch number

api-reference.md:
- WebSocket URL + protocol (subscribe message format, incoming message format)
- 5 preset tables
- Polling endpoints: /emission/current, /emission/epochs
- Event field table is in protocol.md — do not repeat here

Then copy protocol.md (from Step 2) into skills/awp-monitor/references/.
```

---

## Step 6: Final review

```
All files are complete. Run the final review checklist:

Format:
□ Both SKILL.md files have correct YAML frontmatter?
□ awp SKILL.md < 500 lines? (target ~130)
□ awp-monitor SKILL.md < 500 lines? (target ~50)
□ Descriptions cover diverse trigger keywords?
□ No JavaScript/Solidity code blocks inside SKILL.md? (code belongs in api-reference.md)

Data correctness (verify each item against rest-api.md and contract-api.md):
□ REST endpoint paths exactly match?
□ Response field names exactly match (snake_case)?
□ Contract function signatures exactly match (param types, return values)?
□ SubnetParams struct has all 7 fields?
□ AgentInfo struct has all 4 fields?

Event fields (verify against rest-api.md WebSocket section):
□ Deposited uses lockEndEpoch (absolute), not lockEpochs (relative)?
□ Allocated/Deallocated/Reallocated include operator?
□ AgentRemoved/ManagerUpdated include operator?
□ SubnetRegistered includes metadataURI + coordinatorURL + skillsURI?
□ PositionIncreased fields are tokenId + addedAmount + newLockEndEpoch?
□ All 25 event types listed in protocol.md?

Safety and logic:
□ All write actions have a confirmation step?
□ S2 Deposit: approve target is stakeNFT?
□ S1 registerAndStake: approve target is rootNet?
□ M1 Register Subnet: approve target is rootNet?
□ M3 updateMetadata: warns that all three strings are required?
□ G2 Vote: uses encodeAbiParameters, not encodePacked?
□ G2 Vote: states that castVote() is blocked?
□ No hardcoded contract addresses? (use /registry)

Fix any issues found and explain each change.
```

---

## Future: if awp SKILL.md exceeds 500 lines

Split into `awp-query` (Q1–Q7, read-only) + `awp-write` (S1–S3 + M1–M3 + G1–G4, wallet required). The split signal is the line-count limit, not functional taxonomy.
