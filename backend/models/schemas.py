"""Pydantic models — mirrored by hand in frontend/src/lib/types.ts."""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "volunteer"]
UserStatus = Literal["pending", "active", "rejected"]
Category = Literal["AIB", "PC"]
EntryStatus = Literal["pending", "approved", "rejected"]
ActivityType = Literal["intervento", "avvistamento", "esercitazione", "formazione", "manutenzione", "sede", "altro"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# ---------- Users ----------
class RegisterIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    phone: str = Field(default="", max_length=30)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    role: Role
    status: UserStatus
    created_at: datetime


class MessageOut(BaseModel):
    message: str


class UserUpdateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    phone: str = Field(default="", max_length=30)


class UserRoleIn(BaseModel):
    role: Role


class UserStatusIn(BaseModel):
    status: UserStatus


# ---------- Entries ----------
class EntryIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    category: Category
    activity_type: ActivityType
    description: str = Field(default="", max_length=500)


class EntryOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    date: str
    start_time: str
    end_time: str
    hours: float
    category: Category
    activity_type: ActivityType
    description: str
    status: EntryStatus
    reject_reason: str = ""
    reviewed_by_name: str = ""
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ReviewIn(BaseModel):
    status: Literal["approved", "rejected"]
    reject_reason: str = Field(default="", max_length=300)


class BulkReviewIn(BaseModel):
    ids: list[str]
    status: Literal["approved", "rejected"]


class BulkReviewOut(BaseModel):
    updated: int
    skipped: int


class MyStats(BaseModel):
    year: int
    today: str
    aib_hours: float
    pc_hours: float
    total_hours: float
    pending_hours: float
    pending_count: int


class SummaryRow(BaseModel):
    user_id: str
    user_name: str
    aib_hours: float
    pc_hours: float
    total_hours: float
    entries: int


class SummaryOut(BaseModel):
    year: int
    month: Optional[int] = None
    rows: list[SummaryRow]
    aib_total: float
    pc_total: float
    grand_total: float


class AdminCounts(BaseModel):
    pending_entries: int
    pending_users: int
