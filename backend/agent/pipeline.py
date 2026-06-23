"""
agent/pipeline.py – خط معالجة المزاد الكامل لمشروع صدى التمر
صوت → تحسين الصوت (ffmpeg) → نص (Whisper) → بيانات منظَّمة

الترتيب:
  1. تحسين الصوت بـ ffmpeg
  2. Whisper → نص عربي
  3. Gemini (إذا توفر GEMINI_API_KEY) → بيانات دقيقة
     Fallback: extractor.py → كلمات مفتاحية
  4. VoicePrint (إذا توفرت بصمة الدلال) → التحقق من الهوية
  5. XGBoost classifier → تصنيف الحالة (fallback لـ Gemini)
"""

import subprocess
import tempfile
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from agent.extractor import extract_auction_data
from agent.classifier import classify_auction_state

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# تحسين الصوت قبل المعالجة (رفع المستوى + تقليل الضجيج)
# ---------------------------------------------------------------------------

def _normalize_audio(file_path: str) -> str:
    """
    يرفع مستوى الصوت المنخفض ويطبّق فلتر تقليل ضجيج باستخدام ffmpeg،
    ويحفظ النتيجة في ملف WAV مؤقت.
    لو فشل ffmpeg → يرجع المسار الأصلي (لا نوقف العملية).
    """
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-af", "highpass=f=80,afftdn=nf=-25,dynaudnorm=f=150:g=15",
                "-ar", "16000", "-ac", "1",
                output_path,
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return output_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        # احذف الملف المؤقت الفارغ قبل الرجوع للأصلي
        Path(output_path).unlink(missing_ok=True)
        return file_path


# ---------------------------------------------------------------------------
# تحميل نموذج Whisper مرة واحدة فقط
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_whisper_model() -> WhisperModel:
    """يحمّل نموذج Whisper مرة واحدة ويعيد استخدامه."""
    return WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
    )


# ---------------------------------------------------------------------------
# تحويل الصوت إلى نص
# ---------------------------------------------------------------------------

