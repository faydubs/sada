import { useAuth } from "../context/AuthContext.jsx";
import { Icon, Avatar } from "./ui.jsx";

// شريط علوي موحّد لكل الشاشات: عنوان + وصف + إجراءات + هوية المستخدم
export default function TopBar({ title, sub, children }) {
  const { user, isAdmin } = useAuth();
  const initial = (user?.username || "ض").trim().charAt(0);

  return (
    <header className="topbar">
      <div>
        <div className="eyebrow" style={{ marginBottom: 6 }}>
          صدى التمر · منصة المزادات
        </div>
        <h1 style={{ fontSize: 27, color: "var(--brown-800)" }}>{title}</h1>
        {sub && <p style={{ margin: "5px 0 0", color: "var(--ink-soft)", fontSize: 14 }}>{sub}</p>}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {children}
        <button className="btn btn-ghost btn-fab" title="الإشعارات">
          <Icon name="bell" size={19} />
        </button>
        <div className="glass-inset" style={{ display: "flex", alignItems: "center" }}>
          <div style={{ padding: "7px 7px 7px 14px", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ textAlign: "right", lineHeight: 1.2 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.username}</div>
              <div style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>
                {isAdmin ? "مدير المنصة" : "دلّال معتمد"}
              </div>
            </div>
            <Avatar name={initial} />
          </div>
        </div>
      </div>
    </header>
  );
}
