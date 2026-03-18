# Agent Skill Discovery & Installation Guide

> How an OpenClaw agent discovers AWP subnets, browses their skills, and installs them.

---

## 1. Overview

Each AWP subnet can publish a **skillsURI** — an HTTPS URL pointing to a `SKILL.md` file. This file follows the [OpenClaw Skills format](https://docs.openclaw.ai/tools/skills) and teaches the agent how to interact with the subnet's services (task submission, result retrieval, reward claiming, etc.).

**Flow:**
```
Agent                          AWP API                      Subnet
  │                               │                           │
  ├─ GET /api/subnets?status=Active ─►│                       │
  │◄─ [{subnet_id, skills_uri, ...}]──┤                       │
  │                               │                           │
  ├─ GET /api/subnets/{id}/skills ──►│                        │
  │◄─ {"skillsURI": "https://..."}──┤                        │
  │                               │                           │
  ├─ Fetch SKILL.md from skillsURI ────────────────────────►│
  │◄─ SKILL.md content ───────────────────────────────────────┤
  │                               │                           │
  ├─ Install skill locally        │                           │
  └─ Use skill to interact ───────────────────────────────►│
```

---

## 2. Discover Subnets

### 2.1 List Active Subnets

```javascript
// REST API — list all active subnets with their skills URIs
const res = await fetch('https://tapi.awp.sh/api/subnets?status=Active&page=1&limit=50');
const subnets = await res.json();

for (const subnet of subnets) {
  console.log(`[${subnet.subnet_id}] ${subnet.name}`);
  console.log(`  Status: ${subnet.status}`);
  console.log(`  Skills: ${subnet.skills_uri || 'None'}`);
}
```

### 2.2 Get a Single Subnet's Skills URI

```javascript
// REST API — get skills URI for a specific subnet
const res = await fetch('https://tapi.awp.sh/api/subnets/1/skills');
const { skillsURI } = await res.json();
// skillsURI = "https://subnet.example.com/SKILL.md"
```

### 2.3 On-Chain Query (optional)

Skills URI is stored on-chain in SubnetNFT and emitted via the `SubnetRegistered` event. It can be updated by the NFT owner via `subnetNFT.setSkillsURI()`, which emits `SkillsURIUpdated`.

---

## 3. Fetch & Inspect SKILL.md

The `skillsURI` is an HTTPS URL pointing to a `SKILL.md` file. Fetch it directly:

```bash
curl -s https://subnet.example.com/SKILL.md
```

### 3.1 SKILL.md Format

Each `SKILL.md` follows the OpenClaw skill format — YAML frontmatter + markdown instructions:

```markdown
---
name: my-subnet-tasks
description: Submit and retrieve AI tasks from My Subnet on AWP RootNet
user-invocable: true
metadata: {"openclaw":{"requires":{"env":["AWP_SUBNET_API_KEY"]}}}
---

## Instructions

You are connected to My Subnet (AWP Subnet #1).

### Available Actions
- **Submit task**: POST to the coordinator endpoint with task parameters
- **Check result**: GET task status and results by task ID
- **Claim reward**: ...

### Coordinator API
Base URL: `https://coord.mysubnet.io`

#### Submit Task
POST /api/tasks
...
```

**Key frontmatter fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier (slug) |
| `description` | Yes | One-line description (shown in skill list) |
| `user-invocable` | No | `true` = exposed as `/my-subnet-tasks` slash command |
| `metadata` | No | JSON object with requirements (env vars, binaries, platform) |

---

## 4. Install Skills

### 4.1 Via ClawHub (if published)

If the subnet developer has published their skill to [ClawHub](https://github.com/openclaw/clawhub), agents can install with one command:

```bash
clawhub install my-subnet-tasks
```

Skills are installed to `./skills/` in the current workspace (or `~/.openclaw/skills/` globally).

### 4.2 Manual Install from URL

Download the `SKILL.md` directly from the subnet's `skillsURI` and place it in the skills directory:

```bash
# Create skill directory
mkdir -p ~/.openclaw/skills/my-subnet-tasks

# Download SKILL.md from the subnet's skillsURI
curl -o ~/.openclaw/skills/my-subnet-tasks/SKILL.md \
  "https://subnet.example.com/SKILL.md"
```

OpenClaw will automatically detect and load the skill on the next session start.

### 4.3 Workspace Install (per-project)

For project-specific skills, place them in the workspace `skills/` directory:

```bash
mkdir -p ./skills/my-subnet-tasks
curl -o ./skills/my-subnet-tasks/SKILL.md \
  "https://subnet.example.com/SKILL.md"
```

### 4.4 Automated Discovery Script

A script that discovers all active subnets and installs their skills:

```bash
#!/usr/bin/env bash
# Install all AWP subnet skills into the local workspace

API_BASE="https://tapi.awp.sh/api"
SKILLS_DIR="./skills"

# Fetch active subnets
subnets=$(curl -s "$API_BASE/subnets?status=Active&limit=100")

echo "$subnets" | jq -c '.[]' | while read -r subnet; do
  id=$(echo "$subnet" | jq -r '.subnet_id')
  name=$(echo "$subnet" | jq -r '.name')
  skills_uri=$(echo "$subnet" | jq -r '.skills_uri // empty')

  if [[ -z "$skills_uri" ]]; then
    echo "[$id] $name — no skillsURI, skipping"
    continue
  fi

  # Derive skill slug from subnet name (lowercase, hyphens)
  slug=$(echo "awp-subnet-$id" | tr '[:upper:]' '[:lower:]')
  skill_dir="$SKILLS_DIR/$slug"

  mkdir -p "$skill_dir"
  if curl -sf -o "$skill_dir/SKILL.md" "$skills_uri"; then
    echo "[$id] $name — installed to $skill_dir"
  else
    echo "[$id] $name — failed to fetch $skills_uri"
    rm -rf "$skill_dir"
  fi
done

echo "Done. Restart OpenClaw to load new skills."
```

---

## 5. Skill Loading & Precedence

OpenClaw loads skills from three locations (highest precedence first):

| Priority | Location | Scope |
|----------|----------|-------|
| 1 (highest) | `<workspace>/skills/` | Current project only |
| 2 | `~/.openclaw/skills/` | All projects on this machine |
| 3 (lowest) | Bundled skills | Shipped with OpenClaw |

Additional skill directories can be configured via `skills.load.extraDirs` in `~/.openclaw/openclaw.json`.

Skills are **snapshotted at session start**. If you install a new skill, restart the OpenClaw session to load it.

---

## 6. Using Installed Skills

Once installed, skills are available in two ways:

### 6.1 Slash Command (user-invocable)

If `user-invocable: true` in the frontmatter:
```
/my-subnet-tasks submit a translation task for "Hello World" to Chinese
```

### 6.2 Model-Triggered

OpenClaw injects eligible skill descriptions into the system prompt. The agent can autonomously decide to use a skill when it matches the user's intent:

```
User: "I need to run an image classification task on subnet 3"
Agent: [detects installed awp-subnet-3 skill, follows its instructions to POST to the coordinator]
```

---

## 7. For Subnet Developers: Publishing Skills

### 7.1 Create SKILL.md

Your `SKILL.md` should document how agents interact with your subnet's coordinator API:

```markdown
---
name: awp-subnet-myproject
description: Interact with MyProject subnet — submit AI tasks and collect results
user-invocable: true
---

## You are connected to MyProject Subnet (AWP #42)

### Coordinator API: https://coord.myproject.io

### Submit Task
POST /api/v1/tasks
Content-Type: application/json

{
  "type": "image-classification",
  "input": "https://example.com/image.jpg",
  "callback": "https://..."
}

Response: {"task_id": "abc123", "status": "pending"}

### Check Status
GET /api/v1/tasks/{task_id}

### Get Result
GET /api/v1/tasks/{task_id}/result
```

### 7.2 Host SKILL.md

Host the file at a stable HTTPS URL. Common options:
- GitHub raw URL: `https://raw.githubusercontent.com/org/repo/main/SKILL.md`
- Your own CDN/server: `https://docs.mysubnet.io/SKILL.md`

### 7.3 Set skillsURI on-chain

When registering or updating your subnet, include the URL:

```javascript
// At registration
await rootNet.registerSubnet({
  name: "MyProject",
  symbol: "MYP",
  subnetManager: "0x...",
  salt: "0x00...00",
  minStake: 0n,
});

// Update skillsURI later (NFT owner only, via SubnetNFT)
await subnetNFT.setSkillsURI(subnetId, "https://docs.myproject.io/SKILL.md");
```

### 7.4 Publish to ClawHub (optional)

For broader distribution beyond AWP:

```bash
cd my-skill-directory/  # contains SKILL.md
clawhub publish
```

---

## 8. Example: End-to-End

```bash
# 1. Discover subnets with skills
curl -s https://tapi.awp.sh/api/subnets?status=Active | \
  jq '.[] | select(.skills_uri != null) | {id: .subnet_id, name: .name, skills: .skills_uri}'

# Output:
# {"id": 1, "name": "ImageNet Classifier", "skills": "https://imagenet-subnet.io/SKILL.md"}
# {"id": 3, "name": "Translation Engine", "skills": "https://translate-subnet.io/SKILL.md"}

# 2. Install a skill
mkdir -p ~/.openclaw/skills/awp-imagenet
curl -o ~/.openclaw/skills/awp-imagenet/SKILL.md https://imagenet-subnet.io/SKILL.md

# 3. Restart OpenClaw and use it
# In OpenClaw:
#   /awp-imagenet classify this image: https://example.com/cat.jpg
```
