# 将 10,000 AWP 存入 StakeNFT 并分配给 Subnet 3 的 Agent

> **声明：** 我没有 AWP RootNet 协议的专用技能文件或官方文档。以下内容基于通用的 DeFi 质押协议知识和常见模式推断，**可能存在不准确之处**。在执行任何链上交易前，请务必核实官方文档。

## 概述

你希望完成两件事：
1. 将 10,000 AWP 代币存入 StakeNFT 合约，锁定 26 个 epoch
2. 将全部质押分配给 subnet 3 上的 agent `0xAbCdEf1234567890AbCdEf1234567890AbCdEf12`

## 大致步骤

### 第一步：获取合约地址

你需要知道以下合约的地址（我无法确认具体地址）：
- **AWPToken** — AWP 的 ERC-20 代币合约
- **StakeNFT** — 质押合约
- **RootNet** — 主协议合约（可能用于分配操作）

通常这类协议会提供一个 registry 或官方文档列出所有合约地址。请查阅 AWP RootNet 的官方网站或文档获取。

### 第二步：授权（Approve）

在存入代币之前，你需要先授权 StakeNFT 合约花费你的 AWP 代币：

```javascript
// 授权 StakeNFT 合约使用 10,000 AWP
// 10000 AWP = 10000 * 10^18 wei
await awpToken.approve(stakeNFTAddress, 10000n * 10n ** 18n);
```

**等待授权交易确认后再进行下一步。**

### 第三步：存入（Deposit）

调用 StakeNFT 的存入方法：

```javascript
// 存入 10,000 AWP，锁定 26 个 epoch
await stakeNFT.deposit(10000n * 10n ** 18n, 26);
```

这应该会铸造一个 StakeNFT 给你，代表你的质押头寸。记录下返回的 tokenId。

### 第四步：分配（Allocate）

将质押分配给指定 subnet 和 agent。这一步我不太确定具体的函数签名，可能的调用方式：

```javascript
// 可能需要调用 RootNet 合约的 allocate 方法
// 参数可能包括：tokenId、subnetId、agent 地址、分配数量
await rootNet.allocate(
  tokenId,           // 第二步获得的 StakeNFT tokenId
  3,                 // subnet ID
  "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12", // agent 地址
  10000n * 10n ** 18n  // 分配全部 10,000 AWP
);
```

## 重要提醒

1. **我不确定以上函数签名是否正确。** AWP RootNet 是一个特定协议，合约接口可能与我推断的不同。
2. **锁定期：** 26 个 epoch 的具体时长取决于协议的 epoch 定义（可能是天、周或其他时间单位），请确认。
3. **Gas 费：** 这些操作在 BSC（Chain ID 56）上执行，需要 BNB 支付 gas 费。
4. **分配机制：** 我不清楚 allocate 是基于 tokenId 还是基于用户地址，也不确定是否需要一次性分配全部数量或是否支持部分分配。
5. **Agent 有效性：** 建议先查询 subnet 3 上是否确实存在该 agent 地址，以免交易失败浪费 gas。

## 我无法确认的关键细节

- AWPToken、StakeNFT、RootNet 的具体合约地址
- `deposit` 和 `allocate` 的确切函数签名和参数顺序
- 是否有最小/最大质押限制
- 分配时是否需要额外的参数（如 operator 地址）
- 授权（approve）的目标地址是否一定是 StakeNFT（某些协议可能需要授权给其他合约）

**建议：** 请提供 AWP RootNet 的官方文档或合约 ABI，我可以给出更准确的操作指引。
