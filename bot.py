# 导入 Web3 库
from web3 import Web3
from eth_account import Account
import time
import sys
import os
import random
import threading  # 引入多线程模块

# 数据桥接配置
from data_bridge import data_bridge
from keys_and_addresses import private_keys, labels
from network_config import networks

# 全局变量和锁
successful_txs = 0
successful_txs_lock = threading.Lock()
print_lock = threading.Lock()
running = True  # 控制线程运行

# 文本居中函数
def center_text(text):
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 80
    lines = text.splitlines()
    centered_lines = [line.center(terminal_width) for line in lines]
    return "\n".join(centered_lines)

# 清理终端函数
def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

description = """
自动桥接机器人  https://unlock3d.t3rn.io/rewards
"""

chain_symbols = {
    'Base': '\033[34m',
    'OP Sepolia': '\033[91m',         
}

green_color = '\033[92m'
reset_color = '\033[0m'
menu_color = '\033[95m'

explorer_urls = {
    'Base': 'https://sepolia.base.org', 
    'OP Sepolia': 'https://sepolia-optimism.etherscan.io/tx/',
    'b2n': 'https://b2n.explorer.caldera.xyz/tx/'
}

class AddressState:
    def __init__(self, private_keys, initial_network='Base'):
        self.address_states = {}
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
        current = self.address_states[address]['current_network']
        alternate = self.address_states[address]['alternate_network']
        self.address_states[address]['current_network'] = alternate
        self.address_states[address]['alternate_network'] = current
        return alternate

def get_b2n_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

def check_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

def send_bridge_transaction(web3, account, my_address, data, network_name):
    nonce = web3.eth.get_transaction_count(my_address, 'pending')
    value_in_ether = 1.0
    value_in_wei = web3.to_wei(value_in_ether, 'ether')

    try:
        gas_estimate = web3.eth.estimate_gas({
            'to': networks[network_name]['contract_address'],
            'from': my_address,
            'data': data,
            'value': value_in_wei
        })
        gas_limit = gas_estimate + 50000
    except Exception as e:
        with print_lock:
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
        with print_lock:
            print(f"签名交易错误: {e}")
        return None

    try:
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        balance = web3.eth.get_balance(my_address)
        formatted_balance = web3.from_wei(balance, 'ether')

        explorer_link = f"{explorer_urls[network_name]}{web3.to_hex(tx_hash)}"

        with print_lock:
            print(f"{green_color}📤 发送地址: {account.address}")
            print(f"⛽ 使用Gas: {tx_receipt['gasUsed']}")
            print(f"🗳️  区块号: {tx_receipt['blockNumber']}")
            print(f"💰 ETH余额: {formatted_balance} ETH")
            b2n_balance = get_b2n_balance(Web3(Web3.HTTPProvider('https://b2n.rpc.caldera.xyz/http')), my_address)
            print(f"🔵 b2n余额: {b2n_balance} b2n")
            print(f"🔗 区块浏览器链接: {explorer_link}\n{reset_color}")

        return web3.to_hex(tx_hash), value_in_ether
    except Exception as e:
        with print_lock:
            print(f"发送交易错误: {e}")
        return None

def replace_middle_address(original_data, current_address):
    current_address_clean = current_address.lower().replace("0x", "")
    start = 162
    end = 202
    if len(current_address_clean) != 40:
        raise ValueError(f"地址长度应为40字符，实际 {len(current_address_clean)}")
    modified_data = original_data[:start] + current_address_clean + original_data[end:]
    return modified_data

def process_single_address_transaction(web3, account, network_name, bridge):
    my_address = account.address
    original_data = data_bridge.get(bridge)
    if not original_data:
        with print_lock:
            print(f"桥接 {bridge} 数据不可用!")
        return False, None

    try:
        modified_data = replace_middle_address(original_data, my_address)
    except ValueError as e:
        with print_lock:
            print(f"地址格式错误: {e}")
        return False, None

    result = send_bridge_transaction(web3, account, my_address, modified_data, network_name)
    if result is not None:
        return True, result[1]
    return False, None

def process_address_loop(private_key, label, index, address_state):
    account = Account.from_key(private_key)
    my_address = account.address
    while running:
        try:
            current_network = address_state.get_network(my_address)
            alternate_network = address_state.address_states[my_address]['alternate_network']

            try:
                web3 = create_web3_connection(current_network)
            except ConnectionError as e:
                with print_lock:
                    print(f"❌ {e}")
                time.sleep(3)
                continue

            balance = check_balance(web3, my_address)
            if balance < 1.01:
                with print_lock:
                    print(f"{chain_symbols[current_network]}⚠️ {my_address} 在 {current_network} 余额不足 1.01 ETH，尝试切换到 {alternate_network}{reset_color}")
                
                try:
                    alt_web3 = create_web3_connection(alternate_network)
                    alt_balance = check_balance(alt_web3, my_address)
                except Exception as e:
                    with print_lock:
                        print(f"备用网络检查失败: {e}")
                    time.sleep(3)
                    continue
                
                if alt_balance >= 1.01:
                    new_network = address_state.switch_network(my_address)
                    current_network = new_network
                    web3 = alt_web3
                    with print_lock:
                        print(f"🔄 已切换到 {new_network}，余额充足")
                else:
                    with print_lock:
                        print(f"❌ 两个网络余额均不足，跳过地址 {my_address}")
                    time.sleep(3)
                    continue

            bridge_name = "Base - OP Sepolia" if current_network == 'Base' else "OP - Base"
            success, value_sent = process_single_address_transaction(web3, account, current_network, bridge_name)
            
            if success:
                with successful_txs_lock:
                    global successful_txs
                    successful_txs += 1
                    current_success = successful_txs
                with print_lock:
                    symbol_color = chain_symbols.get(current_network, reset_color)
                    print(f"{symbol_color}🚀 成功交易总数: {current_success} | 桥接: {bridge_name} | 金额: {value_sent:.5f} ETH ✅{reset_color}\n")

            wait_time = random.uniform(1, 2)
            time.sleep(wait_time)
        
        except Exception as e:
            with print_lock:
                print(f"处理地址 {my_address} 时发生异常: {str(e)}")
            time.sleep(1)

def create_web3_connection(network_name):
    max_retries = 3
    rpc_urls = networks[network_name]['rpc_urls']
    for _ in range(max_retries):
        selected_rpc = random.choice(rpc_urls)
        web3 = Web3(Web3.HTTPProvider(selected_rpc))
        if web3.is_connected():
            return web3
        time.sleep(0.5)
    raise ConnectionError(f"无法连接到 {network_name} 网络")

def main():
    print("\033[92m" + center_text(description) + "\033[0m")
    print("\n\n")

    address_state = AddressState(private_keys)
    threads = []

    for i, priv_key in enumerate(private_keys):
        label = labels[i] if i < len(labels) else f"地址 {i+1}"
        thread = threading.Thread(
            target=process_address_loop,
            args=(priv_key, label, i+1, address_state),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        global running
        running = False
        print("\n正在停止所有线程...")

if __name__ == "__main__":
    main()
