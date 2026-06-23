"""
صدى التمر - نماذج قاعدة البيانات
SQLAlchemy Models with PostgreSQL
"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

# استيراد Base من database – لا نعيد تعريفه هنا
from core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    admin  = "admin"
    dallal = "dallal"


class SessionStatus(str, enum.Enum):
    active = "active"
    closed = "closed"


class AuctionStatus(str, enum.Enum):
    pending = "pending"
    active  = "active"
    closed  = "closed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.dallal)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # مسار ملف البصمة الصوتية (.npy) — يُملأ بعد تسجيل الدلال بصوته عبر
    # POST /api/auth/voiceprint. NULL يعني لم يسجّل بصمة بعد (التحقق يُتجاهل).
    voiceprint_path = Column(String(500), nullable=True)

    # المنطقة الإدارية للدلّال (إحدى مناطق السعودية) — لخريطة المسؤول وتجميع
    # التحليلات حسب المنطقة. تُزرَع تلقائياً (seed/auto-assign) لا من شاشة التسجيل.
    region = Column(String(50), nullable=True, index=True)

    # ✅ بدون type hints على العلاقات
    sessions = relationship(
        "Session",
        back_populates="dallal",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class Session(Base):
    __tablename__ = "sessions"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    dallal_id     = Column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    date          = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    status        = Column(Enum(SessionStatus, name="session_status"), nullable=False, default=SessionStatus.active)
    total_revenue = Column(Numeric(14, 3), nullable=False, default=0)

    dallal = relationship("User", back_populates="sessions")
    auctions = relationship(
        "Auction",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return f"<Session id={self.id} dallal_id={self.dallal_id} status={self.status}>"


class Auction(Base):
    __tablename__ = "auctions"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id   = Column(BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_name = Column(String(200), nullable=False)
    quantity     = Column(Numeric(10, 3), nullable=False)
    unit         = Column(String(50), nullable=False)
    final_price  = Column(Numeric(14, 3), nullable=True)
    buyer_name   = Column(String(200), nullable=True)
    started_at   = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    closed_at    = Column(DateTime(timezone=True), nullable=True)
    status       = Column(Enum(AuctionStatus, name="auction_status"), nullable=False, default=AuctionStatus.pending)

    session = relationship("Session", back_populates="auctions")
    audio_chunks = relationship(
        "AudioChunk",
        back_populates="auction",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self):
        return (
            f"<Auction id={self.id} product={self.product_name!r} "
            f"qty={self.quantity} {self.unit} status={self.status}>"
        )


class AudioChunk(Base):
    __tablename__ = "audio_chunks"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    auction_id    = Column(BigInteger, ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path     = Column(String(500), nullable=False)
    transcription = Column(Text, nullable=True)
    processed_at  = Column(DateTime(timezone=True), nullable=True)

    auction = relationship("Auction", back_populates="audio_chunks")

    def __repr__(self):
        return f"<AudioChunk id={self.id} auction_id={self.auction_id} processed={self.processed_at is not None}>"
