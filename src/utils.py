import json
from typing import Any

import yaml
import requests
from loguru import logger
from tls_requests import Response

from src.models import UserDB, UserQuestDB, QuestDB, User, UserQuest, Quest, Quiz, QuizDB, UserQuizDB, UserQuiz


class Utils:
    @staticmethod
    def handle_response(account_index: int, response: Response | requests.Response) -> dict[str, Any] | list[Any] | None:
        if response.status_code == 200:
            response_data = response.json()
            if response_data:
                return response_data
            else:
                logger.error(f'{account_index+1} | No [response_data] found in given response')
                logger.error(f'{account_index+1} | Full response: {response.text}')
                return
        else:
            logger.error(f'{account_index+1} | Bad response status code: {response.status_code}')
            logger.error(f'{account_index+1} | Full response: {response.text}')
            return
    
    @staticmethod
    def generate_name(account_index: int, user_agent: str) -> str | None:
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Length": "0",
            "Origin": "http://castlots.org",
            "Referer": "http://castlots.org/generator-nikov-online/",
            "User-Agent": user_agent,
            "X-Requested-With": "XMLHttpRequest"
        }
        try:
            response = requests.post(
                url='http://castlots.org/generator-nikov-online/generate.php',
                verify=False,
                headers=headers,
            )
        except Exception as e:
            logger.error(f'{account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(account_index, response)
            if response_data and isinstance(response_data, dict):
                status = response_data.get("success")
                if status:
                    name: str = response_data.get("va", "")
                    logger.debug(f'{account_index+1} | Got [name]: {name}')
                    return name
            logger.error(f'{account_index+1} | Something gone wrong...')
            logger.error(f'{account_index+1} | Full response: {response.text}')
            return    


    @staticmethod
    def convert_from_pydantic_to_alchemy(obj: User | Quest | UserQuest | Quiz | UserQuiz) -> UserDB | QuestDB | UserQuestDB | QuizDB | UserQuizDB:
        if isinstance(obj, User):
            return UserDB(**obj.model_dump())
        elif isinstance(obj, Quest):
            return QuestDB(**obj.model_dump())
        elif isinstance(obj, UserQuest):
            return UserQuestDB(
                is_completed=obj.is_completed,
                reward=obj.reward,
                exp=obj.exp,
                user_id=obj.user_id,
                quest_id=obj.quest_id,
            )
        elif isinstance(obj, Quiz):
            return QuizDB(**obj.model_dump())
        else:
            return UserQuizDB(
                is_completed=obj.is_completed,
                reward=obj.reward,
                exp=obj.exp,
                user_id=obj.user_id,
                quiz_id=obj.quiz_id,
            )

    @staticmethod
    def read_file(path: str, encoding: str | None = None) -> str:
        with open(path, "r", encoding=encoding) as f:
            return f.read()

    @staticmethod
    def read_strings_from_file(path: str) -> list[str]:
        strings: list[str] = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    strings.append(line)
        return strings

    @staticmethod
    def read_json(path: str, encoding: str | None = None) -> list[Any] | dict[str, Any]:
        with open(path, 'r', encoding=encoding) as file:
            return json.loads(file.read())
        
    @staticmethod
    def validate_data(private_keys: list[str]) -> bool:
        if not private_keys:
            logger.error("[private_keys] are not supposed to be empty")
            return False
        return True
        
    @staticmethod
    def read_yaml(yaml_path: str):
        with open(yaml_path, 'r') as f:
            yaml_file = yaml.safe_load(f)
            return yaml_file
