# 导入 Web3 库
from web3 import Web3
from eth_account import Account
import time
import sys
import os
import random  # 引入随机模块

# 数据桥接配置
from data_bridge import data_bridge
from keys_and_addresses import private_keys, labels
from network_config import networks

# 文本居中函数
def center_text(text):
    terminal_width = os.get_terminal_size().columns
    lines = text.splitlines()
    centered_lines = [line.center(terminal_width) for line in lines]
    return "\n".join(centered_lines)

# 清理终端函数
def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

description = """
自动桥接机器人  https://unlock3d.t3rn.io/rewards
"""

# 每个链的颜色和符号
chain_symbols = {
    'Base': '\033[34m',  # 更新为 Base 链的颜色
    'OP Sepolia': '\033[91m',         
}

# 颜色定义
green_color = '\033[92m'
reset_color = '\033[0m'
menu_color = '\033[95m'  # 菜单文本颜色

# 每个网络的区块浏览器URL
explorer_urls = {
    'Base': 'https://sepolia.base.org', 
    'OP Sepolia': 'https://sepolia-optimism.etherscan.io/tx/',
    'b2n': 'https://b2n.explorer.caldera.xyz/tx/'
}

# 地址管理类
class AddressState:
    def __init__(self, private_keys, initial_network='Base'):
        self.address_states = {}
        # 初始化每个地址的链状态
        for priv_key in private_keys:
            account = Account.from_key(priv_key)
            address = account.address
            self.address_states[address] = {
                'current_network': initial_network,
                'alternate_network': 'OP Sepolia' if initial_network == 'Base' else 'Base'
            }
    
    def get_network(self, address):
        return self.address_states[address]['current_network']
    
    def switch_network(self, address):
        # 切换当前链和备用链
        current = self.address_states[address]['current_network']
        alternate = self.address_states[address]['alternate_network']
        self.address_states[address]['current_network'] = alternate
        self.address_states[address]['alternate_network'] = current
        return alternate

# 获取b2n余额的函数
def get_b2n_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

# 检查链的余额函数
def check_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

# 创建和发送交易的函数
def send_bridge_transaction(web3, account, my_address, data, network_name):
    nonce = web3.eth.get_transaction_count(my_address, 'pending')
    value_in_ether = 0.201
    value_in_wei = web3.to_wei(value_in_ether, 'ether')

    try:
        gas_estimate = web3.eth.estimate_gas({
            'to': networks[network_name]['contract_address'],
            'from': my_address,
            'data': data,
            'value': value_in_wei
        })
        gas_limit = gas_estimate + 50000  # 增加安全边际
    except Exception as e:
        print(f"估计gas错误: {e}")
        return None

    base_fee = web3.eth.get_block('latest')['baseFeePerGas']
    priority_fee = web3.to_wei(5, 'gwei')
    max_fee = base_fee + priority_fee

    transaction = {
        'nonce': nonce,
        'to': networks[network_name]['contract_address'],
        'value': value_in_wei,
        'gas': gas_limit,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': priority_fee,
        'chainId': networks[network_name]['chain_id'],
        'data': data
    }

    try:
        signed_txn = web3.eth.account.sign_transaction(transaction, account.key)
    except Exception as e:
        print(f"签名交易错误: {e}")
        return None

    try:
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # 获取最新余额
        balance = web3.eth.get_balance(my_address)
        formatted_balance = web3.from_wei(balance, 'ether')

        # 获取区块浏览器链接
        explorer_link = f"{explorer_urls[network_name]}{web3.to_hex(tx_hash)}"

        # 显示交易信息
        print(f"{green_color}📤 发送地址: {account.address}")
        print(f"⛽ 使用Gas: {tx_receipt['gasUsed']}")
        print(f"🗳️  区块号: {tx_receipt['blockNumber']}")
        print(f"💰 ETH余额: {formatted_balance} ETH")
        b2n_balance = get_b2n_balance(Web3(Web3.HTTPProvider('https://b2n.rpc.caldera.xyz/http')), my_address)
        print(f"🔵 b2n余额: {b2n_balance} b2n")
        print(f"🔗 区块浏览器链接: {explorer_link}\n{reset_color}")

        return web3.to_hex(tx_hash), value_in_ether
    except Exception as e:
        print(f"发送交易错误: {e}")
        return None, None

