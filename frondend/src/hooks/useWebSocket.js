import { useEffect, useRef, useState } from "react";

// يشتق عنوان WebSocket: من VITE_WS_BASE إن وُجد، وإلا من موقع الصفحة الحالي
// (يعمل مع proxy الخاص بـ Vite في التطوير).
function wsUrl(sessionId) {
  const base = import.meta.env.VITE_WS_BASE;
  if (base) return `${base.replace(/\/$/, "")}/ws/${sessionId}`;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/${sessionId}`;
}

/**
 * اتصال WebSocket بجلسة مزاد للبث اللحظي.
 * onMessage يُستدعى لكل رسالة واردة (transcription / auction_started / session_closed).
 * يعيد الاتصال تلقائياً عند الانقطاع طالما الجلسة مفتوحة.
 */
export function useWebSocket(sessionId, onMessage, enabled = true) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!enabled || !sessionId) return;
    let closedByUs = false;

    function connect() {
      const ws = new WebSocket(wsUrl(sessionId));
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs) {
          // أعد المحاولة بعد ثانيتين
          reconnectRef.current = setTimeout(connect, 2000);
        }
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handlerRef.current?.(data);
        } catch {
          /* تجاهل الرسائل غير الصالحة */
        }
      };
    }

    connect();

    return () => {
      closedByUs = true;
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [sessionId, enabled]);

  return { connected };
}
