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
 * هوك تسجيل صوتي من الميكروفون مع عدّاد دقيق ودعم الإيقاف المؤقت/الاستئناف.
 *
 * العدّاد يُحسب من طوابع زمنية حقيقية (performance.now) لا من عدّ نبضات
 * setInterval — فلا ينحرف ولا يتأخّر عند تجميد التبويب، ويطابق مدة الصوت
 * الفعلية (نستخدم MediaRecorder.pause الذي يستبعد زمن الإيقاف من التسجيل).
 *
 * يعيد: { recording, paused, seconds, error, start, pause, resume, stop }
 * عند الإيقاف النهائي يستدعي onStop(file) بملف جاهز للرفع.
 */
export function useAudioRecorder(onStop) {
  const [recording, setRecording] = useState(false);
  const [paused, setPaused] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const onStopRef = useRef(onStop);
  onStopRef.current = onStop;

  // ── حساب الوقت: زمن متراكم قبل آخر استئناف + الزمن منذ آخر استئناف ──
  const accumulatedMsRef = useRef(0); // ملّي ثانية مكتملة قبل الجزء الجاري
  const segmentStartRef = useRef(0);  // طابع بدء الجزء الجاري (performance.now)
  const tickRef = useRef(null);

  const _elapsedMs = useCallback((isPaused) => {
    const live = isPaused ? 0 : performance.now() - segmentStartRef.current;
    return accumulatedMsRef.current + live;
  }, []);

  const _startTicking = useCallback(() => {
    clearInterval(tickRef.current);
    // تحديث كل 200ms للسلاسة، لكن القيمة محسوبة من الطوابع الزمنية (دقيقة)
    tickRef.current = setInterval(() => {
      setSeconds(Math.floor(_elapsedMs(false) / 1000));
    }, 200);
  }, [_elapsedMs]);

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
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        onStopRef.current?.(file);
      };

      recorder.start();
      recorderRef.current = recorder;

      accumulatedMsRef.current = 0;
      segmentStartRef.current = performance.now();
      setSeconds(0);
      setRecording(true);
      setPaused(false);
      _startTicking();
    } catch (e) {
      setError(
        e?.name === "NotAllowedError"
          ? "تم رفض إذن الميكروفون. فعّله من إعدادات المتصفح."
          : "تعذّر الوصول إلى الميكروفون."
      );
    }
  }, [_startTicking]);

  const pause = useCallback(() => {
    const rec = recorderRef.current;
    if (!rec || rec.state !== "recording") return;
    rec.pause();
    // ثبّت الزمن المتراكم وأوقف عدّ الجزء الجاري
    accumulatedMsRef.current += performance.now() - segmentStartRef.current;
    clearInterval(tickRef.current);
    setSeconds(Math.floor(accumulatedMsRef.current / 1000));
    setPaused(true);
  }, []);

  const resume = useCallback(() => {
    const rec = recorderRef.current;
    if (!rec || rec.state !== "paused") return;
    rec.resume();
    segmentStartRef.current = performance.now();
    setPaused(false);
    _startTicking();
  }, [_startTicking]);

  const stop = useCallback(() => {
    clearInterval(tickRef.current);
    // ثبّت العدّاد النهائي على القيمة الفعلية لحظة الإيقاف
    const isPaused = recorderRef.current?.state === "paused";
    setSeconds(Math.round(_elapsedMs(isPaused) / 1000));
    setRecording(false);
    setPaused(false);
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }, [_elapsedMs]);

  return { recording, paused, seconds, error, start, pause, resume, stop };
}
