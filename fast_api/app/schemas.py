from typing import Optional

from pydantic import BaseModel


class Item(BaseModel):
    name: str
    price: float
    description: Optional[str] = None
