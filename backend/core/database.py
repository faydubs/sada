"""
database.py – إعداد الاتصال بقاعدة البيانات لمشروع صدى التمر.
"""


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings


DATABASE_URL = settings.DATABASE_URL 

class Base(DeclarativeBase):
    pass

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # يفحص الاتصال قبل الاستخدام ويعيد الاتصال إن كان ميتاً
    pool_recycle=280,        # يعيد تدوير الاتصال كل ~5 دقائق قبل أن يقتله Supabase بسبب الخمول
    pool_size=10,
    max_overflow=20,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
