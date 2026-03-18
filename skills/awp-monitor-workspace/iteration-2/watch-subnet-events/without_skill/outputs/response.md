# 监控 Subnet 相关事件

我可以帮你设置 subnet 相关事件的实时监控。不过我需要先说明，我目前没有 AWP RootNet 协议的专用工具或技能，所以我只能提供一个通用的实现思路。

## 大致方案

你需要监控的事件类型大概包括：
- **新 Subnet 注册**（类似 `SubnetRegistered` 事件）
- **SkillsURI 更新**（类似 `MetadataUpdated` 事件）
- **MinStake 变更**（类似参数更新事件）

### 方法 1：WebSocket 订阅（如果协议提供）

如果 AWP 提供 WebSocket 端点，你可以连接并订阅 subnet 相关事件：

```javascript
const ws = new WebSocket('wss://api.awp.network/ws/live'); // 地址需确认

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    // 具体的订阅参数需要参考 AWP 的 API 文档
    events: ['SubnetRegistered', 'MetadataUpdated', 'SubnetParamsUpdated']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('收到事件:', data);
};
```

> **注意**：以上代码是基于通用 WebSocket 模式的推测，实际的端点地址、订阅格式和事件名称需要查阅 AWP 官方文档确认。

### 方法 2：链上事件监听

如果你有合约地址和 ABI，可以用 viem 或 ethers.js 监听链上事件：

```javascript
import { createPublicClient, webSocket } from 'viem';
import { bsc } from 'viem/chains';

const client = createPublicClient({
  chain: bsc,
  transport: webSocket('wss://bsc-ws-node.nariox.org') // 需要可靠的 BSC WSS 节点
});

// 监听合约事件 — 需要实际的合约地址和 ABI
client.watchContractEvent({
  address: '0x...', // RootNet 或 SubnetManager 合约地址
  abi: [...],       // 合约 ABI
  eventName: 'SubnetRegistered',
  onLogs: (logs) => {
    for (const log of logs) {
      console.log('新 Subnet 注册:', log.args);
    }
  }
});
```

### 方法 3：轮询 REST API

最简单但实时性较差的方案：

```javascript
async function pollSubnetEvents() {
  while (true) {
    try {
      const response = await fetch('https://api.awp.network/subnets?status=Active');
      const data = await response.json();
      // 与上次结果比较，找出变化
      // ...
    } catch (err) {
      console.error('轮询失败:', err);
    }
    await new Promise(r => setTimeout(r, 60000)); // 每 60 秒轮询一次
  }
}
```

## 我无法确认的关键信息

由于我没有 AWP 协议的专用技能文档，以下信息我无法确定：

1. **WebSocket 端点的确切地址和订阅格式**
2. **事件的具体字段结构**（比如 `SubnetRegistered` 事件到底包含哪些字段）
3. **合约地址**（RootNet、SubnetManager 等合约在 BSC 上的部署地址）
4. **是否有预设的事件过滤器**（比如能否只订阅 subnet 类别的事件）
5. **SkillsURI 更新是通过哪个具体事件触发的**
6. **MinStake 变更对应的具体事件名称**
7. **事件中金额字段的精度**（是否是 18 位小数的 wei 值）

## 建议

如果你能提供以下任一信息，我可以给出更精确的实现：
- AWP 的 API 文档链接
- 合约地址和 ABI
- WebSocket 端点的具体规格

或者，如果有可用的 AWP 专用技能/插件，安装后我可以直接帮你配置监控。
