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
    notes: str | None = None

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
    notes: str | None = None

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

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for key in ("name", "chit_type", "default_amount", "start_date", "status"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self

class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    mobile: Mobile | None = None
    address: str | None = Field(default=None, min_length=3)
    joining_date: date | None = None
    notes: str | None = None
    status: Literal["active", "inactive"] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for key in ("name", "mobile", "address", "joining_date", "status"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self

class PaymentUpdate(BaseModel):
    amount: Money | None = None
    paid_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        for key in ("amount", "paid_at"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self

class PaymentCorrection(PaymentUpdate):
    owner_password: str | None = Field(default=None, max_length=128)

class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=190)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "staff"] = "staff"

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    groups: list[dict] = Field(default_factory=list)
    members: list[dict] = Field(default_factory=list)
    payments: list[dict] = Field(default_factory=list)


class SavedDesignCreate(BaseModel):
    design_type: Literal["resume", "pvc"]
    title: str = Field(min_length=1, max_length=120)
    data: dict

class SavedDesignUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    data: dict | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if "title" in self.model_fields_set and (self.title is None or not self.title.strip()):
            raise ValueError("title cannot be empty")
        if "data" in self.model_fields_set and self.data is None:
            raise ValueError("data cannot be null")
        return self
