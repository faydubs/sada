import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

// يحمي المسارات: يحوّل غير المسجّلين لصفحة الدخول.
// adminOnly=true  يقصر المسار على المدير (يُحوّل الدلّال إلى هيكله).
// dallalOnly=true يقصر المسار على الدلّال (يُحوّل المسؤول إلى لوحته).
export default function ProtectedRoute({ children, adminOnly = false, dallalOnly = false }) {
  const { user, isAdmin } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (adminOnly && !isAdmin) {
    return <Navigate to="/" replace />;
  }
  if (dallalOnly && isAdmin) {
    return <Navigate to="/admin" replace />;
  }
  return children;
}
