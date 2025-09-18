from typing import Literal

from pydantic import BaseModel, Field, model_validator, HttpUrl


class AnyRange(BaseModel):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode='before')
    def check_min_le_max(cls, values):
        if values['min'] > values['max']:
            raise ValueError("[min] is not supposed to be > than [max]")
        return values
  
class DelaysConfig(BaseModel):
    delay_between_tasks: AnyRange
    delay_between_accs: AnyRange
    delay_between_retries: AnyRange

class GeneralConfig(BaseModel):
    threads: int = Field(ge=1)
    retry_attempts: int = Field(ge=0)
    sepolia_rpc: HttpUrl
    humanize: bool

class ReferralConfig(BaseModel):
    invite_by_next_ref_code: bool
    invite_by_certain_ref_code: bool
    ref_code: str | None = None

    @model_validator(mode='before')
    def check_if_both_true(cls, values):
        if values['invite_by_next_ref_code'] == True and values['invite_by_certain_ref_code'] == True:
            raise ValueError("[invite_by_next_ref_code] and [invite_by_certain_ref_code] are not supposed to be both 'true'")
        return values

    @model_validator(mode='before')
    def check_ref_code(cls, values):
        if values['invite_by_certain_ref_code'] == True and not values['ref_code']:
            raise ValueError("[ref_code] are not supposed to be empty")
        return values
    
class Config(BaseModel):
    general: GeneralConfig
    delays: DelaysConfig
    actions: list[Literal['ethereum_ecosystem', 'complete_quests', 'mint_certificates', 'manage_quack']]
    referral: ReferralConfig
