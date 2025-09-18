import random
from typing import Literal, Any

from loguru import logger
from bs4 import BeautifulSoup as BS
from tenacity import retry, stop_after_attempt, wait_random, retry_if_result
from better_proxy import Proxy

from src.utils import Utils
from src.base import BaseClient
from src.models import Quest, UserData, ResultData, Quiz, Ecosystem, Course, Phase, PhaseQuiz, CertificateData
from src.vars import config


class LoginClient(BaseClient):
    def __init__(self, account_index: int, wallet_address: str, proxy: Proxy | None = None) -> None:
        self.account_index = account_index
        self.wallet_address = wallet_address

        super().__init__(proxy)
    
    def get_data_to_login(self) -> tuple[str, str] | None:
        headers = self._get_headers()
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation GetNonce($address: String\u0021) {\n  nonce: getNonce(address: $address) {\n    nonce\n    message\n  }\n}\n    ",
            "variables": {
                "address": self.wallet_address
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                nonce_data: dict[str, Any] = response_data.get("data", {}).get("nonce", {})
                if not nonce_data:
                    logger.error(f'{self.account_index+1} | No [nonce_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                message_to_sign: str = nonce_data.get("message", "")
                if not message_to_sign:
                    logger.error(f'{self.account_index+1} | No [message_to_sign] found in given [nonce_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return

                nonce: str = nonce_data.get("nonce", "")
                if not nonce:
                    logger.error(f'{self.account_index+1} | No [nonce] found in given [nonce_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return

                logger.debug(f'{self.account_index+1} | Got [message_to_sign]: {message_to_sign}')
                logger.debug(f'{self.account_index+1} | Got [nonce]: {nonce}')
                return message_to_sign, nonce
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return

    def login(self, message: str, nonce: str, signature: str) -> UserData | None:
        headers = self._get_headers()
        payload: dict[str, str | dict[str, dict[str, str | int]]] = {
            "query": "\n    mutation LoginByWallet($input: SignInByWalletInput\u0021) {\n  loginByWallet(input: $input) {\n    access_token\n    refresh_token\n    user {\n      ...baseUserInfo\n    }\n  }\n}\n    \n    fragment baseUserInfo on UserExtend {\n  id\n  uid\n  name\n  avatar\n  username\n  nickname\n  email\n  role\n  voteRole\n  status\n  inviteCode\n  invitedBy\n  hackCoin {\n    coin\n  }\n  levelInfo {\n    level\n    exp\n  }\n  organizations {\n    id\n    creatorId\n    slug\n    name\n    displayName\n    backgroundImage\n    oneLineIntro\n    about\n    logo\n    webSite\n    socialLinks\n    profileSectionState\n    permissionCode\n    permissions\n    createdAt\n    active\n    members {\n      id\n      userId\n      isOwner\n    }\n    features {\n      featureCode\n    }\n  }\n}\n    ",
            "variables": {
                "input": {
                    "address": self.wallet_address,
                    "chainId": 1,
                    "signature": signature, 
                    "message": message,
                    "nonce": nonce,
                    "walletType": random.choice(self.WALLET_TYPES)
                }
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                login_data: dict[str, Any] = response_data.get("data", {}).get("loginByWallet", {})
                if not login_data:
                    logger.error(f'{self.account_index+1} | No [login_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                                
                access_token: str = login_data.get("access_token", "")
                BaseClient.access_token = access_token

                status: Literal['ACTIVATED', 'UNACTIVATED'] = login_data.get("user", {}).get("status", "")
                invite_code: str = login_data.get("user", {}).get("inviteCode", "")
                id: str = login_data.get("user", {}).get("id", "")
                uid: int = login_data.get("user", {}).get("uid", 0)
                invited_by: str = login_data.get("user", {}).get("invitedBy", "")

                logger.debug(f'{self.account_index+1} | Got [access_token]: {access_token[:8]}...{access_token[-8:]}')
                logger.debug(f'{self.account_index+1} | Got [status]: {status}')
                logger.debug(f'{self.account_index+1} | Got [invite_code]: {invite_code}')
                logger.debug(f'{self.account_index+1} | Got [id]: {id}')
                logger.debug(f'{self.account_index+1} | Got [uid]: {uid}')
                logger.debug(f'{self.account_index+1} | Got [invited_by]: {invited_by}')
                
                return UserData(access_token=access_token, account_status=status, invite_code=invite_code, id=id, uid=uid, invited_by=invited_by)
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return
    
    def activate_account(self, ref_code: str | None = None) -> UserData | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation ActivateUser($accessToken: String\u0021, $inviteCode: String) {\n  activateUser(access_token: $accessToken, inviteCode: $inviteCode) {\n    access_token\n    user {\n      ...baseUserInfo\n    }\n    status\n    error\n  }\n}\n    \n    fragment baseUserInfo on UserExtend {\n  id\n  uid\n  name\n  avatar\n  username\n  nickname\n  email\n  role\n  voteRole\n  status\n  inviteCode\n  invitedBy\n  hackCoin {\n    coin\n  }\n  levelInfo {\n    level\n    exp\n  }\n  organizations {\n    id\n    creatorId\n    slug\n    name\n    displayName\n    backgroundImage\n    oneLineIntro\n    about\n    logo\n    webSite\n    socialLinks\n    profileSectionState\n    permissionCode\n    permissions\n    createdAt\n    active\n    members {\n      id\n      userId\n      isOwner\n    }\n    features {\n      featureCode\n    }\n  }\n}\n    ",
            "variables": {
                "accessToken": self.access_token
            }
        }
        if ref_code and isinstance(payload["variables"], dict):
            payload["variables"]["inviteCode"] = ref_code
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                activate_data = response_data.get("data", {}).get("activateUser", {})
                if not activate_data:
                    logger.error(f'{self.account_index+1} | No [activate_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return

                new_access_token: str = activate_data.get("access_token", "")
                BaseClient.access_token = new_access_token

                new_status: Literal['ACTIVATED', 'UNACTIVATED'] = activate_data.get("user", {}).get("status", "")
                new_invite_code: str = activate_data.get("user", {}).get("inviteCode", "")
                new_id: str = activate_data.get("user", {}).get("id", "")
                new_uid: int = activate_data.get("user", {}).get("uid", 0)
                invited_by: str = activate_data.get("user", {}).get("invitedBy", "")

                logger.debug(f'{self.account_index+1} | Got [new_access_token]: {new_access_token[:8]}...{new_access_token[-8:]}')
                logger.debug(f'{self.account_index+1} | Got [new_status]: {new_status}')
                logger.debug(f'{self.account_index+1} | Got [new_invite_code]: {new_invite_code}')
                logger.debug(f'{self.account_index+1} | Got [new_id]: {new_id}')
                logger.debug(f'{self.account_index+1} | Got [new_uid]: {new_uid}')
                logger.debug(f'{self.account_index+1} | Got [invited_by]: {invited_by}')

                logger.debug(f'{self.account_index+1} | Successfully activated account!')
                
                return UserData(access_token=new_access_token, account_status=new_status, invite_code=new_invite_code, id=new_id, uid=new_uid, invited_by=invited_by)
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return


class PetClient(BaseClient):
    def __init__(self, account_index: int, proxy: Proxy | None = None) -> None:
        self.account_index = account_index

        super().__init__(proxy)

    def create_pet(self, name: str) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return False
        
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation CreatePet($name: String\u0021) {\n  createPet(name: $name) {\n    id\n    name\n    level\n    exp\n    expNextLevel\n    userId\n    hatch\n    extra\n  }\n}\n    ",
            "variables": {
                "name": name
            }
        }
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                errors: list[dict[str, Any]] = response_data.get("errors", [{}])
                if errors:
                    error_message = errors[0].get("message", "")
                    if "already exists" in error_message :
                        logger.debug(f'{self.account_index+1} | Already created pet!')
                        return True
                    
                pet_data = response_data.get("data", {}).get("createPet", {})
                if pet_data:
                    logger.debug(f'{self.account_index+1} | Created pet with name {name}')
                    return True
                else:
                    logger.error(f'{self.account_index+1} | Failed to create pet')
                    return False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response.text}')
            return False    

    def feed_pet(self, amount: int) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return False
        
        payload: dict[str, str | dict[str, int]] = {
            "query":"\n    mutation FeedPet($amount: Float\u0021) {\n  feedPet(amount: $amount) {\n    userId\n    level\n    exp\n  }\n}\n    ",
            "variables": {
                "amount": amount
            }
        }
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                pet_data = response_data.get("data", {}).get("feedPet", {})
                if pet_data:
                    logger.debug(f'{self.account_index+1} | Feeded pet with {amount} coins')
                    return True
                else:
                    logger.error(f'{self.account_index+1} | Failed to feed pet')
                    return False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response.text}')
            return False   


class QuestClient(BaseClient):
    def __init__(self, account_index: int, proxy: Proxy | None = None) -> None:
        self.account_index = account_index

        super().__init__(proxy)
    
    def claim_quest_reward(self, quest: Quest) -> ResultData | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation ClaimMissionReward($missionId: String\u0021) {\n  claimMissionReward(missionId: $missionId) {\n    coin\n    exp\n  }\n}\n    ",
            "variables": {
                "missionId": quest.id
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                errors: list[dict[str, Any]] = response_data.get("errors", [{}])
                if errors:
                    error_message = errors[0].get("message", "")
                    if error_message == 'The reward has been claimed!':
                        logger.debug(f'{self.account_index+1} | [{quest.name}] Already claimed quest!')
                        return ResultData(reward=0, exp=0, is_claimed=True)
                    else:
                        logger.debug(f'{self.account_index+1} | [{quest.name}] Failed to claim quest')
                        logger.debug(f'{self.account_index+1} | Full response: {error_message}')
                        return ResultData(reward=0, exp=0, is_claimed=False)      
                                  
                reward_data: dict[str, Any] = response_data.get("data", {}).get("claimMissionReward", {})
                if not reward_data:
                    logger.error(f'{self.account_index+1} | No [reward_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                                
                reward: int = reward_data.get("coin", 0)
                if not reward:
                    reward = 0
                exp: int = reward_data.get("exp", 0)
                if not exp:
                    exp = 0

                logger.debug(f'{self.account_index+1} | Successfully claimed quest <{quest.name}>!')
                return ResultData(reward=reward, exp=exp, is_claimed=True)
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return 


class LearningClient(BaseClient):
    def __init__(self, account_index: int, proxy: Proxy | None = None) -> None:
        self.account_index = account_index

        super().__init__(proxy)

    def get_ecosystem_id(self) -> str | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    query FindActiveEcosystem {\n  ecosystem: findActiveEcosystem {\n    id\n    image\n    type\n  }\n}\n    ",
            "variables": {}
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                ecosystem_data: dict[str, Any] = response_data.get("data", {}).get("ecosystem", {})
                if not ecosystem_data:
                    logger.error(f'{self.account_index+1} | No [ecosystem_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                ecosystem_id: str = ecosystem_data.get("id", "")

                logger.debug(f'{self.account_index+1} | Got [ecosystem_id]: {ecosystem_id}')
                return ecosystem_id
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return    

    def get_ecosystem_info(self, ecosystem_id: str) -> Ecosystem | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, dict[str, dict[str, str]]]] = {
            "query": "\n    query FindActiveEcosystemInfo($where: EcosystemInfoWhereUniqueInput\u0021) {\n  ecosystem: findUniqueEcosystemInfo(where: $where) {\n    ecosystemId\n    lang\n    basic {\n      type\n      image\n    }\n    phases {\n      id\n      coin\n      title\n      progress\n      order\n      cover\n      certificateId\n      certificate {\n        id\n        image\n        name\n        template\n        chainId\n        contract\n        credits\n        extra\n        userCertification {\n          claimed\n          mint\n          username\n          certificateId\n          certificationId\n        }\n      }\n      rewardClaimRecord {\n        claimed\n        coin\n      }\n      courses {\n        id\n        alias\n        type\n        title\n        icon\n        progress\n        order\n        currentPageId\n        units {\n          id\n          currentPageId\n          title\n          progress\n          isCompleted\n        }\n      }\n      quizzes {\n        id\n        order\n        progress\n        currentPageId\n        extra\n        quizList {\n          id\n          correct\n        }\n        description\n      }\n      extra\n      build {\n        hackathons {\n          id\n          name\n          alias\n          status\n          currentStatus\n          info {\n            image\n            intro\n          }\n          timeline {\n            timeZone\n            openReviewSame\n            registrationOpen\n            registrationClose\n            submissionOpen\n            submissionClose\n            rewardTime\n          }\n        }\n      }\n    }\n    currentPhase {\n      id\n      title\n      learningInfo {\n        id\n        alias\n        type\n        learningId\n      }\n    }\n  }\n}\n    ",
            "variables": {
                "where": {
                    "ecosystemId_lang": {
                        "ecosystemId": ecosystem_id,
                        "lang": "en"
                    }
                }
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                ecosystem_data: dict[str, Any] = response_data.get("data", {}).get("ecosystem", {})
                if not ecosystem_data:
                    logger.error(f'{self.account_index+1} | No [ecosystem_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                                
                phases_models: list[Phase] = []

                phases: list[dict[str, Any]] = ecosystem_data.get("phases", [])
                if not phases:
                    logger.error(f'{self.account_index+1} | No [phases] found in given [ecosystem_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                        
                for i, phase in enumerate(phases):
                    phase_id: str = phase.get("id", "")
                    if not phase_id:
                        logger.debug(f'{self.account_index+1} | No [phase_id] found in given [phase]')
                        logger.debug(f'{self.account_index+1} | Full response: {response_data}')
                        continue

                    certificate_id: str = phase.get("certificateId", "")
                    if not certificate_id:
                        certificate_id = ""

                    courses: list[dict[str, Any]] = phase.get("courses", [])
                    if not courses:
                        logger.error(f'{self.account_index+1} | No [courses] found in given [phase_data]')
                        logger.error(f'{self.account_index+1} | Full response: {response_data}')
                        return
                         
                    course_models: list[Course] = []
                    
                    for course in courses:
                        course_id: str = course.get("id", "")
                        if not course_id:
                            logger.debug(f'{self.account_index+1} | No [course_id] found in given [course]')
                            logger.debug(f'{self.account_index+1} | Full response: {response_data}')
                            continue

                        course_models.append(Course(
                            id=course_id
                        ))

                    quizzes: list[dict[str, Any]] = phase.get("quizzes", [])

                    quiz_models: list[PhaseQuiz] = []
                    quiz_pages: list[Quiz] = []

                    for quiz in quizzes:
                        quiz_id: str = quiz.get("id", "")
                        if not quiz_id:
                            logger.debug(f'{self.account_index+1} | No [quiz_id] found in given [quiz]')
                            logger.debug(f'{self.account_index+1} | Full response: {response_data}')
                            continue

                        quiz_list: list[dict[str, Any]] = quiz.get("quizList", [])
                        for j, quiz_page in enumerate(quiz_list):
                            quiz_page_id: str = quiz_page.get("id", "")
                            quiz_pages.append(Quiz(
                                name=f"{j+1}. Phase {i+1} quiz",
                                id=quiz_page_id
                            ))
                        quiz_models.append(PhaseQuiz(
                            id=quiz_id,
                            quiz_list=quiz_pages
                        ))
                    phases_models.append(Phase(
                        id=phase_id,
                        courses=course_models,
                        certificate_id=certificate_id,
                        quizzes=quiz_models
                    ))

                ecosystem_info = Ecosystem(
                    id=ecosystem_id,
                    phases=phases_models
                )

                logger.debug(f'{self.account_index+1} | Got [ecosystem_info]: {ecosystem_info}')
                return ecosystem_info
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return  

    def get_course_ids(self, phase_index: int, ecosystem_id: str) -> list[str] | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, dict[str, dict[str, str]]]] = {
            "query": "\n    query FindActiveEcosystemInfo($where: EcosystemInfoWhereUniqueInput\u0021) {\n  ecosystem: findUniqueEcosystemInfo(where: $where) {\n    ecosystemId\n    lang\n    basic {\n      type\n      image\n    }\n    phases {\n      id\n      coin\n      title\n      progress\n      order\n      cover\n      certificateId\n      certificate {\n        id\n        image\n        name\n        template\n        chainId\n        contract\n        credits\n        extra\n        userCertification {\n          claimed\n          mint\n          username\n          certificateId\n          certificationId\n        }\n      }\n      rewardClaimRecord {\n        claimed\n        coin\n      }\n      courses {\n        id\n        alias\n        type\n        title\n        icon\n        progress\n        order\n        currentPageId\n        units {\n          id\n          currentPageId\n          title\n          progress\n          isCompleted\n        }\n      }\n      quizzes {\n        id\n        order\n        progress\n        currentPageId\n        extra\n        quizList {\n          id\n          correct\n        }\n        description\n      }\n      extra\n      build {\n        hackathons {\n          id\n          name\n          alias\n          status\n          currentStatus\n          info {\n            image\n            intro\n          }\n          timeline {\n            timeZone\n            openReviewSame\n            registrationOpen\n            registrationClose\n            submissionOpen\n            submissionClose\n            rewardTime\n          }\n        }\n      }\n    }\n    currentPhase {\n      id\n      title\n      learningInfo {\n        id\n        alias\n        type\n        learningId\n      }\n    }\n  }\n}\n    ",
            "variables": {
                "where": {
                    "ecosystemId_lang": {
                        "ecosystemId": ecosystem_id,
                        "lang": "en"
                    }
                }
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                ecosystem_data: dict[str, Any] = response_data.get("data", {}).get("ecosystem", {})
                if not ecosystem_data:
                    logger.error(f'{self.account_index+1} | No [ecosystem_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                    
                phases: list[dict[str, Any]] = ecosystem_data.get("phases", [])
                if not phases:
                    logger.error(f'{self.account_index+1} | No [phases] found in given [ecosystem_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                        
                phase_data = phases[phase_index]

                phase_id: str = phase_data.get("id", "")
                if not phase_id:
                    logger.error(f'{self.account_index+1} | No [phase_id] found in given [phase_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                BaseClient.current_phase_id = phase_id

                course_ids: list[str] = []

                courses: list[dict[str, Any]] = phase_data.get("courses", [])
                if not courses:
                    logger.error(f'{self.account_index+1} | No [courses] found in given [phase_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                for course in courses:
                    course_ids.append(course.get("id", ""))

                logger.debug(f'{self.account_index+1} | Got [course_ids]: {course_ids}')
                return course_ids
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return   

    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def get_quizzes(self, course_id: str) -> list[Quiz] | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, dict[str, dict[str, str]]]] = {
            "query": "\n    query FindCourseUnits($where: CourseV2WhereInput) {\n  findCourseDetail(where: $where) {\n    units {\n      title\n      description\n      progress\n      pages {\n        id\n        title\n        isCompleted\n      }\n    }\n    alias\n    id\n    currentPageId\n    nextPageId\n  }\n}\n    ",
            "variables": {
                "where": {
                    "id": {
                        "equals": course_id
                    }
                }
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                course_data = response_data.get("data", {}).get("findCourseDetail", {})
                if not course_data:
                    logger.error(f'{self.account_index+1} | No [course_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                units: list[dict[str, Any]] = course_data.get("units", [])
                if not units:
                    logger.error(f'{self.account_index+1} | No [units] found in given [course_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                quizzes: list[Quiz] = []

                for unit in units:
                    pages: list[dict[str, Any]] = unit.get("pages", [])
                    if not pages:
                        logger.error(f'{self.account_index+1} | No [pages] found in given [unit]')
                        logger.error(f'{self.account_index+1} | Full response: {response_data}')
                        return
                
                    for page in pages:
                        id = page.get("id")
                        title = page.get("title")
                        if id and title:
                            quizzes.append(Quiz(name=title, id=id))

                logger.debug(f'{self.account_index+1} | Got [quizzes]: {quizzes}')
                return quizzes
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return  
         
    def submit_quiz(self, quiz: Quiz, quiz_index: int = 0) -> tuple[int, int, bool]:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return 0, 0, False
        
        payload: dict[str, str | dict[str, dict[str, str | bool | int]]] = {
            "query": "\n    mutation SubmitQuiz($input: SubmitQuizInput\u0021) {\n  submitQuiz(input: $input) {\n    treasure {\n      exp\n      coin\n    }\n  }\n}\n    ",
            "variables": {
                "input": {
                    "lessonId": quiz.id,
                    "status": True,
                    "quizIndex": quiz_index
                }
            }
        }
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return 0, 0, False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                if not response_data.get("data", {}).get("submitQuiz", {}).get("treasure"):
                    logger.debug(f'{self.account_index+1} | Failed to claim quiz reward for quiz [{quiz.name}]: The reward has been claimed!')
                    return 0, 0, True
                
                treasure_data: dict[str, Any] = response_data.get("data", {}).get("submitQuiz", {}).get("treasure", {})
                if not treasure_data:
                    logger.error(f'{self.account_index+1} | No [treasure_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return 0, 0, False
                
                reward: int = treasure_data.get("coin", 0)
                if not reward:
                    reward = 0
                exp: int = treasure_data.get("exp", 0)
                if not exp:
                    exp = 0

                logger.debug(f'{self.account_index+1} | Successfully claimed +{reward} coins, +{exp} exp for quiz [{quiz.name}]')
                return reward, exp, True
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return 0, 0, False

    def check_quiz_number(self, quiz: Quiz) -> int | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return
        
        payload: dict[str, str | dict[str, dict[str, str]]] = {
            "query": " \n    query FindUniquePage($where: PageV2WhereUniqueInput\u0021) {\n  findUniquePage(where: $where) {\n    id\n    title\n    content\n    type\n    completeQuiz\n    isCompleted\n    unitPage {\n      pageId\n      unitId\n    }\n  }\n}\n    ",
            "variables": {
                "where": {
                    "id": quiz.id
                }
            }
        }

        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                page_content: dict[str, list[dict[str, Any]]] | list[dict[str, Any]] = response_data.get("data", {}).get("findUniquePage", {}).get("content")
                if not page_content:
                    logger.error(f'{self.account_index+1} | No [page_content] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return

                number_of_quizzes = 0

                if isinstance(page_content, dict):
                    for page_parts in page_content.values():
                        for page_part in page_parts:
                            page_children: list[dict[str, Any]] = page_part.get("children", [])
                            for children_data in page_children:
                                if children_data.get("type") in ["ChoiceFill", "Choice", "QuizA", "QuizB", "QuizC"]:
                                    number_of_quizzes += 1
                else:
                    for page_part in page_content:
                        page_children: list[dict[str, Any]] = page_part.get("children", [])
                        for children_data in page_children:
                            if children_data.get("type") in ["ChoiceFill", "Choice", "QuizA", "QuizB", "QuizC"]:
                                number_of_quizzes += 1
                logger.debug(f'{self.account_index+1} | Got [number_of_quizzes]: {number_of_quizzes}')
                return number_of_quizzes
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return   

    def complete_lesson(self, quiz: Quiz, course_id: str, phase_id: str = "", complete_course: bool = False) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty [access_token]')
            return False
        
        payload: dict[str, str | dict[str, dict[str, str | bool]]] = {
            "query": "\n    mutation CompleteLesson($input: CompleteLessonInput\u0021) {\n  completeLesson(input: $input) {\n    nextLearningInfo {\n      learningId\n      id\n      type\n      alias\n    }\n  }\n}\n    ",
            "variables": {
                "input": {
                    "lessonId": quiz.id,
                    "courseId": course_id,
                    "completeCourse": complete_course, 
                    "phaseId": phase_id,
                    "lang": "en"
                }
            }
        }

        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                if response_data.get("data", {}).get("completeLesson"):
                    logger.debug(f'{self.account_index+1} | Successfully completed lesson [{quiz.name}]')
                    return True
                logger.error(f'{self.account_index+1} | Failed to complete lesson [{quiz.name}]')
                return False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return False
        
    def claim_phase_reward(self, phase_id: str) -> tuple[int, int, bool]:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return 0, 0, False
        
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation ClaimPhaseReward($phaseId: String\u0021) {\n  claimPhaseReward(phaseId: $phaseId) {\n    coin\n    claimed\n  }\n}\n    ",
            "variables": {
                "phaseId": phase_id
            }
        }

        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return 0, 0, False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                reward_data: dict[str, Any] = response_data.get("data", {}).get("claimPhaseReward", {})
                if not reward_data:
                    logger.error(f'{self.account_index+1} | No [reward_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return 0, 0, False
                
                reward: int = reward_data.get("coin", 0)
                if not reward:
                    reward = 0

                logger.debug(f'{self.account_index+1} | Successfully claimed +{reward} coins, +0 exp for phase reward')
                return reward, 0, True
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return 0, 0, False

    def switch_phase(self, phase_id: str) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return False
        
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation SwitchCurrentPhase($phaseId: String\u0021) {\n  switchCurrentPhase(phaseId: $phaseId)\n}\n    ",
            "variables": {
                "phaseId": phase_id
            }
        }

        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                switch_result = response_data.get("data", {}).get("switchCurrentPhase")
                if switch_result:
                    logger.success(f'{self.account_index+1} | Successfully switched phase')
                    BaseClient.current_phase_id = phase_id
                    return switch_result
                logger.error(f'{self.account_index+1} | Something gone wrong...')
                logger.error(f'{self.account_index+1} | Full response: {response_data}')
                return False
            return False

    def submit_phase_quiz(self, phase_quiz_id: str, quiz: Quiz) -> tuple[int, int, bool]:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return 0, 0, False
        
        payload: dict[str, str | dict[str, dict[str, str | bool]]] = {
            "query": "\n    mutation SubmitPhaseQuiz($input: SubmitPhaseQuizInput\u0021) {\n  submitPhaseQuiz(input: $input) {\n    isCompleted\n    tryAgain\n    progress\n    treasure {\n      coin\n      exp\n    }\n  }\n}\n    ",
            "variables": {
                "input": {
                    "phaseQuizId": phase_quiz_id,
                    "lessonId": quiz.id,
                    "status": True
                }
            }
        }

        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return 0, 0, False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                submit_data = response_data.get("data", {}).get("submitPhaseQuiz", {})
                if not submit_data:
                    logger.error(f'{self.account_index+1} | No [submit_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return 0, 0, False

                treasure_data: dict[str, int] = submit_data.get("treasure", {})
                if treasure_data:
                    reward = treasure_data.get("coin", 0)
                    logger.debug(f'{self.account_index+1} | Successfully completed stage 3/3 at phase quiz <{quiz.name}>')
                    logger.debug(f'{self.account_index+1} | Successfully claimed +{reward} coins, +0 exp for phase reward')
                    return reward, 0, True
                
                progress = submit_data.get("progress", [])
                try_again = submit_data.get("tryAgain")
                if progress[0] != progress[1] and try_again == False:
                    logger.debug(f'{self.account_index+1} | Successfully completed stage {progress[0]}/{progress[1]} at phase quiz <{quiz.name}>!')
                    return 0, 0, True
                
                return 0, 0, False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response.text}')
            return 0, 0, False       

    def claim_certificate(self, certificate_id: str, username: str) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return False
        
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation ClaimCertification($certificationId: String\u0021, $username: String\u0021) {\n  certificate: claimCertification(\n    certificationId: $certificationId\n    username: $username\n  ) {\n    id\n    claimed\n    mint\n    username\n    txId\n    userId\n    certificateId\n    certificationId\n    certificateTime\n    certification {\n      chainId\n      name\n      contract\n      extra\n    }\n  }\n}\n    ",
            "variables": {
                "certificationId": certificate_id,
                "username": username
            }
        }
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                certificate_data = response_data.get("data", {}).get("certificate", {})
                if not certificate_data:
                    logger.error(f'{self.account_index+1} | No [certificate_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return False

                claimed: dict[str, int] = certificate_data.get("claimed")
                if claimed:
                    name = certificate_data.get("certification", {}).get("name")
                    logger.debug(f'{self.account_index+1} | Successfully claimed <{name}> certificate!')
                    return True
                else:
                    logger.error(f'{self.account_index+1} | Failed to claim certificate')
                return False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response.text}')
            return False       


class InfoClient(BaseClient):
    def __init__(self, account_index: int, proxy: Proxy | None = None) -> None:
        self.account_index = account_index

        super().__init__(proxy)
    
    def get_coin_balance(self) -> int:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return 0
        
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "cache-control": "max-age=0",
            "priority": "u=0, i",
            "referer": "https://www.hackquest.io/",
            "sec-ch-ua": r"\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Google Chrome\";v=\"140\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": r"\"Windows\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": self.user_agent
        }
        cookies = { "access_token": self.access_token }
        try:
            response = self.session.get(
                url="https://www.hackquest.io/quest",
                headers=headers,
                cookies=cookies
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return 0
        else:
            soup = BS(response.text, 'html.parser')
            coin_img = soup.find("img", {"alt": "coin"})
            if not coin_img:
                logger.debug(f"{self.account_index+1} | Got [coin_amount]: 0")
                return 0
            coins = coin_img.find_next("span")
            if not coins:
                logger.debug(f"{self.account_index+1} | Got [coin_amount]: 0")
                return 0
            coin_amount = coins.text
            logger.debug(f"{self.account_index+1} | Got [coin_amount]: {coin_amount}")
            return int(coin_amount)
    
    def check_ecosystem_completion(self, ecosystem_id: str) -> bool:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return False
         
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    query ListActiveEcosystemInfos($lang: String\u0021) {\n  ecosystems: listActiveEcosystemInfos(lang: $lang) {\n    ecosystemId\n    basic {\n      image\n      type\n    }\n    progress {\n      progressMap\n      status\n    }\n  }\n}\n    ",
            "variables": {
                "lang": "en"
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return False
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                ecosystems: list[dict[str, Any]] = response_data.get("data", {}).get("ecosystems", [])
                if not ecosystems:
                    logger.error(f'{self.account_index+1} | No [ecosystems] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return False
                
                for found_ecosystem in ecosystems:
                    found_ecosystem_id = found_ecosystem.get("ecosystemId")
                    if found_ecosystem_id == ecosystem_id:
                        progress = found_ecosystem.get("progress", {})
                        if not progress:
                            return False
                        
                        status = progress.get("status")
                        if status == "COMPLETED":
                            return True
                return False
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return False

        
    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    ) 
    def get_certificate_info(self, ecosystem_id: str, certificate_id: str) -> CertificateData | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return 
         
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, dict[str, dict[str, str]]]]  = {
            "query": "\n    query CertificateProgress($where: EcosystemInfoWhereUniqueInput\u0021) {\n  certificate: certificateProgress(where: $where) {\n    id\n    name\n    indexMap\n    progress\n    level\n    chainId\n    contract\n    credits\n    extra\n    template\n    userCertification {\n      mint\n      claimed\n      certificateId\n      certificationId\n      username\n    }\n  }\n}\n    ",
            "variables": {
                "where": {
                    "ecosystemId_lang": {
                        "ecosystemId": ecosystem_id,
                        "lang": "en"
                    }
                }
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                certificates: list[dict[str, Any]] = response_data.get("data", {}).get("certificate", [])
                if not certificates:
                    logger.error(f'{self.account_index+1} | No [certificates] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                for found_certificate in certificates:
                    found_certificate_id: str = found_certificate.get("id", "")
                    name: str = found_certificate.get("name", "")

                    if found_certificate_id == certificate_id:
                        chain_id: int = found_certificate.get("chainId", 0)
                        ca: str = found_certificate.get("contract", "")

                        status: dict[str, Any] = found_certificate.get("userCertification", {})
                        if not status:
                            logger.debug(f'{self.account_index+1} | No [status] found in given [found_certificate]')
                            logger.debug(f'{self.account_index+1} | Full response: {response_data}')
                            return CertificateData(id=found_certificate_id, name=name, chain_id=chain_id, ca=ca, is_claimed=False, is_minted=False, claim_number=0, claim_username="")

                        is_claimed: bool = status.get("claimed", False)

                        is_minted: bool = status.get("mint", False)

                        claim_number: int = status.get("certificateId", 0)

                        claim_username: str = status.get("username", "")

                        return CertificateData(id=found_certificate_id, name=name, chain_id=chain_id, ca=ca, is_claimed=is_claimed, is_minted=is_minted, claim_number=claim_number, claim_username=claim_username)
                return
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return

    @retry(
        retry=retry_if_result(lambda x: x is None), 
        stop=stop_after_attempt(config.general.retry_attempts), 
        wait=wait_random(min=config.delays.delay_between_retries.min, max=config.delays.delay_between_retries.max)
    )         
    def get_certificate_signature(self, certificate_id: str, wallet_address: str) -> str | None:
        if not self.access_token:
            logger.error(f'{self.account_index+1} | Empty access token')
            return
         
        headers = self._get_headers()
        headers["authorization"] = f"Bearer {self.access_token}"
        payload: dict[str, str | dict[str, str]] = {
            "query": "\n    mutation GetCertificationSignature($certificationId: String\u0021, $address: String\u0021) {\n  signature: getCertificationSignature(\n    certificationId: $certificationId\n    address: $address\n  ) {\n    msg\n    signature\n  }\n}\n    ",
            "variables": {
                "certificationId": certificate_id,
                "address": wallet_address
            }
        }
        try:
            response = self.session.post(
                url=self.BASE_URL,
                headers=headers,
                json=payload
            )
        except Exception as e:
            logger.error(f'{self.account_index+1} | Request error: {str(e)}')
            return
        else:
            response_data = Utils.handle_response(self.account_index, response)
            if response_data and isinstance(response_data, dict):
                signature_data: dict[str, str] = response_data.get("data", {}).get("signature", {})
                if not signature_data:
                    logger.error(f'{self.account_index+1} | No [signature_data] found in given [response_data]')
                    logger.error(f'{self.account_index+1} | Full response: {response_data}')
                    return
                
                signature = signature_data.get("signature", "")
                logger.error(f'{self.account_index+1} | Got [signature]: {signature}')
                return signature
            logger.error(f'{self.account_index+1} | Something gone wrong...')
            logger.error(f'{self.account_index+1} | Full response: {response_data}')
            return
