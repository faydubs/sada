import { useCallback, useEffect, useRef, useState } from "react";
import { auctionsApi, sessionsApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useAudioRecorder } from "../hooks/useAudioRecorder.js";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition.js";
import { useOnline } from "../hooks/useOnline.js";
import { addPending, getAllPending, removePending, countPending, purgeDemoPending } from "../lib/offlineQueue.js";
import { formatDuration, formatNumber } from "../lib/format.js";
import { Brand, Icon, Spinner } from "../components/ui.jsx";

// ── عرض "مسار التحليل" بصورة منطقية: عنوان عربي لكل خطوة + تفصيل ذي معنى ──────
const TRACE_TITLE = {
  transcribe: "تحويل الصوت إلى نص",
  transcribe_audio: "تحويل الصوت إلى نص",
  extract: "استخراج بيانات المزاد",
  extract_auction_data: "استخراج بيانات المزاد",
  classify: "تصنيف حالة المزاد",
  classify_auction_state: "تصنيف حالة المزاد",
  gemini: "تحليل ذكي (Gemini)",
  gemini_audio: "تحليل الصوت (Gemini)",
  gemini_text: "تحليل النص (Gemini)",
  parse_with_gemini: "تحليل ذكي (Gemini)",
  legacy_extractor: "المستخرِج المحلي",
  decision_route: "اختيار أدقّ مصدر",
  decision_confidence_gate: "تعزيز الثقة بالبصمة",
  voiceprint: "التحقق من البصمة الصوتية",
  verify_voiceprint: "التحقق من البصمة الصوتية",
};
const STATUS_AR = { ok: "تم", error: "تعذّر", skipped: "تُخطّي", low_confidence: "ثقة منخفضة", unavailable: "غير متاح" };

function traceTitle(t) {
  return TRACE_TITLE[t.skill] || TRACE_TITLE[t.step] || t.skill || t.step || "خطوة";
}
function traceDetail(t) {
  if (t.action) return t.action;
  if (t.is_match != null) return t.is_match ? `مطابقة (${t.best_score ?? "—"})` : "غير مطابقة";
  if (t.confidence != null) return typeof t.confidence === "number" ? t.confidence.toFixed(2) : t.confidence;
  if (t.route_chosen) return TRACE_TITLE[t.route_chosen] || "تم";
  if (t.chars != null) return `${formatNumber(t.chars)} حرف`;
  return STATUS_AR[t.status] || t.status || "—";
}
function traceOk(t) {
  return (t.status ? t.status === "ok" : true) && t.is_match !== false;
}

