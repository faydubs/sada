# -*- coding: utf-8 -*-
"""
seed_regions.py — مرّة واحدة:
  1) يضيف عمود users.region إن لم يكن موجوداً (الجدول قائم في Supabase أصلاً).
  2) يوزّع المناطق على الدلّالين الذين لا منطقة لهم (round-robin على ١٣ منطقة).

التشغيل:  .venv\Scripts\python.exe seed_regions.py
"""
from sqlalchemy import text

from core.database import engine, SessionLocal
from core.regions import REGION_NAMES_AR
from models.models import User, UserRole

# 1) أضِف العمود إن لم يوجد
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS region varchar(50)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_region ON users (region)"))

# 2) وزّع المناطق على الدلّالين بلا منطقة
db = SessionLocal()
try:
    dallals = db.query(User).filter(User.role == UserRole.dallal).order_by(User.id.asc()).all()
    assigned = 0
    for i, u in enumerate(dallals):
        if not u.region:
            u.region = REGION_NAMES_AR[i % len(REGION_NAMES_AR)]
            assigned += 1
    db.commit()

    # ملخّص التوزيع
    from collections import Counter
    dist = Counter(u.region for u in dallals if u.region)
    print(f"✓ دلّالون: {len(dallals)} | عُيّنت مناطق جديدة لـ {assigned}")
    for region, n in dist.most_common():
        print(f"  - {region}: {n}")
finally:
    db.close()
