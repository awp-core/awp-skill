# Gasless Subnet 注册：DataMiner (DM)

好的！你想要完全 gasless 地注册一个新 subnet，我来帮你走完整个流程。

> **注意：** 我对 AWP RootNet 协议的了解有限，以下流程是基于一般 DeFi 协议的 gasless 模式推理出来的，具体参数和签名格式请以官方文档为准。

---

## 前置条件

- 你需要一个连接了钱包的环境（如 MetaMask），钱包里有足够的 AWP token
- 你不需要 BNB，因为我们会使用 relay 服务来帮你提交交易
- 网络：BSC Mainnet (Chain ID: 56)

## 第一步：确认 AWP 余额

先确认你的钱包有足够的 AWP。注册 subnet 需要支付 LP 初始化成本（AWP token），具体金额取决于协议的 `initialAlphaPrice` 参数。

大致计算：
```
LP 成本 = initialAlphaPrice × 100,000,000 Alpha (初始铸造量)
```

你可以通过链上调用 `RootNet.initialAlphaPrice()` 来查询具体金额。

## 第二步：准备 Subnet 参数

```javascript
const subnetParams = {
  name: "DataMiner",
  symbol: "DM",
  metadataURI: "",                    // 可后续补充 IPFS metadata
  subnetManager: "0x0000000000000000000000000000000000000000",  // address(0) = 自动部署
  coordinatorURL: "",                 // 可后续补充
  salt: "0x0000000000000000000000000000000000000000000000000000000000000000",  // 使用默认 salt
  minStake: 100000000000000000000n    // 100 AWP = 100 × 10^18 wei
};
```

## 第三步：签署 ERC-2612 Permit（AWP 授权）

因为你没有 BNB，无法发送 `approve` 交易。好消息是 AWP token 支持 ERC-2612 permit 标准，你可以通过离线签名来授权。

```javascript
// 构造 permit 签名数据
const permitData = {
  owner: yourAddress,
  spender: ROOTNET_ADDRESS,        // 授权给 RootNet 合约
  value: lpCost,                   // LP 初始化所需的 AWP 金额
  nonce: await awpToken.nonces(yourAddress),
  deadline: Math.floor(Date.now() / 1000) + 3600  // 1 小时后过期
};

// 使用 EIP-712 签名
const permitSignature = await wallet.signTypedData(permitDomain, permitTypes, permitData);
```

## 第四步：签署 EIP-712 注册签名

```javascript
// 构造 registerSubnet 的 EIP-712 签名数据
const registerData = {
  user: yourAddress,
  name: "DataMiner",
  symbol: "DM",
  metadataURI: "",
  subnetManager: "0x0000000000000000000000000000000000000000",
  coordinatorURL: "",
  salt: "0x0000000000000000000000000000000000000000000000000000000000000000",
  minStake: 100000000000000000000n,
  deadline: Math.floor(Date.now() / 1000) + 3600,
  nonce: await rootNet.nonces(yourAddress)
};

const registerSignature = await wallet.signTypedData(registerDomain, registerTypes, registerData);
```

## 第五步：提交到 Relay 服务

将两个签名发送到 AWP 的 relay 端点：

```javascript
const response = await fetch('https://api.awp.network/api/relay/register-subnet', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user: yourAddress,
    name: "DataMiner",
    symbol: "DM",
    metadataURI: "",
    subnetManager: "0x0000000000000000000000000000000000000000",
    coordinatorURL: "",
    salt: "0x0000000000000000000000000000000000000000000000000000000000000000",
    minStake: "100000000000000000000",
    deadline: Math.floor(Date.now() / 1000) + 3600,
    permitSignature: permitSig,
    registerSignature: registerSig
  })
});

const { txHash } = await response.json();
console.log(`交易已提交: https://bscscan.com/tx/${txHash}`);
```

Relay 服务会调用 `RootNet.registerSubnetForWithPermit()`，由 relayer 支付所有 gas 费用。

## 第六步：等待交易确认并获取 Subnet ID

交易确认后，从 `SubnetRegistered` 事件中获取你的 `subnetId`。

## 第七步：设置 skillsURI

**⚠️ 这一步需要发送链上交易，但你没有 BNB...**

设置 skillsURI 需要调用 `SubnetNFT.setSkillsURI(subnetId, skillsURI)`，这是一个需要 gas 的写操作。据我所知，AWP 的 relay 服务只支持 register、bind 和 register-subnet 三种 gasless 操作，**不支持 gasless 设置 skillsURI**。

你有几个选择：

### 选项 A：先获取少量 BNB
从交易所提一点 BNB（约 0.001 BNB 就够一次交易），然后：

```javascript
await subnetNFT.setSkillsURI(subnetId, "https://dataminer.io/SKILL.md");
```

### 选项 B：请别人帮你发交易
让有 BNB 的朋友帮你调用（但需要你是 SubnetNFT 的 owner，所以这个方法行不通，除非协议支持 meta-transaction）。

### 选项 C：使用 updateMetadata
如果 `RootNet.updateMetadata()` 也接受 skillsURI 参数，可能有对应的 gasless relay。但根据我的了解，`updateMetadata` 只更新 `metadataURI` 和 `coordinatorURL`，不包含 `skillsURI`。

---

## 总结

| 步骤 | 操作 | Gas 需求 |
|------|------|----------|
| 1 | 查询 AWP 余额和 LP 成本 | 无（读操作） |
| 2 | 签署 ERC-2612 permit | 无（离线签名） |
| 3 | 签署 EIP-712 注册授权 | 无（离线签名） |
| 4 | 提交到 relay 端点 | 无（relayer 支付） |
| 5 | 设置 skillsURI | **需要 BNB** ❌ |

**结论：** Subnet 注册本身可以完全 gasless 完成，但设置 `skillsURI` 目前没有 gasless 通道，你需要少量 BNB 来完成这最后一步。建议先从交易所转入约 0.001 BNB，然后调用 `SubnetNFT.setSkillsURI(subnetId, "https://dataminer.io/SKILL.md")`。

---

**⚠️ 免责声明：** 以上流程基于我对 AWP 协议的有限了解。EIP-712 签名的具体 domain 和 types 结构、relay 端点的确切参数格式等细节，请务必参考 AWP 官方文档。签名数据的任何不匹配都会导致交易失败。
