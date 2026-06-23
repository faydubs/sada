"""
agent/gemini_parser.py – تحليل نص المزاد بـ Gemini لرفع دقة الاستخراج
يُستدعى بعد Whisper كبديل ذكي لـ extractor.py عند توفر GEMINI_API_KEY.
إذا لم يتوفر المفتاح أو فشل الاتصال → يرجع None وخط المعالجة يكمل بـ extractor.py.
"""

import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── كلمات الإغلاق نكتشفها محلياً قبل إرسال Gemini (تُضاف للـ prompt كإشارة)
CLOSING_KEYWORDS = [
    "حراج واحد", "حراج اثنين", "حراج ثلاثة", "حراج ثلاثه",
    "تم البيع", "تمت البيعه", "تمت البيعة",
    "بيعت", "مباع", "مباعة", "مبروك", "الله يبارك",
    "تكتمل", "رست", "خلاص", "راحت",
]

# ── تصحيحات أخطاء Whisper الشائعة قبل الإرسال لـ Gemini
WHISPER_FIXES = {
    "تماميه": "ثمانميه", "تمامية": "ثمانميه",
    "تمانيه": "ثمانيه", "تمانية": "ثمانيه", "تماني": "ثماني",
    "ثمنميه": "ثمانميه", "ثمنيه": "ثمانيه",
    "حرج": "حراج", "حراچ": "حراج",
    "حراج دين": "حراج اثنين", "حرج دين": "حراج اثنين",
    "كرتونه": "كرتون", "كرتونة": "كرتون",
    "صناديق": "صندوق", "كراتين": "كرتون",
}

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _normalize(text: str) -> str:
    """تطبيع النص: أرقام عربية → إنجليزية + تصحيح أخطاء Whisper الشائعة"""
    text = text.translate(ARABIC_DIGITS)
    for wrong, right in WHISPER_FIXES.items():
        text = text.replace(wrong, right)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_closing_keywords(normalized: str) -> list[str]:
    """اكتشف كلمات الإغلاق محلياً"""
    found = []
    for kw in CLOSING_KEYWORDS:
        kw_norm = kw.translate(ARABIC_DIGITS)
        if kw_norm in normalized:
            found.append(kw)
    return found


def parse_with_gemini(transcript: str, gemini_api_key: str) -> Optional[dict]:
    """
    أرسل نص المزاد لـ Gemini واستخرج البيانات المنظَّمة.

    Args:
        transcript: النص الخام من Whisper
        gemini_api_key: مفتاح Gemini API

    Returns:
        dict مع الحقول المستخرجة، أو None عند الفشل
    """
    try:
        from google import genai
    except ImportError:
        logger.warning("مكتبة google-genai غير مثبتة — استخدام extractor.py")
        return None

    normalized = _normalize(transcript)
    detected_closing = _detect_closing_keywords(normalized)

    prompt = f"""
أنت محلل مزادات تمر في السوق السعودي. عندك تفريغ صوتي خام من Whisper لمزاد تمر.
التفريغ قد يحتوي أخطاء، تكرار، كلمات غير مفهومة، أو أرقام مكتوبة بشكل خاطئ.

المطلوب: استخرج بيانات المزاد كـ JSON منظم فقط. لا تكتب أي كلام خارج الـ JSON.

قواعد المزاد:
1. سعر المزاد لا ينقص أبدًا — التسلسل تصاعدي أو ثابت.
2. احذف التكرارات المتتالية (300، 300، 300) → 300 واحدة.
3. لا تخترع رقم غير موجود أو غير واضح من السياق.
4. لا تعتبر "مزاد رقم واحد" سعرًا — هذا رقم مزاد.
5. استخرج: سعر الافتتاح، السعر النهائي، هل تم البيع، الصنف، الكمية.

أخطاء Whisper الشائعة:
- تمامية/تمانية/ثمنمية → ثمانمية (=800)
- حرج → حراج | مية/مائة → 100 | ألف → 1000
- ثلاثمية/ثلاثمائة → 300 | خمسمية → 500 | سبعمية → 700
- خمسين → 50 | سبعين → 70 | تسعين → 90

أصناف تمر شائعة: سكري، خلاص، صقعي، مجدول، برحي، برني، خضري، عجوة، عنبرة،
رشودية، روثانة، مبروم، صفاوي، شيشي، رزيز، حلوة، مشروك، نبتة علي، سكري جالكسي.

وحدات الكمية: كرتون، كراتين، صندوق، صناديق، كيس، أكياس، كيلو، طن، عبوة.

عبارات إغلاق البيع (رقم قبلها = السعر النهائي):
حراج واحد → حراج اثنين → حراج ثلاثة = تم البيع.
أيضاً: تم البيع، بيعت، مباع، مبروك، الله يبارك، رست، خلاص.

إشارات إغلاق مكتشفة مسبقاً: {json.dumps(detected_closing, ensure_ascii=False)}

التفريغ الأصلي: {transcript}
التفريغ بعد التطبيع: {normalized}

أخرج JSON فقط بالصيغة التالية بالضبط:
{{
  "opening_price": null,
  "final_price": null,
  "highest_price": null,
  "sold_status": "sold|unknown",
  "confidence": "low|medium|high",
  "product": null,
  "quantity_value": null,
  "quantity_unit": null,
  "cleaned_bids_sequence": [],
  "closing_keywords_detected": [],
  "closing_evidence": "الدليل النصي أو غير واضح",
  "short_report": "تقرير مختصر بالعربي"
}}
"""

    try:
        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning("Gemini لم يرجع JSON صالح")
            return None

        result = json.loads(json_match.group(0))
        result = _post_validate(result, detected_closing)
        return result

    except Exception as e:
        logger.warning(f"Gemini فشل: {e} — الرجوع لـ extractor.py")
        return None


