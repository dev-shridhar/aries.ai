from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserProfile(BaseModel):
    username: str
    real_name: Optional[str] = None
    avatar: Optional[str] = None
    ranking: int = 0
    last_sync: Optional[datetime] = None
