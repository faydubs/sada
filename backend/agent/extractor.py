"""
agent/extractor.py – استخراج بيانات المزاد من النص العربي
يعمل حالياً بـ fallback (كلمات مفتاحية + regex) بدون أي API خارجي.
لاحقاً: استبدال أو دمج مع Allam API لدقة أعلى.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# قوائم الكلمات المفتاحية
# ---------------------------------------------------------------------------

# أصناف التمر الشائعة في السوق السعودي
# مُحدَّثة من auction_samples.json (395 جملة حقيقية) — رُتِّبت الأطول أولاً
# لتفادي تطابق جزئي خاطئ (مثل "سكري" يطابق قبل "سكري جالكسي")
KNOWN_PRODUCTS = sorted([
    "سكري جالكسي", "نبتة سيف", "نبتة علي",
    "سكري", "خلاص", "صقعي", "مجدول", "برحي", "برني",
    "خضري", "عجوة", "عنبرة", "رشودية", "روثانة", "مكتومي",
    "مبروم", "صفاوي", "صفري", "شقراء", "شيشي", "رزيز",
    "حوشانه", "حلوة", "مشروك",
], key=len, reverse=True)

# كلمات تدل على افتتاح المزاد (تُطابَق في أي مكان بالجملة، مو بس البداية)
OPEN_KEYWORDS = [
    "نفتح", "نبدأ", "افتتاح", "نفتتح", "أول سعر", "السعر الافتتاحي",
    "البداية من", "البداية", "السعر يبدأ", "نفتح السوم", "نفتح المزاد",
]

# كلمات تدل على إغلاق/بيع
CLOSE_KEYWORDS = ["بيع", "تم البيع", "خلاص بيع", "آخر نداء", "مرة أولى مرة ثانية", "انتهى"]

# وحدات القياس الشائعة
UNITS = ["كيلو", "كجم", "صندوق", "كرتون", "طن", "كيس"]

# كلمات الأرقام العربية الشائعة (للأسعار المنطوقة بدون أرقام)
# تشمل صيغ عامية شائعة: "مية" (=مئة)، "ميتين" (=مئتين)، "عشره" بتاء مربوطة
WORD_NUMBERS = {
    "صفر": 0, "واحد": 1, "اثنين": 2, "ثلاثة": 3, "أربعة": 4, "اربعة": 4,
    "خمسة": 5, "ستة": 6, "سبعة": 7, "ثمانية": 8, "تسعة": 9,
    "عشرة": 10, "عشره": 10, "عشرين": 20, "ثلاثين": 30, "أربعين": 40, "اربعين": 40,
    "خمسين": 50, "ستين": 60, "سبعين": 70, "ثمانين": 80, "تسعين": 90,
    "مئة": 100, "مائة": 100, "مية": 100, "مئتين": 200, "مائتين": 200, "ميتين": 200,
    "ألف": 1000, "الف": 1000,
}


def _words_to_number(text: str) -> Optional[float]:
    """
    حوّل أرقاماً مكتوبة بالحروف العربية إلى رقم.
    يدعم: "خمسين"=50، "مية وعشرين"=120، وصيغة العقود المركبة
    "ثلاثة عشر"=13 (الآحاد قبل كلمة عشر بدون واو تعني +10 مو ضرب).
    """
    total = 0
    found_any = False

    parts = re.split(r"\s*و\s*", text)
    for part in parts:
        words = [w.strip("،.") for w in part.strip().split()]

        # صيغة "ثلاثة عشر" / "خمسة عشر" = العدد + 10 (وليس عدّين منفصلين)
        if len(words) == 2 and words[1] in ("عشر", "عشرة", "عشره") and words[0] in WORD_NUMBERS:
            ones = WORD_NUMBERS[words[0]]
            if ones < 10:  # تأكد إنه آحاد (واحد..تسعة) مو عدد كبير
                total += ones + 10
                found_any = True
                continue

        for word in words:
            if word in WORD_NUMBERS:
                total += WORD_NUMBERS[word]
                found_any = True

    return total if found_any else None


# ---------------------------------------------------------------------------
# دوال استخراج فرعية
# ---------------------------------------------------------------------------

def _extract_product(text: str) -> Optional[str]:
    """
    دوّر على أقرب اسم صنف تمر معروف داخل النص.
    عند تطابق أكثر من صنف، يُفضَّل الصنف الذي يظهر أولاً في الجملة
    (الدلال عادة يذكر الصنف الرئيسي أولاً، وأي ذكر لاحق غالباً وصف ثانوي
    كاسم منطقة يشبه صنفاً آخر، مثل "صقعي شقراء" = صنف صقعي من منطقة شقراء).
    """
    best_match = None
    best_position = len(text) + 1

    for product in KNOWN_PRODUCTS:
        idx = text.find(product)
        if idx != -1 and idx < best_position:
            best_position = idx
            best_match = product

    return best_match


def _extract_price(text: str) -> Optional[float]:
    """
    استخرج السعر من النص. يجرّب أولاً الأرقام الرقمية (50، ٥٠)،
    وإذا ما لقى شيء يجرّب الأرقام المكتوبة بالحروف (خمسين، مئة وعشرين).
    """
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    translation = str.maketrans(arabic_digits, "0123456789")
    normalized = text.translate(translation)

    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ريال|رس|sar)?", normalized, re.IGNORECASE)
    if match:
        return float(match.group(1))

    # لا يوجد رقم صريح → جرّب الأرقام المنطوقة بالحروف
    # افصل حرف الجر "ب" الملتصق بأول كلمة (بخمسين → ب + خمسين)
    spaced = re.sub(r"\bب([أ-ي])", r"ب \1", text)

    # خذ من بعد "ب" إلى قبل "ريال"/"رس" أو نهاية الجملة
    price_phrase_match = re.search(r"ب\s+([\w\s]+?)(?:\s*(?:ريال|رس)\b|$)", spaced)
    search_zone = price_phrase_match.group(1) if price_phrase_match else text

    word_price = _words_to_number(search_zone)
    return word_price


def _extract_unit(text: str) -> Optional[str]:
    """دوّر على وحدة القياس المذكورة"""
    for unit in UNITS:
        if unit in text:
            return unit
    return None


def _extract_action(text: str) -> str:
    """
    حدد نوع الحدث: افتتاح / جارٍ / إغلاق

    الترتيب مهم: نتحقق من "افتتاح" أولاً لأن جمل الافتتاح أحياناً
    تحتوي صدفة على كلمات قريبة من الإغلاق. كلمة "بيع" وحدها مو كافية
    للحكم بإغلاق إذا الجملة فيها أيضاً مؤشر بيع مستقبلي مثل "مهب بعيد"
    أو "قريب" (يعني البيع لسا ما تم).
    """
    for kw in OPEN_KEYWORDS:
        if kw in text:
            return "افتتاح"

    # عبارات تنفي تمام البيع رغم وجود كلمة "بيع" بالجملة
    not_yet_sold = ["مهب بعيد", "مهوب بعيد", "بعيد عن", "قريب يا", "البيع قريب"]
    if any(p in text for p in not_yet_sold):
        return "جارٍ"

    for kw in CLOSE_KEYWORDS:
        if kw in text:
            return "إغلاق"

    return "جارٍ"


# ---------------------------------------------------------------------------
# استخراج الكمية
# ---------------------------------------------------------------------------

def _extract_quantity(text: str) -> float | None:
    """
    استخرج الكمية من جمل مثل:
    - عشرين صندوق
    - 15 كيلو
    """
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    translation = str.maketrans(arabic_digits, "0123456789")
    normalized = text.translate(translation)

    unit_pattern = "|".join(UNITS)
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:" + unit_pattern + r")",
        normalized
    )

    if match:
        return float(match.group(1))

    word_qty = _words_to_number(text)
    return word_qty


# ---------------------------------------------------------------------------
# الدالة الرئيسية
# ---------------------------------------------------------------------------

def extract_auction_data(text: str) -> dict:
    """
    استخرج بيانات المزاد المنظَّمة من نص عربي خام.

    Args:
        text: النص الناتج من Whisper

    Returns:
        {
            "status": "ok" | "low_confidence" | "invalid_input",  # عقد الـ Skill
            "product": اسم الصنف أو None,
            "price": السعر كرقم أو None,
            "unit": وحدة القياس أو None,
            "action": "افتتاح" | "جارٍ" | "إغلاق",
            "raw_text": النص الأصلي,
            "quantity": الكمية كرقم أو None,
            "confidence": "low" | "medium" | "high"  (تقدير تقريبي حسب اكتمال البيانات)
        }
    """
    # ── (1) Input validation — نص فارغ يرجع status لا استثناء (قانون Skill #2)
    if not text or not text.strip():
        return {
            "status": "invalid_input",
            "product": None, "price": None, "unit": None,
            "action": "جارٍ", "raw_text": text or "",
            "quantity": None, "confidence": "low",
        }

    product = _extract_product(text)
    price = _extract_price(text)
    unit = _extract_unit(text)
    action = _extract_action(text)
    quantity = _extract_quantity(text)

    # تقدير ثقة بسيط: كل ما زادت الحقول المُستخرَجة زادت الثقة
    found_fields = sum(1 for v in [product, price, unit] if v is not None)
    if found_fields >= 3:
        confidence = "high"
    elif found_fields >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    # status يتبع الثقة: low ⟶ low_confidence (يسمح للوكيل بالتوجيه عليه)
    status = "low_confidence" if confidence == "low" else "ok"

    return {
        "status": status,
        "product": product,
        "price": price,
        "unit": unit,
        "action": action,
        "raw_text": text,
        "quantity": quantity,
        "confidence": confidence,
    }


if __name__ == "__main__":
    import sys
    import json

    test_text = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "بسم الله نبدأ مزاد التمر السكري الكيلو بخمسين ريال"
    )

    result = extract_auction_data(test_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))

