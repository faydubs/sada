# -*- coding: utf-8 -*-
"""
seed_demo_data.py — بيانات وهمية لتنشيط الموقع (عرض/تجربة).

يضيف لكل دلّال عدّة جلسات موزّعة على آخر ~6 أشهر، وكل جلسة فيها مزادات
مغلقة بأصناف تمور واقعية وأسعار ومشترين وتواريخ — حتى تمتلئ لوحات
التحليلات، خريطة المناطق، التقارير، ونظرة المسؤول ببيانات حيّة.

التشغيل:
    .venv\\Scripts\\python.exe seed_demo_data.py
    .venv\\Scripts\\python.exe seed_demo_data.py --reset   # يحذف الجلسات والمزادات أولاً

آمن لإعادة التشغيل: يتخطّى الدلّالين الذين لديهم جلسات كثيرة أصلاً
(إلا مع --reset). لا يلمس حسابات المستخدمين.
"""
import argparse
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# كونسول ويندوز قد يكون cp1252 فيفشل عند طباعة العربية/الرموز — أجبره على UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.database import SessionLocal
from models.models import (
    Auction,
    AuctionStatus,
    Session as SessionModel,
    SessionStatus,
    User,
    UserRole,
)

# بذرة ثابتة → نتائج قابلة للتكرار
random.seed(2026)

# ── أصناف تمور سعودية واقعية: (الاسم، الوحدة، نطاق سعر اللوت بالريال)
PRODUCTS = [
    ("سكري",        "كرتون",  (70, 180)),
    ("عجوة المدينة", "كيلو",   (90, 260)),
    ("صقعي",        "كرتون",  (60, 150)),
    ("خلاص",        "صندوق",  (80, 200)),
    ("برحي",        "صندوق",  (40, 120)),
    ("مجدول جامبو",  "كرتون",  (180, 420)),
    ("خضري",        "كيس",    (25, 70)),
    ("صفري",        "كرتون",  (50, 130)),
    ("روثانة",      "صندوق",  (70, 170)),
    ("نبتة علي",     "كرتون",  (90, 210)),
    ("مبروم",       "كيلو",   (55, 140)),
    ("عنبرة",       "كرتون",  (150, 380)),
    ("رشودية",      "كيس",    (30, 85)),
    ("شيشي",        "صندوق",  (45, 110)),
]

# ── أسماء مشترين / تجّار واقعية
BUYERS = [
    "أبو فهد", "مؤسسة الرواد للتمور", "أبو سلطان", "تجارة الديرة", "أبو ناصر",
    "شركة بريدة الزراعية", "أبو خالد", "حمد العتيبي", "مزارع النخبة", "أبو يوسف",
    "سعد القحطاني", "بيت التمور الفاخر", "أبو تركي", "ناصر الدوسري", "أبو محمد",
    "مجموعة الواحة", "عبدالله الشمري", "أبو عبدالعزيز", "تموين الجزيرة", "أبو ماجد",
]


def daterange_back(n_days_max: int) -> datetime:
    """تاريخ عشوائي خلال آخر n_days_max يوماً (مع وقت نهاري معقول)."""
    days_ago = random.randint(0, n_days_max)
    base = datetime.utcnow() - timedelta(days=days_ago)
    return base.replace(
        hour=random.randint(16, 22),
        minute=random.randint(0, 59),
        second=0,
        microsecond=0,
    )


def make_auctions_for_session(session: SessionModel, when: datetime) -> Decimal:
    """ينشئ مزادات لجلسة ويعيد مجموع الإيراد."""
    n = random.randint(6, 14)
    total = Decimal("0")
    t = when
    for _ in range(n):
        name, unit, (lo, hi) = random.choice(PRODUCTS)
        qty = Decimal(str(random.choice([1, 1, 2, 2, 3, 5, 10])))
        price = Decimal(str(round(random.uniform(lo, hi), 0)))
        t = t + timedelta(minutes=random.randint(3, 12))
        closed_at = t + timedelta(minutes=random.randint(1, 4))
        auction = Auction(
            session_id=session.id,
            product_name=name,
            quantity=qty,
            unit=unit,
            final_price=price,
            buyer_name=random.choice(BUYERS),
            started_at=t,
            closed_at=closed_at,
            status=AuctionStatus.closed,
        )
        session.auctions.append(auction)
        total += price
    return total


def reset_demo(db):
    """يحذف كل الجلسات والمزادات (المزادات تُحذف تلقائياً عبر cascade)."""
    n_auctions = db.query(Auction).count()
    n_sessions = db.query(SessionModel).count()
    db.query(Auction).delete()
    db.query(SessionModel).delete()
    db.commit()
    print(f"🗑️  حُذف {n_sessions} جلسة و {n_auctions} مزاد.")


def main(reset: bool):
    db = SessionLocal()
    try:
        if reset:
            reset_demo(db)

        dallals = (
            db.query(User)
            .filter(User.role == UserRole.dallal)
            .order_by(User.id.asc())
            .all()
        )
        if not dallals:
            print("⚠️  لا يوجد دلّالون. شغّل seed أولاً لإنشاء المستخدمين.")
            return

        total_sessions = 0
        total_auctions = 0
        total_revenue = Decimal("0")

        for d in dallals:
            existing = (
                db.query(SessionModel)
                .filter(SessionModel.dallal_id == d.id)
                .count()
            )
            # تخطّى من لديه بيانات وافرة أصلاً (إلا بعد reset)
            if existing >= 4 and not reset:
                continue

            n_sessions = random.randint(4, 8)
            for _ in range(n_sessions):
                when = daterange_back(180)
                session = SessionModel(
                    dallal_id=d.id,
                    date=when,
                    status=SessionStatus.closed,
                    total_revenue=Decimal("0"),
                )
                db.add(session)
                db.flush()  # نحتاج session.id
                revenue = make_auctions_for_session(session, when)
                session.total_revenue = revenue
                total_sessions += 1
                total_auctions += len(session.auctions)
                total_revenue += revenue

            # اجعل آخر جلسة لبعض الدلّالين "نشطة" لإحياء اللوحة الحية
            if random.random() < 0.4:
                last = (
                    db.query(SessionModel)
                    .filter(SessionModel.dallal_id == d.id)
                    .order_by(SessionModel.date.desc())
                    .first()
                )
                if last:
                    last.status = SessionStatus.active

        db.commit()

        print("✅ تمت إضافة البيانات الوهمية:")
        print(f"   • جلسات جديدة : {total_sessions}")
        print(f"   • مزادات جديدة: {total_auctions}")
        print(f"   • إجمالي الإيراد المُضاف: {float(total_revenue):,.0f} ريال")
        print("   • إجمالي القاعدة الآن:")
        print(f"       users    = {db.query(User).count()}")
        print(f"       sessions = {db.query(SessionModel).count()}")
        print(f"       auctions = {db.query(Auction).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="احذف كل الجلسات والمزادات قبل الإضافة",
    )
    args = parser.parse_args()
    main(reset=args.reset)
