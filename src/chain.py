import json
import base64
from web3 import Web3
from eth_account.messages import encode_defunct

def wei_to_miota(wei):
    return wei / 1e18

def miota_to_wei(wei):
    return int(wei * 1e18)

def iota_to_wei(wei):
    return int(wei * 1e12)

def fix_price(p, chunks):
    # price divisible by chunks length and chunk price divivisble by distributor fee (10%)
    return p - (p % (chunks * 10))

class Chain:
    def __init__(self):
        # Connect to chain
        try:
            self.get_chain_info()
        except:
            print('You are not connected to any chain')
            self.set_chain_info()
        print(f'\nConnected to chain\n')
        # Create account in the contract
        while not self.get_user_info()[0]:
            print(f'Deposit to your chain wallet: {self.account.address}')
            print(self.get_balances())
            print("\nChoose an action:\n\t(c) Create account\n\t( ) Reload\n")
            if input('> ') == 'c':
                try:
                    self.create_contract_account()
                except Exception as e:
                    print(f'\n{e}')
    
    def get_chain_info(self):
        with open('config.json', 'r') as f:
            config = json.load(f)
            # Connect to the local Ethereum node
            self.w3 = Web3(Web3.HTTPProvider(config["url"]))
            self.set_contract(config["contract"])
            # Generate wallet account
            self.account = self.w3.eth.account.from_key(base64.b64decode(config["key"]))

    def set_chain_info(self):
        # Connect to the local Ethereum node
        self.w3 = Web3(Web3.HTTPProvider(''))
        while not self.w3.is_connected():
            provider = input('JSON-RPC URL: ')
            self.w3 = Web3(Web3.HTTPProvider(provider))
        self.set_contract(input('Platform address: '))
        # Generate wallet account
        self.account = self.w3.eth.account.create()
        # Save user in config file
        with open('config.json', 'w') as f:
            f.write(json.dumps({
                "url": provider,
                "contract": self.contract.address,
                "key": base64.b64encode(self.account.key).decode('ascii')
            }))

    def set_contract(self, address):
        with open('contract/Platform.abi', 'r') as f:
            self.contract = self.w3.eth.contract(address=address, abi=json.load(f))

    def get_user_info(self, address=None):
        if address is None:
            address = self.account.address
        return self.contract.functions.users(address).call()

    def create_contract_account(self):
        name = input('\nName: ')
        desc = input('Description: ')
        tx = self.contract.functions.create_user(name, desc).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1),
        })
        return self.sign_and_send(tx)

    def deposit(self, amount):
        tx = self.contract.functions.deposit().build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": 3000000,
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1),
            "value": miota_to_wei(amount)
        })
        return self.sign_and_send(tx)

    def upload(self, song):
        tx = self.contract.functions.upload_song(
            song.name,
            fix_price(miota_to_wei(song.price), len(song.chunks)),
            song.length,
            int(song.duration),
            song.chunks
        ).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        if not self.sign_and_send(tx).status:
            return None
        return self.gen_song_id(song.name)

    def gen_song_id(self, name):
        return '0x'+self.contract.functions.gen_song_id(name, self.account.address).call().hex()

    def distribute(self, id):
        tx = self.contract.functions.distribute(id).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        return self.sign_and_send(tx)

    def undistribute_all(self, ids):
        print('\n')
        for id in ids:
            if self.is_distributing(id) and self.undistribute(id).status:
                print(f'Stopped serving {id}')

    def undistribute(self, id):
        tx = self.contract.functions.undistribute(id).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        return self.sign_and_send(tx)

    def edit_url(self, url):
        tx = self.contract.functions.edit_url(url).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        return self.sign_and_send(tx)

    def get_song_list(self):
        i, lst = 0, []
        while True:
            try:
                id = '0x'+self.contract.functions.song_list(i).call().hex()
                info = self.get_valid_song_info(id)
                if info is not None:
                    name,auth,p = info
                    lst.append((id,name,auth,wei_to_miota(p)))
                i += 1
            except:
                break
        return lst

    def get_valid_song_info(self, id):
        _,valid,addr,name,p,_,_ = self.contract.functions.songs(id).call()
        if valid or addr == self.account.address:
            _,auth,_,_,_,_ = self.contract.functions.users(addr).call()
            price = self.get_real_price(p)
            return name,auth,price
        return None

    def get_real_price(self, p):
        return p + self.contract.functions.compute_distributor_fee(p).call()

    def get_song_metadata(self, id):
        _,_,_,_,_,length,duration = self.contract.functions.songs(id).call()
        chunk_len = self.contract.functions.chunks_length(id).call()
        return length, duration, chunk_len
    
    def is_distributing(self, id, address=None):
        if address is None:
            address = self.account.address
        return self.contract.functions.is_distributing(id, address).call()

    def create_session(self, song_id, distributor=None):
        if distributor is None:
            distributor = self.get_rand_distributor(song_id)
        tx = self.contract.functions.create_session(song_id, distributor).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        if not self.sign_and_send(tx).status:
            return None, distributor
        return self.gen_session_id(self.account.address, distributor, song_id), distributor

    def get_rand_distributor(self, id):
        return self.contract.functions.get_rand_distributor(id).call()
        
    def gen_session_id(self, sender, distributor, song_id):
        return '0x'+self.contract.functions.gen_session_id(sender, distributor, song_id).call().hex()

    def get_chunk(self, id, index):
        tx = self.contract.functions.get_chunk(id, index).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        return self.sign_and_send(tx)

    def check_chunk(self, id, index, chunk):

        return self.contract.functions.check_chunk(id, index, chunk).call()
    
    def is_chunk_paid(self, id, index):
        return self.contract.functions.is_chunk_paid(id, index).call()
    
    def get_session_info(self, id):
        active,addr,dist,song_id,p,b = self.contract.functions.sessions(id).call()
        return active,addr,dist,'0x'+song_id.hex(),wei_to_miota(p),wei_to_miota(b)

    def close_session(self, id):
        tx = self.contract.functions.close_session(id).build_transaction({
            "nonce": self.w3.eth.get_transaction_count(self.account.address),
            "gas": iota_to_wei(1),
            "chainId": self.w3.eth.chain_id,
            "gasPrice": iota_to_wei(1)
        })
        return self.sign_and_send(tx)

    def get_balances(self):
        chain = wei_to_miota(self.w3.eth.get_balance(self.account.address))
        try:
            contract = self.get_contract_balance()
        except:
            contract = 0
        return f'\nBalance sheet:\n\tOn-Chain: {chain} Mi\n\tOn-Contract: {contract} Mi'

    def sign_message(self, msg):
        return self.w3.eth.account.sign_message(encode_defunct(text=msg), self.account.key).signature.hex()

    def verify_message(self, msg, sig, address):
        return self.w3.eth.account.recover_message(encode_defunct(text=msg), signature=sig) == address

    def get_contract_balance(self):
        return wei_to_miota(self.get_user_info()[4])

    def sign_and_send(self, tx):
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)