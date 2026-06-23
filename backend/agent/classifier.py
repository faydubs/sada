"""
agent/classifier.py – كشف حالة المزاد (افتتاح/جارٍ/إغلاق) بـ XGBoost
لمشروع صدى التمر.

بديل أذكى من الكلمات المفتاحية الصرفة في extractor.py — يتعلم من أمثلة
حقيقية بدل قواعد ثابتة، فيتعامل أفضل مع التنويعات اللغوية غير المتوقَّعة.
"""

import re
import pickle
from pathlib import Path
from functools import lru_cache

import numpy as np
import xgboost as xgb


# ---------------------------------------------------------------------------
# مسار حفظ النموذج المدرَّب
# ---------------------------------------------------------------------------

MODEL_PATH = Path(__file__).parent / "auction_classifier.json"
LABELS = ["افتتاح", "جارٍ", "إغلاق"]  # ترتيب ثابت يطابق ترميز التدريب


# ---------------------------------------------------------------------------
# استخراج Features من النص
# ---------------------------------------------------------------------------

OPEN_HINTS   = ["نفتح", "نبدأ", "افتتاح", "نفتتح", "البداية", "بسم الله", "السوم وصل", "نفتح السوم"]
CLOSE_HINTS  = ["بيع", "تم البيع", "ترسى", "السومة", "آخر نداء", "انتهى", "يبارك له"]
BID_HINTS    = ["يعطي", "سيم", "واصل", "سيمت", "يقول"]  # مؤشرات مزايدة جارية


def extract_features(text: str) -> np.ndarray:
    """
    حوّل جملة عربية إلى متجه أرقام (features) يفهمه XGBoost.

    Features المُستخدَمة:
      0. طول الجملة (عدد الكلمات)
      1. عدد الأرقام الصريحة بالنص (0، 1، 2...)
      2. وجود أي كلمة افتتاح (0/1)
      3. وجود أي كلمة إغلاق (0/1)
      4. وجود أي كلمة مزايدة (0/1)
      5. موضع أول كلمة افتتاح نسبةً لطول الجملة (0=بداية، 1=نهاية، -1=غير موجودة)
      6. موضع أول كلمة إغلاق نسبةً لطول الجملة
      7. وجود "ريال" أو "ريالات" (0/1)
      8. هل الجملة تبدأ بـ "بسم الله" أو "يا" (نداء افتتاحي شائع) (0/1)
    """
    words = text.split()
    word_count = len(words)

    digit_count = len(re.findall(r"\d", text))

    has_open  = any(h in text for h in OPEN_HINTS)
    has_close = any(h in text for h in CLOSE_HINTS)
    has_bid   = any(h in text for h in BID_HINTS)

    def relative_position(hints: list[str]) -> float:
        positions = [text.find(h) for h in hints if h in text]
        if not positions or word_count == 0:
            return -1.0
        return min(positions) / max(len(text), 1)

    open_pos  = relative_position(OPEN_HINTS)
    close_pos = relative_position(CLOSE_HINTS)

    has_riyal = 1 if ("ريال" in text) else 0
    starts_with_call = 1 if (text.startswith("بسم الله") or text.startswith("يا ")) else 0

    return np.array([
        word_count,
        digit_count,
        int(has_open),
        int(has_close),
        int(has_bid),
        open_pos,
        close_pos,
        has_riyal,
        starts_with_call,
    ], dtype=np.float32)


# ---------------------------------------------------------------------------
# تحميل النموذج (lazy loading)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_model() -> xgb.XGBClassifier:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"النموذج المدرَّب غير موجود في {MODEL_PATH}. "
            f"شغّل أولاً: python agent/train_classifier.py"
        )
    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))
    return model


# ---------------------------------------------------------------------------
# الدالة الرئيسية للاستخدام في الـ pipeline
# ---------------------------------------------------------------------------

def classify_auction_state(text: str) -> dict:
    """
    صنّف حالة الجملة: افتتاح / جارٍ / إغلاق — باستخدام XGBoost المدرَّب.

    Returns:
        {
            "action": "افتتاح" | "جارٍ" | "إغلاق",
            "confidence": نسبة ثقة النموذج (0.0 - 1.0),
            "probabilities": {label: probability, ...}  لكل الفئات
        }
    """
    model = _load_model()
    features = extract_features(text).reshape(1, -1)

    probabilities = model.predict_proba(features)[0]
    predicted_idx = int(np.argmax(probabilities))

    return {
        "action": LABELS[predicted_idx],
        "confidence": round(float(probabilities[predicted_idx]), 3),
        "probabilities": {
            label: round(float(prob), 3)
            for label, prob in zip(LABELS, probabilities)
        },
    }


if __name__ == "__main__":
    import sys
    import json

    text = sys.argv[1] if len(sys.argv) > 1 else "بسم الله نبدأ مزاد السكري الكيلو بخمسين ريال"
    result = classify_auction_state(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))