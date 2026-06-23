"""
tests/test_extractor.py – اختبارات agent/extractor.py
تغطي: استخراج الصنف/السعر/الوحدة/الفعل/الكمية، الأرقام المكتوبة بالحروف،
والتحقق من إصلاح خلل التعريف المكرر لـ extract_auction_data.
"""

import sys
from pathlib import Path

# اسمح بتشغيل pytest من جذر backend/ بدون الحاجة لتثبيت الحزمة
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.extractor import extract_auction_data, _extract_quantity, _words_to_number


# ---------------------------------------------------------------------------
# extract_auction_data – حالات واقعية من auction_samples.json
# ---------------------------------------------------------------------------

def test_open_auction_with_explicit_price():
    result = extract_auction_data(
        "بسم الله نفتح حراج الليلة على تمر السكري المعلّق من مزارع الرس، البداية من خمسة وثمانين ريال"
    )
    assert result["product"] == "سكري"
    assert result["price"] == 85
    assert result["action"] == "افتتاح"


def test_open_auction_with_quantity_unit():
    result = extract_auction_data(
        "يالله توكلنا، نفتح السوم على عنبرة العُلا الفاخرة، كرتون مرتب ونظيف، البداية من مية وستين"
    )
    assert result["product"] == "عنبرة"
    assert result["price"] == 160
    assert result["unit"] == "كرتون"
    assert result["action"] == "افتتاح"


def test_close_auction_sold():
    result = extract_auction_data("تم البيع على المجدول بمية وعشرين ريال")
    assert result["action"] == "إغلاق"
    assert result["product"] == "مجدول"


def test_not_yet_sold_overrides_close_keyword():
    # "بيع" موجودة لكن "مهب بعيد" تنفي تمام البيع → يجب أن تبقى "جارٍ" وليست "إغلاق"
    result = extract_auction_data("سعر البيع مهب بعيد عن المية")
    assert result["action"] == "جارٍ"


def test_no_keywords_defaults_to_ongoing():
    result = extract_auction_data("الجو حلو اليوم في السوق")
    assert result["action"] == "جارٍ"
    assert result["product"] is None
    assert result["price"] is None


def test_numeric_price_with_arabic_digits():
    result = extract_auction_data("السكري بـ ٧٥ ريال للكيلو")
    assert result["price"] == 75
    assert result["unit"] == "كيلو"


def test_confidence_high_when_three_fields_found():
    result = extract_auction_data("نفتح على الخلاص كيلو بخمسين ريال")
    assert result["confidence"] == "high"


def test_confidence_low_when_nothing_found():
    result = extract_auction_data("كلام عام بدون أي بيانات مزاد")
    assert result["confidence"] == "low"


def test_quantity_field_is_present_and_consistent_with_extract_quantity():
    text = "عشرين صندوق من الصقعي"
    result = extract_auction_data(text)
    assert result["quantity"] == _extract_quantity(text)
    assert result["quantity"] == 20


# ---------------------------------------------------------------------------
# تأكيد عدم وجود تعريف مكرر لـ extract_auction_data (الخلل الذي تم إصلاحه)
# ---------------------------------------------------------------------------

def test_extract_auction_data_defined_once():
    import inspect
    import agent.extractor as extractor_module

    source = inspect.getsource(extractor_module)
    assert source.count("def extract_auction_data(") == 1


# ---------------------------------------------------------------------------
# _words_to_number – أرقام مكتوبة بالحروف
# ---------------------------------------------------------------------------

def test_words_to_number_simple():
    assert _words_to_number("خمسين") == 50


def test_words_to_number_compound():
    assert _words_to_number("مية وعشرين") == 120


def test_words_to_number_teen():
    assert _words_to_number("ثلاثة عشر") == 13


def test_words_to_number_no_match_returns_none():
    assert _words_to_number("كلام بدون أرقام") is None
