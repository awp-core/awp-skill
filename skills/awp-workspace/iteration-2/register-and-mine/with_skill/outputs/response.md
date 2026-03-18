# AWP RootNet — 新用户 Gasless 注册 + Agent Mining 引导

---

## Welcome

> **Welcome to AWP RootNet!**
>
> AWP RootNet is a decentralized Agent Mining protocol on BSC. Agents register on subnets, execute tasks for subnet coordinators, and earn AWP token emissions as rewards. Each subnet auto-deploys a SubnetManager with Merkle distribution and configurable AWP strategies (Reserve, AddLiquidity, BuybackBurn).
>
> This skill lets you:
> - **Query** subnet info, staking balances, emissions, agents, proposals
> - **Mine** by registering as Principal or Agent, staking AWP, and working on subnets
> - **Manage** subnets — register (gasless supported), update metadata, set skills URI, set min stake
> - **Govern** by creating proposals and voting with your staked positions
> - **Monitor** real-time events (use the `awp-monitor` skill)
>
> **Get started:**
> - New user? Say "I want to start mining on AWP" — I'll guide you through registration.
> - Already registered? Say "check my balance" or "list active subnets".
> - Need help? Say "what can I do with AWP?"

---

## Step 1: Version Check

读取本地 skill 版本：**1.1.0**

```bash
curl -s https://raw.githubusercontent.com/awp-core/awp-skill/main/skills/awp/SKILL.md | head -3 | grep version
```

假设远程版本也是 1.1.0，版本一致，静默继续。

---

## Step 2: Wallet Setup

你需要 AWP Wallet skill 来完成注册。

**安装 AWP Wallet skill（如尚未安装）：**

```bash
openclaw skill install https://raw.githubusercontent.com/awpix/agent-wallet/refs/heads/main/SKILL.md
```

**初始化 + 解锁钱包：**

```bash
awp-wallet init
awp-wallet unlock --scope full --chain bsc
# → {"token": "T_SESSION_TOKEN", "address": "0xYourWalletAddr", ...}
```

记录你的 session token（后续命令中用 `{T}` 表示）和钱包地址。

---

## Step 3: Check Registration Status

先检查地址是否已注册：

```bash
curl -s http://ec2-100-31-107-3.compute-1.amazonaws.com/address/0xYourWalletAddr/check
```

预期返回（新用户）：

```json
{
  "isRegisteredUser": false,
  "isRegisteredAgent": false,
  "ownerAddress": "",
  "isManager": false
}
```

确认：未注册用户，需要走 S1 注册流程。

---

## Step 4: Gas Routing — 检查 BNB 余额

```bash
awp-wallet balance --token {T} --chain bsc
```

结果：**BNB 余额为 0**。

判定路由：**No BNB → Gasless Relay 路径**。通过 EIP-712 签名 + Relay API 完成注册和绑定，无需 gas。

> 限制提示：Gasless relay 每个 IP 每 4 小时最多 5 次请求（所有 relay 端点共享额度）。

---

## Step 5: Quick Start 选择 — Principal (自管理模式)

你说想自己挖矿，所以选择 **Principal (Master mode)**：自持资金、自领奖励。流程是 bind(myAddress)，一步完成注册 + 绑定。

---

## Step 6: 获取合约地址和 Nonce

```bash
# 获取所有协议合约地址
REGISTRY=$(curl -s http://ec2-100-31-107-3.compute-1.amazonaws.com/registry)
ROOT_NET=$(echo $REGISTRY | jq -r '.rootNet')
AWP_TOKEN=$(echo $REGISTRY | jq -r '.awpToken')
STAKE_NFT=$(echo $REGISTRY | jq -r '.stakeNFT')
SUBNET_NFT=$(echo $REGISTRY | jq -r '.subnetNFT')

# 获取钱包地址
WALLET_ADDR=$(awp-wallet status --token {T} | jq -r '.address')

# 获取 EIP-712 签名所需的 nonce
NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
```

