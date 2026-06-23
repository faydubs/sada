"""
crud.py – دوال CRUD لمشروع صدى التمر
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.models import Auction, AudioChunk
from models.models import Session as SessionModel
from models.models import User, AuctionStatus, SessionStatus
from schemas.schemas import (
    AuctionCreate, AuctionUpdate,
    SessionCreate, SessionUpdate,
    UserCreate,
)


# ===========================================================================
# User CRUD
# ===========================================================================

def create_user(db: Session, data: UserCreate, hashed_password: str) -> User:
    """
    أنشئ مستخدماً جديداً.
    hashed_password: مُمرَّر من الـ router بعد التهاش – لا نهاش هنا.
    """
    user = User(
        username      = data.username,
        password_hash = hashed_password,
        role          = data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 50) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def delete_user(db: Session, user_id: int) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


# ===========================================================================
# Session CRUD
# ===========================================================================

def create_session(db: Session, data: SessionCreate) -> SessionModel:
    session = SessionModel(dallal_id=data.dallal_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_id(db: Session, session_id: int) -> SessionModel | None:
    return db.query(SessionModel).filter(SessionModel.id == session_id).first()


def get_sessions_by_dallal(db: Session, dallal_id: int) -> list[SessionModel]:
    return (
        db.query(SessionModel)
        .filter(SessionModel.dallal_id == dallal_id)
        .order_by(SessionModel.date.desc())
        .all()
    )


def close_session(db: Session, session_id: int) -> SessionModel | None:
    """أغلق الجلسة واحسب إجمالي الإيراد تلقائياً"""
    session = get_session_by_id(db, session_id)
    if not session:
        return None

    total = (
        db.query(func.sum(Auction.final_price))
        .filter(Auction.session_id == session_id)
        .scalar()
    ) or 0

    session.status        = SessionStatus.closed
    session.total_revenue = total
    db.commit()
    db.refresh(session)
    return session


def update_session(db: Session, session_id: int, data: SessionUpdate) -> SessionModel | None:
    session = get_session_by_id(db, session_id)
    if not session:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(session, field, value)
    db.commit()
    db.refresh(session)
    return session


# ===========================================================================
# Auction CRUD
# ===========================================================================

def create_auction(db: Session, data: AuctionCreate) -> Auction:
    auction = Auction(
        session_id   = data.session_id,
        product_name = data.product_name,
        quantity     = data.quantity,
        unit         = data.unit,
        buyer_name   = data.buyer_name,
        final_price  = data.final_price,
        status       = data.status,
    )
    db.add(auction)
    db.commit()
    db.refresh(auction)
    return auction


def get_auction_by_id(db: Session, auction_id: int) -> Auction | None:
    return db.query(Auction).filter(Auction.id == auction_id).first()


def get_auctions_by_session(db: Session, session_id: int) -> list[Auction]:
    return (
        db.query(Auction)
        .filter(Auction.session_id == session_id)
        .order_by(Auction.started_at.desc())
        .all()
    )


def close_auction(
    db: Session,
    auction_id: int,
    final_price: float,
    buyer_name: str,
) -> Auction | None:
    """أغلق المزاد بتسجيل السعر والمشتري"""
    auction = get_auction_by_id(db, auction_id)
    if not auction:
        return None

    auction.final_price = final_price
    auction.buyer_name  = buyer_name
    auction.status      = AuctionStatus.closed
    auction.closed_at   = datetime.now(timezone.utc)
    db.commit()
    db.refresh(auction)
    return auction


def update_auction(db: Session, auction_id: int, data: AuctionUpdate) -> Auction | None:
    auction = get_auction_by_id(db, auction_id)
    if not auction:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(auction, field, value)
    db.commit()
    db.refresh(auction)
    return auction


def delete_auction(db: Session, auction_id: int) -> bool:
    auction = get_auction_by_id(db, auction_id)
    if not auction:
        return False
    db.delete(auction)
    db.commit()
    return True
