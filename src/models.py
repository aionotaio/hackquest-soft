from typing import Literal
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	pass

class UserDB(Base):
	__tablename__ = 'users'
	
	id: Mapped[str] = mapped_column(primary_key=True)
	uid: Mapped[int] = mapped_column()

	username: Mapped[str] = mapped_column()
	wallet_address: Mapped[str] = mapped_column(String(42))
	private_key: Mapped[str] = mapped_column()
	coin_balance: Mapped[int] = mapped_column()

	invite_code: Mapped[str] = mapped_column()
	invited_by: Mapped[str] = mapped_column(nullable=True)

	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

	completed_quests: Mapped[list["UserQuestDB"]] = relationship(back_populates="user", cascade='all, delete-orphan')
	completed_quizzes: Mapped[list["UserQuizDB"]] = relationship(back_populates="user", cascade='all, delete-orphan')
	
	def __repr__(self) -> str:
		return f"UserDB(id={self.id!r}, uid={self.uid!r}, username={self.username!r}, wallet_address={self.wallet_address!r}, coin_balance={self.coin_balance!r}, invite_code={self.invite_code!r}, invited_by={self.invited_by!r}, created_at={self.created_at!r})"
	
class QuestDB(Base):
	__tablename__ = 'quests'
	
	id: Mapped[str] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column()
	
	users: Mapped[list["UserQuestDB"]] = relationship(back_populates="quest", cascade='all, delete-orphan')
	
	def __repr__(self) -> str:
		return f"QuestDB(id={self.id!r}, name={self.name!r})"
										   
class UserQuestDB(Base):
	__tablename__ = 'user_quests'

	user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
	quest_id: Mapped[str] = mapped_column(ForeignKey('quests.id'), primary_key=True)

	is_completed: Mapped[bool] = mapped_column(default=False)
	reward: Mapped[int] = mapped_column(default=0)
	exp: Mapped[int] = mapped_column(default=0)

	user: Mapped["UserDB"] = relationship(back_populates="completed_quests")
	quest: Mapped["QuestDB"] = relationship(back_populates="users")

	def __repr__(self) -> str:
		return f"UserQuestDB(user_id={self.user_id!r}, quest_id={self.quest_id!r}, is_completed={self.is_completed!r}, reward={self.reward!r}, exp={self.exp!r})"
	
class QuizDB(Base):
	__tablename__ = 'quizzes'
	
	id: Mapped[str] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column()
	
	users: Mapped[list["UserQuizDB"]] = relationship(back_populates="quiz", cascade='all, delete-orphan')
	
	def __repr__(self) -> str:
		return f"QuizDB(id={self.id!r}, name={self.name!r})"
										   
class UserQuizDB(Base):
	__tablename__ = 'user_quizzes'

	user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
	quiz_id: Mapped[str] = mapped_column(ForeignKey('quizzes.id'), primary_key=True)

	is_completed: Mapped[bool] = mapped_column(default=False)
	reward: Mapped[int] = mapped_column(default=0)
	exp: Mapped[int] = mapped_column(default=0)

	user: Mapped["UserDB"] = relationship(back_populates="completed_quizzes")
	quiz: Mapped["QuizDB"] = relationship(back_populates="users")

	def __repr__(self) -> str:
		return f"UserQuizDB(user_id={self.user_id!r}, quiz_id={self.quiz_id!r}, is_completed={self.is_completed!r}, reward={self.reward!r}, exp={self.exp!r})"


class User(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: str
	uid: int
	username: str
	wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
	private_key: str
	coin_balance: int
	invite_code: str
	invited_by: str | None

class Quest(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	name: str
	id: str

class UserQuest(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	is_completed: bool = Field(default=False)
	reward: int = Field(default=0, ge=0)
	exp: int = Field(default=0, ge=0)
	user_id: str
	quest_id: str

class Quiz(BaseModel):
	model_config = ConfigDict(from_attributes=True)
	
	name: str
	id: str

class UserQuiz(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	is_completed: bool = Field(default=False)
	reward: int = Field(default=0, ge=0)
	exp: int = Field(default=0, ge=0)
	user_id: str
	quiz_id: str


class UserData(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	access_token: str
	account_status: Literal['ACTIVATED', 'UNACTIVATED']
	invite_code: str
	id: str
	uid: int
	invited_by: str | None = None

class CertificateData(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: str
	name: str
	chain_id: int
	ca: str
	is_claimed: bool
	is_minted: bool
	claim_number: int
	claim_username: str

class ResultData(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	reward: int
	exp: int
	is_claimed: bool

	def __iadd__(self, other: tuple[int, int]):
		self.reward += other[0]
		self.exp += other[1]
		return self		


class Course(BaseModel):
	id: str

class PhaseQuiz(BaseModel):
	id: str
	quiz_list: list[Quiz]

class Phase(BaseModel):
	id: str
	courses: list[Course]
	certificate_id: str
	quizzes: list[PhaseQuiz]

class Ecosystem(BaseModel):
	id: str
	phases: list[Phase]


class Network(BaseModel):
    name: str
    rpc: str
    chain_id: int
    coin_symbol: str
    explorer: str
    decimals: int = Field(default=18, ge=0)
