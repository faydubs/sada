"""
agent/train_classifier.py – تدريب نموذج XGBoost لكشف حالة المزاد
لمشروع صدى التمر.

يُشغَّل مرة واحدة (أو كل ما تحدّث الـ Dataset) لإنتاج ملف النموذج
المدرَّب auction_classifier.json الذي يستخدمه classifier.py لاحقاً.

الاستخدام:
    python agent/train_classifier.py
"""

import json
from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

from classifier import extract_features, LABELS, MODEL_PATH


DATA_PATH = Path(__file__).parent.parent / "auction_samples.json"
# يطابق تسمية الـ Dataset (مزايدة) مع تسمية النموذج الداخلية (جارٍ)
INTENT_MAP = {"افتتاح": "افتتاح", "مزايدة": "جارٍ", "إغلاق": "إغلاق"}
LABEL_TO_IDX = {label: idx for idx, label in enumerate(LABELS)}


def load_dataset() -> tuple[np.ndarray, np.ndarray]:
    """حمّل auction_samples.json واستخرج (X, y) جاهزة للتدريب"""
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    X, y = [], []
    for item in data:
        features = extract_features(item["text"])
        label = INTENT_MAP[item["intent"]]
        X.append(features)
        y.append(LABEL_TO_IDX[label])

    return np.array(X), np.array(y)


def main():
    print(f"📂 تحميل البيانات من: {DATA_PATH}")
    X, y = load_dataset()
    print(f"✅ {len(X)} عيّنة، {X.shape[1]} features")

    # تقسيم 80% تدريب / 20% اختبار، مع الحفاظ على توازن الفئات (stratify)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"📊 تدريب: {len(X_train)} | اختبار: {len(X_test)}")

    model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.1,
        objective="multi:softprob",
        num_class=len(LABELS),
        eval_metric="mlogloss",
        random_state=42,
    )

    print("\n🔧 جارٍ التدريب...")
    model.fit(X_train, y_train)

    # ── تقييم على بيانات الاختبار (لم يرها النموذج أثناء التدريب)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n🎯 الدقة على بيانات الاختبار: {accuracy:.1%}")
    print("\n📋 تقرير مفصّل لكل فئة:")
    print(classification_report(y_test, y_pred, target_names=LABELS, zero_division=0))

    # ── احفظ النموذج
    model.save_model(str(MODEL_PATH))
    print(f"\n💾 تم حفظ النموذج في: {MODEL_PATH}")


if __name__ == "__main__":
    main()