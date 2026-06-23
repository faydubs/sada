import { useCallback, useEffect, useRef, useState } from "react";
import { auctionsApi, sessionsApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useAudioRecorder } from "../hooks/useAudioRecorder.js";
import { useOnline } from "../hooks/useOnline.js";
import { addPending, getAllPending, removePending, countPending, seedDemoPending } from "../lib/offlineQueue.js";
import { CONFIDENCE, formatCurrency, formatDuration, formatNumber } from "../lib/format.js";
import { Brand, Icon, Spinner } from "../components/ui.jsx";

const ACTION_LABEL = {
  افتتاح: { txt: "افتتاح", cls: "chip-green" },
  إغلاق: { txt: "إغلاق", cls: "chip-green" },
  جارٍ: { txt: "جارٍ", cls: "chip-muted" },
};

// ── عرض "مسار التحليل" بصورة منطقية: عنوان عربي لكل خطوة + تفصيل ذي معنى ──────
const TRACE_TITLE = {
  transcribe: "تحويل الصوت إلى نص",
  transcribe_audio: "تحويل الصوت إلى نص",
  extract: "استخراج بيانات المزاد",
  extract_auction_data: "استخراج بيانات المزاد",
  classify: "تصنيف حالة المزاد",
  classify_auction_state: "تصنيف حالة المزاد",
  gemini: "تحليل ذكي (Gemini)",
  parse_with_gemini: "تحليل ذكي (Gemini)",
  decision_route: "اختيار أدقّ مصدر",
  decision_confidence_gate: "تعزيز الثقة بالبصمة",
  voiceprint: "التحقق من البصمة الصوتية",
  verify_voiceprint: "التحقق من البصمة الصوتية",
};
const STATUS_AR = { ok: "تم", error: "تعذّر", skipped: "تُخطّي", low_confidence: "ثقة منخفضة", unavailable: "غير متاح" };
const ROUTE_AR = {
  extractor_only: "المستخرِج المحلي",
  gemini: "Gemini",
  gemini_low_fallback_extractor: "المستخرِج المحلي",
  gemini_low_kept: "Gemini",
  voiceprint_boost: "تعزيز بالبصمة",
  offline_demo: "وضع الأوفلاين",
  none_empty_transcript: "لا يوجد كلام",
};

function traceTitle(t) {
  return TRACE_TITLE[t.skill] || TRACE_TITLE[t.step] || t.skill || t.step || "خطوة";
}
function traceDetail(t) {
  if (t.action) return t.action;                                       // إغلاق / افتتاح / جارٍ
  if (t.is_match != null) return t.is_match ? `مطابقة (${t.best_score ?? "—"})` : "غير مطابقة";
  if (t.confidence) return CONFIDENCE[t.confidence]?.label || t.confidence;
  if (t.route_chosen) return ROUTE_AR[t.route_chosen] || "تم";
  if (t.chars != null) return `${formatNumber(t.chars)} حرف`;
  return STATUS_AR[t.status] || t.status || "—";
}
function traceOk(t) {
  return (t.status ? t.status === "ok" : true) && t.is_match !== false;
}

/*
 * تبويب "تسجيل مزاد" للدلّال (التطبيق الجوال).
 * الميكروفون هو العنصر الأبرز: ضغطه يبدأ الجلسة + التسجيل؛ عند الإيقاف تُحلَّل
 * النتيجة وتُعرض، ثم زر "اعتماد" يثبّتها. يدعم الوضع دون اتصال عبر طابور IndexedDB.
 */
