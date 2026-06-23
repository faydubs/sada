import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { authApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { Avatar, Icon, Brand, Spinner } from "../components/ui.jsx";

/*
 * حساب الدلّال (التبويب الأيسر). عرض البيانات الشخصية + تعديلها + تسجيل الخروج.
 */
export default function Account() {
  const { user, logout, applyToken } = useAuth();
  const navigate = useNavigate();
  const initial = (user?.username || "ض").trim().charAt(0);

  const [editing, setEditing] = useState(false);
  const [username, setUsername] = useState(user?.username || "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  async function save() {
    setError(null);
    const payload = {};
    if (username.trim() && username.trim() !== user.username) payload.username = username.trim();
    if (password) payload.password = password;
    if (!Object.keys(payload).length) { setEditing(false); return; }
    setBusy(true);
    try {
      const { data } = await authApi.updateMe(payload);
      if (data.access_token) applyToken(data.access_token);
      setPassword("");
      setEditing(false);
      setNotice("تم حفظ التعديلات ✓");
    } catch (err) {
      setError(apiError(err, "تعذّر حفظ التعديلات"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
        <Brand size={34} showTag={false} />
        <span className="chip chip-brown"><Icon name="user" size={14} /> حسابي</span>
      </header>

      <div className="glass glass-2 panel" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
        <Avatar name={initial} size={78} />
        <div>
          <div style={{ fontWeight: 700, fontSize: 22, color: "var(--brown-800)" }}>{user?.username}</div>
          <div style={{ fontSize: 13.5, color: "var(--ink-soft)", marginTop: 2 }}>دلّال معتمد</div>
        </div>
      </div>

      {notice && <div className="banner banner-ok">{notice}</div>}
      {error && <div className="banner banner-error">{error}</div>}

      {!editing ? (
        <>
          <div className="glass glass-2 panel" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <Row label="اسم المستخدم" value={user?.username} icon="user" />
            <Row label="الصلاحية" value="دلّال" icon="scale" />
            <Row label="مُعرّف الحساب" value={`#${user?.id}`} icon="box" last />
          </div>
          <button className="btn btn-ghost" style={{ width: "100%", padding: 15 }} onClick={() => { setEditing(true); setUsername(user?.username || ""); setNotice(null); }}>
            <Icon name="user" size={18} /> تعديل البيانات الشخصية
          </button>
        </>
      ) : (
        <div className="glass glass-2 panel" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="modal-field">
            <label>اسم المستخدم</label>
            <input className="modal-input" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="modal-field">
            <label>كلمة مرور جديدة (اتركها فارغة لإبقائها)</label>
            <input className="modal-input" type="password" value={password} placeholder="••••••" onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-ghost" style={{ flex: 1, padding: 13 }} onClick={() => { setEditing(false); setError(null); setPassword(""); }} disabled={busy}>إلغاء</button>
            <button className="btn btn-green" style={{ flex: 1, padding: 13 }} onClick={save} disabled={busy}>
              {busy ? <Spinner /> : <><Icon name="check" size={17} /> حفظ</>}
            </button>
          </div>
        </div>
      )}

      <button className="btn btn-danger" style={{ width: "100%", padding: 15 }} onClick={handleLogout}>
        <Icon name="logout" size={18} /> تسجيل الخروج
      </button>
    </div>
  );
}

function Row({ label, value, icon, last }) {
  return (
    <div className="kv" style={last ? { borderBottom: "none" } : undefined}>
      <span className="kv-label"><Icon name={icon} size={16} /> {label}</span>
      <span style={{ fontWeight: 600, fontSize: 15, color: "var(--brown-800)" }}>{value}</span>
    </div>
  );
}
