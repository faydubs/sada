import axios from "axios";

// قاعدة العنوان: في التطوير نتركها فارغة ونعتمد على proxy الخاص بـ Vite.
// في الإنتاج تُضبط عبر VITE_API_BASE.
const baseURL = import.meta.env.VITE_API_BASE || "";

export const TOKEN_KEY = "sada_token";

const client = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// أرفق التوكن تلقائياً مع كل طلب
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// عند انتهاء صلاحية التوكن (401) → امسحه وأعد التوجيه لصفحة الدخول
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      // تجنّب حلقة إعادة توجيه إن كنا أصلاً في صفحة الدخول
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// استخرج رسالة الخطأ العربية القادمة من الـ backend (detail) بشكل موحّد
export function apiError(err, fallback = "حدث خطأ غير متوقع") {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d.msg).join("، ");
  }
  return err?.message || fallback;
}

export default client;