export default function LiveSession() {
  const { user } = useAuth();
  const online = useOnline();

  const [sessionId, setSessionId] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | processing | result
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [pending, setPending] = useState(0);
  const [flushing, setFlushing] = useState(false);
  const [flushProgress, setFlushProgress] = useState(null);

  const sessionRef = useRef(null);
  sessionRef.current = sessionId;

  const refreshPending = useCallback(async () => {
    try { setPending(await countPending()); } catch { /* ignore */ }
  }, []);

  // عند الإقلاع: ازرع تسجيلاً معلّقاً تجريبياً (مرة واحدة) لعرض تجربة الأوفلاين،
  // ثم حُلّ الجلسة النشطة (إن وُجدت ونحن متصلون) + اعرف عدد المعلّق
  useEffect(() => {
    (async () => {
      try { await seedDemoPending(false); } catch { /* ignore */ }
      refreshPending();
    })();
    if (!online) return;
    (async () => {
      try {
        const { data } = await sessionsApi.list();
        const active = data.find((s) => s.status === "active");
        if (active) setSessionId(active.id);
      } catch { /* ignore — تُنشأ عند أول تسجيل */ }
    })();
  }, [online, refreshPending]);

  // يضمن وجود جلسة نشطة (يعيد id) — يُنشئها عند الحاجة (يتطلب اتصالاً)
  const ensureSession = useCallback(async () => {
    if (sessionRef.current) return sessionRef.current;
    const { data } = await sessionsApi.list();
    const active = data.find((s) => s.status === "active");
    let id;
    if (active) id = active.id;
    else id = (await sessionsApi.start(user.id)).data.id;
    setSessionId(id);
    return id;
  }, [user.id]);

  // عند جهوزية المقطع الصوتي (إيقاف التسجيل)
  const handleAudioReady = useCallback(
    async (file) => {
      setError(null);
      const durationSec = recSecondsRef.current;
      if (!online) {
        // دون اتصال: احفظ محلياً واخرج
        try {
          await addPending({ file, sessionId: sessionRef.current ?? null, durationSec });
          await refreshPending();
          setNotice("لا يوجد اتصال — حُفظ التسجيل محلياً وسيُحلَّل عند عودة الإنترنت.");
        } catch {
          setError("تعذّر حفظ التسجيل محلياً");
        }
        setPhase("idle");
        return;
      }
      setPhase("processing");
      try {
        const id = await ensureSession();
        const { data } = await auctionsApi.processAudio(id, file);
        setResult(data);
        setPhase("result");
      } catch (err) {
        setError(apiError(err, "تعذّرت معالجة المقطع — حُفظ محلياً لإعادة المحاولة."));
        // فشل الإرسال رغم الاتصال → احفظه في الطابور حتى لا يضيع
        try { await addPending({ file, sessionId: sessionRef.current ?? null, durationSec }); await refreshPending(); } catch { /* ignore */ }
        setPhase("idle");
      }
    },
    [online, ensureSession, refreshPending]
  );

  const { recording, seconds, error: recError, start, stop } = useAudioRecorder(handleAudioReady);
  const recSecondsRef = useRef(0);
  recSecondsRef.current = seconds;

  async function handleMicPress() {
    setError(null);
    setNotice(null);
    if (recording) { stop(); return; }
    // ابدأ الجلسة (إن أمكن) ثم التسجيل
    if (online) {
      try { await ensureSession(); }
      catch (err) { setError(apiError(err, "تعذّر بدء الجلسة")); return; }
    }
    setResult(null);
    setPhase("idle");
    start();
  }

  // اعتماد النتيجة → إنهاء الجلسة وتثبيت المبيعات
  async function confirmResult() {
    const id = sessionRef.current;
    if (!id) { setPhase("idle"); setResult(null); return; }
    try {
      await sessionsApi.end(id);
      setSessionId(null);
      setResult(null);
      setPhase("idle");
      setNotice("تم اعتماد المزاد وإنهاء الجلسة ✓");
    } catch (err) {
      setError(apiError(err, "تعذّر اعتماد الجلسة"));
    }
  }

  // تحليل الطابور المعلّق (يدوياً أو تلقائياً عند عودة الاتصال)
  const flushQueue = useCallback(async () => {
    if (flushing) return;
    const items = await getAllPending();
    if (!items.length) return;
    setFlushing(true);
    setError(null);
    let done = 0;
    let failed = 0;
    let lastResult = null; // نتيجة آخر تسجيل أوفلاين تمّت معالجته — لعرضها للدلّال
    for (const item of items) {
      setFlushProgress({ done, total: items.length });
      try {
        // تسجيل تجريبي: نعرض نتيجته الجاهزة دون اتصال بالخادم (محاكاة الأوفلاين).
        if (item.demo) {
          lastResult = item.demoResult;
          await removePending(item.id);
          done += 1;
          continue;
        }
        const id = item.sessionId || (await ensureSession());
        const file = new File([item.file], `queued.${(item.file.type || "audio/webm").includes("mp4") ? "mp4" : "webm"}`, { type: item.file.type || "audio/webm" });
        const { data } = await auctionsApi.processAudio(id, file);
        lastResult = data;
        await removePending(item.id);
        done += 1;
      } catch {
        failed += 1; // أبقِ العنصر في الطابور لإعادة المحاولة لاحقاً
      }
    }
    setFlushProgress(null);
    setFlushing(false);
    await refreshPending();
    // اعرض نتيجة آخر جلسة أوفلاين حُلّلت حتى يرى الدلّال مخرجاتها مباشرة.
    if (lastResult) {
      setResult(lastResult);
      setPhase("result");
    }
    setNotice(
      failed === 0
        ? `تم تحليل ${formatNumber(done)} جلسة معلّقة ✓ (تُعرض نتيجة الأخيرة)`
        : `حُلّلت ${formatNumber(done)} وتعذّر ${formatNumber(failed)} — أعد المحاولة لاحقاً.`
    );
  }, [flushing, ensureSession, refreshPending]);

  // تفريغ تلقائي عند عودة الاتصال
  useEffect(() => {
    if (online && pending > 0 && !flushing && !recording) flushQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  const showBanner = pending > 0 || !online;
  const ex = result?.extracted;
  const action = ex?.action || "جارٍ";
  const actionMeta = ACTION_LABEL[action] || ACTION_LABEL["جارٍ"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: "100%" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
        <Brand size={34} showTag={false} />
        <span className={"chip " + (online ? "chip-green" : "chip-muted")}>
          <span className="pulse" style={{ width: 6, height: 6, background: online ? undefined : "var(--ink-faint)" }} />
          {online ? "متصل" : "دون اتصال"}
        </span>
      </header>

      {/* بانر الجلسات المعلّقة — يظهر فقط عند وجود معلّق أو انقطاع الاتصال */}
      {showBanner && (
        <div className="glass glass-2" style={{ padding: "13px 15px", display: "flex", alignItems: "center", gap: 12, borderRadius: 18 }}>
          <div className="kpi-ico" style={{ width: 36, height: 36, color: pending ? "var(--brown-700)" : "var(--ink-faint)" }}>
            <Icon name={pending ? "box" : "sound"} size={18} />
          </div>
          <div style={{ flex: 1, fontSize: 13.5 }}>
            {pending > 0 ? (
              <>لديك <b className="num">{formatNumber(pending)}</b> جلسة معلّقة بانتظار التحليل</>
            ) : (
              <span style={{ color: "var(--ink-soft)" }}>لا يوجد اتصال — سيُحفظ تسجيلك محلياً</span>
            )}
          </div>
          {pending > 0 && (
            <button className="btn btn-primary" style={{ padding: "9px 16px", fontSize: 13 }} onClick={flushQueue} disabled={flushing || !online} title={!online ? "بانتظار الاتصال" : "تحليل"}>
              {flushing ? <><Spinner /> {flushProgress ? `${formatNumber(flushProgress.done)}/${formatNumber(flushProgress.total)}` : ""}</> : <><Icon name="refresh" size={15} /> تحليل</>}
            </button>
          )}
        </div>
      )}

      {error && <div className="banner banner-error">{error}</div>}
      {notice && <div className="banner banner-ok">{notice}</div>}

      {/* منطقة الميكروفون — العنصر الأبرز */}
      {phase !== "result" && (
        <div className="glass glass-2 panel" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 18, padding: "40px 20px", textAlign: "center" }}>
          <div className={"waveform" + (recording ? "" : " idle")} aria-hidden="true">
            {[...Array(15)].map((_, i) => <span key={i} style={{ animationDelay: i * 0.07 + "s" }} />)}
          </div>

          <button
            className={"rec-btn" + (recording ? " recording" : "")}
            style={{ width: 132, height: 132 }}
            onClick={handleMicPress}
            disabled={phase === "processing"}
            title={recording ? "إيقاف" : "ابدأ المزاد"}
          >
            {phase === "processing" ? <Spinner style={{ width: 40, height: 40 }} /> : <Icon name={recording ? "stop" : "mic"} size={52} />}
          </button>

          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: "var(--brown-800)" }}>
              {phase === "processing" ? "جارٍ التحليل…" : recording ? formatDuration(seconds) : "ابدأ المزاد"}
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 4 }}>
              {phase === "processing"
                ? "تحويل الصوت واستخراج البيانات"
                : recording
                ? "اضغط لإيقاف التسجيل وعرض التحليل"
                : online
                ? "اضغط الميكروفون لبدء الجلسة والتسجيل"
                : "اضغط للتسجيل — سيُحفظ محلياً حتى عودة الاتصال"}
            </div>
            {recError && <div style={{ fontSize: 12, color: "#7e2a1c", marginTop: 6 }}>{recError}</div>}
          </div>

          {/* تجربة تسجيل معلّق (أوفلاين) كبروتوتايب — يضيف عنصراً للطابور لعرضه */}
          {phase === "idle" && !recording && (
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: "8px 14px", fontSize: 12.5 }}
              onClick={async () => { await seedDemoPending(true); await refreshPending(); setNotice("أُضيف تسجيل معلّق تجريبي — اضغط «تحليل» في الأعلى لعرض نتيجته."); }}
            >
              <Icon name="box" size={15} /> تجربة تسجيل معلّق (أوفلاين)
            </button>
          )}
        </div>
      )}

      {/* نتيجة التحليل + اعتماد */}
      {phase === "result" && ex && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass glass-2 panel">
            <div className="panel-head">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Icon name="spark" size={18} style={{ color: "var(--green-700)" }} />
                <h3 style={{ fontSize: 16, color: "var(--brown-800)" }}>نتيجة التحليل</h3>
              </div>
              <span className={"chip " + actionMeta.cls}>{actionMeta.txt}</span>
            </div>

            <div className="glass-inset" style={{ padding: "16px 18px", marginBottom: 12, textAlign: "center" }}>
              <div style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>السعر</div>
              <div className="kv-val" style={{ fontSize: 36, fontWeight: 300 }}>{ex.price != null ? formatCurrency(ex.price) : "—"}</div>
            </div>

            {[
              ["نوع التمر", "box", ex.product || "—"],
              ["الوحدة", "scale", ex.unit || "—"],
              ["ثقة الاستخراج", "check", ex.confidence ? CONFIDENCE[ex.confidence]?.label || ex.confidence : "—"],
            ].map(([label, icon, val]) => (
              <div className="kv" key={label}>
                <span className="kv-label"><Icon name={icon} size={16} style={{ color: "var(--ink-faint)" }} /> {label}</span>
                <span style={{ fontWeight: 600, fontSize: 15, color: "var(--brown-800)" }}>{val}</span>
              </div>
            ))}

            {result?.transcription && (
              <div style={{ marginTop: 12, fontSize: 13, lineHeight: 1.8, color: "var(--ink-soft)", background: "rgba(255,252,246,0.4)", borderRadius: 12, padding: "10px 14px" }}>
                «{result.transcription}»
              </div>
            )}
          </div>

          {/* أثر قرارات الوكيل (إن وُجد) */}
          {Array.isArray(result?.trace) && result.trace.length > 0 && (
            <div className="glass glass-2 panel">
              <div className="panel-head"><h3 style={{ fontSize: 14, color: "var(--brown-800)" }}>مسار التحليل</h3></div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {result.trace.map((t, i) => {
                  const ok = traceOk(t);
                  return (
                    <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13 }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--brown-800)" }}>
                        <span style={{ width: 7, height: 7, borderRadius: "50%", background: ok ? "var(--green-700)" : "var(--ink-faint)", flexShrink: 0 }} />
                        {traceTitle(t)}
                      </span>
                      <span className={"chip " + (ok ? "chip-green" : "chip-muted")} style={{ padding: "2px 10px", fontSize: 11.5 }}>{traceDetail(t)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-ghost" style={{ flex: 1, padding: 14 }} onClick={() => { setResult(null); setPhase("idle"); }}>
              <Icon name="mic" size={17} /> تسجيل آخر
            </button>
            <button className="btn btn-green" style={{ flex: 1, padding: 14 }} onClick={confirmResult}>
              <Icon name="check" size={17} /> اعتماد وإنهاء
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
