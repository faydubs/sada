"""
agent/audio_utils.py — تحويل الصوت إلى WAV 16kHz mono في الذاكرة عبر PyAV.

المتصفح يسجّل بصيغة webm/opus التي قد لا يقبلها Gemini مباشرةً؛ نحوّلها هنا
إلى WAV (PCM s16) قياسي مدعوم. PyAV (av) مثبّت أصلاً كاعتمادية لـ
faster-whisper، فلا نحتاج ffmpeg على النظام.
"""

import io
import logging
import wave

import av

logger = logging.getLogger(__name__)

TARGET_RATE = 16000


def to_wav_bytes(audio_path: str) -> tuple[bytes, float]:
    """
    يحوّل ملف صوت (أي صيغة يفهمها PyAV) إلى WAV 16kHz أحادي القناة.

    Returns:
        (wav_bytes, duration_seconds)

    Raises:
        Exception: عند تعذّر فكّ/تحويل الصوت (ليتفرّع المنسّق لمسار احتياطي).
    """
    in_container = av.open(audio_path)
    try:
        in_stream = next(s for s in in_container.streams if s.type == "audio")
        resampler = av.audio.resampler.AudioResampler(
            format="s16", layout="mono", rate=TARGET_RATE
        )

        out_buf = io.BytesIO()
        out_container = av.open(out_buf, mode="w", format="wav")
        try:
            out_stream = out_container.add_stream("pcm_s16le", rate=TARGET_RATE)

            def _mux_resampled(frame):
                resampled = resampler.resample(frame)
                # PyAV الحديث يرجّع قائمة إطارات؛ القديم يرجّع إطاراً واحداً
                frames = resampled if isinstance(resampled, list) else [resampled]
                for rf in frames:
                    if rf is None:
                        continue
                    for packet in out_stream.encode(rf):
                        out_container.mux(packet)

            for frame in in_container.decode(in_stream):
                _mux_resampled(frame)
            # أفرغ ما تبقّى في الـ resampler ثم في الـ encoder
            _mux_resampled(None)
            for packet in out_stream.encode(None):
                out_container.mux(packet)
        finally:
            out_container.close()

        data = out_buf.getvalue()
    finally:
        in_container.close()

    duration = _wav_duration(data)
    return data, duration


def probe_duration(audio_path: str) -> float:
    """يقيس مدّة ملف صوت بالثواني دون تحويله كاملاً (للميتاداتا فقط)."""
    try:
        container = av.open(audio_path)
        try:
            if container.duration:
                return round(container.duration / 1_000_000.0, 2)  # av.time_base = 1e-6
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is not None and stream.duration and stream.time_base:
                return round(float(stream.duration * stream.time_base), 2)
        finally:
            container.close()
    except Exception:
        pass
    return 0.0


def _wav_duration(wav_bytes: bytes) -> float:
    """يحسب مدة WAV بالثواني من ترويسته."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or TARGET_RATE
            return round(frames / float(rate), 2)
    except Exception:
        return 0.0
