# HackQuest Soft

## About
- Register on hackquest.io
- Complete learning track of Ethereum Developer and claim certificates
- Mint certificates
- Complete quests
- Create and feed Quack
- Save stats in SQLite

## Used tech stack
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![web3.py](https://img.shields.io/badge/web3.py-3C3C3D?style=for-the-badge&logo=ethereum&logoColor=white)

### Follow: https://t.me/touchingcode

## Settings
- `files/proxies.txt` - HTTP proxies. 1 line = 1 proxy in format login:pass@ip:port (**Not required, but recommended for a large number of accounts**)
- `files/private_keys.txt` - private keys (1 line = 1 private key)

## config.yaml
```yaml
general:
    threads: int                                                        # Threads
    retry_attempts: int                                                 # Retry attempts
    sepolia_rpc: http_url                                               # Ethereum Sepolia RPC URL
    humanize: bool                                                      # More human-like interactions (takes more time especially on the Quack feeding)

delays:
    delay_between_tasks:                                                # Delay between tasks in seconds
        min: int
        max: int

    delay_between_accs:                                                 # Delay between accounts in seconds
        min: int
        max: int

    delay_between_retries:                                              # Delay between retry attempts in seconds
        min: int
        max: int

referral:
    invite_by_next_ref_code: bool                                       # Invite all accounts by referral code of the previous account (if this param is enabled, then you should check if below param is disabled)
    invite_by_certain_ref_code: bool                                    # Invite all accounts by below referral code (if this param is enabled, then you should check if above param is disabled)
    ref_code: str | None                                                # Referral code (should enable 'invite_by_certain_ref_code' param)

actions:
    - ethereum_ecosystem
    - mint_certificates
    - complete_quests
    - manage_quack

# available_actions:
#     - ethereum_ecosystem                            # Completes learning track of Ethereum Developer and claims certificates
#     - mint_certificates                             # Mints your learning certificates on-chain (need to have some Sepolia $ETH on balance)
#     - complete_quests                               # Completes all possible quests
#     - manage_quack                                  # Creates and feeds Quack on main page
```

## Start
- Python ver. >= 3.11

### Windows
`pip install poetry` - _if poetry is not installed_

`cd <project_dir>`

`poetry install`

`poetry run python main.py`

### Linux
`curl -sSL https://install.python-poetry.org | python3 -` - _if poetry is not installed_

`cd <project_dir>`

`poetry install`

`poetry run python main.py`

## Results
- `data/db.sqlite3` - Results
- `logs/logs.txt` - Logs
