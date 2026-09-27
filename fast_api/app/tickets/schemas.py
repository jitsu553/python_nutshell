from datetime import datetime
from pydantic import BaseModel, Field


class CreateTicketRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=4000)


class TicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    description: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateTicketStatusRequest(BaseModel):
    status: str = Field(pattern="^(open|in_progress|closed)$")