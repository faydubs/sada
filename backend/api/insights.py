"""
api/insights.py — تحليلات تراكمية عبر كل الجلسات (لا تقتصر على جلسة واحدة).

- /me                     : تحليلات مبيعات الدلّال الحالي مدى الحياة (لتبويب "مبيعاتي" + PDF).
- /admin/overview         : مؤشرات عامة للمنصّة (للمسؤول).
- /admin/regions          : تجميع حسب المنطقة + المجموعات الجغرافية (لخريطة المسؤول).
- /admin/regions/{region} : تفاصيل منطقة + دلّالوها ومبيعاتهم.
- /admin/dallals          : كل الدلّالين مع مبيعاتهم ومنطقتهم (للبحث في لوحة المسؤول).
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user, get_current_admin
from core.database import get_db
from core.regions import SAUDI_REGIONS, group_of, key_of, GROUPS
from models.models import Auction, User, UserRole
from models.models import Session as SessionModel

router = APIRouter()


# ---------------------------------------------------------------------------
# أدوات تجميع مشتركة
# ---------------------------------------------------------------------------

def _summarize(auctions: list) -> dict:
    prices = [float(a.final_price) for a in auctions if a.final_price is not None]
    total = sum(prices)
    return {
        "auctions_count": len(auctions),
        "closed_count": sum(1 for a in auctions if a.status.value == "closed"),
        "total_revenue": round(total, 2),
        "avg_price": round(total / len(prices), 2) if prices else None,
        "top_price": max(prices) if prices else None,
        "unique_buyers": len({a.buyer_name for a in auctions if a.buyer_name}),
    }


def _by_product(auctions: list) -> list:
    d = defaultdict(lambda: {"count": 0, "revenue": 0.0, "prices": []})
    for a in auctions:
        e = d[a.product_name]
        e["count"] += 1
        if a.final_price is not None:
            p = float(a.final_price)
            e["revenue"] += p
            e["prices"].append(p)
    out = [
        {
            "product_name": k,
            "auctions_count": v["count"],
            "revenue": round(v["revenue"], 2),
            "avg_price": round(sum(v["prices"]) / len(v["prices"]), 2) if v["prices"] else None,
        }
        for k, v in d.items()
    ]
    out.sort(key=lambda x: x["revenue"], reverse=True)
    return out


def _monthly(auctions: list, n: int = 6) -> list:
    d = defaultdict(lambda: {"revenue": 0.0, "count": 0})
    for a in auctions:
        if not a.started_at:
            continue
        key = a.started_at.strftime("%Y-%m")
        e = d[key]
        e["count"] += 1
        if a.final_price is not None:
            e["revenue"] += float(a.final_price)
    keys = sorted(d.keys())[-n:]
    return [{"month": k, "revenue": round(d[k]["revenue"], 2), "count": d[k]["count"]} for k in keys]


def _auction_dict(a) -> dict:
    return {
        "id": a.id,
        "product_name": a.product_name,
        "quantity": float(a.quantity) if a.quantity is not None else None,
        "unit": a.unit,
        "final_price": float(a.final_price) if a.final_price is not None else None,
        "buyer_name": a.buyer_name,
        "status": a.status.value,
        "started_at": a.started_at.isoformat() if a.started_at else None,
    }


def _auctions_for_dallal(db: Session, dallal_id: int) -> list:
    return (
        db.query(Auction)
        .join(SessionModel, Auction.session_id == SessionModel.id)
        .filter(SessionModel.dallal_id == dallal_id)
        .order_by(Auction.started_at.asc())
        .all()
    )


def _all_auctions_with_dallal(db: Session):
    """يرجع [(Auction, dallal_id), ...] لكل المزادات — لتجميعها حسب المنطقة."""
    return (
        db.query(Auction, SessionModel.dallal_id)
        .join(SessionModel, Auction.session_id == SessionModel.id)
        .order_by(Auction.started_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# الدلّال — مبيعاتي مدى الحياة
# ---------------------------------------------------------------------------

@router.get("/me")
def my_sales(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    auctions = _auctions_for_dallal(db, current_user.id)
    sessions_count = (
        db.query(SessionModel).filter(SessionModel.dallal_id == current_user.id).count()
    )
    return {
        "dallal": {
            "id": current_user.id,
            "username": current_user.username,
            "region": getattr(current_user, "region", None),
        },
        "summary": _summarize(auctions),
        "sessions_count": sessions_count,
        "by_product": _by_product(auctions),
        "monthly": _monthly(auctions),
        "recent": [_auction_dict(a) for a in reversed(auctions[-12:])],
    }


# ---------------------------------------------------------------------------
# المسؤول — مؤشرات عامة
# ---------------------------------------------------------------------------

@router.get("/admin/overview")
def admin_overview(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    dallals = db.query(User).filter(User.role == UserRole.dallal).all()
    rows = _all_auctions_with_dallal(db)
    auctions = [a for a, _ in rows]
    summary = _summarize(auctions)
    sessions_count = db.query(SessionModel).count()
    active_regions = len({u.region for u in dallals if u.region})
    return {
        "dallals_count": len(dallals),
        "sessions_count": sessions_count,
        "regions_active": active_regions,
        "regions_total": len(SAUDI_REGIONS),
        **summary,
        "by_product": _by_product(auctions)[:8],
        "monthly": _monthly(auctions),
    }


# ---------------------------------------------------------------------------
# المسؤول — تجميع حسب المنطقة (للخريطة)
# ---------------------------------------------------------------------------

@router.get("/admin/regions")
def admin_regions(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    dallals = db.query(User).filter(User.role == UserRole.dallal).all()
    region_of = {u.id: (u.region or "غير محدد") for u in dallals}
    dallals_per_region = defaultdict(int)
    for u in dallals:
        if u.region:
            dallals_per_region[u.region] += 1

    rows = _all_auctions_with_dallal(db)
    auctions_per_region = defaultdict(list)
    for a, dallal_id in rows:
        auctions_per_region[region_of.get(dallal_id, "غير محدد")].append(a)

    regions = []
    for r in SAUDI_REGIONS:
        ar = r["ar"]
        s = _summarize(auctions_per_region.get(ar, []))
        regions.append({
            "region": ar,
            "key": r["key"],
            "group": r["group"],
            "dallals_count": dallals_per_region.get(ar, 0),
            "auctions_count": s["auctions_count"],
            "total_revenue": s["total_revenue"],
            "avg_price": s["avg_price"],
        })

    # ملخّص حسب المجموعة الجغرافية
    groups = []
    for g in GROUPS:
        members = [x for x in regions if x["group"] == g]
        groups.append({
            "group": g,
            "regions_count": len(members),
            "dallals_count": sum(x["dallals_count"] for x in members),
            "auctions_count": sum(x["auctions_count"] for x in members),
            "total_revenue": round(sum(x["total_revenue"] for x in members), 2),
        })

    return {"regions": regions, "groups": groups}


@router.get("/admin/regions/{region}")
def admin_region_detail(
    region: str, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)
):
    dallals = db.query(User).filter(User.role == UserRole.dallal, User.region == region).all()
    if not any(r["ar"] == region for r in SAUDI_REGIONS):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="منطقة غير معروفة")

    dallal_ids = {u.id for u in dallals}
    rows = _all_auctions_with_dallal(db)
    region_auctions = [a for a, did in rows if did in dallal_ids]

    # ملخّص لكل دلّال في المنطقة
    per_dallal_auctions = defaultdict(list)
    for a, did in rows:
        if did in dallal_ids:
            per_dallal_auctions[did].append(a)

    dallals_out = []
    for u in dallals:
        s = _summarize(per_dallal_auctions.get(u.id, []))
        dallals_out.append({
            "id": u.id,
            "username": u.username,
            "auctions_count": s["auctions_count"],
            "total_revenue": s["total_revenue"],
            "avg_price": s["avg_price"],
        })
    dallals_out.sort(key=lambda x: x["total_revenue"], reverse=True)

    return {
        "region": region,
        "key": key_of(region),
        "group": group_of(region),
        "summary": _summarize(region_auctions),
        "dallals_count": len(dallals),
        "dallals": dallals_out,
        "by_product": _by_product(region_auctions),
        "monthly": _monthly(region_auctions),
    }


# ---------------------------------------------------------------------------
# المسؤول — كل الدلّالين (للبحث)
# ---------------------------------------------------------------------------

@router.get("/admin/dallals")
def admin_dallals(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    dallals = db.query(User).filter(User.role == UserRole.dallal).all()
    rows = _all_auctions_with_dallal(db)
    per_dallal = defaultdict(list)
    for a, did in rows:
        per_dallal[did].append(a)

    out = []
    for u in dallals:
        s = _summarize(per_dallal.get(u.id, []))
        out.append({
            "id": u.id,
            "username": u.username,
            "region": u.region or "غير محدد",
            "group": group_of(u.region) if u.region else "غير محدد",
            "voiceprint_registered": bool(u.voiceprint_path),
            "auctions_count": s["auctions_count"],
            "total_revenue": s["total_revenue"],
            "avg_price": s["avg_price"],
        })
    out.sort(key=lambda x: x["total_revenue"], reverse=True)
    return {"dallals": out}
