"""
agent/gemini_analyzer.py — محلِّلات Gemini لمزاد التمر السعودي.

- GeminiAudioAnalyzer: يرسل الصوت الأصلي لـ Gemini فيُفرّغ ويفهم ويستخرج في
  تمريرة واحدة (أدقّ مسار للهجة الخليجية والأرقام المنطوقة والضجيج).
- GeminiTextAnalyzer: يحلّل تفريغاً نصياً جاهزاً (مسار احتياطي بعد Whisper).

كلاهما يفرض مخرجات JSON منظَّمة (response_schema)، حرارة 0 للحتمية، وإعادة
محاولة بـ tenacity عند تعطّل الشبكة.
"""

import logging
from typing import Optional

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# نعيد المحاولة فقط على الأخطاء العابرة (خادم/شبكة) — لا على ClientError
# (مفتاح غير صالح/طلب خاطئ) حتى لا نهدر الوقت ثم نتفرّع للمسار الاحتياطي بسرعة.
_RETRYABLE = (genai_errors.ServerError, ConnectionError, TimeoutError)

from agent.analysis_schema import AuctionAnalysis, GeminiAuctionSchema
from agent.audio_utils import to_wav_bytes

logger = logging.getLogger(__name__)


# ── تعليمات النظام: خبير تحليل مزادات التمر السعودي. الدقّة قبل كل شيء. ───────
SYSTEM_INSTRUCTION = """\
أنت خبير في تحليل مزادات (حراج) التمور في السوق السعودي. تفهم العربية الفصحى
واللهجات الخليجية/النجدية، ومصطلحات الحراج، والأرقام المنطوقة بالكلمات، وتتعامل
مع التسجيلات المزعجة وأخطاء النطق.

مهمتك: استخراج بيانات المزاد بأعلى دقّة ممكنة وإخراجها JSON منظَّم فقط.

قواعد صارمة:
1) الدقّة فوق كل شيء. إذا لم تستطع تحديد حقل بثقة، أعد null — لا تخمّن أبداً.
2) الأرقام المنطوقة: حوّل الكلام إلى أرقام بدقّة، مثل: "مية وخمسة وأربعين"=145،
   "ميتين وثمانين"=280، "ألف وخمسمية"=1500، "ثمانمية"=800.
3) لا تعتبر "حراج واحد/اثنين/ثلاثة" أسعاراً — هذه نداءات إغلاق، رقم قبلها قد يكون
   السعر النهائي. ولا تعتبر "مزاد رقم ١" سعراً.
4) المزايدات تصاعدية: رتّب bids زمنياً تصاعدياً، واحذف التكرارات المتتالية،
   ولا تُدرِج نزولاً في السعر.
5) opening_price = أول سعر، final_price = آخر سعر عند البيع.
6) حالة المزاد status: open (افتتاح) / in_progress (مزايدة جارية) / sold (تم البيع)
   / unsold (انتهى بلا بيع) / unknown.
7) عبارات الإغلاق: "بيع"، "تم البيع"، "مبروك"، "الله يبارك"، "رست/ترسى"، "خلاص بيع"،
   تسلسل "حراج واحد→اثنين→ثلاثة". الفائز/المشتري = من رست عليه.
8) أصناف شائعة: سكري، خلاص، صقعي، مجدول، برحي، برني، خضري، عجوة، عنبرة، رشودية،
   روثانة، مبروم، صفري، شيشي، رزيز، نبتة علي، سكري جالكسي.
9) الكمية: استخرج العدد (quantity) والوحدة (unit) إن ذُكرا — مثل: عدد الكراتين،
   الصناديق، الأكياس، الطبليات/البالات (pallets)، السلال (baskets)، الكيلوات، الأطنان.
   أمثلة: "عشرين كرتون"=20 كرتون، "خمس طبليات"=5 طبلية. وإلا null.
10) رقم المشتري (buyer_number): إن نادى الدلّال برقم المشتري/المضرب (مثل "بيع على
    رقم خمسة"، "المشتري رقم ١٢") فاستخرجه نصاً، وإلا null. (مختلف عن اسم المشتري.)
11) العملة الافتراضية SAR ما لم يُذكر غيرها.
12) املأ transcript بتفريغ نصي أمين للمقطع (بالعربية)، وnotes بأي سياق مفيد.
13) confidence رقم بين 0.0 و1.0 يعكس مدى وضوح المقطع وثقتك بالاستخراج.
"""

_USER_AUDIO_PROMPT = (
    "حلّل تسجيل مزاد التمر هذا واستخرج كل البيانات الممكنة وفق المخطط. "
    "أعد null لأي حقل غير مؤكَّد."
)


def _coerce(schema_obj: GeminiAuctionSchema, model_used: str) -> AuctionAnalysis:
    """يحوّل ناتج Gemini إلى نموذج المجال الموحّد مع تنظيف بسيط."""
    data = schema_obj.model_dump()
    # ثبّت الثقة ضمن [0,1]
    try:
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence") or 0.0)))
    except (TypeError, ValueError):
        data["confidence"] = 0.0
    analysis = AuctionAnalysis.model_validate(data)
    analysis.model_used = model_used
    return analysis


class _GeminiBase:
    """منطق مشترك: عميل + نداء مُعاد المحاولة بمخرجات منظَّمة."""

    def __init__(self, api_key: str, model: str, max_retries: int = 2, max_output_tokens: int = 8192):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_retries = max_retries
        self._max_output_tokens = max_output_tokens

    def _generate(self, contents) -> GeminiAuctionSchema:
        @retry(
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(_RETRYABLE),
            reraise=True,
        )
        def _call() -> GeminiAuctionSchema:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.0,
                    max_output_tokens=self._max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=GeminiAuctionSchema,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, GeminiAuctionSchema):
                return parsed
            # احتياط: فُكّ النص يدوياً إذا لم يُرجِع الـ SDK كائناً مُحلَّلاً
            import json
            raw = (response.text or "").strip()
            return GeminiAuctionSchema.model_validate(json.loads(raw))

        return _call()


class GeminiAudioAnalyzer(_GeminiBase):
    """يحقّق AudioAnalyzer: صوت أصلي → AuctionAnalysis."""

    name = "gemini_audio"

    def analyze_audio(self, audio_path: str) -> AuctionAnalysis:
        wav_bytes, _duration = to_wav_bytes(audio_path)
        contents = [
            types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
            _USER_AUDIO_PROMPT,
        ]
        schema_obj = self._generate(contents)
        return _coerce(schema_obj, self._model)


class GeminiTextAnalyzer(_GeminiBase):
    """يحقّق TextAnalyzer: تفريغ نصي → AuctionAnalysis."""

    name = "gemini_text"

    def analyze_text(self, transcript: str) -> AuctionAnalysis:
        prompt = (
            "هذا تفريغ نصي خام (قد يحتوي أخطاء Whisper) لمزاد تمر. "
            "استخرج البيانات وفق المخطط، وأعد null لأي حقل غير مؤكَّد.\n\n"
            f"التفريغ:\n{transcript}"
        )
        schema_obj = self._generate([prompt])
        analysis = _coerce(schema_obj, self._model)
        # احفظ التفريغ الأصلي إن لم يُعده الموديل
        if not analysis.transcript:
            analysis.transcript = transcript
        return analysis
