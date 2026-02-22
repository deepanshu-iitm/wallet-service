from pydantic import BaseModel
from uuid import UUID

class TopUpRequest(BaseModel):
    user_id: UUID
    asset_code: str
    amount: int
    idempotency_key: str

class BonusRequest(BaseModel):
    user_id: UUID
    asset_code: str
    amount: int
    idempotency_key: str

class SpendRequest(BaseModel):
    user_id: UUID
    asset_code: str
    amount: int
    idempotency_key: str

