"""
agent/whisper_transcriber.py — مُفرِّغ صوت Whisper (faster-whisper) كـ Adapter.

يُستخدم كمسار احتياطي (Transcriber) عندما يتعذّر تحليل الصوت مباشرةً عبر
Gemini (لا مفتاح/تعطّل الشبكة). أُخرج من pipeline.py لتفادي الاستيراد الدائري
وفصل المسؤوليات.
"""

import logging
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# موجِّه عربي افتراضي يُملي سياق المجال (تمور + مزاد) فيحسّن التعرّف على
# أسماء الأصناف والمصطلحات. يُتجاوَز عبر WHISPER_INITIAL_PROMPT في البيئة.
_DEFAULT_AR_PROMPT = (
    "حراج ومزاد تمور سعودي. أصناف: سكري، عجوة، صقعي، خلاص، برحي، مجدول، "
    "خضري، صفري، روثانة، نبتة علي، مبروم، عنبرة، رشودية، شيشي. مصطلحات: "
    "البداية، السوم، زايد، بيع، مبروك، كرتون، كيس، صندوق، كيلو، ريال."
)


def _normalize_audio(file_path: str) -> str:
    """يرفع المستوى ويقلّل الضجيج عبر ffmpeg إن توفّر؛ وإلا يرجع الأصل."""
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", file_path,
                "-af", "highpass=f=80,afftdn=nf=-25,dynaudnorm=f=150:g=15",
                "-ar", "16000", "-ac", "1",
                output_path,
            ],
            check=True, capture_output=True, timeout=120,
        )
        return output_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        Path(output_path).unlink(missing_ok=True)
        return file_path


@lru_cache(maxsize=1)
def _get_whisper_model() -> WhisperModel:
    """يحمّل نموذج Whisper مرة واحدة؛ الحجم/الجهاز/نوع الحساب من الإعدادات."""
    size = device = compute = None
    try:
        from core.config import settings
        size = settings.WHISPER_MODEL_SIZE
        device = settings.WHISPER_DEVICE
        compute = settings.WHISPER_COMPUTE_TYPE
    except Exception:
        pass
    return WhisperModel(size or "medium", device=device or "cpu", compute_type=compute or "int8")


def transcribe_audio(file_path: str) -> dict:
    """
    حوّل ملف صوتي إلى نص عربي.

    Returns dict: {text, status, language, language_probability, duration, segments}.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ملف الصوت غير موجود: {file_path}")

    model = _get_whisper_model()
    normalized_path = _normalize_audio(str(path))
    is_temp_file = normalized_path != str(path)

    initial_prompt = None
    try:
        from core.config import settings
        initial_prompt = settings.WHISPER_INITIAL_PROMPT or _DEFAULT_AR_PROMPT
    except Exception:
        initial_prompt = _DEFAULT_AR_PROMPT

    try:
        segments_generator, info = model.transcribe(
            normalized_path,
            language="ar",
            task="transcribe",
            initial_prompt=initial_prompt,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=1000, speech_pad_ms=400),
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
            beam_size=5,
            best_of=5,
            temperature=[0.0, 0.2, 0.4],
        )

        segments, parts = [], []
        for seg in segments_generator:
            text = seg.text.strip()
            if not text:
                continue
            segments.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
            parts.append(text)

        full_text = " ".join(parts).strip()

        # حماية من الهلوسة: لا أحرف عربية → نص غير موثوق
        has_arabic = any("؀" <= ch <= "ۿ" and not ch.isdigit() for ch in full_text)
        if full_text and not has_arabic:
            full_text, segments = "", []

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


class WhisperTranscriber:
    """Adapter يحقّق واجهة Transcriber اعتماداً على transcribe_audio."""

    name = "whisper"

    def transcribe(self, audio_path: str) -> dict:
        return transcribe_audio(audio_path)
