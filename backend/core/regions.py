"""
core/regions.py — مناطق السعودية الإدارية + تصنيفها لمجموعات جغرافية.

تُستخدم في:
- زرع المناطق للدلّالين (seed_regions.py) والتعيين التلقائي عند التسجيل.
- تجميع تحليلات المسؤول حسب المنطقة وحسب المجموعة.
- مطابقة أسماء المناطق مع خريطة GeoJSON في الواجهة (الحقل `key` بالإنجليزية).

ملاحظة: للسعودية ١٣ منطقة إدارية رسمية (نتبع التقسيم الرسمي).
"""

# key: اسم إنجليزي لمطابقة الخريطة · ar: الاسم العربي المخزَّن في users.region · group: المجموعة
SAUDI_REGIONS = [
    {"key": "Riyadh",          "ar": "الرياض",          "group": "الوسطى"},
    {"key": "Al-Qassim",       "ar": "القصيم",          "group": "الوسطى"},
    {"key": "Makkah",          "ar": "مكة المكرمة",     "group": "الغربية"},
    {"key": "Al-Madinah",      "ar": "المدينة المنورة", "group": "الغربية"},
    {"key": "Al-Bahah",        "ar": "الباحة",          "group": "الغربية"},
    {"key": "Eastern Province","ar": "المنطقة الشرقية", "group": "الشرقية"},
    {"key": "Asir",            "ar": "عسير",            "group": "الجنوبية"},
    {"key": "Jazan",           "ar": "جازان",           "group": "الجنوبية"},
    {"key": "Najran",          "ar": "نجران",           "group": "الجنوبية"},
    {"key": "Tabuk",           "ar": "تبوك",            "group": "الشمالية"},
    {"key": "Hail",            "ar": "حائل",            "group": "الشمالية"},
    {"key": "Northern Borders","ar": "الحدود الشمالية", "group": "الشمالية"},
    {"key": "Al-Jawf",         "ar": "الجوف",           "group": "الشمالية"},
]

REGION_NAMES_AR = [r["ar"] for r in SAUDI_REGIONS]
AR_TO_KEY = {r["ar"]: r["key"] for r in SAUDI_REGIONS}
AR_TO_GROUP = {r["ar"]: r["group"] for r in SAUDI_REGIONS}
GROUPS = ["الوسطى", "الغربية", "الشرقية", "الجنوبية", "الشمالية"]


def group_of(region_ar: str) -> str:
    return AR_TO_GROUP.get(region_ar, "غير محدد")


def key_of(region_ar: str) -> str:
    return AR_TO_KEY.get(region_ar, "")
