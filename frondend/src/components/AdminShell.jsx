import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { Icon, Logo } from "./ui.jsx";

/*
 * هيكل المسؤول: لوحة تحكم سطح مكتب بشريط جانبي رأسي (rail).
 * لا يحتوي صفحة تسجيل مزاد — المسؤول يشرف فقط.
 */
const NAV = [
  { to: "/admin", label: "لوحة المسؤول", icon: "grid", end: true },
  { to: "/admin/analytics", label: "التحليلات والخريطة", icon: "chart" },
];

export default function AdminShell() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="rail glass glass-2">
        <div className="rail-brand">
          <Logo size={40} />
        </div>
        <nav className="rail-nav">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => "rail-item" + (isActive ? " active" : "")}
              title={n.label}
            >
              {({ isActive }) => (
                <>
                  <Icon name={n.icon} size={21} stroke={isActive ? 2 : 1.7} />
                  <span className="rail-tip">{n.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <button className="rail-item rail-logout" onClick={handleLogout} title="تسجيل الخروج">
          <Icon name="logout" size={20} />
          <span className="rail-tip">تسجيل الخروج</span>
        </button>
      </aside>

      <main className="app-main scroll">
        <Outlet />
      </main>
    </div>
  );
}
