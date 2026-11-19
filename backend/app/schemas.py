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
