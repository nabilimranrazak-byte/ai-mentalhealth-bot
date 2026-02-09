from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class UserCreate(BaseModel):
    user_id: str
    name: Optional[str] = None
    nickname: Optional[str] = None
    age: Optional[int] = None
    hobbies: Optional[str] = None
    diagnosis: Optional[str] = None

class UserOut(BaseModel):
    id: int
    user_id: str
    name: Optional[str]
    nickname: Optional[str]
    age: Optional[int]
    hobbies: Optional[str]
    diagnosis: Optional[str]
    last_seen: Optional[datetime]

    class Config:
        from_attributes = True

class ChatIn(BaseModel):
    user_id: str
    message: str
    conversation_id: Optional[int] = None

class ChatOut(BaseModel):
    conversation_id: int
    reply: str
    last_seen_delta_human: Optional[str] = None
    annotations: Optional[dict[str, Any]] = None

from typing import List
from datetime import datetime

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    annotations: Optional[dict] = None

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None

    class Config:
        from_attributes = True

from typing import List
from datetime import date

class MoodLogIn(BaseModel):
    user_id: str
    mood: str                    # "positive" | "neutral" | "negative" | "anxious" | etc.
    note: Optional[str] = None
    sentiment_score: Optional[float] = None  # e.g. VADER compound

class MoodOut(BaseModel):
    id: int
    user_id: str
    mood: str
    note: Optional[str] = None
    sentiment_score: Optional[float] = None
    day: date
    created_at: datetime

    class Config:
        from_attributes = True