---

## Step 7: Gasless Register — EIP-712 签名 + Relay

### 7a. 设置 deadline

```bash
DEADLINE=$(date -d '+1 hour' +%s)
```

### 7b. 签署 EIP-712 Register 消息

完整的 EIP-712 JSON 如下：

```bash
awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Register": [
      {"name": "user", "type": "address"},
      {"name": "deadline", "type": "uint256"},
      {"name": "nonce", "type": "uint256"}
    ]
  },
  "primaryType": "Register",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": 56,
    "verifyingContract": "'$ROOT_NET'"
  },
  "message": {
    "user": "'$WALLET_ADDR'",
    "deadline": '$DEADLINE',
    "nonce": '$NONCE'
  }
}'
```

预期返回：

```json
{"signature": "0x...130 hex chars", "v": 28, "r": "0x...", "s": "0x..."}
```

### 7c. 提交 Register 到 Relay

```bash
curl -X POST http://ec2-100-31-107-3.compute-1.amazonaws.com/relay/register \
  -H "Content-Type: application/json" \
  -d '{"user": "'$WALLET_ADDR'", "deadline": '$DEADLINE', "signature": "0x...签名结果..."}'
```

预期返回：

```json
{"txHash": "0xabc123..."}
```

在 BSCScan 上查看交易：`https://bscscan.com/tx/0xabc123...`

> 注册成功！你现在是 AWP RootNet 的已注册用户了。

---

## Step 8: Gasless Bind — 绑定自己为 Agent (Principal 模式)

作为 Principal 自绑定：`bind(myAddress)`，即 agent = 自己，principal = 自己。

### 8a. 签署 EIP-712 Bind 消息

需要重新获取 nonce（register 消费了一次）：

```bash
NONCE=$(cast call $ROOT_NET "nonces(address)" $WALLET_ADDR --rpc-url https://bsc-dataseed.binance.org | cast --to-dec)
PRINCIPAL=$WALLET_ADDR
DEADLINE=$(date -d '+1 hour' +%s)
```

完整的 EIP-712 JSON 如下：

```bash
awp-wallet sign-typed-data --token {T} --data '{
  "types": {
    "EIP712Domain": [
      {"name": "name", "type": "string"},
      {"name": "version", "type": "string"},
      {"name": "chainId", "type": "uint256"},
      {"name": "verifyingContract", "type": "address"}
    ],
    "Bind": [
      {"name": "agent", "type": "address"},
      {"name": "principal", "type": "address"},
      {"name": "deadline", "type": "uint256"},
      {"name": "nonce", "type": "uint256"}
    ]
  },
  "primaryType": "Bind",
  "domain": {
    "name": "AWPRootNet",
    "version": "1",
    "chainId": 56,
    "verifyingContract": "'$ROOT_NET'"
  },
  "message": {
    "agent": "'$WALLET_ADDR'",
    "principal": "'$WALLET_ADDR'",
    "deadline": '$DEADLINE',
    "nonce": '$NONCE'
  }
}'
```

预期返回：

```json
{"signature": "0x...130 hex chars", "v": 27, "r": "0x...", "s": "0x..."}
```

### 8b. 提交 Bind 到 Relay

```bash
curl -X POST http://ec2-100-31-107-3.compute-1.amazonaws.com/relay/bind \
  -H "Content-Type: application/json" \
  -d '{"agent": "'$WALLET_ADDR'", "principal": "'$WALLET_ADDR'", "deadline": '$DEADLINE', "signature": "0x...签名结果..."}'
```

预期返回：

```json
{"txHash": "0xdef456..."}
```

在 BSCScan 上查看交易：`https://bscscan.com/tx/0xdef456...`

> 绑定成功！你现在同时是 Principal 和 Agent，可以自管理挖矿了。

---

## Step 9: 验证注册状态

```bash
curl -s http://ec2-100-31-107-3.compute-1.amazonaws.com/address/$WALLET_ADDR/check
```

