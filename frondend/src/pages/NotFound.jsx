import { useNavigate } from "react-router-dom";
import { Logo } from "../components/ui.jsx";

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <div className="glass glass-2 panel" style={{ textAlign: "center", padding: "48px 40px", maxWidth: 420 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
          <Logo size={64} />
        </div>
        <h1 style={{ fontSize: 24, color: "var(--brown-800)", marginBottom: 8 }}>الصفحة غير موجودة</h1>
        <p style={{ color: "var(--ink-soft)", marginBottom: 24 }}>الرابط الذي طلبته غير متاح.</p>
        <button className="btn btn-primary" onClick={() => navigate("/")}>
          العودة للرئيسية
        </button>
      </div>
    </div>
  );
}
