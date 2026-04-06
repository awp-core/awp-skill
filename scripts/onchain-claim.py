#!/usr/bin/env python3
"""On-chain claim — WorknetManager epoch rewards
claim(uint32 epoch, uint256 amount, bytes32[] proof)
Claims earned WorknetToken rewards for a given epoch using a Merkle proof.
The WorknetManager address is worknet-specific (not from the global registry).
Requires ETH for gas.
"""
import re

from awp_lib import *


def build_claim_calldata(epoch: int, amount_wei: int, proof: list[str]) -> str:
    """Build calldata for claim(uint32 epoch, uint256 amount, bytes32[] proof)
    selector = 0x5e4b62ab
    Layout: selector + pad_uint256(epoch) + pad_uint256(amount) + offset_proof + length + proof_elements
    """
    selector = "5e4b62ab"

    # epoch — 静态 uint32（ABI 编码仍占 32 字节）
    slot0 = pad_uint256(epoch)
    # amount — 静态 uint256
    slot1 = pad_uint256(amount_wei)
    # offset to proof array — 3 static slots * 32 = 96
    slot2 = pad_uint256(3 * 32)

    # proof array: length + each bytes32 element
    proof_parts: list[str] = []
    proof_parts.append(format(len(proof), "064x"))
    for p in proof:
        # 去掉 0x 前缀，已经是 64 hex 字符
        proof_parts.append(p[2:].lower())

    return "0x" + selector + slot0 + slot1 + slot2 + "".join(proof_parts)


def main() -> None:
    # ── 参数解析 ──
    parser = base_parser("Claim WorknetManager epoch rewards")
    parser.add_argument("--manager", required=True, help="WorknetManager contract address")
    parser.add_argument("--epoch", required=True, help="Epoch number (uint32)")
    parser.add_argument("--amount", required=True, help="Claim amount in human-readable tokens (18 decimals)")
    parser.add_argument("--proof", required=True,
                        help="Comma-separated Merkle proof bytes32 values (0x-prefixed)")
    args = parser.parse_args()

    # ── 验证输入 ──
    manager: str = args.manager
    validate_address(manager, "manager")

    # epoch 必须是正整数且在 uint32 范围内
    epoch_str: str = args.epoch
    if not re.match(r"^[0-9]+$", epoch_str):
        die("Invalid --epoch: must be a positive integer")
    epoch = int(epoch_str)
    if epoch <= 0 or epoch > 0xFFFFFFFF:
        die(f"Invalid --epoch: must be > 0 and <= {0xFFFFFFFF} (uint32 max)")

    amount_str: str = args.amount
    validate_positive_number(amount_str, "amount")
    amount_wei = to_wei(amount_str)

    # 解析并验证 proof
    proof_strs = [s.strip() for s in args.proof.split(",") if s.strip()]
    if not proof_strs:
        die("--proof must contain at least one bytes32 value")
    for p in proof_strs:
        validate_bytes32(p, "proof")

    # ── 预检查 ──
    wallet_addr = get_wallet_address()
    validate_address(wallet_addr, "wallet")

    step("claim",
         manager=manager,
         epoch=epoch,
         amount=f"{amount_str} tokens",
         proofLength=len(proof_strs))

    # ── 构建 calldata 并发送 ──
    calldata = build_claim_calldata(epoch, amount_wei, proof_strs)
    result = wallet_send(args.token, manager, calldata)
    print(result)


if __name__ == "__main__":
    main()
