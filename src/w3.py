from web3 import Web3
from web3.types import BlockData, TxParams, Wei, Nonce
from loguru import logger
from eth_typing import HexStr
from hexbytes import HexBytes
from eth_account.messages import encode_defunct
from eth_account.datastructures import SignedMessage
from better_proxy import Proxy

from src.utils import Utils
from src.models import Network
from src.vars import ABI_PATH


class W3:
    def __init__(self, account_index: int, private_key: str, network: Network, proxy: Proxy | None = None) -> None:
        self.account_index = account_index
        self.private_key = private_key
        self.proxy = proxy
        self.network = network

        self.w3 = Web3(Web3.HTTPProvider(endpoint_uri=self.network.rpc, request_kwargs={"proxy": self.proxy.as_url if self.proxy else None}))
        self.address = Web3.to_checksum_address(self.w3.eth.account.from_key(private_key=self.private_key).address)
    
    def get_signature(self, message: str) -> str | None:
        try:
            message_encoded = encode_defunct(text=message)

            signed_message: SignedMessage = self.w3.eth.account.sign_message(message_encoded, private_key=self.private_key)
            hex_signature: str = signed_message.signature.hex()
            if hex_signature:
                logger.debug(f'{self.account_index+1} | Got [hex_signature]: {hex_signature}')
                return hex_signature
        except Exception as e:
            logger.error(f'{self.account_index+1} | Error: {str(e)}')
            return

    def build_tx_params(
        self, 
        is_eip1559: bool, 
        to_address: str | None = None, 
        data: HexStr |  None = None, 
        value: Wei | None = None, 
        increase_gas: float = 1.25
    ) -> TxParams | None:
        try:
            tx_params: TxParams = {
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'chainId': self.w3.eth.chain_id
            }
            if to_address:
                tx_params['to'] = to_address
                logger.debug(f'{self.account_index+1} | tx_params["to"]: {tx_params["to"]}')
            if data:
                tx_params['data'] = data
                logger.debug(f'{self.account_index+1} | tx_params["data"]: {tx_params["data"]}')
            if value:
                tx_params['value'] = value
                logger.debug(f'{self.account_index+1} | tx_params["value"]: {tx_params["value"]}')
            if is_eip1559:
                last_block = self.w3.eth.get_block('latest')

                max_priority_fee = self.calculate_max_priority_fee(last_block)
                if not max_priority_fee:
                    return
                
                base_fee_per_gas = last_block.get('baseFeePerGas')
                if not base_fee_per_gas:
                    return
                
                base_fee = int(base_fee_per_gas * increase_gas)
                max_fee = base_fee + max_priority_fee

                tx_params['maxPriorityFeePerGas'] = Wei(max_priority_fee)
                tx_params['maxFeePerGas'] = Wei(max_fee)
                
                logger.debug(f'{self.account_index+1} | EIP-1559 gas params set: {tx_params["maxFeePerGas"]}')
            else:
                tx_params['gasPrice'] = self.w3.eth.gas_price

                logger.debug(f'{self.account_index+1} | Legacy gas params set: {tx_params["gasPrice"]}')
            return tx_params
        except Exception as err:
            logger.error(f'{self.account_index+1} | Error: {err}')
            return         

    def calculate_max_priority_fee(self, block: BlockData) -> int | None:
        try:
            block_number = block.get('number')
            if not block_number:
                return
            latest_block_transaction_count = self.w3.eth.get_block_transaction_count(block_number)
            max_priority_fee_per_gas_lst: list[int] = []
            
            for i in range(latest_block_transaction_count):
                try:
                    transaction = self.w3.eth.get_transaction_by_block(block_number, i)
                    if 'maxPriorityFeePerGas' in transaction:
                        max_priority_fee_per_gas_lst.append(transaction['maxPriorityFeePerGas'])
                except Exception:
                    continue

            if not max_priority_fee_per_gas_lst:
                return self.w3.eth.max_priority_fee
                
            max_priority_fee_per_gas_lst.sort()
            return max_priority_fee_per_gas_lst[len(max_priority_fee_per_gas_lst) // 2]
        except Exception as err:
            logger.error(f'{self.account_index+1} | Error: {err}')
            return

       
    def send_transaction(
            self,
            is_eip1559: bool,
            increase_gas: float = 1.25, 
            to_: str | None = None, 
            data: HexStr | None = None, 
            value: Wei | None = None, 
            tx_params: TxParams | None = None) -> HexBytes | None:
        try:
            if not tx_params:
                tx_params = self.build_tx_params(
                    is_eip1559=is_eip1559,
                    to_address=to_,
                    data=data,
                    value=value,
                    increase_gas=increase_gas)
                if not tx_params:
                    return                     
            try:
                tx_params['gas'] = int(self.w3.eth.estimate_gas(tx_params) * increase_gas)
            except Exception as err:
                if 'max fee per gas less than block base fee' in str(err):
                    if is_eip1559:
                        if 'maxFeePerGas' in tx_params:
                            if type(tx_params['maxFeePerGas']) == Wei:
                                tx_params['maxFeePerGas'] = Wei(int(tx_params['maxFeePerGas'] * increase_gas))
                            else:
                                return
                    else:
                        if 'gasPrice' in tx_params:
                            tx_params['gasPrice'] = Wei(int(tx_params['gasPrice'] * increase_gas))
                    return self.send_transaction(
                        is_eip1559=is_eip1559, 
                        increase_gas=increase_gas, 
                        tx_params=tx_params
                    )
                logger.error(f'{self.account_index+1} | Error estimating gas: {err}')
                return
            try:
                signed_tx = self.w3.eth.account.sign_transaction(tx_params, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                logger.debug(f'{self.account_index+1} | Transaction sent: {tx_hash.hex()}')
                return tx_hash
            except Exception as err:
                if 'nonce too low' in str(err) or 'replacement transaction underpriced' in str(err) or 'already known' in str(err):
                    if 'nonce' in tx_params:
                        new_nonce = Nonce(tx_params['nonce'] + 1)
                        tx_params['nonce'] = new_nonce
                        return self.send_transaction(
                            is_eip1559=is_eip1559, 
                            increase_gas=increase_gas, 
                            tx_params=tx_params
                        )
                logger.error(f'{self.account_index+1} | Error sending transaction: {err}')
                return 
        except Exception as err:
            logger.error(f'{self.account_index+1} | Error: {err}')
            return
        
    def verify_tx(self, tx_hash: HexBytes) -> bool:
        try:
            data = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=200)
            if data.get('status') == 1:
                logger.success(f'{self.account_index+1} | Successful tx: {self.network.explorer}/tx/{tx_hash.hex()}')
                return True
            else:
                logger.error(f'{self.account_index+1} | Failed tx: {self.network.explorer}/tx/{data["transactionHash"].hex()}')
                return False    
        except Exception as err:
            logger.error(f'{self.account_index+1} | Error: {err}')
            return False
        
    def mint_certificate(self, contract_address: str, username: str, certification_number: int, signature: str) -> bool:
        abi = Utils.read_json(ABI_PATH)
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)

        args = [self.address, username, str(self.w3.eth.chain_id), "", str(certification_number), "", "", bytes.fromhex(signature[2:])]

        tx_hash = self.send_transaction(is_eip1559=True, to_=contract.address, data=HexStr(contract.encode_abi("0x18e770cc", args).replace('0xcd520cc', '0x18e770cc')))
        if not tx_hash:
            return False
        
        return self.verify_tx(tx_hash)
    