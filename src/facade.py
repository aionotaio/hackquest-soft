import time
import random

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random, retry_if_result

from src.db import Database
from src.models import User, Quest, UserQuest, Ecosystem, Quiz, Phase, Course, UserDB, UserQuizDB, QuizDB, UserQuiz, UserQuestDB, QuestDB, PhaseQuiz, Network, UserData
from src.client import LoginClient, PetClient, QuestClient, LearningClient, InfoClient
from src.utils import Utils
from src.w3 import W3
from src.vars import INIT_QUESTS, config
from better_proxy import Proxy


class Facade:
    def __init__(self, account_index: int, private_key: str, network: Network, proxy: Proxy | None = None) -> None:
        self.account_index = account_index
        self.private_key = private_key
        self.network = network
        self.proxy = proxy

        self.db = Database(self.account_index)
        self.w3 = W3(self.account_index, self.private_key, self.network, self.proxy)
        self.login_client = LoginClient(self.account_index, self.w3.address, self.proxy)
        self.learning_client = LearningClient(self.account_index, self.proxy)
        self.quest_client = QuestClient(self.account_index, self.proxy)
        self.pet_client = PetClient(self.account_index, self.proxy)
        self.info_client = InfoClient(self.account_index, self.proxy)

    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def login(self, ref_code: str | None = None) -> User | None:
        logger.info(f'{self.account_index+1} | Attempting to log in...')

        username = self.generate_name()
        if not username:
            username = f"user{self.account_index+1}"

        login_data_result = self.login_client.get_data_to_login()
        if not login_data_result:
            return
        message, nonce = login_data_result

        signature = self.w3.get_signature(message)
        if not signature:
            return
        
        login_result = self.login_client.login(message, nonce, signature)
        if not login_result:
            return

        if login_result.account_status == 'UNACTIVATED':
            login_result = self.login_client.activate_account(ref_code)
            if not login_result:
                return
            
            user = User(id=login_result.id, uid=login_result.uid, username=username, wallet_address=self.w3.address, private_key=self.w3.private_key, coin_balance=0, invite_code=login_result.invite_code, invited_by=login_result.invited_by)

            user = self._save_user(user)

            logger.success(f'{self.account_index+1} | Successfully logged in!')

            return user           
                   
        coin_balance = self.info_client.get_coin_balance()

        user = User(id=login_result.id, uid=login_result.uid, username=username, wallet_address=self.w3.address, private_key=self.w3.private_key, coin_balance=coin_balance, invite_code=login_result.invite_code, invited_by=login_result.invited_by)

        user = self._save_user(user, coin_balance)

        logger.success(f'{self.account_index+1} | Successfully logged in!')

        return user  

    def complete_ethereum_ecosystem(self, user: User, ecosystem: Ecosystem) -> None:
        if self.info_client.check_ecosystem_completion(ecosystem.id):
            logger.info(f'{self.account_index+1} | Already completed ecosystem!')
            return
        
        for i, phase in enumerate(ecosystem.phases):
            self.complete_phase_units(user, i, phase.courses)
            if not self.check_phase_units_completion(user, i, phase.courses):
                continue

            if phase.quizzes:
                self.complete_phase_quiz(user, i, phase.quizzes)
                if not self.check_phase_quizzes_completion(user, i, phase.quizzes):    
                    continue

            if phase.certificate_id:
                certificate_info = self.info_client.get_certificate_info(ecosystem.id, phase.certificate_id)
                if not certificate_info:
                    continue
                if certificate_info.is_claimed == True:
                    continue
                if not self.claim_certificate(i, phase.certificate_id, user.username):
                    continue

            self.claim_phase_reward(user, i, phase.id)

            if i != len(ecosystem.phases) - 1:
                self.learning_client.switch_phase(ecosystem.phases[i+1].id)

            coin_balance = self.info_client.get_coin_balance()
            user_db = self.db.read_one(UserDB, user.id)
            user_from_db = User.model_validate(user_db)

            new_user = User(id=user_from_db.id, uid=user_from_db.uid, username=user_from_db.username, wallet_address=user_from_db.wallet_address, private_key=user_from_db.private_key, coin_balance=coin_balance, invite_code=user_from_db.invite_code, invited_by=user_from_db.invited_by)

            self.db.update_one(UserDB, new_user, user.id)   

    def mint_certificates(self, ecosystem: Ecosystem) -> None:
        for phase in ecosystem.phases:
            if phase.certificate_id:
                certificate_info = self.info_client.get_certificate_info(ecosystem.id, phase.certificate_id)
                if not certificate_info:
                    continue
                
                if not certificate_info.is_claimed:
                    logger.info(f'{self.account_index+1} | [{certificate_info.name}] Certificate not claimed!')
                    continue

                logger.info(f'{self.account_index+1} | [{certificate_info.name}] Attempting to mint certificate...')

                if certificate_info.is_minted == True:
                    logger.info(f'{self.account_index+1} | [{certificate_info.name}] Already minted certificate!')
                    continue
                
                if certificate_info.chain_id != self.w3.network.chain_id:
                    logger.error(f'{self.account_index+1} | [{certificate_info.name}] Mint cancelled: wrong network id ({certificate_info.chain_id})')
                    continue
                            
                balance = self.w3.w3.eth.get_balance(self.w3.address)
                
                if balance <= 0:
                    logger.error(f'{self.account_index+1} | [{certificate_info.name}] Mint cancelled: zero balance')
                    continue
                
                signature = self.info_client.get_certificate_signature(phase.certificate_id, self.w3.address)
                if not signature:
                    continue
                
                if not self.w3.mint_certificate(certificate_info.ca, certificate_info.claim_username, certificate_info.claim_number, signature):
                    continue  

            time.sleep(random.uniform(config.delays.delay_between_tasks.min, config.delays.delay_between_tasks.max))

    def complete_quests(self, user: User, quests: list[Quest]) -> None:
        random.shuffle(quests)

        self._init_quests(user, quests)

        for quest in quests:
            reward_quest_db = self.db.read_one(UserQuestDB, (user.id, quest.id))
            reward_quest = UserQuest.model_validate(reward_quest_db)
            if reward_quest.is_completed == True:
                logger.info(f'{self.account_index+1} | [{quest.name}] Already claimed quest reward!')
                continue
            
            if quest.name == "Got 2000 coins":
                user_db = self.db.read_one(UserDB, user.id)
                user_model = User.model_validate(user_db)
                if user_model.coin_balance < 2000:
                    continue
            
            if quest.name == "Finish 20 quests" or quest.name == 'Quest terminator':
                finished_quest_count = self.db.count_all(UserQuestDB, UserQuestDB.user_id, user.id, UserQuestDB.is_completed, True)
                finished_quiz_count = self.db.count_all(UserQuizDB, UserQuizDB.user_id, user.id, UserQuizDB.is_completed, True)
                if finished_quiz_count == None or finished_quest_count == None:
                    continue
                total_count = finished_quest_count + finished_quiz_count
                if total_count < 20:
                    continue
            
            self.claim_quest_reward(user, quest) 

            coin_balance = self.info_client.get_coin_balance()
            user_db = self.db.read_one(UserDB, user.id)
            user_from_db = User.model_validate(user_db)

            new_user = User(id=user_from_db.id, uid=user_from_db.uid, username=user_from_db.username, wallet_address=user_from_db.wallet_address, private_key=user_from_db.private_key, coin_balance=coin_balance, invite_code=user_from_db.invite_code, invited_by=user_from_db.invited_by)

            self.db.update_one(UserDB, new_user, user.id)   

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def claim_quest_reward(self, user: User, quest: Quest) -> bool:
        reward_quest_db = self.db.read_one(UserQuestDB, (user.id, quest.id))
        reward_quest = UserQuest.model_validate(reward_quest_db)
        if reward_quest.is_completed == True:
            logger.debug(f'{self.account_index+1} | [{quest.name}] Already claimed quest reward!')
            return True

        logger.info(f'{self.account_index+1} | [{quest.name}] Attempting to claim quest reward...')

        quest_result = self.quest_client.claim_quest_reward(quest)
        if not quest_result or not quest_result.is_claimed:
            logger.error(f'{self.account_index+1} | [{quest.name}] Failed to claim quest')
            return False
        
        if quest_result.is_claimed:
            logger.info(f'{self.account_index+1} | [{quest.name}] Already claimed quest reward!')
        else:
            logger.success(f'{self.account_index+1} | [{quest.name}] Successfully claimed +{quest_result.reward} coins, +{quest_result.exp} exp!')
        
        self.db.update_one(UserQuestDB, UserQuest(is_completed=True, reward=quest_result.reward, exp=quest_result.exp, user_id=user.id, quest_id=quest.id), (user.id, quest.id))
        return True  

    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def submit_unit_lesson_quiz(self, quiz: Quiz, phase_index: int, quiz_index: int = 0) -> None | tuple[int, int]:
        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Attempting to submit unit lesson quiz [{quiz.name}]...')

        reward, exp, status = self.learning_client.submit_quiz(quiz, quiz_index)
        if status is False:
            return
        
        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully submitted unit lesson quiz [{quiz.name}]!')
        return reward, exp   
        
    def complete_phase_units(self, user: User, phase_index: int, courses: list[Course]) -> None:
        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Attempting to complete phase units...')
        
        for course in courses:
            quizzes = self.learning_client.get_quizzes(course.id)
            if not quizzes:
                continue
            
            self._init_phase_quizzes(phase_index, user, quizzes)

            for i, quiz in enumerate(quizzes):
                user_quiz_db = self.db.read_one(UserQuizDB, (user.id, quiz.id))
                user_quiz = UserQuiz.model_validate(user_quiz_db)
                if user_quiz.is_completed == True:
                    logger.debug(f'{self.account_index+1} | [Phase {phase_index+1}] Already completed unit lesson [{quiz.name}]!')
                    continue
                
                number_of_quizzes = self.learning_client.check_quiz_number(quiz)
                if number_of_quizzes == 0:
                    self.db.update_one(UserQuizDB, UserQuiz(is_completed=True, reward=0, exp=0, user_id=user.id, quiz_id=quiz.id), (user.id, quiz.id))
                    
                    if self._complete_lesson(quiz, course.id, i, len(quizzes)):
                        logger.success(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully completed unit lesson [{quiz.name}]!')
                    continue

                if not number_of_quizzes:
                    continue

                j = -1
                total_result = 0, 0
                while j != number_of_quizzes - 1:
                    result = self.submit_unit_lesson_quiz(quiz, phase_index, j+1)
                    if not result:
                        j += 1
                        continue
                    
                    total_result = (total_result[0] + result[0], total_result[1] + result[1])

                    time.sleep(random.uniform(1, 2))

                    j += 1
                
                self.db.update_one(UserQuizDB, UserQuiz(is_completed=True, reward=total_result[0], exp=total_result[1], user_id=user.id, quiz_id=quiz.id), (user.id, quiz.id))
                    
                if self._complete_lesson(quiz, course.id, i, len(quizzes)):
                    logger.success(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully completed unit lesson [{quiz.name}]!')
                
                time.sleep(random.uniform(config.delays.delay_between_tasks.min, config.delays.delay_between_tasks.max))

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def complete_phase_quiz(self, user: User, phase_index: int, phase_quizzes: list[PhaseQuiz]) -> bool:
        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Attempting to complete phase quizzes...')
        for phase_quiz in phase_quizzes:
            self._init_phase_quizzes(phase_index, user, phase_quiz.quiz_list)
            for quiz in phase_quiz.quiz_list:
                user_quiz_db = self.db.read_one(UserQuizDB, (user.id, quiz.id))
                user_quiz = UserQuiz.model_validate(user_quiz_db)
                if user_quiz.is_completed == True:
                    logger.debug(f'{self.account_index+1} | [Phase {phase_index+1}] Already completed phase quiz [{quiz.name}]!')
                    continue

                reward, exp, status = self.learning_client.submit_phase_quiz(phase_quiz.id, quiz)
                if not status:
                    return False
                
                self.db.update_one(UserQuizDB, UserQuiz(is_completed=True, reward=reward, exp=exp, user_id=user.id, quiz_id=quiz.id), (user.id, quiz.id))

                time.sleep(random.uniform(config.delays.delay_between_tasks.min, config.delays.delay_between_tasks.max))

        logger.success(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully completed phase quizzes!')
        return True
    
    def check_phase_units_completion(self, user: User, phase_index: int, courses: list[Course]) -> bool:        
        for course in courses:
            quizzes = self.learning_client.get_quizzes(course.id)
            if not quizzes:
                return False
            
            for quiz in quizzes:
                user_quiz_db = self.db.read_one(UserQuizDB, (user.id, quiz.id))
                user_quiz = UserQuiz.model_validate(user_quiz_db)
                if user_quiz.is_completed == True:
                    logger.debug(f'{self.account_index+1} | [Phase {phase_index+1}] Already completed unit lesson [{quiz.name}]!')
                else:
                    return False
        return True
    
    def check_phase_quizzes_completion(self, user: User, phase_index: int, phase_quizzes: list[PhaseQuiz]) -> bool:        
        for phase_quiz in phase_quizzes:
            for quiz in phase_quiz.quiz_list:
                user_quiz_db = self.db.read_one(UserQuizDB, (user.id, quiz.id))
                user_quiz = UserQuiz.model_validate(user_quiz_db)
                if user_quiz.is_completed == True:
                    logger.debug(f'{self.account_index+1} | [Phase {phase_index+1}] Already completed phase quiz [{quiz.name}]!')
                else:
                    return False
        return True

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    )     
    def claim_phase_reward(self, user: User, phase_index: int, phase_id: str) -> bool:
        reward_quest_db = self.db.read_one(UserQuestDB, (user.id, f'Phase {phase_index+1} Reward'))
        reward_quest = UserQuest.model_validate(reward_quest_db)
        if reward_quest.is_completed == True:
            logger.debug(f'{self.account_index+1} | [Phase {phase_index+1}] Already claimed phase reward!')
            return True

        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Attempting to claim phase reward...')

        reward, exp, status = self.learning_client.claim_phase_reward(phase_id)
        if status is False:
            return False
        
        self.db.update_one(UserQuestDB, UserQuest(is_completed=True, reward=reward, exp=exp, user_id=user.id, quest_id=f'Phase {phase_index+1} Reward'), (user.id, f'Phase {phase_index+1} Reward'))

        logger.success(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully claimed phase reward!')
        return True

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    )     
    def claim_certificate(self, phase_index: int, certificate_id: str, username: str) -> bool:
        logger.info(f'{self.account_index+1} | [Phase {phase_index+1}] Attempting to claim certificate...')

        if not self.learning_client.claim_certificate(certificate_id, username):
            return False

        logger.success(f'{self.account_index+1} | [Phase {phase_index+1}] Successfully claimed certificate!')
        return True

    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    )     
    def get_ecosystem_info(self) -> Ecosystem | None:
        logger.info(f'{self.account_index+1} | Attempting to get ecosystem info...')

        ecosystem_id = self.learning_client.get_ecosystem_id()
        if not ecosystem_id:
            return            

        ecosystem_info = self.learning_client.get_ecosystem_info(ecosystem_id)
        if not ecosystem_info:
            return
        
        logger.success(f'{self.account_index+1} | Successfully got ecosystem info!')
        return ecosystem_info

    def manage_quack(self, user: User, humanize: bool) -> bool:
        user_db = self.db.read_one(UserDB, user.id)
        user_model = User.model_validate(user_db)

        coin_balance = user.coin_balance

        if not self.create_pet(user_model.username):
            return False
        
        if coin_balance == 0:
            return False
        
        if coin_balance < 5:
            coin_amount = coin_balance
        else:
            coin_amount = random.randrange(0, coin_balance+1, 5)
        
        if humanize:
            i = 0
            while i < coin_amount:
                self.feed_pet(5)
                i += 5
            return True

        return self.feed_pet(coin_amount)

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    )     
    def create_pet(self, name: str) -> bool:
        logger.info(f'{self.account_index+1} | [Quack] Attempting to create pet...')

        if not self.pet_client.create_pet(name):
            return False
        
        logger.success(f'{self.account_index+1} | [Quack] Successfully created pet!')
        return True        

    @retry(
        retry=retry_if_result(lambda x: x is False), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def feed_pet(self, coin_amount: int) -> bool:
        logger.info(f'{self.account_index+1} | [Quack] Attempting to feed pet...')

        if not self.pet_client.feed_pet(coin_amount):
            return False
        
        logger.success(f'{self.account_index+1} | [Quack] Successfully feeded pet with {coin_amount} coins!')
        return True  

    def generate_name(self) -> str | None:
        return Utils.generate_name(self.account_index, self.info_client.user_agent)

    def _init_quests(self, user: User, quests: list[Quest]):
        for quest in quests:
            alchemy_quest_obj = Utils.convert_from_pydantic_to_alchemy(quest)
            alchemy_userquest_obj = Utils.convert_from_pydantic_to_alchemy(UserQuest(is_completed=False, reward=0, exp=0, user_id=user.id, quest_id=quest.id))
            self.db.create_one(QuestDB, alchemy_quest_obj)
            self.db.create_one(UserQuestDB, alchemy_userquest_obj)
                        
    def _init_phase_quizzes(self, phase_index: int, user: User, quizzes: list[Quiz]) -> None:
        alchemy_reward_obj = Utils.convert_from_pydantic_to_alchemy(Quest(name=f'Phase {phase_index+1} Reward', id=f'Phase {phase_index+1} Reward'))
        alchemy_userreward_obj = Utils.convert_from_pydantic_to_alchemy(UserQuest(is_completed=False, reward=0, exp=0, user_id=user.id, quest_id=f'Phase {phase_index+1} Reward'))

        self.db.create_one(QuestDB, alchemy_reward_obj)
        self.db.create_one(UserQuestDB, alchemy_userreward_obj)

        for quiz in quizzes:
            alchemy_quiz_obj = Utils.convert_from_pydantic_to_alchemy(quiz)
            alchemy_userquiz_obj = Utils.convert_from_pydantic_to_alchemy(UserQuiz(is_completed=False, reward=0, exp=0, user_id=user.id, quiz_id=quiz.id))
            self.db.create_one(QuizDB, alchemy_quiz_obj)
            self.db.create_one(UserQuizDB, alchemy_userquiz_obj)
            
    def _complete_lesson(self, quiz: Quiz, course_id: str, index: int, total: int) -> bool:
        if index == 0:
            return self.learning_client.complete_lesson(quiz, course_id, self.learning_client.current_phase_id)
        elif index == total - 1:
            return self.learning_client.complete_lesson(quiz, course_id, self.learning_client.current_phase_id, complete_course=True)
        else:
            return self.learning_client.complete_lesson(quiz, course_id)

    def _save_user(self, user: User, coin_balance: int | None = None):
        created_user_db = self.db.read_one(UserDB, user.id)
        if created_user_db:
            created_user = User.model_validate(created_user_db)
            if created_user:
                user = User(id=user.id, uid=user.uid, username=created_user.username, wallet_address=self.w3.address, private_key=self.w3.private_key, coin_balance=coin_balance if coin_balance is not None else created_user.coin_balance, invite_code=user.invite_code, invited_by=user.invited_by)

        alchemy_obj = Utils.convert_from_pydantic_to_alchemy(user)
        if not self.db.create_one(UserDB, alchemy_obj):
            self.db.update_one(UserDB, user, user.id)  
        
        return user
