from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Mobile = Annotated[str, StringConstraints(pattern=r"^[0-9+() -]{7,20}$")]

class GroupCreate(BaseModel):
    group_code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    chit_type: Literal["daily", "weekly", "monthly"]
    default_amount: Money
    start_date: date
    description: str | None = None

class GroupOut(GroupCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str

class MemberCreate(BaseModel):
    member_code: str = Field(min_length=2, max_length=60)
    group_id: int
    name: str = Field(min_length=2, max_length=160)
    mobile: Mobile
    address: str = Field(min_length=3)
    joining_date: date
    notes: str | None = None

class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    member_code: str
    group_id: int
    name: str
    mobile: str
    address: str
    joining_date: date
    status: str

class PaymentCreate(BaseModel):
    member_id: int
    amount: Money
    paid_at: datetime
    frequency: Literal["daily", "weekly", "monthly"]
    notes: str | None = None

class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    payment_ref: str
    member_id: int
    amount: Decimal
    paid_at: datetime
    frequency: str
    recorded_by: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

from pydantic import model_validator

class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    chit_type: Literal["daily", "weekly", "monthly"] | None = None
    default_amount: Money | None = None
    start_date: date | None = None
    description: str | None = None
    status: Literal["active", "paused", "completed"] | None = None

class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    mobile: Mobile | None = None
    address: str | None = Field(default=None, min_length=3)
    joining_date: date | None = None
    notes: str | None = None
    status: Literal["active", "inactive"] | None = None

class PaymentUpdate(BaseModel):
    amount: Money | None = None
    paid_at: datetime | None = None
    notes: str | None = None

class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=190)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "staff"] = "staff"

class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

class UserStatusUpdate(BaseModel):
    is_active: bool

class BackupImport(BaseModel):
    schema_version: int = Field(ge=1, le=1)
    exported_at: datetime | None = None
    groups: list[dict] = []
    members: list[dict] = []
    payments: list[dict] = []
