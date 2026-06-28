"""
core/db_migrate.py — هجرات خفيفة idempotent تُشغَّل عند الإقلاع.

Base.metadata.create_all يُنشئ الجداول المفقودة فقط، ولا يضيف أعمدة لجدول
قائم. هذه الدالة تضيف أعمدة التحليل الغني إلى جدول auctions القائم في Supabase
عبر ADD COLUMN IF NOT EXISTS (آمنة، تُعاد بلا أثر جانبي).
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (اسم العمود، تعريفه SQL) — يطابق الأعمدة المضافة في models.Auction
_AUCTION_COLUMNS = [
    ("buyer_number", "varchar(50)"),
    ("seller_name", "varchar(200)"),
    ("winner", "varchar(200)"),
    ("opening_price", "numeric(14,3)"),
    ("currency", "varchar(8)"),
    ("bids", "jsonb"),
    ("confidence", "numeric(4,3)"),
    ("notes", "text"),
    ("transcript", "text"),
    ("analysis_status", "varchar(20)"),
    ("model_used", "varchar(50)"),
]


def run_lightweight_migrations(engine: Engine) -> None:
    """يضيف أعمدة التحليل الغني لجدول auctions إن لم تكن موجودة."""
    try:
        with engine.begin() as conn:
            for name, sql_type in _AUCTION_COLUMNS:
                conn.execute(text(
                    f'ALTER TABLE auctions ADD COLUMN IF NOT EXISTS {name} {sql_type}'
                ))
        logger.info("تمت هجرة أعمدة التحليل الغني (auctions).")
    except Exception as e:
        # لا نُسقط الإقلاع بسبب فشل هجرة — نسجّل ونكمل.
        logger.warning("تعذّرت الهجرة الخفيفة: %s", e)
