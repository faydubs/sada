"""
schemas.py – Pydantic schemas لمشروع صدى التمر
مبنية على models.py الفعلية
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator

from models.models import AuctionStatus, SessionStatus, UserRole


# ===========================================================================
# User
# ===========================================================================

class UserCreate(BaseModel):
    username: str
    password: str                        # كلمة المرور الخام – تُهاش قبل الحفظ
    role: UserRole = UserRole.dallal

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("اسم المستخدم لا يكون فارغاً")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("كلمة المرور 6 أحرف على الأقل")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}   # يقرأ من SQLAlchemy object مباشرة


# ===========================================================================
# Session
# ===========================================================================

class SessionCreate(BaseModel):
    dallal_id: int


class SessionUpdate(BaseModel):
    status: Optional[SessionStatus] = None
    total_revenue: Optional[Decimal] = None


class SessionResponse(BaseModel):
    id: int
    dallal_id: int
    date: datetime
    status: SessionStatus
    total_revenue: Decimal

    model_config = {"from_attributes": True}


class SessionWithAuctions(SessionResponse):
    """جلسة مع قائمة مزاداتها – تُستخدم في صفحة التفاصيل"""
    auctions: list["AuctionResponse"] = []

    model_config = {"from_attributes": True}


# ===========================================================================
# Auction
# ===========================================================================

class AuctionCreate(BaseModel):
    session_id: int
    product_name: str
    quantity: Decimal
    unit: str
    buyer_name: Optional[str] = None
    final_price: Optional[Decimal] = None
    status: AuctionStatus = AuctionStatus.pending

    @field_validator("product_name")
    @classmethod
    def product_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("اسم المنتج لا يكون فارغاً")
        return v.strip()

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("الكمية يجب أن تكون أكبر من صفر")
        return v


class AuctionReviewCreate(BaseModel):
    """
    إنشاء مزاد من بيانات راجعها الدلّال يدوياً بعد التحليل (شاشة المراجعة).
    لا تُحفظ نتائج الـ AI تلقائياً — تُنشأ عبر هذا المسار بعد التعديل والاعتماد.
    """
    session_id: int
    product_name: str
    quantity: Decimal = Decimal(1)
    unit: str = "غير محدد"
    opening_price: Optional[Decimal] = None
    final_price: Optional[Decimal] = None
    buyer_name: Optional[str] = None
    buyer_number: Optional[str] = None
    seller_name: Optional[str] = None
    winner: Optional[str] = None
    currency: Optional[str] = "SAR"
    bids: Optional[list] = None
    notes: Optional[str] = None
    transcript: Optional[str] = None
    confidence: Optional[Decimal] = None
    analysis_status: Optional[str] = None
    model_used: Optional[str] = None
    status: AuctionStatus = AuctionStatus.active

    @field_validator("product_name")
    @classmethod
    def product_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("اسم المنتج لا يكون فارغاً")
        return v.strip()


class AuctionUpdate(BaseModel):
    """لتحديث/تصحيح المزاد وإغلاقه يدوياً من شاشة الدلّال."""
    product_name: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    final_price: Optional[Decimal] = None
    buyer_name: Optional[str] = None
    buyer_number: Optional[str] = None
    status: Optional[AuctionStatus] = None
    closed_at: Optional[datetime] = None


class AuctionResponse(BaseModel):
    id: int
    session_id: int
    product_name: str
    quantity: Decimal
    unit: str
    final_price: Optional[Decimal]
    buyer_name: Optional[str]
    buyer_number: Optional[str] = None
    started_at: datetime
    closed_at: Optional[datetime]
    status: AuctionStatus

    # ── حقول التحليل الغني (اختيارية — تظهر عند توفّرها) ──
    seller_name: Optional[str] = None
    winner: Optional[str] = None
    opening_price: Optional[Decimal] = None
    currency: Optional[str] = None
    bids: Optional[list] = None
    confidence: Optional[Decimal] = None
    notes: Optional[str] = None
    transcript: Optional[str] = None
    analysis_status: Optional[str] = None
    model_used: Optional[str] = None

    model_config = {"from_attributes": True}


# حل forward reference لـ SessionWithAuctions
SessionWithAuctions.model_rebuild()


# ===========================================================================
# Auth
# ===========================================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    """تعديل الدلّال لبياناته الشخصية (اسم المستخدم و/أو كلمة المرور)."""
    username: Optional[str] = None
    password: Optional[str] = None


class AdminRegister(BaseModel):
    """تسجيل حساب مسؤول من الواجهة — يتطلب رمز المسؤول الصحيح."""
    username: str
    password: str
    code: str                            # رمز المسؤول (يُطابَق مع ADMIN_SIGNUP_CODE)

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("اسم المستخدم لا يكون فارغاً")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("كلمة المرور 6 أحرف على الأقل")
        return v
