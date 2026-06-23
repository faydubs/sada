# دليل النشر — صدى التمر

المعمارية: **الواجهة (React/Vite) على Vercel** + **الخلفية (FastAPI) على Render** + **قاعدة البيانات (Postgres) على Supabase** (قائمة أصلاً).

> الـ backend لا يصلح لـ Vercel (يستخدم WebSocket ونماذج صوتية ضخمة تتجاوز حدود الدوال اللحظية)، لذلك يُستضاف على Render الذي يدعم خوادم Python طويلة التشغيل.

---

## الخطوة 0 — رفع الكود إلى GitHub (مرة واحدة)

من مجلد `myproject/myproject` (حيث يوجد `.gitignore`):

```bash
git init
git add .
git commit -m "Initial deploy"
git branch -M main
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```

`.gitignore` يتجاهل `.env` و`venv` و`node_modules` تلقائياً — **الأسرار لن تُرفع**.

---

## الخطوة 1 — نشر الخلفية على Render

1. ادخل [render.com](https://render.com) → **New → Blueprint**.
2. اربط مستودع GitHub. سيقرأ Render ملف [`render.yaml`](render.yaml) ويُنشئ خدمة `sada-altamr-api`.
3. اضبط المتغيّرات السرّية (Environment) من لوحة Render — انسخها من `backend/.env` المحلي:
   - `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
   - `SECRET_KEY`, `GEMINI_API_KEY`, `ADMIN_SIGNUP_CODE`
   - `CORS_ORIGINS` = رابط واجهة Vercel (مثال: `https://sada-altamr.vercel.app`) — يمكن ضبطه بعد الخطوة 2 ثم إعادة النشر.
4. انتظر اكتمال البناء. ستحصل على رابط مثل: `https://sada-altamr-api.onrender.com`
5. تحقّق: افتح الرابط، يجب أن يردّ `{"status":"صدى التمر يعمل ✅"}`.

> **الذاكرة:** خطة `starter` تكفي اللوحات والتحليلات. التفريغ الصوتي (Whisper) قد يحتاج خطة `standard` (2GB). عدّل في `render.yaml` عند الحاجة.

---

## الخطوة 2 — نشر الواجهة على Vercel

اضبط متغيّري البيئة ليشيرا إلى رابط Render، إما:

**(أ) عبر لوحة Vercel** → Project → Settings → Environment Variables:
```
VITE_API_BASE = https://sada-altamr-api.onrender.com
VITE_WS_BASE  = wss://sada-altamr-api.onrender.com
```

**(ب) أو عبر ملف** `frondend/.env.production` (يُرفع مع الكود — يحتوي رابطاً عاماً فقط):
```
VITE_API_BASE=https://sada-altamr-api.onrender.com
VITE_WS_BASE=wss://sada-altamr-api.onrender.com
```

ثم في Vercel: **New Project** → استورد المستودع → اضبط **Root Directory = `frondend`** → Deploy.
(ملف [`frondend/vercel.json`](frondend/vercel.json) يضبط البناء وتوجيه مسارات React Router.)

---

## الخطوة 3 — الربط النهائي

1. خذ رابط Vercel النهائي (مثال `https://sada-altamr.vercel.app`).
2. ضعه في `CORS_ORIGINS` على Render → أعد نشر الخلفية.
3. افتح رابط Vercel → سجّل الدخول (`admin` / `admin123`) → تأكّد من ظهور البيانات والخريطة.

---

## ملاحظات أمنية

- بعد النشر العام، **غيّر** `SECRET_KEY` و`ADMIN_SIGNUP_CODE` وكلمة مرور المسؤول الافتراضية.
- مفاتيح Supabase الحالية في `backend/.env` ستبقى صالحة؛ إن سُرّبت سابقاً يُنصح بتدويرها من لوحة Supabase.
