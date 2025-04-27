import os, time, random, threading
from web3 import Web3
from eth_account import Account
from data_bridge import data_bridge
from keys_and_addresses import private_keys, labels
from network_config import networks

# 余额
value_in_ether = 1.0
successful_txs = 0
running = True

# 颜色定义
green_color = '\033[92m'
blue_color  = '\033[94m'
white_color = '\033[97m'
reset_color = '\033[0m'

explorer_urls = {
    'Base': 'https://sepolia.base.org', 
    'OP Sepolia': 'https://sepolia-optimism.etherscan.io/tx/',
    'b2n': 'https://b2n.explorer.caldera.xyz/tx/'
}

print_lock = threading.Lock()
txs_lock = threading.Lock()

def center_text(text):
    try: width = os.get_terminal_size().columns
    except OSError: width = 80
    return "\n".join(line.center(width) for line in text.splitlines())

def create_web3(network_name):
    for _ in range(3):
        url = random.choice(networks[network_name]['rpc_urls'])
        w3 = Web3(Web3.HTTPProvider(url))
        if w3.is_connected(): return w3
        time.sleep(random.uniform(2, 4))
    raise ConnectionError(f"连接 {network_name} 失败")

def get_balance(web3, addr):
    return web3.from_wei(web3.eth.get_balance(addr), 'ether')

def get_b2n_balance(web3, my_address):
    balance = web3.eth.get_balance(my_address)
    return web3.from_wei(balance, 'ether')

def replace_data(original_data, address):
    addr_clean = address.lower().replace("0x", "")
    return original_data[:162] + addr_clean + original_data[202:]

def send_tx(web3, account, data, net):
    my_address = account.address
    try:
        tx = {
            'nonce': web3.eth.get_transaction_count(my_address, 'pending'),
            'to': networks[net]['contract_address'],
            'value': web3.to_wei(value_in_ether, 'ether'),
            'gas': web3.eth.estimate_gas({'to': networks[net]['contract_address'], 'from': my_address, 'data': data, 'value': web3.to_wei(value_in_ether, 'ether')}) + 100000,
            'maxFeePerGas': web3.eth.get_block('latest')['baseFeePerGas'] + web3.to_wei(5, 'gwei'),
            'maxPriorityFeePerGas': web3.to_wei(5, 'gwei'),
            'chainId': networks[net]['chain_id'],
            'data': data
        }
        signed = web3.eth.account.sign_transaction(tx, account.key)
        tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # 打印成功信息
        formatted_balance = web3.from_wei(web3.eth.get_balance(my_address), 'ether')
        b2n_balance = get_b2n_balance(
            Web3(Web3.HTTPProvider('https://b2n.rpc.caldera.xyz/http')),
            my_address
        )

        with print_lock:
            print(f"{green_color}📤 发送地址: {account.address}")
            print(f"⛽ 使用Gas: {receipt['gasUsed']}")
            print(f"🗳️  区块号: {receipt['blockNumber']}")
            print(f"💰 ETH余额: {formatted_balance} ETH")
            print(f"🔵 b2n余额: {b2n_balance} b2n")
            print(f"🥳 网络: {net} | 桥接: { 'Base to OP' if net=='Base' else 'OP to Base' }{reset_color}\n")

        return True
    except Exception as e:
        with print_lock:
            print(f"{white_color}❌ 交易失败 @ {net}: {e}{reset_color}")
            time.sleep(random.uniform(1, 2))
        return False

def bridge_loop(priv_key, label):
    account = Account.from_key(priv_key)
    my_address = account.address

    while running:
        try:
            network = random.choice(['Base', 'OP Sepolia'])
            web3 = create_web3(network)

            balance = get_balance(web3, my_address)
            if balance < (value_in_ether + 0.01):
                with print_lock:
                    print(f"{blue_color}⚠️ {my_address} @ {network} 余额不足（{balance:.4f} ETH）{reset_color}")
                time.sleep(random.uniform(3, 5))
                continue

            bridge = "Base - OP Sepolia" if network == 'Base' else "OP - Base"
            raw_data = data_bridge.get(bridge)
            if not raw_data:
                with print_lock: print(f"⚠️ 桥接数据不可用：{bridge}")
                time.sleep(2); continue

            tx_data = replace_data(raw_data, my_address)
            if send_tx(web3, account, tx_data, network):
                with txs_lock:
                    global successful_txs
                    successful_txs += 1
                    print(f"\033[96m🚀 成功交易总数：{successful_txs} | {bridge} | {value_in_ether:.2f} ETH\033[0m\n")

            time.sleep(random.uniform(2, 4))
        except Exception as e:
            with print_lock:
                print(f"\033[91m处理异常：{e}\033[0m")
            time.sleep(random.uniform(2, 4))

def main():
    print("\033[92m" + center_text("自动桥接机器人  https://unlock3d.t3rn.io/rewards") + "\033[0m\n")
    for i, key in enumerate(private_keys):
        label = labels[i] if i < len(labels) else f"地址{i+1}"
        threading.Thread(target=bridge_loop, args=(key, label), daemon=True).start()

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        global running
        running = False
        print("\n停止中...")

if __name__ == "__main__":
    main()
