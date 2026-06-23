"""
api/reports.py – تقارير جلسة المزاد: عرض تفصيلي + تصدير CSV
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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


@router.get("/trends")
def get_report(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تقرير تفصيلي بكل مزادات الجلسة — أساس شاشة "التقارير" قبل التصدير.
    """
    session = _get_session_or_403(db, session_id, current_user)

    auctions = (
        db.query(Auction)
        .filter(Auction.session_id == session_id)
        .order_by(Auction.started_at.asc())
        .all()
    )

    rows = [
        {
            "auction_id": a.id,
            "product_name": a.product_name,
            "quantity": float(a.quantity),
            "unit": a.unit,
            "final_price": float(a.final_price) if a.final_price is not None else None,
            "buyer_name": a.buyer_name,
            "status": a.status.value,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "closed_at": a.closed_at.isoformat() if a.closed_at else None,
        }
        for a in auctions
    ]

    return {
        "session_id": session_id,
        "session_status": session.status.value,
        "total_revenue": float(session.total_revenue),
        "auctions_count": len(rows),
        "auctions": rows,
    }


@router.get("/export")
def export_report(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    صدّر مزادات الجلسة كملف CSV قابل للتنزيل والفتح في Excel.
    """
    _get_session_or_403(db, session_id, current_user)

    auctions = (
        db.query(Auction)
        .filter(Auction.session_id == session_id)
        .order_by(Auction.started_at.asc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "auction_id", "product_name", "quantity", "unit",
        "final_price", "buyer_name", "status", "started_at", "closed_at",
    ])
    for a in auctions:
        writer.writerow([
            a.id,
            a.product_name,
            float(a.quantity),
            a.unit,
            float(a.final_price) if a.final_price is not None else "",
            a.buyer_name or "",
            a.status.value,
            a.started_at.isoformat() if a.started_at else "",
            a.closed_at.isoformat() if a.closed_at else "",
        ])

    buffer.seek(0)
    filename = f"session_{session_id}_report.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
