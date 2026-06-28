"""
agent/pipeline.py – واجهة خط معالجة المزاد (طبقة رفيعة فوق المنسّق).

أُعيدت هيكلته: المنطق الفعلي انتقل إلى طبقة محلِّلات نظيفة (ports/adapters):
  - agent/analyzer_service.py  : المنسّق والاستراتيجية المتدرّجة
  - agent/gemini_analyzer.py   : Gemini على الصوت الأصلي/النص (الأدقّ)
  - agent/whisper_transcriber.py, agent/legacy_analyzer.py : مسارات احتياطية

تبقى هذه الدالة public بنفس العقد (تُستدعى من api/auctions.py)، وتُحوِّل
النتيجة الموحَّدة AuctionAnalysis إلى شكل الاستجابة المتوافق مع الواجهة،
مع إضافة الحقل الغني `analysis` دون كسر أي شيء.
"""

import logging
from typing import Optional

import numpy as np

from agent.analysis_schema import AuctionAnalysis, AuctionStatusEnum
from agent.analyzer_service import get_analyzer_service
# إعادة تصدير للتوافق مع أي استيراد قديم لـ transcribe_audio
from agent.whisper_transcriber import transcribe_audio  # noqa: F401

logger = logging.getLogger(__name__)

# حالة المزاد الموحَّدة → فعل عربي تتوقّعه الواجهة الحالية
_STATUS_TO_ACTION = {
    AuctionStatusEnum.open: "افتتاح",
    AuctionStatusEnum.in_progress: "جارٍ",
    AuctionStatusEnum.sold: "إغلاق",
    AuctionStatusEnum.unsold: "جارٍ",
    AuctionStatusEnum.unknown: "جارٍ",
}


def _confidence_level(score: float) -> str:
    """رقم الثقة (0..1) → مستوى نصّي تتوقّعه الواجهة وشرط الإنشاء التلقائي."""
    if score >= 0.7:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _analysis_to_extracted(a: AuctionAnalysis) -> dict:
    """يحوّل AuctionAnalysis الموحَّد إلى شكل `extracted` المتوافق مع الواجهة."""
    level = _confidence_level(a.confidence)
    bids_prices = [b.price for b in a.bids] if a.bids else []
    price = a.final_price if a.final_price is not None else a.opening_price
    return {
        "status": "ok" if level != "low" else "low_confidence",
        "product": a.product_type,
        "price": price,
        "opening_price": a.opening_price,
        "final_price": a.final_price,
        "highest_price": max(bids_prices) if bids_prices else None,
        "unit": a.unit,
        "quantity": a.quantity,
        "action": _STATUS_TO_ACTION.get(a.status, "جارٍ"),
        "confidence": level,
        # حقول غنية إضافية (الواجهة تتجاهل ما لا تعرفه، وتفيد التخزين/العرض لاحقاً)
        "seller": a.seller_name,
        "buyer": a.buyer_name,
        "buyer_number": a.buyer_number,
        "winner": a.winner,
        "currency": a.currency,
        "bids_sequence": bids_prices,
        "notes": a.notes,
        "raw_text": a.transcript,
        "source": a.model_used or "unknown",
    }


def process_audio_to_auction_data(
    file_path: str,
    registered_embedding: Optional[np.ndarray] = None,
) -> dict:
    """
    خط المعالجة الكامل: ملف صوتي → بيانات مزاد منظَّمة.

    Returns:
        {
            "transcription": {text, status, language, duration, segments},
            "extracted":     شكل متوافق مع الواجهة (+ حقول غنية),
            "voiceprint":    نتيجة التحقق من البصمة | None,
            "trace":         خطوات قرار الوكيل,
            "analysis":      AuctionAnalysis الكامل (المخطط الغني الجديد),
        }
    """
    service = get_analyzer_service()
    analysis, transcription, trace = service.analyze(file_path)
    extracted = _analysis_to_extracted(analysis)

    # ── البصمة الصوتية (اختيارية) — تُبقي السلوك السابق: تطابق + إغلاق ⟶ رفع الثقة
    voiceprint_result = None
    if registered_embedding is not None:
        try:
            from agent.voiceprint import verify_voiceprint
            voiceprint_result = verify_voiceprint(
                audio_path=file_path,
                registered_embedding=registered_embedding,
                duration_sec=transcription.get("duration", 0.0),
            )
            trace.append({
                "skill": "verify_voiceprint",
                "status": voiceprint_result.get("status"),
                "is_match": voiceprint_result.get("is_match"),
                "best_score": voiceprint_result.get("best_score"),
            })
            if (
                voiceprint_result.get("is_match")
                and extracted["action"] == "إغلاق"
                and extracted["confidence"] != "high"
            ):
                extracted["confidence"] = "high"
                extracted["status"] = "ok"
                extracted["voiceprint_boosted"] = True
                trace.append({"step": "decision_confidence_gate",
                              "route_chosen": "voiceprint_boost", "status": "ok"})
        except Exception as e:
            trace.append({"skill": "verify_voiceprint", "status": "error", "error": str(e)[:160]})

    return {
        "transcription": transcription,
        "extracted": extracted,
        "voiceprint": voiceprint_result,
        "trace": trace,
        "analysis": analysis.model_dump(mode="json"),
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("الاستخدام: python -m agent.pipeline path/to/audio")
        sys.exit(1)

    result = process_audio_to_auction_data(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