def transcribe_audio(file_path: str) -> dict:
    """
    حوّل ملف صوتي إلى نص عربي.

    Returns:
        {
            "text": النص الكامل,
            "language": اللغة,
            "language_probability": نسبة الثقة,
            "duration": المدة بالثواني,
            "segments": [{start, end, text}, ...]
        }
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ملف الصوت غير موجود: {file_path}")

    model = _get_whisper_model()
    normalized_path = _normalize_audio(str(path))
    is_temp_file = normalized_path != str(path)

    try:
        segments_generator, info = model.transcribe(
            normalized_path,
            language="ar",
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=1000,
                speech_pad_ms=400,
            ),
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
            beam_size=5,
        )

        segments = []
        full_text_parts = []

        for seg in segments_generator:
            text = seg.text.strip()
            if not text:
                continue
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
            })
            full_text_parts.append(text)

        full_text = " ".join(full_text_parts).strip()

        # حماية من الهلوسة: لو ما في أحرف عربية → نص غير موثوق
        has_arabic = any("\u0600" <= ch <= "\u06FF" and not ch.isdigit() for ch in full_text)
        if full_text and not has_arabic:
            full_text = ""
            segments = []

        return {
            "text": full_text,
            "status": "ok" if full_text else "low_confidence",
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": segments,
        }
    finally:
        if is_temp_file:
            Path(normalized_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# الدالة المُجمِّعة الكاملة: صوت → بيانات مزاد منظَّمة
# ---------------------------------------------------------------------------

# ── ترتيب الثقة — يُستخدم في نقطة قرار التوجيه (أعلى = أوثق)
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, None: 0}


def _route_extraction(extractor_out: dict, gemini_out: Optional[dict]) -> tuple[dict, str]:
    """
    نقطة القرار الحقيقية #1 — Confidence routing.

    بخلاف الإصدار السابق (الذي كان يثق بـ Gemini لمجرد وجود المفتاح)، هنا
    extractor يعمل دائماً كمسار مضمون، ونقارن ثقة المصدرين فعلياً:
      - Gemini بثقة medium/high  ⟶ نأخذه.
      - Gemini بثقة low          ⟶ نرجع للأقوى بينه وبين extractor.
      - لا Gemini أصلاً          ⟶ extractor.
    يرجّع (الناتج المختار، اسم المسار) لتسجيله في الـ trace.
    """
    if gemini_out is None:
        return extractor_out, "extractor_only"

    g_rank = _CONFIDENCE_RANK.get(gemini_out.get("confidence"), 0)
    e_rank = _CONFIDENCE_RANK.get(extractor_out.get("confidence"), 0)

    if g_rank >= 2:                       # Gemini موثوق بما يكفي
        return gemini_out, "gemini"
    if e_rank > g_rank:                   # Gemini ضعيف و extractor أقوى
        return extractor_out, "gemini_low_fallback_extractor"
    return gemini_out, "gemini_low_kept"  # متساويان/extractor ليس أفضل


def process_audio_to_auction_data(
    file_path: str,
    registered_embedding: Optional[np.ndarray] = None,
) -> dict:
    """
    خط المعالجة الكامل: ملف صوتي → بيانات مزاد منظَّمة.

    أُعيدت هيكلته كـ Supervisor يقرأ `status` كل Skill ويتفرّع عليه، مع
    نقطتي قرار حقيقيتين مُعلَّمتين صراحةً (Confidence routing + Voiceprint
    gate)، ويبني `trace` مُهيكلاً يُظهر تفكير الوكيل (يُبَث لاحقاً عبر WS).

    Args:
        file_path: مسار ملف الصوت
        registered_embedding: بصمة الدلال المسجَّلة (اختياري)

    Returns:
        {
            "transcription": { ...نتيجة transcribe_audio... },
            "extracted":     { ...البيانات المستخرجة + status... },
            "voiceprint":    { ...نتيجة VoicePrint... } | None,
            "trace":         [ {step, skill, status, ...}, ... ]  # جديد (إضافي)
        }
    """
    trace: list[dict] = []

    def _trace(step: str, **fields) -> None:
        entry = {"step": step, **fields}
        trace.append(entry)
        logger.info("TRACE %s", entry)

    # ── Skill: تحويل الصوت إلى نص
    transcription = transcribe_audio(file_path)
    _trace(
        "transcribe", skill="transcribe_audio",
        status=transcription["status"],
        duration=transcription.get("duration"),
        chars=len(transcription["text"]),
    )

    # توقّف مبكر: لا نص ⟶ لا فائدة من باقي الـ Skills
    if not transcription["text"]:
        empty_extracted = {
            "status": "low_confidence",
            "product": None, "price": None, "unit": None,
            "action": "جارٍ", "raw_text": "",
            "confidence": "low", "source": "whisper_empty",
        }
        _trace("decision_route", route_chosen="none_empty_transcript", status="low_confidence")
        return {
            "transcription": transcription,
            "extracted": empty_extracted,
            "voiceprint": None,
            "trace": trace,
        }

    text = transcription["text"]

    # ── Skill: extractor (مسار مضمون يعمل دائماً) + إثراء الحالة بـ XGBoost
    extractor_out = extract_auction_data(text)
    extractor_out["source"] = "extractor"
    try:
        classification = classify_auction_state(text)
        extractor_out["action"] = classification["action"]
        extractor_out["action_confidence"] = classification["confidence"]
        _trace("classify", skill="classify_auction_state", status="ok",
               action=classification["action"], confidence=classification["confidence"])
    except Exception as e:
        # المصنّف اختياري — فشله لا يُسقط الطلب؛ نُبقي action من extractor.
        extractor_out["action_confidence"] = None
        _trace("classify", skill="classify_auction_state", status="error", error=str(e))
    _trace("extract", skill="extract_auction_data",
           status=extractor_out.get("status"), confidence=extractor_out.get("confidence"))

    # ── Skill: Gemini (اختياري) — فشله يصبح status لا استثناء
    gemini_out = None
    gemini_key = _get_gemini_key()
    if gemini_key:
        try:
            from agent.gemini_parser import parse_with_gemini, gemini_to_extracted
            gemini_result = parse_with_gemini(text, gemini_key)
            if gemini_result:
                gemini_out = gemini_to_extracted(gemini_result)
                _trace("gemini", skill="parse_with_gemini",
                       status=gemini_out.get("status"), confidence=gemini_out.get("confidence"))
            else:
                _trace("gemini", skill="parse_with_gemini", status="error", note="returned None")
        except Exception as e:
            _trace("gemini", skill="parse_with_gemini", status="error", error=str(e))
    else:
        _trace("gemini", skill="parse_with_gemini", status="skipped", note="no GEMINI_API_KEY")

    # ── نقطة القرار الحقيقية #1: Confidence routing
    extracted, route = _route_extraction(extractor_out, gemini_out)
    _trace("decision_route", route_chosen=route, status=extracted.get("status"),
           confidence=extracted.get("confidence"))

    # ── Skill + نقطة القرار الحقيقية #2: VoicePrint confidence gate
    voiceprint_result = None
    if registered_embedding is not None:
        try:
            from agent.voiceprint import verify_voiceprint
            voiceprint_result = verify_voiceprint(
                audio_path=file_path,
                registered_embedding=registered_embedding,
                duration_sec=transcription.get("duration", 0.0),
            )
            _trace("voiceprint", skill="verify_voiceprint",
                   status=voiceprint_result.get("status"),
                   is_match=voiceprint_result.get("is_match"),
                   best_score=voiceprint_result.get("best_score"))

            # بصمة مطابقة + بيع مُغلق ⟶ ارفع الثقة (دمج إشارتين)
            if (
                voiceprint_result.get("is_match")
                and extracted.get("action") == "إغلاق"
                and extracted.get("confidence") != "high"
            ):
                extracted["confidence"] = "high"
                extracted["status"] = "ok"
                extracted["voiceprint_boosted"] = True
                _trace("decision_confidence_gate", route_chosen="voiceprint_boost", status="ok")

        except Exception as e:
            _trace("voiceprint", skill="verify_voiceprint", status="error", error=str(e))

    return {
        "transcription": transcription,
        "extracted": extracted,
        "voiceprint": voiceprint_result,
        "trace": trace,
    }


# ---------------------------------------------------------------------------
# قراءة مفتاح Gemini من الإعدادات
# ---------------------------------------------------------------------------

def _get_gemini_key() -> Optional[str]:
    """يقرأ GEMINI_API_KEY من config — يرجع None إذا غير موجود"""
    try:
        from core.config import settings
        return getattr(settings, "GEMINI_API_KEY", None)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# اختبار مباشر من سطر الأوامر
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("الاستخدام: python agent/pipeline.py path/to/audio.wav")
        sys.exit(1)

    result = process_audio_to_auction_data(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))