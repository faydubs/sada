"""
agent/ports.py — واجهات (Ports) طبقة تحليل المزاد وفق Clean Architecture.

تعتمد طبقة التنسيق (analyzer_service) على هذه الـ Protocols لا على
تطبيقات محددة → نقدر نبدّل المزوّد (Gemini / Whisper / المستخرِج القديم)
أو نحقنه في الاختبارات دون تعديل المنطق (Dependency Inversion).
"""

from typing import Optional, Protocol, runtime_checkable

from agent.analysis_schema import AuctionAnalysis


@runtime_checkable
class AudioAnalyzer(Protocol):
    """يحلّل ملف صوت مباشرةً إلى نتيجة منظَّمة (المسار الأدقّ — الصوت الأصلي)."""

    name: str

    def analyze_audio(self, audio_path: str) -> AuctionAnalysis: ...


@runtime_checkable
class TextAnalyzer(Protocol):
    """يحلّل تفريغاً نصياً إلى نتيجة منظَّمة (مسار احتياطي بعد التفريغ)."""

    name: str

    def analyze_text(self, transcript: str) -> AuctionAnalysis: ...


@runtime_checkable
class Transcriber(Protocol):
    """يحوّل ملف صوت إلى تفريغ نصي (يُستخدم كمدخل للمسار الاحتياطي)."""

    name: str

    def transcribe(self, audio_path: str) -> dict:
        """يرجع dict: {text, status, language, language_probability, duration, segments}."""
        ...
