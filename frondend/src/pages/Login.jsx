import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { apiError } from "../api/client.js";
import { authApi } from "../api/endpoints.js";
import { useAudioRecorder } from "../hooks/useAudioRecorder.js";
import { formatDuration } from "../lib/format.js";
import { Brand, Logo, Icon, Spinner } from "../components/ui.jsx";

export default function Login({ initialMode = "login" }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname;

  // stage: splash → role → auth
  const splashSeen = sessionStorage.getItem("sada_splash_seen");
  const [stage, setStage] = useState(splashSeen ? "role" : "splash");
  const [fading, setFading] = useState(false);
  const [role, setRole] = useState(null); // dallal | admin

  const [mode, setMode] = useState(initialMode); // login | signup
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [voiceFile, setVoiceFile] = useState(null);
  const [adminCode, setAdminCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("");

  const { recording, seconds, error: recError, start, stop } = useAudioRecorder((file) =>
    setVoiceFile(file)
  );

  // مؤقّت شاشة الترحيب: تلاشٍ بعد ٥ ثوانٍ
  useEffect(() => {
    if (stage !== "splash") return;
    const f = setTimeout(() => setFading(true), 4400);
    const t = setTimeout(() => {
      sessionStorage.setItem("sada_splash_seen", "1");
      setStage("role");
    }, 5000);
    return () => {
      clearTimeout(f);
      clearTimeout(t);
    };
  }, [stage]);

  function skipSplash() {
    sessionStorage.setItem("sada_splash_seen", "1");
    setStage("role");
  }

  function chooseRole(r) {
    setRole(r);
    setMode("login");
    setError(null);
    setVoiceFile(null);
    setAdminCode("");
    setStage("auth");
  }

  function backToRole() {
    setStage("role");
    setError(null);
    setVoiceFile(null);
    setConfirm("");
    setAdminCode("");
  }

  function switchMode(m) {
    setMode(m);
    setError(null);
    setVoiceFile(null);
  }

  function pickFile(e) {
    const f = e.target.files?.[0];
    if (f) setVoiceFile(f);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (mode === "login") {
      setBusy(true);
      try {
        const u = await login(username.trim(), password);
        navigate(from || (u?.role === "admin" ? "/admin" : "/"), { replace: true });
      } catch (err) {
        setError(apiError(err, "تعذّر تسجيل الدخول"));
      } finally {
        setBusy(false);
      }
      return;
    }

    // signup
    if (password.length < 6) return setError("كلمة المرور 6 أحرف على الأقل");
    if (password !== confirm) return setError("كلمتا المرور غير متطابقتين");
    if (role === "admin" && !adminCode.trim()) return setError("أدخل رمز المسؤول");

    setBusy(true);
    try {
      if (role === "dallal") {
        // الخطوة الأولى: إنشاء الحساب فقط — البصمة الصوتية تأتي في خطوة مستقلّة بعدها
        setStep("جارٍ إنشاء الحساب…");
        await register(username.trim(), password);
        setStage("voiceprint");
      } else {
        setStep("جارٍ إنشاء حساب المسؤول…");
        await authApi.registerAdmin(username.trim(), password, adminCode.trim());
        await login(username.trim(), password);
        navigate("/admin", { replace: true });
      }
    } catch (err) {
      setError(apiError(err, "تعذّر إنشاء الحساب"));
    } finally {
      setBusy(false);
      setStep("");
    }
  }

  // ── الخطوة الثانية للدلّال: حفظ البصمة الصوتية بعد إنشاء الحساب ──────────────
  async function saveVoiceprint() {
    if (!voiceFile) return setError("سجّل صوتك أو ارفع ملفاً أولاً");
    setBusy(true);
    setError(null);
    setStep("جارٍ حفظ البصمة الصوتية…");
    try {
      await authApi.uploadVoiceprint(voiceFile);
      navigate("/", { replace: true });
    } catch (err) {
      setError(apiError(err, "تعذّر حفظ البصمة الصوتية"));
    } finally {
      setBusy(false);
      setStep("");
    }
  }

  function skipVoiceprint() {
    // الحساب أُنشئ ودخل بالفعل؛ يمكن تسجيل البصمة لاحقاً من صفحة الحساب
    navigate("/", { replace: true });
  }

  // ── المرحلة 1: شاشة الترحيب ───────────────────────────────────────────────
  if (stage === "splash") {
    return (
      <div className={"splash" + (fading ? " fade" : "")} onClick={skipSplash}>
        <div className="splash-inner">
          <Logo size={104} />
          <div className="splash-title">صدى التمر</div>
          <div className="splash-tag">صوت المزاد .. بيانات تدوم</div>
          <p className="splash-desc">
            منصّة ذكية تحوّل مزادات التمور الصوتية المباشرة إلى بياناتٍ منظّمة
            وتحليلاتٍ فورية بالذكاء الاصطناعي.
          </p>
          <div className="splash-dots" aria-hidden="true">
            <i /><i /><i />
          </div>
          <div className="splash-skip">اضغط للتخطّي</div>
        </div>
      </div>
    );
  }

  // ── المرحلة 2: اختيار الدور ───────────────────────────────────────────────
  if (stage === "role") {
    return (
        <div className="role-wrap">
          <div className="role-inner">
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 6 }}>
              <Brand size={44} showTag={false} />
            </div>
            <h1 className="display" style={{ fontSize: 34, fontFamily: "var(--font-ar)", fontWeight: 600, marginTop: 14 }}>
              اختر طريقة الدخول
            </h1>
            <p style={{ color: "var(--ink-soft)", fontSize: 15, marginTop: 8 }}>
              كل دور له تجربته الخاصة في المنصّة.
            </p>

            <div className="role-cards">
              <button type="button" className="glass glass-2 role-card dallal" onClick={() => chooseRole("dallal")}>
                <div className="role-ico"><Icon name="mic" size={28} /></div>
                <h3>دلّال</h3>
                <p>سجّل مزاداتك بصوتك وحوّلها إلى بيانات — مع بصمة صوتية للتعرّف عليك، ثم ابدأ العمل مباشرة.</p>
              </button>
              <button type="button" className="glass glass-2 role-card admin" onClick={() => chooseRole("admin")}>
                <div className="role-ico"><Icon name="chart" size={28} /></div>
                <h3>مسؤول</h3>
                <p>تابع الإحصائيات والتقارير، وأدِر الدلّالين والمستخدمين وجميع الجلسات.</p>
              </button>
            </div>
          </div>
        </div>
    );
  }

  // ── الخطوة الثانية للدلّال: تسجيل البصمة الصوتية (بعد إنشاء الحساب) ─────────
  if (stage === "voiceprint") {
    return (
        <div className="auth-wrap">
          <div className="auth-stack" style={{ maxWidth: 460 }}>
            <div className="glass glass-2 auth-card">
              <div style={{ marginBottom: 18 }}>
                <span className="chip chip-green"><Icon name="check" size={14} /> تم إنشاء حسابك</span>
              </div>

              <h1 className="display" style={{ fontSize: 34, fontFamily: "var(--font-ar)", fontWeight: 600, marginBottom: 6 }}>
                سجّل بصمتك الصوتية
              </h1>
              <p style={{ color: "var(--ink-soft)", fontSize: 15, margin: "0 0 16px" }}>
                نسجّل صوتك مرة واحدة لنتعرّف عليك تلقائياً في مزاداتك القادمة. اضغط الميكروفون واقرأ الجملة التالية بصوتٍ واضح (١٠–٣٠ ثانية)، أو ارفع ملفاً صوتياً.
              </p>

              {/* جملة موحّدة يقرأها الدلّال أثناء التسجيل — تحسّن جودة البصمة */}
              <div
                className="glass-inset"
                style={{ padding: "16px 18px", marginBottom: 18, textAlign: "center", borderRight: "3px solid var(--green-700)" }}
              >
                <div style={{ fontSize: 12, color: "var(--ink-faint)", marginBottom: 6, display: "flex", alignItems: "center", gap: 6, justifyContent: "center" }}>
                  <Icon name="mic" size={14} style={{ color: "var(--green-700)" }} /> اقرأ هذه الجملة بصوتك
                </div>
                <p style={{ fontSize: 17, lineHeight: 2, fontWeight: 600, color: "var(--brown-800)", margin: 0, fontFamily: "var(--font-ar)" }}>
                  «بسم الله، أفتح حراج الليلة على تمر السكري الفاخر من مزارع القصيم،
                  البداية من مئة ريال، من يزيد؟ … بيع مبارك على أبو فهد.»
                </p>
              </div>

              {error && <div className="banner banner-error" style={{ marginBottom: 16 }}>{error}</div>}

              <div className="glass-inset" style={{ padding: "20px 18px", display: "flex", flexDirection: "column", gap: 16, alignItems: "center" }}>
                <button
                  type="button"
                  className={"rec-btn" + (recording ? " recording" : "")}
                  style={{ width: 92, height: 92 }}
                  onClick={recording ? stop : start}
                  disabled={busy}
                  title={recording ? "إيقاف" : "تسجيل"}
                >
                  <Icon name={recording ? "stop" : "mic"} size={34} />
                </button>
                <div style={{ fontSize: 14, color: "var(--ink-soft)", textAlign: "center" }}>
                  {voiceFile
                    ? "تم تجهيز التسجيل ✓"
                    : recording
                    ? `يسجّل… ${formatDuration(seconds)}`
                    : "اضغط على الميكروفون للبدء"}
                </div>

                {voiceFile ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="chip chip-green"><Icon name="check" size={14} /> جاهز للحفظ</span>
                    <button type="button" className="btn btn-ghost" style={{ padding: "8px 14px", fontSize: 13 }} onClick={() => setVoiceFile(null)} disabled={busy}>
                      إعادة التسجيل
                    </button>
                  </div>
                ) : (
                  <label className="btn btn-ghost" style={{ padding: "9px 16px", fontSize: 13, cursor: "pointer" }}>
                    <Icon name="download" size={16} /> رفع ملف صوتي
                    <input type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.webm,.mp4" onChange={pickFile} style={{ display: "none" }} />
                  </label>
                )}
                {recError && <p style={{ color: "#7e2a1c", fontSize: 12, margin: 0 }}>{recError}</p>}
              </div>

              <button type="button" className="btn btn-primary" style={{ marginTop: 18, padding: "16px", width: "100%" }} onClick={saveVoiceprint} disabled={busy || !voiceFile}>
                {busy ? <><Spinner /> {step}</> : <>حفظ البصمة والمتابعة <Icon name="arrowL" size={19} /></>}
              </button>
              <button type="button" className="role-back" style={{ marginTop: 14, alignSelf: "center" }} onClick={skipVoiceprint} disabled={busy}>
                تخطّي الآن — سأسجّلها لاحقاً
              </button>
            </div>
          </div>
        </div>
    );
  }

  // ── المرحلة 3: الدخول / التسجيل (حسب الدور) ───────────────────────────────
  const isDallal = role === "dallal";
  const heading =
    mode === "login" ? "أهلاً بعودتك" : isDallal ? "انضمّ كدلّال" : "حساب مسؤول جديد";

  return (
      <div className="auth-wrap">
        <div className="auth-stack">
          <div className="glass glass-2 auth-card">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
              <Brand size={38} showTag={false} />
              <button type="button" className="role-back" onClick={backToRole}>
                <Icon name="arrow" size={16} /> تغيير الدور
              </button>
            </div>

            <div style={{ marginBottom: 20 }}>
              <span className={"chip " + (isDallal ? "chip-brown" : "chip-green")}>
                <Icon name={isDallal ? "mic" : "chart"} size={14} />
                {isDallal ? "دلّال" : "مسؤول"}
              </span>
            </div>

            <h1 className="display" style={{ fontSize: 40, fontFamily: "var(--font-ar)", fontWeight: 600, marginBottom: 6 }}>
              {heading}
            </h1>
            <p style={{ color: "var(--ink-soft)", fontSize: 15, margin: "0 0 24px" }}>
              {mode === "login"
                ? "سجّل دخولك للمتابعة."
                : isDallal
                ? "أنشئ حسابك، ثم سجّل بصمتك الصوتية في الخطوة التالية."
                : "أنشئ حساب مسؤول بإدخال رمز المسؤول."}
            </p>

            {error && <div className="banner banner-error" style={{ marginBottom: 16 }}>{error}</div>}

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <label className="field">
                <span className="ico"><Icon name="user" size={19} /></span>
                <input
                  placeholder="اسم المستخدم"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </label>
              <label className="field">
                <span className="ico"><Icon name="lock" size={19} /></span>
                <input
                  type="password"
                  placeholder="كلمة المرور"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  required
                />
              </label>

              {mode === "signup" && (
                <label className="field">
                  <span className="ico"><Icon name="lock" size={19} /></span>
                  <input
                    type="password"
                    placeholder="تأكيد كلمة المرور"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </label>
              )}

              {/* رمز المسؤول — لتسجيل المسؤول فقط */}
              {mode === "signup" && !isDallal && (
                <label className="field">
                  <span className="ico"><Icon name="lock" size={19} /></span>
                  <input
                    placeholder="رمز المسؤول"
                    value={adminCode}
                    onChange={(e) => setAdminCode(e.target.value)}
                    required
                  />
                </label>
              )}

              <button type="submit" className="btn btn-primary" style={{ marginTop: 6, padding: "16px" }} disabled={busy}>
                {busy ? (
                  <><Spinner /> {step}</>
                ) : (
                  <>
                    {mode === "login" ? "تسجيل الدخول" : "إنشاء الحساب"}
                    <Icon name="arrowL" size={19} />
                  </>
                )}
              </button>
            </form>

            {/* تبديل بين الدخول والتسجيل — أسفل الزر */}
            <div style={{ marginTop: 20, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 13, color: "var(--ink-faint)" }}>
                {mode === "login" ? "ليس لديك حساب؟" : "لديك حساب بالفعل؟"}
              </span>
              <div className="seg">
                <button className={mode === "login" ? "on" : ""} onClick={() => switchMode("login")} type="button">دخول</button>
                <button className={mode === "signup" ? "on" : ""} onClick={() => switchMode("signup")} type="button">حساب جديد</button>
              </div>
            </div>
          </div>
        </div>
      </div>
  );
}
