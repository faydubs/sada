"""
agent/legacy_analyzer.py — مُحوِّل (Adapter) للمستخرِج القديم.

يلفّ extractor.py (+ classifier.py الاختياري) خلف واجهة TextAnalyzer ويُرجع
AuctionAnalysis الموحَّد. يُستخدم كحلٍّ أخير عند غياب مفتاح Gemini أو تعطّله،
فلا تُفقد أي وظيفة قائمة سابقاً.
"""

import logging
from typing import Optional

from agent.analysis_schema import AuctionAnalysis, AuctionStatusEnum
from agent.extractor import extract_auction_data

logger = logging.getLogger(__name__)

# فعل المستخرِج العربي → حالة المزاد الموحَّدة
_ACTION_TO_STATUS = {
    "افتتاح": AuctionStatusEnum.open,
    "جارٍ": AuctionStatusEnum.in_progress,
    "إغلاق": AuctionStatusEnum.sold,
}
# مستوى ثقة المستخرِج النصّي → رقم تقريبي
_CONF_TO_FLOAT = {"high": 0.8, "medium": 0.55, "low": 0.3}


class LegacyExtractorAnalyzer:
    """يحقّق TextAnalyzer اعتماداً على المستخرِج القديم (regex/كلمات مفتاحية)."""

    name = "legacy_extractor"

    def analyze_text(self, transcript: str) -> AuctionAnalysis:
        ex = extract_auction_data(transcript or "")

        action = ex.get("action") or "جارٍ"
        status = _ACTION_TO_STATUS.get(action, AuctionStatusEnum.unknown)
        price = ex.get("price")

        # إثراء الحالة بمصنّف XGBoost إن توفّر (فشله لا يُسقط شيئاً)
        try:
            from agent.classifier import classify_auction_state
            clf = classify_auction_state(transcript or "")
            status = _ACTION_TO_STATUS.get(clf.get("action"), status)
        except Exception as e:
            logger.debug("classifier unavailable: %s", e)

        return AuctionAnalysis(
            product_type=ex.get("product"),
            opening_price=price if status == AuctionStatusEnum.open else None,
            final_price=price if status == AuctionStatusEnum.sold else None,
            quantity=ex.get("quantity"),
            unit=ex.get("unit"),
            status=status,
            confidence=_CONF_TO_FLOAT.get(ex.get("confidence", "low"), 0.3),
            transcript=transcript,
            language="ar",
            model_used="legacy_extractor",
        )
