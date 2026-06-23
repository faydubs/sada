"""
core/security.py – دوال التشفير والمصادقة المشتركة لمشروع صدى التمر
"""

from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 ساعة


def hash_password(plain: str) -> str:
    """شفّر كلمة المرور بـ bcrypt"""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """تحقق من تطابق كلمة المرور مع الهاش المخزَّن"""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    """أنشئ JWT صالح لمدة ACCESS_TOKEN_EXPIRE_MINUTES"""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