// نص → رقم أو null (للحقول العددية في نموذج المراجعة)
function num(v) {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

// يبني نموذج المراجعة القابل للتعديل من استجابة /process-audio
function buildForm(data) {
  const a = data?.analysis || {};
  const ex = data?.extracted || {};
  return {
    product_name: a.product_type ?? ex.product ?? "",
    quantity: a.quantity ?? ex.quantity ?? "",
    unit: a.unit ?? ex.unit ?? "",
    opening_price: a.opening_price ?? "",
    final_price: a.final_price ?? ex.price ?? "",
    buyer_name: a.buyer_name ?? "",
    buyer_number: a.buyer_number ?? ex.buyer_number ?? "",
    seller_name: a.seller_name ?? "",
    winner: a.winner ?? "",
    currency: a.currency ?? "SAR",
    notes: a.notes ?? "",
    status: a.status === "sold" ? "closed" : "active",
    // ميتاداتا تُمرَّر كما هي للحفظ (غير قابلة للتعديل من الواجهة)
    bids: Array.isArray(a.bids) ? a.bids : null,
    transcript: a.transcript ?? data?.transcription ?? "",
    confidence: a.confidence ?? null,
    analysis_status: a.status ?? null,
    model_used: a.model_used ?? null,
  };
}

/*
 * تبويب "تسجيل مزاد" للدلّال (التطبيق الجوال).
 * الميكروفون يبدأ الجلسة + التسجيل (مع عدّاد دقيق + إيقاف مؤقت + تفريغ حيّ).
 * بعد الإيقاف يُحلَّل المقطع، ثم تُعرض البيانات في نموذج قابل للتعديل، ولا
 * تُحفظ إلا بعد مراجعة الدلّال واعتماده. يدعم الوضع دون اتصال عبر IndexedDB.
 */
export default function LiveSession() {
  const { user } = useAuth();
  const online = useOnline();
  const speech = useSpeechRecognition("ar-SA");

  const [sessionId, setSessionId] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | processing | review
  const [form, setForm] = useState(null);      // نموذج المراجعة القابل للتعديل
  const [result, setResult] = useState(null);  // الاستجابة الخام (للمزايدات/المسار)
  const [saving, setSaving] = useState(false);
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

  // عند الإقلاع: نظّف أي تسجيل معلّق تجريبي قديم (ميزة أُلغيت) + اعرف عدد المعلّق،
  // ثم حُلّ الجلسة النشطة إن وُجدت ونحن متصلون.
  useEffect(() => {
    (async () => {
      try { await purgeDemoPending(); } catch { /* ignore */ }
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
        setForm(buildForm(data));
        setPhase("review");
      } catch (err) {
        setError(apiError(err, "تعذّرت معالجة المقطع — حُفظ محلياً لإعادة المحاولة."));
        try { await addPending({ file, sessionId: sessionRef.current ?? null, durationSec }); await refreshPending(); } catch { /* ignore */ }
        setPhase("idle");
      }
    },
    [online, ensureSession, refreshPending]
  );

  const { recording, paused, seconds, error: recError, start, pause, resume, stop } = useAudioRecorder(handleAudioReady);
  const recSecondsRef = useRef(0);
  recSecondsRef.current = seconds;

  async function handleMicPress() {
    setError(null);
    setNotice(null);
    if (recording) {
      stop();
      speech.stop();
      return;
    }
    if (online) {
      try { await ensureSession(); }
      catch (err) { setError(apiError(err, "تعذّر بدء الجلسة")); return; }
    }
    setResult(null);
    setForm(null);
    setPhase("idle");
    start();
    speech.start(); // تفريغ حيّ (يتدهور بلطف إن لم يكن مدعوماً)
  }

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  // حفظ المزاد بعد المراجعة → إنشاء سجل + إنهاء الجلسة (لا حفظ تلقائي قبل ذلك)
  async function saveAuction() {
    if (!form?.product_name?.trim()) { setError("أدخل نوع التمر قبل الحفظ"); return; }
    const id = sessionRef.current;
    if (!id) { setError("لا توجد جلسة نشطة"); return; }
    setSaving(true);
    setError(null);
    try {
      await auctionsApi.create({
        session_id: id,
        product_name: form.product_name.trim(),
        quantity: num(form.quantity) ?? 1,
        unit: form.unit?.trim() || "غير محدد",
        opening_price: num(form.opening_price),
        final_price: num(form.final_price),
        buyer_name: form.buyer_name?.trim() || null,
        buyer_number: form.buyer_number?.trim() || null,
        seller_name: form.seller_name?.trim() || null,
        winner: form.winner?.trim() || null,
        currency: form.currency?.trim() || "SAR",
        bids: form.bids || null,
        notes: form.notes?.trim() || null,
        transcript: form.transcript || null,
        confidence: form.confidence ?? null,
        analysis_status: form.analysis_status || null,
        model_used: form.model_used || null,
        status: form.status === "closed" ? "closed" : "active",
      });
      await sessionsApi.end(id);
      setSessionId(null);
      setForm(null);
      setResult(null);
      setPhase("idle");
      setNotice("تم حفظ المزاد وإنهاء الجلسة ✓");
    } catch (err) {
      setError(apiError(err, "تعذّر حفظ المزاد"));
    } finally {
      setSaving(false);
    }
  }

  function discardReview() {
    setForm(null);
    setResult(null);
    setPhase("idle");
  }

  // تفريغ الطابور المعلّق (تسجيلات الأوفلاين الحقيقية) — يعرض آخرها للمراجعة
  const flushQueue = useCallback(async () => {
    if (flushing) return;
    const items = await getAllPending();
    if (!items.length) return;
    setFlushing(true);
    setError(null);
    let done = 0, failed = 0, lastData = null;
    for (const item of items) {
      setFlushProgress({ done, total: items.length });
      try {
        const id = item.sessionId || (await ensureSession());
        const file = new File([item.file], `queued.${(item.file.type || "audio/webm").includes("mp4") ? "mp4" : "webm"}`, { type: item.file.type || "audio/webm" });
        const { data } = await auctionsApi.processAudio(id, file);
        lastData = data;
        await removePending(item.id);
        done += 1;
      } catch {
        failed += 1;
      }
    }
    setFlushProgress(null);
    setFlushing(false);
    await refreshPending();
    if (lastData) {
      setResult(lastData);
      setForm(buildForm(lastData));
      setPhase("review");
    }
    setNotice(
      failed === 0
        ? `تم تحليل ${formatNumber(done)} تسجيل معلّق ✓ (راجِع الأخير واحفظه)`
        : `حُلّل ${formatNumber(done)} وتعذّر ${formatNumber(failed)} — أعد المحاولة لاحقاً.`
    );
  }, [flushing, ensureSession, refreshPending]);

  useEffect(() => {
    if (online && pending > 0 && !flushing && !recording) flushQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  const showBanner = pending > 0 || !online;
  const liveText = (speech.finalText + " " + speech.interim).trim();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: "100%" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
        <Brand size={34} showTag={false} />
        <span className={"chip " + (online ? "chip-green" : "chip-muted")}>
          <span className="pulse" style={{ width: 6, height: 6, background: online ? undefined : "var(--ink-faint)" }} />
          {online ? "متصل" : "دون اتصال"}
        </span>
      </header>

      {/* بانر التسجيلات المعلّقة (أوفلاين حقيقي) أو انقطاع الاتصال */}
      {showBanner && (
        <div className="glass glass-2" style={{ padding: "13px 15px", display: "flex", alignItems: "center", gap: 12, borderRadius: 18 }}>
          <div className="kpi-ico" style={{ width: 36, height: 36, color: pending ? "var(--brown-700)" : "var(--ink-faint)" }}>
            <Icon name={pending ? "box" : "sound"} size={18} />
          </div>
          <div style={{ flex: 1, fontSize: 13.5 }}>
            {pending > 0 ? (
              <>لديك <b className="num">{formatNumber(pending)}</b> تسجيل معلّق بانتظار التحليل</>
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

      {/* منطقة الميكروفون */}
      {phase !== "review" && (
        <div className="glass glass-2 panel" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: "32px 20px", textAlign: "center" }}>
          <div className={"waveform" + (recording && !paused ? "" : " idle")} aria-hidden="true">
            {[...Array(15)].map((_, i) => <span key={i} style={{ animationDelay: i * 0.07 + "s" }} />)}
          </div>

          <button
            className={"rec-btn" + (recording ? " recording" : "")}
            style={{ width: 128, height: 128 }}
            onClick={handleMicPress}
            disabled={phase === "processing"}
            title={recording ? "إيقاف" : "ابدأ المزاد"}
          >
            {phase === "processing" ? <Spinner style={{ width: 40, height: 40 }} /> : <Icon name={recording ? "stop" : "mic"} size={50} />}
          </button>

          <div>
            <div className="num" style={{ fontSize: 22, fontWeight: 700, color: paused ? "var(--ink-soft)" : "var(--brown-800)" }}>
              {phase === "processing" ? "جارٍ التحليل…" : recording ? formatDuration(seconds) : "ابدأ المزاد"}
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 4 }}>
              {phase === "processing"
                ? "تحويل الصوت واستخراج البيانات"
                : paused
                ? "التسجيل متوقّف مؤقتاً"
                : recording
                ? "اضغط لإيقاف التسجيل وعرض التحليل"
                : online
                ? "اضغط الميكروفون لبدء الجلسة والتسجيل"
                : "اضغط للتسجيل — سيُحفظ محلياً حتى عودة الاتصال"}
            </div>
            {recError && <div style={{ fontSize: 12, color: "#7e2a1c", marginTop: 6 }}>{recError}</div>}
          </div>

          {/* إيقاف مؤقت / استئناف أثناء التسجيل */}
          {recording && (
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: "9px 18px", fontSize: 13.5 }}
              onClick={paused ? resume : pause}
            >
              <Icon name={paused ? "mic" : "stop"} size={15} /> {paused ? "استئناف" : "إيقاف مؤقت"}
            </button>
          )}

          {/* التفريغ المباشر أثناء التسجيل */}
          {recording && speech.supported && (
            <div className="glass-inset" style={{ width: "100%", padding: "12px 14px", minHeight: 54, textAlign: "start" }}>
              <div style={{ fontSize: 11.5, color: "var(--ink-faint)", marginBottom: 4, display: "flex", alignItems: "center", gap: 5 }}>
                <span className="pulse" style={{ width: 6, height: 6 }} /> التفريغ المباشر
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.8, color: "var(--brown-800)" }}>
                {speech.finalText}
                {speech.interim && <span style={{ color: "var(--ink-faint)" }}> {speech.interim}</span>}
                {!liveText && <span style={{ color: "var(--ink-faint)" }}>… أستمع</span>}
              </div>
            </div>
          )}

          {/* إنهاء الجلسة الحالية (إن كانت مفتوحة ولسنا نسجّل) */}
          {!recording && phase === "idle" && sessionId && (
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: "7px 14px", fontSize: 12.5 }}
              onClick={async () => {
                try { await sessionsApi.end(sessionId); setSessionId(null); setNotice("تم إنهاء الجلسة الحالية ✓"); }
                catch (err) { setError(apiError(err, "تعذّر إنهاء الجلسة")); }
              }}
            >
              <Icon name="check" size={14} /> إنهاء الجلسة الحالية
            </button>
          )}
        </div>
      )}

      {/* نموذج المراجعة القابل للتعديل — لا حفظ إلا بعد مراجعة الدلّال */}
      {phase === "review" && form && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="glass glass-2 panel">
            <div className="panel-head">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Icon name="spark" size={18} style={{ color: "var(--green-700)" }} />
                <h3 style={{ fontSize: 16, color: "var(--brown-800)" }}>راجِع وعدّل قبل الحفظ</h3>
              </div>
              <span className="chip chip-muted" style={{ fontSize: 11.5 }}>تحرير</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <ReviewField label="نوع التمر" value={form.product_name} onChange={(v) => setField("product_name", v)} span2 />
              <ReviewField label="الكمية" value={form.quantity} onChange={(v) => setField("quantity", v)} type="number" />
              <ReviewField label="الوحدة" value={form.unit} onChange={(v) => setField("unit", v)} placeholder="كرتون / صندوق / كيلو" />
              <ReviewField label="سعر الافتتاح" value={form.opening_price} onChange={(v) => setField("opening_price", v)} type="number" />
              <ReviewField label="السعر النهائي" value={form.final_price} onChange={(v) => setField("final_price", v)} type="number" />
              <ReviewField label="اسم المشتري" value={form.buyer_name} onChange={(v) => setField("buyer_name", v)} />
              <ReviewField label="رقم المشتري" value={form.buyer_number} onChange={(v) => setField("buyer_number", v)} placeholder="مثل: ٥" />
              <ReviewField label="البائع" value={form.seller_name} onChange={(v) => setField("seller_name", v)} />
              <ReviewField label="الفائز" value={form.winner} onChange={(v) => setField("winner", v)} />
              <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>الحالة</span>
                <select className="rv-input" value={form.status} onChange={(e) => setField("status", e.target.value)}>
                  <option value="active">جارٍ/مفتوح</option>
                  <option value="closed">تم البيع</option>
                </select>
              </div>
              <ReviewField label="العملة" value={form.currency} onChange={(v) => setField("currency", v)} />
              <ReviewField label="ملاحظات" value={form.notes} onChange={(v) => setField("notes", v)} span2 />
            </div>

            {/* قراءة فقط: تسلسل المزايدات الذي استخرجه الذكاء الاصطناعي */}
            {Array.isArray(form.bids) && form.bids.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 12.5, color: "var(--ink-soft)", marginBottom: 6 }}>تسلسل المزايدات (من التحليل)</div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                  {form.bids.map((b, i) => (
                    <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span className="chip chip-green" style={{ padding: "3px 10px", fontSize: 12 }}>
                        {formatNumber(b.price)}{b.bidder ? ` · ${b.bidder}` : ""}
                      </span>
                      {i < form.bids.length - 1 && <span style={{ color: "var(--ink-faint)" }}>←</span>}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {form.transcript && (
              <div style={{ marginTop: 12, fontSize: 13, lineHeight: 1.8, color: "var(--ink-soft)", background: "rgba(255,252,246,0.4)", borderRadius: 12, padding: "10px 14px" }}>
                «{form.transcript}»
              </div>
            )}
          </div>

          {/* مسار التحليل (إن وُجد) */}
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
            <button className="btn btn-ghost" style={{ flex: 1, padding: 14 }} onClick={discardReview} disabled={saving}>
              <Icon name="mic" size={17} /> تسجيل آخر
            </button>
            <button className="btn btn-green" style={{ flex: 1, padding: 14 }} onClick={saveAuction} disabled={saving}>
              {saving ? <><Spinner /> جارٍ الحفظ…</> : <><Icon name="check" size={17} /> اعتماد وحفظ</>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* حقل إدخال قابل للتعديل في نموذج المراجعة. */
function ReviewField({ label, value, onChange, type = "text", placeholder, span2 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5, gridColumn: span2 ? "1 / -1" : "auto" }}>
      <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>{label}</span>
      <input
        className="rv-input"
        type={type}
        inputMode={type === "number" ? "decimal" : undefined}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
