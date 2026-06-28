"""
agent/analysis_schema.py — نموذج المجال الموحّد لتحليل مزاد التمر.

هذا هو "مصدر الحقيقة الواحد" لمخرجات تحليل المزاد: يُستخدم كـ
response_schema لـ Gemini (structured output)، وكنوع إرجاع موحّد لكل
المحلِّلات (Gemini صوت/نص + المستخرِج القديم)، وكأساس لأي تخزين لاحق.

كل الحقول التي قد لا تُستنتج بثقة افتراضها None — "أرجِع null بدل التخمين".
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AuctionStatusEnum(str, Enum):
    """حالة المزاد كما يفهمها المحلِّل (مستقلة عن AuctionStatus في قاعدة البيانات)."""
    open = "open"               # افتتاح / بداية السوم
    in_progress = "in_progress" # مزايدة جارية
    sold = "sold"               # تم البيع
    unsold = "unsold"           # انتهى بلا بيع
    unknown = "unknown"


class Bid(BaseModel):
    """مزايدة مفردة ضمن تسلسل المزاد."""
    price: float = Field(description="قيمة المزايدة بالعملة")
    bidder: Optional[str] = Field(default=None, description="اسم/وصف المزايد إن ذُكر، وإلا null")


class AuctionAnalysis(BaseModel):
    """
    النتيجة المنظَّمة الكاملة لتحليل مقطع مزاد تمر سعودي.
    تُملأ من Gemini (الصوت الأصلي أو النص)، أو من المستخرِج القديم كحل أخير.
    """
    # ── بيانات المزاد الأساسية ──
    product_type: Optional[str] = Field(default=None, description="نوع/صنف التمر (سكري، مجدول، عجوة…) أو null")
    seller_name: Optional[str] = Field(default=None, description="اسم البائع/صاحب البضاعة إن ذُكر، وإلا null")
    buyer_name: Optional[str] = Field(default=None, description="اسم المشتري الحالي/الأبرز إن ذُكر، وإلا null")
    buyer_number: Optional[str] = Field(default=None, description="رقم المشتري/المضرب إن ذُكر (مثل: المشتري رقم ٥)، وإلا null")
    winner: Optional[str] = Field(default=None, description="اسم الفائز بالمزاد عند البيع، وإلا null")

    # ── الأسعار ──
    opening_price: Optional[float] = Field(default=None, description="سعر الافتتاح/البداية أو null")
    final_price: Optional[float] = Field(default=None, description="السعر النهائي عند الإغلاق أو null")
    bids: list[Bid] = Field(default_factory=list, description="كل المزايدات المكتشفة بالترتيب الزمني التصاعدي")

    currency: Optional[str] = Field(default="SAR", description="رمز العملة، افتراضياً SAR")
    status: AuctionStatusEnum = Field(default=AuctionStatusEnum.unknown, description="حالة المزاد")

    # ── الكمية ──
    quantity: Optional[float] = Field(default=None, description="قيمة الكمية إن ذُكرت، وإلا null")
    unit: Optional[str] = Field(default=None, description="وحدة الكمية (كرتون، صندوق، كيلو…) أو null")

    # ── ميتاداتا التحليل ──
    confidence: float = Field(default=0.0, description="ثقة التحليل من 0.0 إلى 1.0")
    notes: Optional[str] = Field(default=None, description="ملاحظات/سياق إضافي مفيد، أو null")
    transcript: Optional[str] = Field(default=None, description="التفريغ النصي للمقطع (يملؤه Gemini عند تحليل الصوت)")
    language: Optional[str] = Field(default="ar", description="رمز اللغة المكتشفة")
    model_used: Optional[str] = Field(default=None, description="اسم المحلِّل/الموديل الذي أنتج هذه النتيجة")


# مخطط منفصل يُرسَل لـ Gemini كـ response_schema: نستبعد الحقول التي نملؤها
# نحن بأنفسنا (model_used) حتى لا يخمّنها الموديل.
class GeminiAuctionSchema(BaseModel):
    product_type: Optional[str] = None
    seller_name: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_number: Optional[str] = None
    winner: Optional[str] = None
    opening_price: Optional[float] = None
    final_price: Optional[float] = None
    bids: list[Bid] = Field(default_factory=list)
    currency: Optional[str] = "SAR"
    status: AuctionStatusEnum = AuctionStatusEnum.unknown
    quantity: Optional[float] = None
    unit: Optional[str] = None
    confidence: float = 0.0
    notes: Optional[str] = None
    transcript: Optional[str] = None
    language: Optional[str] = "ar"
