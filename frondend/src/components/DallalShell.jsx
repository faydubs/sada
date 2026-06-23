import { NavLink, Outlet } from "react-router-dom";
import { Icon } from "./ui.jsx";

/*
 * هيكل الدلّال: تطبيق بحجم الجوال + شريط تبويب سفلي بثلاثة أزرار.
 * ترتيب RTL (يمين → يسار): مبيعاتي · تسجيل (الأبرز، في المنتصف) · حسابي.
 */
const TABS = [
  { to: "/sales", label: "مبيعاتي", icon: "chart", end: true },
  { to: "/", label: "تسجيل مزاد", icon: "mic", center: true, end: true },
  { to: "/account", label: "حسابي", icon: "user", end: true },
];

export default function DallalShell() {
  return (
    <div className="dallal-shell">
      <main className="dallal-main scroll">
        <Outlet />
      </main>

      <nav className="tabbar glass glass-2" aria-label="التنقّل">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              "tab" + (t.center ? " tab-center" : "") + (isActive ? " active" : "")
            }
          >
            {t.center ? (
              <span className="tab-fab"><Icon name={t.icon} size={26} /></span>
            ) : (
              <Icon name={t.icon} size={22} />
            )}
            <span className="tab-label">{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
