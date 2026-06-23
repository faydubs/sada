---
title: Sada Al-Tamr API
emoji: 🌴
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# صدى التمر — الواجهة الخلفية (API)

واجهة خلفية FastAPI لمنصّة "صدى التمر" لمزادات التمور الصوتية.
هذه الـ Space تشغّل الـ backend فقط؛ الواجهة الأمامية منشورة على Vercel.

## النشر
- **Backend:** Hugging Face Spaces (هذا المستودع، عبر `Dockerfile`).
- **Frontend:** Vercel (مجلد `frondend/`).
- **Database:** Supabase Postgres.

راجع [`DEPLOY.md`](DEPLOY.md) للتفاصيل الكاملة.

## المتغيّرات السرّية المطلوبة (Settings → Secrets على HF)
`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`,
`SECRET_KEY`, `GEMINI_API_KEY`, `ADMIN_SIGNUP_CODE`, `CORS_ORIGINS`
