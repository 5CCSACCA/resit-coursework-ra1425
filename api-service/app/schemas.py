from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JobOut(BaseModel):
    id: int
    status: str
    filename: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TranscriptOut(BaseModel):
    id: int
    job_id: int
    text: str
    language: Optional[str]
    duration_seconds: Optional[float]

    class Config:
        from_attributes = True