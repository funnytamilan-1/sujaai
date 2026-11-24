from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utc_now():
    return datetime.now(timezone.utc)

class ChitGroup(Base):
    __tablename__ = "chit_groups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    chit_type: Mapped[str] = mapped_column(String(12))
    default_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    members: Mapped[list["ChitMember"]] = relationship(back_populates="group")

class ChitMember(Base):
    __tablename__ = "chit_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_code: Mapped[str] = mapped_column(String(60))
    group_id: Mapped[int] = mapped_column(ForeignKey("chit_groups.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    mobile: Mapped[str] = mapped_column(String(20), index=True)
    address: Mapped[str] = mapped_column(Text)
    joining_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(16), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    group: Mapped["ChitGroup"] = relationship(back_populates="members")
    payments: Mapped[list["ChitPayment"]] = relationship(back_populates="member")

class ChitPayment(Base):
    __tablename__ = "chit_payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("chit_members.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    frequency: Mapped[str] = mapped_column(String(12))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    member: Mapped["ChitMember"] = relationship(back_populates="payments")

Index("ix_chit_members_member_code", ChitMember.member_code)
Index("uq_chit_members_group_member_code", ChitMember.group_id, ChitMember.member_code, unique=True)
Index("ix_payment_paid_at_member", ChitPayment.paid_at, ChitPayment.member_id)

class AuditLog(Base):
    __tablename__ = "application_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

from sqlalchemy import Boolean

class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SavedDesign(Base):
    __tablename__ = "saved_designs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_email: Mapped[str] = mapped_column(String(190), index=True)
    design_type: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(120))
    data: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