# 新增：多地址时自动 动态替换data结构中的地址部分
def modify_data_address(original_data, current_address, bridge_type):
    """
    动态替换 data 中的地址部分
    Args:
        original_data (str): 原始 data 字符串
        current_address (str): 当前钱包地址（带0x）
        bridge_type (str): 桥接类型（如 "Base - OP Sepolia"）
    Returns:
        str: 替换后的 data
    """
    # 获取当前地址的小写形式（不带0x）
    current_address_clean = current_address.lower().replace("0x", "")
    
    # 定义不同桥接类型的地址偏移位置（根据你的 data 结构调整）
    address_positions = {
        "Base - OP Sepolia": 322,  # 地址在 data 字符串中的起始位置（16进制字符位置）
        "OP - Base": 322
    }
    
    # 获取地址段的起始位置
    start = address_positions.get(bridge_type, 322)  # 默认322
    
    # 原始地址段（64字符 = 32字节，前24个0 + 40字符地址）
    original_address_part = original_data[start:start+64]
    
    # 新地址段（补零到64字符）
    new_address_part = "000000000000000000000000" + current_address_clean
    
    # 替换地址部分
    modified_data = original_data[:start] + new_address_part + original_data[start+64:]
    
    return modified_data

# 在特定网络上处理交易的函数
def process_network_transactions(network_name, bridges, chain_data, successful_txs):
    web3 = Web3(Web3.HTTPProvider(chain_data['rpc_url']))
    num_addresses = len(private_keys)

    # 如果无法连接，重试直到成功
    while not web3.is_connected():
        print(f"无法连接到 {network_name}，正在尝试重新连接...")
        time.sleep(5)  # 等待 5 秒后重试
        web3 = Web3(Web3.HTTPProvider(chain_data['rpc_url']))
    
    print(f"成功连接到 {network_name}")

    for bridge in bridges:
        for i, private_key in enumerate(private_keys):
            account = Account.from_key(private_key)
            my_address = account.address
            print(f"正在处理地址 {i+1}/{num_addresses}: {my_address}")

            # 动态替换 data 地址部分
            original_data = data_bridge.get(bridge)
            if not original_data:
                print(f"桥接 {bridge} 数据不可用!")
                continue

            modified_data = modify_data_address(
                original_data=original_data,
                current_address=my_address,
                bridge_type=bridge
            )

            # 发送交易
            result = send_bridge_transaction(web3, account, my_address, modified_data, network_name)
            if result:
                tx_hash, value_sent = result
                successful_txs += 1
                print(f"{chain_symbols[network_name]}🚀 成功交易总数: {successful_txs} | {labels[i]} | 桥接: {bridge} | 金额: {value_sent:.5f} ETH ✅{reset_color}\n")

            # 交易间短延时
            wait_time = random.uniform(3, 5)
            time.sleep(wait_time)

    return successful_txs

def main():
    print("\033[92m" + center_text(description) + "\033[0m")
    print("\n\n")

    successful_txs = 0
    level = 1
    address_state = AddressState(private_keys, initial_network='Base')  # 初始化地址状态

    while True:
        # 遍历每个地址并独立处理
        for i, private_key in enumerate(private_keys):
            account = Account.from_key(private_key)
            my_address = account.address
            label = labels[i]

            # 获取当前地址的网络状态
            current_network = address_state.get_network(my_address)
            alternate_network = address_state.address_states[my_address]['alternate_network']

            # 检查当前网络的余额
            web3 = Web3(Web3.HTTPProvider(networks[current_network]['rpc_url']))
            while not web3.is_connected():
                print(f"地址 {my_address} 无法连接到 {current_network}，正在尝试重新连接...")
                time.sleep(5)
                web3 = Web3(Web3.HTTPProvider(networks[current_network]['rpc_url']))

            balance = check_balance(web3, my_address)
            if balance < 0.201:
                print(f"{chain_symbols[current_network]}{my_address} 在 {current_network} 余额不足 0.201 ETH，切换到 {alternate_network}{reset_color}")
                new_network = address_state.switch_network(my_address)
                current_network = new_network  # 更新当前网络

            # 处理当前链的交易
            successful_txs = process_network_transactions(
                current_network,
                ["Base - OP Sepolia"] if current_network == 'Base' else ["OP - Base"],
                networks[current_network],
                successful_txs
            )

            # 地址间延时
            wait_time = random.uniform(60, 90)
            print(f"⏳ 第{[level]}轮成功执行完成，等待 {wait_time:.2f} 秒后继续下一轮...\n")
            level = level +1
            time.sleep(wait_time)
            

if __name__ == "__main__":
    main()
