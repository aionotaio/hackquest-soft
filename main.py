import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from better_proxy import Proxy
from src.menu import Menu

from src.utils import Utils
from src.facade import Facade
from src.vars import LOGS_PATH, SEPOLIA_ETH, PRIVATE_KEYS_PATH, PROXIES_PATH, config, INIT_QUESTS


logger.remove()
logger.add(sink=sys.stdout, level="INFO", format="\u001b[38;5;30m{time:YYYY-MM-DD HH:mm:ss.SSS}\u001b[0m | <level>{level: <8}</level> | \u001b[38;5;78m{name}:{function}:{line}\u001b[0m - <level>{message}</level>")
logger.add(sink=LOGS_PATH, level="DEBUG", rotation="5 MB")


def process_account(account_index: int, private_key: str, proxies: list[Proxy] | None = None):
    facade = Facade(account_index, private_key, SEPOLIA_ETH, proxies[account_index % len(proxies)] if proxies else None)

    referral_code = config.referral.ref_code
    if config.referral.invite_by_next_ref_code:
        last_user = facade.db.read_last_user()
        if last_user and getattr(last_user, "invite_code", None):
            referral_code = last_user.invite_code
    
    user = facade.login(referral_code)
    if not user:
        return
    
    ecosystem_info = facade.get_ecosystem_info()
    if not ecosystem_info:
        return
        
    ACTIONS_DICT = {
        'ethereum_ecosystem': (facade.complete_ethereum_ecosystem, (user, ecosystem_info)),
        'mint_certificates': (facade.mint_certificates, (ecosystem_info,)),
        'manage_quack': (facade.manage_quack, (user, config.general.humanize)),
        'complete_quests': (facade.complete_quests, (user, INIT_QUESTS))
    }
    
    action_keys = list(ACTIONS_DICT.keys())

    for key in action_keys:
        if key in config.actions:
            logger.debug(f'{account_index+1} | {key}')
            func, args = ACTIONS_DICT[key]
            func(*args)

def main():
    private_keys = Utils.read_strings_from_file(PRIVATE_KEYS_PATH)
    proxies = Proxy.from_file(PROXIES_PATH)

    optimal_threads = min(len(private_keys), config.general.threads)

    account_indices = list(range(len(private_keys)))
    
    if not Utils.validate_data(private_keys):
        return
    
    if not Menu.open_menu(len(private_keys), len(proxies)):
        return
    
    with ThreadPoolExecutor(max_workers=optimal_threads) as executor:
        futures = []
        for account_index in account_indices:
            futures.append(
                executor.submit(
                    process_account,
                    account_index,
                    private_keys[account_index],
                    proxies
                )
            )
            time.sleep(random.uniform(config.delays.delay_between_accs.min, config.delays.delay_between_accs.max))

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as err:
                logger.error(f'Error in thread execution: {err}')     
    return 
 

if __name__ == '__main__':
    main()
