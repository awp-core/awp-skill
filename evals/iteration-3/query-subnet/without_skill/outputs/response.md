I'm not familiar with a protocol called "AWP RootNet" or its subnet system, so I can't look up subnet 1 directly for you. However, I can offer some general guidance:

1. **If AWP RootNet has a block explorer or dashboard**, try searching for "subnet 1" there. Many protocols on BSC have a dedicated UI where you can view subnet/network details like name, status, and staking requirements.

2. **If there's a REST API**, you might be able to query it directly. For example, if the project exposes an API, something like:
   ```bash
   curl https://<api-base-url>/subnets/1
   ```
   could return the subnet details you need.

3. **If you have the contract address**, you could try reading on-chain data using a tool like `cast` (from Foundry) or a block explorer's "Read Contract" tab. You'd need to know the specific function signature to call (e.g., something like `getSubnet(uint256)`) and the contract ABI.

4. **Check the project's documentation or GitHub** for API references or SDK usage examples that show how to fetch subnet metadata.

Could you share more context about AWP RootNet — such as a documentation link, contract address, or API URL? That would help me give you a more specific answer.
