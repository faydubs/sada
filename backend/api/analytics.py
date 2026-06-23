"""
api/analytics.py – تحليلات اتجاهات الأسعار حسب الصنف لجلسة مزاد
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.models import Auction, User
from models.models import Session as SessionModel

router = APIRouter()


def _get_session_or_403(db: Session, session_id: int, current_user: User) -> SessionModel:
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الجلسة غير موجودة")

    if current_user.role.value != "admin" and session.dallal_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="لا يمكنك رؤية بيانات جلسة دلّال آخر")

    return session


@router.get("/price-trends")
def get_price_trends(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    إحصائيات السعر مجمَّعة حسب اسم الصنف داخل الجلسة:
    عدد المزادات، متوسط/أدنى/أعلى سعر لكل صنف.
    """
    _get_session_or_403(db, session_id, current_user)

    rows = (
        db.query(
            Auction.product_name,
            func.count(Auction.id),
            func.avg(Auction.final_price),
            func.min(Auction.final_price),
            func.max(Auction.final_price),
        )
        .filter(Auction.session_id == session_id, Auction.final_price.isnot(None))
        .group_by(Auction.product_name)
        .order_by(func.count(Auction.id).desc())
        .all()
    )

    products = [
        {
            "product_name": product_name,
            "auctions_count": count,
            "avg_price": round(float(avg_price), 2) if avg_price is not None else None,
            "min_price": float(min_price) if min_price is not None else None,
            "max_price": float(max_price) if max_price is not None else None,
        }
        for product_name, count, avg_price, min_price, max_price in rows
    ]

    return {"session_id": session_id, "products": products}


@router.get("/trends")
def get_trends(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    سلسلة زمنية تفصيلية لكل مزاد (الصنف + السعر + التوقيت) بترتيب حدوثها —
    تُستخدم لرسم خط اتجاه السعر عبر الزمن لكل صنف على حدة.
    """
    _get_session_or_403(db, session_id, current_user)

    auctions = (
        db.query(Auction)
        .filter(Auction.session_id == session_id, Auction.final_price.isnot(None))
        .order_by(Auction.started_at.asc())
        .all()
    )

    return {
        "session_id": session_id,
        "points": [
            {
                "product_name": a.product_name,
                "price": float(a.final_price),
                "started_at": a.started_at.isoformat() if a.started_at else None,
            }
            for a in auctions
        ],
    }
