import { useCallback, useRef, useState } from "react";

/*
 * تفريغ صوتي حيّ أثناء التسجيل عبر Web Speech API (SpeechRecognition).
 * يعرض النص لحظياً (جزئي + نهائي) دون تعطيل التسجيل — مجرد معاينة للدلّال؛
 * المعالجة النهائية تبقى على المقطع المسجَّل عبر خط الـ AI (Gemini).
 *
 * مدعوم في Chrome/Edge (والأندرويد). إن لم يتوفّر → supported=false ويعمل
 * التسجيل عادياً بلا تفريغ حيّ (تدهور لطيف).
 */
function getRecognitionCtor() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function useSpeechRecognition(lang = "ar-SA") {
  const Ctor = getRecognitionCtor();
  const supported = !!Ctor;

  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState(""); // النص الجزئي الجاري
  const [finalText, setFinalText] = useState(""); // النص النهائي المتراكم

  const recRef = useRef(null);
  const wantRef = useRef(false); // هل ما زلنا نريد الاستماع؟ (لإعادة التشغيل التلقائي)
  const finalRef = useRef("");

  const start = useCallback(() => {
    if (!supported) return;
    // صفّر الحالة
    finalRef.current = "";
    setFinalText("");
    setInterim("");
    wantRef.current = true;

    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;

    rec.onresult = (event) => {
      let interimChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const txt = res[0]?.transcript || "";
        if (res.isFinal) {
          finalRef.current = (finalRef.current + " " + txt).trim();
        } else {
          interimChunk += txt;
        }
      }
      setFinalText(finalRef.current);
      setInterim(interimChunk);
    };

    rec.onerror = (e) => {
      // أخطاء شائعة غير قاتلة (no-speech / aborted) — لا نوقف التجربة
      if (e?.error === "not-allowed" || e?.error === "service-not-allowed") {
        wantRef.current = false;
        setListening(false);
      }
    };

    rec.onend = () => {
      // التعرّف المستمر يتوقّف أحياناً بعد صمت — أعِد تشغيله ما دمنا نريد ذلك
      if (wantRef.current) {
        try { rec.start(); } catch { /* ignore */ }
      } else {
        setListening(false);
      }
    };

    try {
      rec.start();
      recRef.current = rec;
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [supported, Ctor, lang]);

  const stop = useCallback(() => {
    wantRef.current = false;
    setInterim("");
    try { recRef.current?.stop(); } catch { /* ignore */ }
    recRef.current = null;
    setListening(false);
  }, []);

  return { supported, listening, interim, finalText, start, stop };
}
