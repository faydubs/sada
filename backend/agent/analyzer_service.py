"""
agent/analyzer_service.py — منسّق تحليل المزاد (Use Case / Orchestrator).

يطبّق استراتيجية متدرّجة تعطي الأولوية للأدقّ، مع حقن الاعتماديات (DI)
وبناء trace شفّاف. لا يعرف تفاصيل أي مزوّد — يعتمد على واجهات ports فقط:

  1) Gemini على الصوت الأصلي        (الأدقّ)
  2) Whisper → Gemini على النص       (احتياطي عند تعذّر مسار الصوت)
  3) Whisper → المستخرِج القديم       (حلٌّ أخير دون إنترنت)

كل فشل يصبح خطوة في trace وتفرّعاً للمسار التالي — لا استثناء يُسقط الطلب.
"""

import logging
from functools import lru_cache
from typing import Optional

from agent.analysis_schema import AuctionAnalysis
from agent.audio_utils import probe_duration
from agent.ports import AudioAnalyzer, TextAnalyzer, Transcriber

logger = logging.getLogger(__name__)


def _empty_transcription() -> dict:
    return {"text": "", "status": "low_confidence", "language": "ar",
            "language_probability": 0.0, "duration": 0.0, "segments": []}


class AnalyzerService:
    """منسّق التحليل — يُحقن بالمحلِّلات عبر الواجهات (قابل للاختبار/التبديل)."""

    def __init__(
        self,
        audio_analyzer: Optional[AudioAnalyzer] = None,
        transcriber: Optional[Transcriber] = None,
        text_analyzer: Optional[TextAnalyzer] = None,
        legacy_analyzer: Optional[TextAnalyzer] = None,
    ):
        self._audio = audio_analyzer
        self._transcriber = transcriber
        self._text = text_analyzer
        self._legacy = legacy_analyzer

    def analyze(self, audio_path: str) -> tuple[AuctionAnalysis, dict, list]:
        """يرجع (AuctionAnalysis، transcription_dict، trace)."""
        trace: list[dict] = []

        # ── 1) المسار الأساسي: Gemini على الصوت الأصلي ──
        if self._audio is not None:
            try:
                analysis = self._audio.analyze_audio(audio_path)
                trace.append({"skill": self._audio.name, "status": "ok",
                              "confidence": analysis.confidence})
                trace.append({"step": "decision_route", "route_chosen": "gemini_audio", "status": "ok"})
                return analysis, self._transcription_from_analysis(analysis, probe_duration(audio_path)), trace
            except Exception as e:
                logger.warning("Gemini audio analyzer failed: %s", e)
                trace.append({"skill": self._audio.name, "status": "error", "error": str(e)[:160]})

        # ── 2) احتياطي: Whisper ثم تحليل النص ──
        transcription = _empty_transcription()
        if self._transcriber is not None:
            try:
                transcription = self._transcriber.transcribe(audio_path)
                trace.append({"skill": self._transcriber.name,
                              "status": transcription.get("status"),
                              "chars": len(transcription.get("text", "") or "")})
            except Exception as e:
                logger.warning("Whisper transcriber failed: %s", e)
                trace.append({"skill": self._transcriber.name, "status": "error", "error": str(e)[:160]})

        text = transcription.get("text", "") or ""

        # ── 2ب) Gemini على نص Whisper ──
        if text and self._text is not None:
            try:
                analysis = self._text.analyze_text(text)
                analysis.transcript = analysis.transcript or text
                trace.append({"skill": self._text.name, "status": "ok", "confidence": analysis.confidence})
                trace.append({"step": "decision_route", "route_chosen": "whisper_gemini_text", "status": "ok"})
                return analysis, transcription, trace
            except Exception as e:
                logger.warning("Gemini text analyzer failed: %s", e)
                trace.append({"skill": self._text.name, "status": "error", "error": str(e)[:160]})

        # ── 3) حلٌّ أخير: المستخرِج القديم ──
        if self._legacy is not None:
            analysis = self._legacy.analyze_text(text)
            trace.append({"skill": self._legacy.name,
                          "status": "ok" if text else "low_confidence",
                          "confidence": analysis.confidence})
            trace.append({"step": "decision_route", "route_chosen": "legacy_extractor", "status": "ok"})
            return analysis, transcription, trace

        # لا محلِّل متاح إطلاقاً
        analysis = AuctionAnalysis(transcript=text, model_used="none")
        trace.append({"step": "decision_route", "route_chosen": "none", "status": "low_confidence"})
        return analysis, transcription, trace

    @staticmethod
    def _transcription_from_analysis(analysis: AuctionAnalysis, duration: float) -> dict:
        text = analysis.transcript or ""
        return {
            "text": text,
            "status": "ok" if text else "low_confidence",
            "language": analysis.language or "ar",
            "language_probability": 1.0 if text else 0.0,
            "duration": duration,
            "segments": [],
        }


# ---------------------------------------------------------------------------
# مصنع الخدمة الافتراضية (Composition Root) — يقرأ الإعدادات ويبني المحلِّلات.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_analyzer_service() -> AnalyzerService:
    """يبني خدمة التحليل الافتراضية مرة واحدة (يعيد استخدام عميل Gemini ونموذج Whisper)."""
    from agent.whisper_transcriber import WhisperTranscriber
    from agent.legacy_analyzer import LegacyExtractorAnalyzer

    audio_analyzer = None
    text_analyzer = None

    try:
        from core.config import settings
        key = settings.GEMINI_API_KEY
        if key:
            from agent.gemini_analyzer import GeminiAudioAnalyzer, GeminiTextAnalyzer
            max_tokens = settings.GEMINI_MAX_OUTPUT_TOKENS
            if settings.GEMINI_AUDIO_ENABLED:
                audio_analyzer = GeminiAudioAnalyzer(
                    key, settings.GEMINI_MODEL, settings.GEMINI_MAX_RETRIES, max_tokens)
            text_analyzer = GeminiTextAnalyzer(
                key, settings.GEMINI_TEXT_MODEL, settings.GEMINI_MAX_RETRIES, max_tokens)
        else:
            logger.info("GEMINI_API_KEY غير مضبوط — سيُعتمد Whisper + المستخرِج القديم.")
    except Exception as e:
        logger.warning("تعذّر تهيئة محلِّلات Gemini: %s — متابعة بالمسار الاحتياطي.", e)

    return AnalyzerService(
        audio_analyzer=audio_analyzer,
        transcriber=WhisperTranscriber(),
        text_analyzer=text_analyzer,
        legacy_analyzer=LegacyExtractorAnalyzer(),
    )
