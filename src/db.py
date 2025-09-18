from typing import Any, Type

from loguru import logger
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, scoped_session

from src.models import UserDB, UserQuestDB, QuestDB, Base, QuizDB, UserQuizDB
from src.vars import P, A, DB_URL


class Database:
    def __init__(self, account_index: int) -> None:
        self.account_index = account_index
        self.engine = create_engine(url=DB_URL, echo=False)
        self.session_maker = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False, autocommit=False)

        Base.metadata.create_all(self.engine)
        
    def get_session(self):
        return scoped_session(self.session_maker)
    
    def _create_one(self, obj: A) -> A | None:
        session = self.get_session()
        with session() as sess:
            sess.add(obj)
            sess.commit()
        return obj

    def create_one(self, model: Type[A], obj: A) -> A | None:
        if isinstance(obj, UserQuestDB):
            read_result = self.read_one(model, (obj.user_id, obj.quest_id))
        elif isinstance(obj, UserQuizDB):
            read_result = self.read_one(model, (obj.user_id, obj.quiz_id))
        elif isinstance(obj, UserDB) or isinstance(obj, QuestDB) or isinstance(obj, QuizDB):
            read_result = self.read_one(model, obj.id)
        else:
            return
        
        if read_result:
            logger.debug(f'{self.account_index+1} | Error: Already exists in DB')
            return
         
        return self._create_one(obj)
    
    def _read_one_by_primary_key(self, model: Type[A], primary_key: Any) -> A | None:
        session = self.get_session()
        with session() as sess:
            return sess.get(model, primary_key)
    
    def read_one(self, model: Type[A], primary_key: Any) -> A | None:
        result = self._read_one_by_primary_key(model, primary_key)
        if not result:
            logger.debug(f'{self.account_index+1} | Error: Not exists in DB')
        return result
    
    def update_one(self, model: Type[A], obj: P, primary_key: Any) -> P | None:
        session = self.get_session()
        with session() as sess:
            db_obj = self.read_one(model, primary_key)
            if not db_obj:
                return
            managed_obj = sess.merge(db_obj)

            for key, val in obj.model_dump().items():
                setattr(managed_obj, key, val)
            sess.commit()
        return obj

    def _read_last_user(self) -> UserDB | None:
        session = self.get_session()
        with session() as sess:
            stmt = select(UserDB).order_by(UserDB.created_at.desc()).limit(1)
            return sess.execute(stmt).scalars().first()
    
    def read_last_user(self) -> UserDB | None:
        result = self._read_last_user()
        if not result:
            logger.debug(f'{self.account_index+1} | Error: Not exists in DB')
        return result
    
    def count_all(self, model: Type[A], field: Any, value: Any, second_field: Any, second_value: Any) -> int | None:
        session = self.get_session()
        with session() as sess:
            total = sess.scalar(select(func.count()).filter(field == value).filter(second_field == second_value).select_from(model))
            return total
