"""
agent/voiceprint.py – التحقق من بصمة الدلال الصوتية لمشروع صدى التمر
يقارن صوت المزاد الحالي بالبصمة المسجَّلة للدلال عند إنشاء حسابه.
يُستدعى اختيارياً من pipeline.py — الفشل لا يوقف المعالجة.
"""

import logging
import tempfile
from pathlib import Path
from functools import lru_cache
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── عتبة التطابق: أعلى = أكثر صرامة، أقل = أكثر تساهلاً
# 0.45 خيار متوازن من كود زملائك (تجربتهم)
MATCH_THRESHOLD = 0.45


@lru_cache(maxsize=1)
def _load_speaker_model():
    """يحمّل نموذج SpeechBrain ECAPA مرة واحدة فقط"""
    try:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError:
            from speechbrain.pretrained import EncoderClassifier

        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(Path.home() / ".cache" / "speechbrain" / "spkrec-ecapa-voxceleb"),
        )
        return classifier
    except Exception as e:
        logger.warning(f"SpeechBrain غير متاح: {e}")
        return None


def _load_audio_16k(wav_path: str):
    """يحمّل ملف WAV ويعيد الإشارة بـ 16kHz mono"""
    try:
        import torchaudio
        import torch

        signal, fs = torchaudio.load(str(wav_path))

        # stereo → mono
        if signal.shape[0] > 1:
            signal = signal.mean(dim=0, keepdim=True)

        # resample → 16k
        if fs != 16000:
            resampler = torchaudio.transforms.Resample(fs, 16000)
            signal = resampler(signal)

        return signal
    except Exception as e:
        logger.warning(f"فشل تحميل الصوت: {e}")
        return None


def _get_embedding(classifier, signal) -> Optional[np.ndarray]:
    """استخرج بصمة صوتية من إشارة الصوت"""
    try:
        import torch
        import torch.nn.functional as F

        signal = signal.to(classifier.device)

        with torch.no_grad():
            emb = classifier.encode_batch(signal)

        emb = emb.squeeze().detach().cpu().float()
        emb = F.normalize(emb, dim=0)
        return emb.numpy()
    except Exception as e:
        logger.warning(f"فشل استخراج البصمة: {e}")
        return None


def _cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    """احسب تشابه Cosine بين بصمتين"""
    try:
        import torch
        import torch.nn.functional as F

        ta = torch.tensor(a).float()
        tb = torch.tensor(b).float()
        return float(F.cosine_similarity(ta, tb, dim=0).item())
    except Exception:
        # fallback numpy
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)


def create_voiceprint(audio_path: str) -> Optional[np.ndarray]:
    """
    أنشئ بصمة صوتية من ملف تسجيل.
    يُستخدم عند تسجيل الدلال لأول مرة لحفظ بصمته.

    Args:
        audio_path: مسار ملف الصوت (wav/mp3/m4a)

    Returns:
        numpy array للبصمة، أو None عند الفشل
    """
    classifier = _load_speaker_model()
    if classifier is None:
        return None

    signal = _load_audio_16k(audio_path)
    if signal is None:
        return None

    return _get_embedding(classifier, signal)


def verify_voiceprint(
    audio_path: str,
    registered_embedding: np.ndarray,
    duration_sec: float = 0.0,
) -> dict:
    """
    قارن صوت المزاد بالبصمة المسجَّلة للدلال.

    Args:
        audio_path: مسار صوت المزاد الحالي
        registered_embedding: البصمة المسجَّلة كـ numpy array
        duration_sec: مدة الصوت (للمقارنة بآخر 10 ثواني)

    Returns:
        {
            "is_match": True/False,
            "best_score": float,
            "label": "registered_auctioneer" | "other_or_unknown",
            "scores": {"full": float, "last_10s": float | None},
            "threshold": float,
            "note": str
        }
    """
    classifier = _load_speaker_model()

    # إذا SpeechBrain مو متاح → نرجع نتيجة محايدة
    if classifier is None:
        return {
            "is_match": False,
            "best_score": 0.0,
            "label": "voiceprint_unavailable",
            "scores": {"full": None, "last_10s": None},
            "threshold": MATCH_THRESHOLD,
            "note": "SpeechBrain غير متاح — تم تجاهل التحقق من البصمة",
            "enabled": False,
            "status": "unavailable",
        }

    try:
        import torchaudio

        signal = _load_audio_16k(audio_path)
        if signal is None:
            raise ValueError("فشل تحميل الصوت")

        # ── مقارنة مع الصوت الكامل
        full_emb = _get_embedding(classifier, signal)
        full_score = _cosine_score(registered_embedding, full_emb) if full_emb is not None else 0.0

        # ── مقارنة مع آخر 10 ثواني (منطقة إغلاق البيع)
        closing_score = None
        sr = 16000
        total_samples = signal.shape[1]
        window_samples = min(10 * sr, total_samples)

        if window_samples >= sr:  # على الأقل ثانية واحدة
            closing_signal = signal[:, total_samples - window_samples:]
            closing_emb = _get_embedding(classifier, closing_signal)
            if closing_emb is not None:
                closing_score = _cosine_score(registered_embedding, closing_emb)

        scores = [full_score]
        if closing_score is not None:
            scores.append(closing_score)

        best_score = max(scores)
        is_match = best_score >= MATCH_THRESHOLD

        label = "registered_auctioneer" if is_match else "other_or_unknown"
        note = (
            "الصوت قريب من بصمة الدلال المسجل."
            if is_match
            else "الصوت لا يطابق بصمة الدلال المسجل بدرجة كافية."
        )

        return {
            "is_match": is_match,
            "best_score": round(best_score, 4),
            "label": label,
            "scores": {
                "full": round(full_score, 4),
                "last_10s": round(closing_score, 4) if closing_score is not None else None,
            },
            "threshold": MATCH_THRESHOLD,
            "note": note,
            "enabled": True,
            "status": "ok",
        }

    except Exception as e:
        logger.warning(f"VoicePrint فشل: {e}")
        return {
            "is_match": False,
            "best_score": 0.0,
            "label": "error",
            "scores": {"full": None, "last_10s": None},
            "threshold": MATCH_THRESHOLD,
            "note": f"خطأ في التحقق من البصمة: {str(e)}",
            "enabled": False,
            "status": "error",
        }


def load_embedding_from_file(npy_path: str) -> Optional[np.ndarray]:
    """حمّل بصمة محفوظة مسبقاً من ملف .npy"""
    try:
        path = Path(npy_path)
        if not path.exists():
            return None
        return np.load(str(path))
    except Exception as e:
        logger.warning(f"فشل تحميل البصمة: {e}")
        return None


def save_embedding_to_file(embedding: np.ndarray, npy_path: str) -> bool:
    """احفظ البصمة في ملف .npy"""
    try:
        Path(npy_path).parent.mkdir(parents=True, exist_ok=True)
        np.save(str(npy_path), embedding)
        return True
    except Exception as e:
        logger.warning(f"فشل حفظ البصمة: {e}")
        return False