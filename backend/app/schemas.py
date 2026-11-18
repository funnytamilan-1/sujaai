from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr
    class Config:
        from_attributes = True

class ContactOut(BaseModel):
    id: int
    name: str
    phone: str
    opted_in: bool
    class Config:
        from_attributes = True

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    template_name: str = Field(pattern=r"^[a-zA-Z0-9_]+$")
    language: str = Field(default="en", max_length=20)
    image_url: str = Field(min_length=8)
    body_text: str = Field(default="", max_length=1024)

class CampaignOut(BaseModel):
    id: int
    name: str
    template_name: str
    language: str
    image_url: str
    body_text: str
    status: str
    total: int
    sent: int
    failed: int
    created_at: datetime
    class Config:
        from_attributes = True
