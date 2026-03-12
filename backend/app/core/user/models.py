from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserProfile(BaseModel):
    username: str
    real_name: Optional[str] = None
    avatar: Optional[str] = None
    ranking: int = 0
    last_sync: Optional[datetime] = None
