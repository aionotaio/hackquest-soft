import os
import sys
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.utils import Utils
from src.config import Config
from src.models import Quest, Base, Network


if getattr(sys, "frozen", False):
    root_dir = Path(sys.executable).parent.parent.absolute()
else:
    root_dir = Path(__file__).parent.parent.absolute()


INIT_QUESTS = [
    Quest(name='Register a HackQuest Account', id='25447f69-2117-4790-aeee-cfe876642ade'),
    Quest(name='Enroll in a learning track', id='1d02280a-da08-43b6-9c85-5a1447a36169'),
    Quest(name='Finish 20 quests', id='1426107e-3031-4d2c-956b-1995d0017739'),
    # Quest(name='Register Hackathon', id='4aca25ba-fec5-41c5-a321-c66aff7c12d6'), # TODO 

    Quest(name='Daily Streak', id='e3fab3d3-e986-4076-9551-b265edaf454d'),
    Quest(name='Daily Course Complete', id='446e3fe3-b674-47e4-9682-4d700d418495'),
    # Quest(name='Daily Project Like', id='1eb56412-45fc-4127-aefa-5c7bd73dc974'), # TODO
    # Quest(name='Daily Treasure', id='d7c751fc-4b43-4a4d-8d2f-c0dc71833a55'), # TODO

    # Quest(name='Create project', id='0ff25a4d-f24d-46e3-a238-0ae753f4a556'), # TODO
    Quest(name='Got 2000 coins', id='57f0eacd-d6e9-4a66-aad3-9335837dd9cc'),
    Quest(name='Quest terminator', id='90b00587-ecad-4169-a809-459be2b4f2b2'),
    # Quest(name='Join Hackathon', id='a9619898-b1a0-4520-a7e8-6e561970fe30') # TODO
]


LOGS_DIR = os.path.join(root_dir, 'logs')
LOGS_PATH = os.path.join(LOGS_DIR, 'logs.txt')

DATA_DIR = os.path.join(root_dir, 'data')
ABI_PATH = os.path.join(DATA_DIR, 'abi.json')
DB_PATH = os.path.join(DATA_DIR, 'db.sqlite3')

FILES_DIR = os.path.join(root_dir, 'files')

PRIVATE_KEYS_PATH = os.path.join(FILES_DIR, 'private_keys.txt')
PROXIES_PATH = os.path.join(FILES_DIR, 'proxies.txt')

CONFIG_PATH = os.path.join(root_dir, 'config.yaml')


P = TypeVar("P", bound=BaseModel)
A = TypeVar("A", bound=Base)


config_dict = Utils.read_yaml(CONFIG_PATH)
config = Config.model_validate(config_dict)


SEPOLIA_ETH = Network(
    name='Ethereum Sepolia',
    rpc=str(config.general.sepolia_rpc),
    chain_id=11155111,
    coin_symbol='ETH',
    explorer='https://sepolia.etherscan.io'
)

# EDU_CHAIN = Network(
#     name='EDU Chain',
#     rpc='https://rpc.edu-chain.raas.gelato.cloud',
#     chain_id=41923,
#     coin_symbol='EDU',
#     explorer='https://educhain.blockscout.com'
# )


DB_URL: str = f"sqlite:///{DB_PATH}"
