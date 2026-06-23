"""
api/ws.py – نقطة اتصال WebSocket للبث اللحظي لمشروع صدى التمر
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket_manager import manager

router = APIRouter()


@router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int):
    """
    اتصال WebSocket لجلسة مزاد معيّنة.

    الاستخدام من الـ frontend:
        ws://127.0.0.1:8000/ws/{session_id}

    أي رسالة تُبَث من process-audio أو أي مصدر آخر لنفس الجلسة
    تصل تلقائياً لكل المتصلين هنا، بدون أي إجراء إضافي من العميل.
    """
    await manager.connect(websocket, session_id)
    try:
        while True:
            # نبقي الاتصال مفتوحاً ونستقبل أي رسائل (حالياً غير مستخدمة فعلياً،
            # لكن ضرورية حتى لا يُغلَق الاتصال فوراً من جهة FastAPI)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)