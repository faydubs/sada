"""
api/auctions.py – إدارة المزادات ومعالجة الصوت لمشروع صدى التمر
"""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from agent.pipeline import process_audio_to_auction_data
from agent.voiceprint import load_embedding_from_file
from api.auth import get_current_user
from core.database import get_db
from core.websocket_manager import manager
from models.models import Auction, AuctionStatus, User
from models.models import Session as SessionModel
from schemas.schemas import AuctionResponse, AuctionUpdate

router = APIRouter()

# صيغ الصوت المسموحة
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".mp4"}
MAX_FILE_SIZE_MB = 25


@router.post("/process-audio", status_code=status.HTTP_201_CREATED)
async def process_audio(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    استقبل مقطعاً صوتياً، حوّله إلى نص، استخرج بيانات المزاد،
    وأنشئ سجل Auction جديداً تلقائياً إذا كانت البيانات كافية.

    خطوات المعالجة:
      1. تحقق من صيغة وحجم الملف
      2. احفظه مؤقتاً على القرص (Whisper يحتاج مسار ملف فعلي)
      3. شغّل pipeline: Whisper → extractor
      4. إذا كان action="افتتاح" وفيه صنف + سعر → أنشئ Auction جديد
      5. احذف الملف المؤقت
    """
    # ── تحقق من الصيغة
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"صيغة غير مدعومة: {suffix}. المسموح: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # ── احفظ الملف مؤقتاً
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

            # تحقق من الحجم بعد الحفظ
            size_mb = Path(tmp_path).stat().st_size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"حجم الملف {size_mb:.1f}MB يتجاوز الحد الأقصى {MAX_FILE_SIZE_MB}MB",
                )

        # ── حمّل بصمة الدلال المسجَّلة (إذا سجّلها سابقاً عبر /api/auth/voiceprint)
        registered_embedding = None
        if current_user.voiceprint_path:
            registered_embedding = load_embedding_from_file(current_user.voiceprint_path)

        # ── شغّل خط المعالجة الكامل
        result = process_audio_to_auction_data(tmp_path, registered_embedding=registered_embedding)
        extracted = result["extracted"]

        trace = result.get("trace", [])
        response = {
            "transcription": result["transcription"]["text"],
            "extracted": extracted,
            "voiceprint": result.get("voiceprint"),
            "trace": trace,
            "analysis": result.get("analysis"),   # المخطط الغني الكامل (الجديد)
            "auction_created": None,
        }

        # ── ابعث النص المُستخرَج فوراً لكل المتصلين بهذه الجلسة (تحديث لحظي)
        await manager.broadcast(session_id, {
            "type": "transcription",
            "text": result["transcription"]["text"],
            "extracted": extracted,
        })

        # ── ابثّ أثر قرارات الوكيل (trace) ليراه المحكّم/المشرف لحظياً
        if trace:
            await manager.broadcast(session_id, {
                "type": "agent_trace",
                "trace": trace,
            })

        # ── أنشئ مزاداً تلقائياً فقط عند ثقة كافية وبيانات أساسية مكتملة
        if (
            extracted["action"] == "افتتاح"
            and extracted["product"]
            and extracted["price"] is not None
            and extracted["confidence"] in ("medium", "high")
        ):
            auction = Auction(
                session_id=session_id,
                product_name=extracted["product"],
                quantity=extracted.get("quantity") or 1,  # قيمة افتراضية مبدئية — تُحدَّث لاحقاً يدوياً أو من بيانات أدق
                unit=extracted["unit"] or "غير محدد",
                final_price=extracted["price"],
                status=AuctionStatus.active,
            )
            db.add(auction)
            db.commit()
            db.refresh(auction)
            auction_data = AuctionResponse.model_validate(auction).model_dump(mode="json")
            response["auction_created"] = auction_data

            # ── ابعث إشعاراً منفصلاً بأن مزاداً جديداً انفتح
            await manager.broadcast(session_id, {
                "type": "auction_started",
                "auction": auction_data,
            })

        return response

    finally:
        # ── احذف الملف المؤقت دائماً، حتى لو حدث خطأ
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink()


@router.patch("/{auction_id}", response_model=AuctionResponse)
async def update_auction(
    auction_id: int,
    data: AuctionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تصحيح/تحديث مزاد وإغلاقه يدوياً (تعيين السعر النهائي والمشتري والكمية).

    يعالج الفجوة المنطقية الأساسية: المزاد يُنشأ تلقائياً بسعر الافتتاح وحالة
    "active"، وهذا المسار يتيح للدلّال ضبط السعر النهائي الحقيقي واسم المشتري
    ثم إغلاق المزاد — فتعكس الإيرادات والتقارير المبيعات الفعلية لا أسعار الافتتاح.
    """
    auction = db.query(Auction).filter(Auction.id == auction_id).first()
    if not auction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المزاد غير موجود")

    session = db.query(SessionModel).filter(SessionModel.id == auction.session_id).first()
    if current_user.role.value != "admin" and session.dallal_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="لا يمكنك تعديل مزاد دلّال آخر")

    # طبّق الحقول المُرسَلة فقط
    fields = data.model_dump(exclude_unset=True)
    for key in ("product_name", "quantity", "unit", "final_price", "buyer_name"):
        if key in fields and fields[key] is not None:
            setattr(auction, key, fields[key])

    if "status" in fields and fields["status"] is not None:
        auction.status = fields["status"]
        # عند الإغلاق نضبط وقت الإغلاق تلقائياً إن لم يُرسَل
        if fields["status"] == AuctionStatus.closed and not auction.closed_at:
            auction.closed_at = fields.get("closed_at") or datetime.now(timezone.utc)

    db.commit()
    db.refresh(auction)

    auction_data = AuctionResponse.model_validate(auction).model_dump(mode="json")
    await manager.broadcast(auction.session_id, {
        "type": "auction_updated",
        "auction": auction_data,
    })
    return auction_data
