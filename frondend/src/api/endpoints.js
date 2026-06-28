import client from "./client.js";

// ───────────────────────────── Auth ─────────────────────────────
export const authApi = {
  login: (username, password) =>
    client.post("/api/auth/login", { username, password }),

  register: (username, password) =>
    client.post("/api/auth/register", { username, password }),

  // تسجيل ذاتي لحساب مسؤول — يتطلب رمز المسؤول
  registerAdmin: (username, password, code) =>
    client.post("/api/auth/register-admin", { username, password, code }),

  // إنشاء مستخدم بأي صلاحية — للـ admin فقط
  adminCreateUser: (username, password, role) =>
    client.post("/api/auth/admin/create-user", { username, password, role }),

  // قائمة كل المستخدمين — للـ admin فقط (لوحة المسؤول)
  listUsers: () => client.get("/api/auth/users"),

  voiceprintStatus: () => client.get("/api/auth/voiceprint/status"),

  me: () => client.get("/api/auth/me"),
  updateMe: (data) => client.patch("/api/auth/me", data), // { username?, password? }

  uploadVoiceprint: (file) => {
    const form = new FormData();
    form.append("file", file);
    return client.post("/api/auth/voiceprint", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

// ─────────────────────────── Sessions ───────────────────────────
export const sessionsApi = {
  list: () => client.get("/api/sessions/"),
  start: (dallalId) => client.post("/api/sessions/start", { dallal_id: dallalId }),
  end: (sessionId) =>
    client.post(`/api/sessions/end?session_id=${sessionId}`),
};

// ─────────────────────────── Auctions ───────────────────────────
export const auctionsApi = {
  // إنشاء مزاد من بيانات راجعها الدلّال يدوياً (لا حفظ تلقائي قبل المراجعة)
  create: (data) => client.post("/api/auctions/", data),

  // تحديث/إغلاق مزاد (تصحيح البيانات وتعيين السعر النهائي والمشتري)
  update: (auctionId, data) => client.patch(`/api/auctions/${auctionId}`, data),

  processAudio: (sessionId, file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return client.post(
      `/api/auctions/process-audio?session_id=${sessionId}`,
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: onProgress,
      }
    );
  },
};

// ─────────────────────────── Dashboard ──────────────────────────
export const dashboardApi = {
  summary: (sessionId) =>
    client.get(`/api/dashboard/summary?session_id=${sessionId}`),
  trends: (sessionId) =>
    client.get(`/api/dashboard/trends?session_id=${sessionId}`),
};

// ─────────────────────────── Analytics ──────────────────────────
export const analyticsApi = {
  priceTrends: (sessionId) =>
    client.get(`/api/analytics/price-trends?session_id=${sessionId}`),
  trends: (sessionId) =>
    client.get(`/api/analytics/trends?session_id=${sessionId}`),
};

// ─────────────────────── Insights (تراكمية) ─────────────────────
// تحليلات عبر كل الجلسات — لا تقتصر على جلسة واحدة.
export const insightsApi = {
  // مبيعات الدلّال الحالي مدى الحياة (تبويب "مبيعاتي")
  mySales: () => client.get("/api/insights/me"),
  // المسؤول
  adminOverview: () => client.get("/api/insights/admin/overview"),
  adminRegions: () => client.get("/api/insights/admin/regions"),
  adminRegionDetail: (region) =>
    client.get(`/api/insights/admin/regions/${encodeURIComponent(region)}`),
  adminDallals: () => client.get("/api/insights/admin/dallals"),
};

// ──────────────────────────── Reports ───────────────────────────
export const reportsApi = {
  detail: (sessionId) =>
    client.get(`/api/reports/trends?session_id=${sessionId}`),
  // تنزيل CSV: نطلبه كـ blob مع التوكن ثم نحفظه
  exportCsv: (sessionId) =>
    client.get(`/api/reports/export?session_id=${sessionId}`, {
      responseType: "blob",
    }),
};
