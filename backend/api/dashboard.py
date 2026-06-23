"""
api/dashboard.py – مؤشرات لوحة التحكم الفورية لجلسة مزاد واحدة
يُستخدم في شاشة الدلال/الأدمن لمتابعة الجلسة الحالية لحظياً.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.models import Auction, AuctionStatus, User
from models.models import Session as SessionModel

router = APIRouter()


def _get_session_or_403(db: Session, session_id: int, current_user: User) -> SessionModel:
    """يرجع الجلسة إذا كانت موجودة ويملك المستخدم الحالي صلاحية رؤيتها."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الجلسة غير موجودة")

    if current_user.role.value != "admin" and session.dallal_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="لا يمكنك رؤية بيانات جلسة دلّال آخر")

    return session


@router.get("/summary")
def get_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    مؤشرات سريعة لبطاقات اللوحة الرئيسية: عدد المزادات، الإيراد،
    أعلى سعر، متوسط السعر، عدد المشترين الفريدين.
    """
    _get_session_or_403(db, session_id, current_user)

    base_query = db.query(Auction).filter(Auction.session_id == session_id)

    auctions_count = base_query.count()
    closed_count = base_query.filter(Auction.status == AuctionStatus.closed).count()
    active_count = base_query.filter(Auction.status == AuctionStatus.active).count()

    price_stats = (
        db.query(
            func.sum(Auction.final_price),
            func.max(Auction.final_price),
            func.avg(Auction.final_price),
        )
        .filter(Auction.session_id == session_id, Auction.final_price.isnot(None))
        .first()
    )
    total_revenue, top_price, avg_price = price_stats or (None, None, None)

    unique_buyers = (
        db.query(func.count(func.distinct(Auction.buyer_name)))
        .filter(Auction.session_id == session_id, Auction.buyer_name.isnot(None))
        .scalar()
    ) or 0

    return {
        "session_id": session_id,
        "auctions_count": auctions_count,
        "closed_count": closed_count,
        "active_count": active_count,
        "total_revenue": float(total_revenue) if total_revenue is not None else 0.0,
        "top_price": float(top_price) if top_price is not None else None,
        "avg_price": round(float(avg_price), 2) if avg_price is not None else None,
        "unique_buyers": unique_buyers,
    }


@router.get("/trends")
def get_trends(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    سلسلة زمنية مبسّطة لأسعار المزادات داخل الجلسة بترتيب حدوثها —
    تُستخدم لرسم مخطط الإيراد التراكمي/السعر عبر الوقت في اللوحة.
    """
    _get_session_or_403(db, session_id, current_user)

    auctions = (
        db.query(Auction)
        .filter(Auction.session_id == session_id)
        .order_by(Auction.started_at.asc())
        .all()
    )

    running_total = 0.0
    points = []
    for a in auctions:
        price = float(a.final_price) if a.final_price is not None else None
        if price is not None:
            running_total += price
        points.append({
            "auction_id": a.id,
            "product_name": a.product_name,
            "price": price,
            "cumulative_revenue": round(running_total, 2),
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "status": a.status.value,
        })

    return {"session_id": session_id, "points": points}
