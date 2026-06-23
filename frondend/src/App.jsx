import { Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import DallalShell from "./components/DallalShell.jsx";
import AdminShell from "./components/AdminShell.jsx";
import Login from "./pages/Login.jsx";
import LiveSession from "./pages/LiveSession.jsx";
import Sales from "./pages/Sales.jsx";
import Account from "./pages/Account.jsx";
import Admin from "./pages/Admin.jsx";
import AdminAnalytics from "./pages/AdminAnalytics.jsx";
import NotFound from "./pages/NotFound.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Login initialMode="signup" />} />

      {/* ── هيكل الدلّال: تطبيق جوال + ٣ تبويبات سفلية ── */}
      <Route
        element={
          <ProtectedRoute dallalOnly>
            <DallalShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<LiveSession />} />
        <Route path="/sales" element={<Sales />} />
        <Route path="/account" element={<Account />} />
      </Route>

      {/* ── هيكل المسؤول: لوحة تحكم سطح مكتب ── */}
      <Route
        element={
          <ProtectedRoute adminOnly>
            <AdminShell />
          </ProtectedRoute>
        }
      >
        <Route path="/admin" element={<Admin />} />
        <Route path="/admin/analytics" element={<AdminAnalytics />} />
      </Route>

      <Route path="/404" element={<NotFound />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  );
}
