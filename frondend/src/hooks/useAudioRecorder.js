import { useCallback, useRef, useState } from "react";

// يختار أفضل صيغة مدعومة من المتصفح ضمن ما يقبله الـ backend
// (.webm / .ogg / .mp4). الـ backend يقبل: wav, mp3, m4a, ogg, webm, mp4.
function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const c of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) {
      return c;
    }
  }
  return "";
}

function extFor(mime) {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("mp4")) return "mp4";
  return "webm";
}

/**
 * هوك تسجيل صوتي من الميكروفون.
 * يعيد دوال البدء/الإيقاف، وحالة التسجيل، ومدة العداد بالثواني.
 * عند الإيقاف يستدعي onStop(file) بملف جاهز للرفع.
 */
export function useAudioRecorder(onStop) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const onStopRef = useRef(onStop);
  onStopRef.current = onStop;

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        const file = new File([blob], `recording.${extFor(type)}`, { type });
        // أغلق المسارات لتحرير الميكروفون
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        onStopRef.current?.(file);
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (e) {
      setError(
        e?.name === "NotAllowedError"
          ? "تم رفض إذن الميكروفون. فعّله من إعدادات المتصفح."
          : "تعذّر الوصول إلى الميكروفون."
      );
    }
  }, []);

  const stop = useCallback(() => {
    clearInterval(timerRef.current);
    setRecording(false);
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }, []);

  return { recording, seconds, error, start, stop };
}
