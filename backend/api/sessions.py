"""
api/sessions.py – إدارة جلسات المزادات لمشروع صدى التمر
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from api.auth import get_current_user
from core.database import get_db
from core.websocket_manager import manager
from models.models import Auction, User
from models.models import Session as SessionModel
from models.models import SessionStatus
from schemas.schemas import SessionCreate, SessionResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /start
# ---------------------------------------------------------------------------

@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    أنشئ جلسة مزاد جديدة للدلّال.
    - dallal_id في الـ body يجب أن يطابق المستخدم الحالي (إلا إذا كان admin).
    """
    if current_user.role.value != "admin" and data.dallal_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك إنشاء جلسة لدلّال آخر",
        )

    # أغلق أي جلسة مفتوحة سابقة لنفس الدلّال تلقائياً بدل رفض البدء (تجربة أسلس
    # — لا مزيد من رسالة "يوجد جلسة مفتوحة بالفعل"). نحسب إيرادها قبل إغلاقها.
    open_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.dallal_id == data.dallal_id,
            SessionModel.status == SessionStatus.active,
        )
        .all()
    )
    for prev in open_sessions:
        prev_total = (
            db.query(func.sum(Auction.final_price))
            .filter(Auction.session_id == prev.id, Auction.final_price.isnot(None))
            .scalar()
        ) or 0
        prev.status = SessionStatus.closed
        prev.total_revenue = prev_total

    session = SessionModel(
        dallal_id=data.dallal_id,
        status=SessionStatus.active,
        total_revenue=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# POST /end
# ---------------------------------------------------------------------------

@router.post("/end", response_model=SessionResponse)
async def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    أغلق الجلسة وأحسب total_revenue من مجموع final_price لمزاداتها.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الجلسة غير موجودة",
        )

    if current_user.role.value != "admin" and session.dallal_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="لا يمكنك إغلاق جلسة دلّال آخر",
        )

    if session.status == SessionStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="الجلسة مغلقة بالفعل",
        )

    total = (
        db.query(func.sum(Auction.final_price))
        .filter(
            Auction.session_id == session_id,
            Auction.final_price.isnot(None),
        )
        .scalar()
    ) or 0

    session.status        = SessionStatus.closed
    session.total_revenue = total
    db.commit()
    db.refresh(session)

    # ── أبلغ كل المتصلين بهذه الجلسة أنها أُغلقت
    await manager.broadcast(session_id, {
        "type": "session_closed",
        "session_id": session_id,
        "total_revenue": float(total),
    })

    return session


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    أرجع كل جلسات الدلّال الحالي. الـ admin يشوف جلسات الجميع.
    """
    query = db.query(SessionModel)

    if current_user.role.value != "admin":
        query = query.filter(SessionModel.dallal_id == current_user.id)

    return query.order_by(SessionModel.date.desc()).all()