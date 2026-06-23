"""
core/websocket_manager.py – إدارة اتصالات WebSocket للبث اللحظي
لمشروع صدى التمر. كل جلسة (session_id) لها قائمة متصلين خاصة بها.
"""

from fastapi import WebSocket


class ConnectionManager:
    """
    يدير اتصالات WebSocket مجمَّعة حسب session_id.
    عدة شاشات (دلال + admin + متفرجون) يقدرون يتصلوا بنفس الجلسة
    ويستقبلوا نفس التحديثات اللحظية.
    """

    def __init__(self) -> None:
        # session_id → قائمة اتصالات نشطة
        self._active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: int) -> None:
        """اقبل اتصالاً جديداً وأضفه لقائمة الجلسة"""
        await websocket.accept()
        self._active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int) -> None:
        """احذف الاتصال عند الانقطاع"""
        connections = self._active_connections.get(session_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and session_id in self._active_connections:
            del self._active_connections[session_id]

    async def broadcast(self, session_id: int, message: dict) -> None:
        """
        ابعث رسالة JSON لكل المتصلين بجلسة معيّنة.
        يتجاهل أي اتصال ميت بدل ما يفشل الإرسال بالكامل.
        """
        connections = self._active_connections.get(session_id, [])
        dead_connections = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # نظّف الاتصالات الميتة
        for dead in dead_connections:
            self.disconnect(dead, session_id)

    def active_count(self, session_id: int) -> int:
        """عدد المتصلين الحاليين بجلسة معيّنة — مفيد للعرض أو الـ debugging"""
        return len(self._active_connections.get(session_id, []))


# ── نسخة واحدة مشتركة (singleton) تُستخدم في main.py وكل الـ routers
manager = ConnectionManager()