def _post_validate(result: dict, detected_closing: list[str]) -> dict:
    """
    حماية بعد Gemini:
    - يمنع نزول السعر
    - يحذف التكرارات
    - يرفع حالة البيع لو كانت unknown مع وجود كلمات إغلاق
    - يعبّي opening/final/highest من التسلسل إذا كانت فارغة
    """
    bids = result.get("cleaned_bids_sequence", [])
    bids = _smooth_sequence([b for b in bids if isinstance(b, (int, float))])
    result["cleaned_bids_sequence"] = bids

    if bids:
        if result.get("opening_price") is None:
            result["opening_price"] = bids[0]
        if result.get("final_price") is None:
            result["final_price"] = bids[-1]
        if result.get("highest_price") is None:
            result["highest_price"] = max(bids)

    if not result.get("closing_keywords_detected"):
        result["closing_keywords_detected"] = detected_closing

    if detected_closing and result.get("sold_status") == "unknown":
        result["sold_status"] = "sold"

    if (
        result.get("sold_status") == "sold"
        and detected_closing
        and result.get("final_price") is not None
    ):
        result["confidence"] = "high"
    elif (
        result.get("sold_status") == "sold"
        and result.get("final_price") is not None
        and result.get("confidence") in (None, "low")
    ):
        result["confidence"] = "medium"

    # نظّف quantity_unit
    unit = result.get("quantity_unit")
    if unit:
        unit_norm = unit.translate(ARABIC_DIGITS)
        unit_map = {
            "كراتين": "كرتون", "كرتونه": "كرتون", "كرتونة": "كرتون",
            "صناديق": "صندوق", "اكياس": "كيس", "أكياس": "كيس",
            "عبوات": "عبوة",
        }
        result["quantity_unit"] = unit_map.get(unit_norm, unit)

    # حوّل quantity_value لـ int إذا ممكن
    try:
        if result.get("quantity_value") is not None:
            result["quantity_value"] = int(result["quantity_value"])
    except (TypeError, ValueError):
        pass

    return result


def _smooth_sequence(numbers: list) -> list:
    """احذف التكرارات المتتالية ومنع نزول السعر"""
    if not numbers:
        return numbers

    # احذف التكرارات
    deduped = []
    for n in numbers:
        if not deduped or deduped[-1] != n:
            deduped.append(n)

    # منع نزول السعر
    result = []
    for n in deduped:
        if not result or n >= result[-1]:
            result.append(n)

    return result


def gemini_to_extracted(gemini_result: dict) -> dict:
    """
    حوّل نتيجة Gemini لنفس صيغة extractor.py
    حتى يكون pipeline.py متوافق مع الاثنين.
    """
    sold = gemini_result.get("sold_status") == "sold"
    bids = gemini_result.get("cleaned_bids_sequence", [])

    if sold:
        action = "إغلاق"
    elif bids and len(bids) > 1:
        action = "جارٍ"
    else:
        action = "افتتاح"

    # status يتبع الثقة (عقد الـ Skill) — يستخدمه الوكيل في نقطة قرار التوجيه
    confidence = gemini_result.get("confidence", "low")
    status = "ok" if confidence in ("high", "medium") else "low_confidence"

    return {
        "status": status,
        "product": gemini_result.get("product"),
        "price": gemini_result.get("final_price"),
        "opening_price": gemini_result.get("opening_price"),
        "highest_price": gemini_result.get("highest_price"),
        "unit": gemini_result.get("quantity_unit"),
        "quantity_value": gemini_result.get("quantity_value"),
        "action": action,
        "sold_status": gemini_result.get("sold_status", "unknown"),
        "confidence": gemini_result.get("confidence", "low"),
        "closing_evidence": gemini_result.get("closing_evidence"),
        "closing_keywords": gemini_result.get("closing_keywords_detected", []),
        "bids_sequence": gemini_result.get("cleaned_bids_sequence", []),
        "short_report": gemini_result.get("short_report"),
        "source": "gemini",
    }