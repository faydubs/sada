import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { jwtDecode } from "jwt-decode";
import { authApi } from "../api/endpoints.js";
import { TOKEN_KEY } from "../api/client.js";

const AuthContext = createContext(null);

// حوّل توكن JWT إلى كائن مستخدم. الـ backend يضع: sub (id), username, role, exp
function userFromToken(token) {
  try {
    const payload = jwtDecode(token);
    // تحقق من انتهاء الصلاحية إن وُجد exp
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return {
      id: Number(payload.sub),
      username: payload.username,
      role: payload.role,
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    return token ? userFromToken(token) : null;
  });
  const [loading, setLoading] = useState(false);

  // لو كان التوكن المخزّن منتهياً، نظّفه عند الإقلاع
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !userFromToken(token)) {
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
    }
  }, []);

  async function login(username, password) {
    setLoading(true);
    try {
      const { data } = await authApi.login(username, password);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      const u = userFromToken(data.access_token);
      setUser(u);
      return u;
    } finally {
      setLoading(false);
    }
  }

  async function register(username, password) {
    // التسجيل ينشئ الحساب فقط؛ نسجّل الدخول بعده مباشرة
    await authApi.register(username, password);
    return login(username, password);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }

  // يطبّق توكناً جديداً (بعد تعديل الملف الشخصي مثلاً) ويحدّث حالة المستخدم
  function applyToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
    setUser(userFromToken(token));
  }

  const value = useMemo(
    () => ({
      user,
      loading,
      isAdmin: user?.role === "admin",
      login,
      register,
      logout,
      applyToken,
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
