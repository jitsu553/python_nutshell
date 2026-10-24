from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class CreateCustomerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    plan: str = Field(default="free", pattern="^(free|pro|enterprise)$")


class CustomerResponse(BaseModel):
    id: UUID
    name: str
    email: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}