预期返回：

```json
{
  "isRegisteredUser": true,
  "isRegisteredAgent": true,
  "ownerAddress": "0xYourWalletAddr",
  "isManager": false
}
```

---

## Step 10: Q5 — 浏览活跃 Subnet

注册完成后，下一步是找到有 skills 的活跃 subnet 加入。

```bash
curl -s "http://ec2-100-31-107-3.compute-1.amazonaws.com/subnets?status=Active&page=1&limit=20"
```

预期返回（示例）：

| ID | Name | Status | Owner | has skillsURI |
|----|------|--------|-------|---------------|
| 1 | EVO Alpha | Active | 0x1234...abcd | Yes |
| 3 | DeepMind Subnet | Active | 0x5678...ef01 | Yes |
| 5 | Research Hub | Active | 0x9abc...2345 | No |

> 带有 skillsURI 的 subnet 已发布了 skill 文件，你的 agent 可以安装它来学习该 subnet 的任务执行方式。选择一个感兴趣的 subnet（比如 ID=1）继续。

---

## Step 11: Q6 — 获取并安装 Subnet Skill

### 11a. 查询 Subnet 的 skillsURI

```bash
curl -s http://ec2-100-31-107-3.compute-1.amazonaws.com/subnets/1/skills
```

预期返回：

```json
{"subnetId": 1, "skillsURI": "ipfs://QmSkillsFile..."}
```

### 11b. 获取 SKILL.md 内容

从 skillsURI 下载 SKILL.md 文件，查看 frontmatter 确认 skill 信息（名称、描述、依赖）。

### 11c. 安装 Subnet Skill

```bash
mkdir -p skills/awp-subnet-1
# 下载 SKILL.md 到 skills/awp-subnet-1/SKILL.md
# 重启 session 以加载新 skill
```

> 安装完成后，subnet skill 会教你的 agent 如何与该 subnet 的 coordinator 交互（领取任务、提交结果、获得奖励）。

---

## 接下来的完整挖矿路径

注册和绑定已经用 gasless 方式完成了。但后续的 **质押 (S2)** 和 **分配 (S3)** 操作 **必须有 BNB gas**，gasless relay 不覆盖这两步。你需要：

1. **获取 BNB**：向你的钱包 `0xYourWalletAddr` 转入少量 BNB（约 0.01 BNB 足够几笔交易的 gas）
2. **获取 AWP 代币**：通过交易所或 DEX 购入 AWP
3. **S2 — 质押 AWP**：
   - `awp-wallet approve` → StakeNFT
   - `StakeNFT.deposit(amount, lockDuration)` → 获得 StakeNFT position
   - lockDuration 以秒为单位（例如 26 周 = 15,724,800 秒）
4. **S3 — 分配到 Agent + Subnet**：
   - `RootNet.allocate(agentAddr, subnetId, amount)`
   - agentAddr = 你自己的地址，subnetId = 你选择的 subnet
5. **使用 subnet skill 执行任务**，赚取 AWP emission 奖励

---

## 摘要

| 步骤 | 操作 | 需要 Gas? | 状态 |
|------|------|-----------|------|
| Wallet Setup | awp-wallet init + unlock | No | Done |
| S1 Register | EIP-712 签名 → POST /relay/register | No (Gasless) | Done |
| S1 Bind | EIP-712 签名 → POST /relay/bind | No (Gasless) | Done |
| Q5 List Subnets | GET /subnets?status=Active | No | Done |
| Q6 Install Skill | GET /subnets/{id}/skills → 安装 SKILL.md | No | Done |
| S2 Deposit AWP | approve + deposit | **Yes (需要 BNB)** | 待办 |
| S3 Allocate | allocate(agent, subnet, amount) | **Yes (需要 BNB)** | 待办 |
| 开始挖矿 | 使用 subnet skill 与 coordinator 交互 | No | 待办 |
