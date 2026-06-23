# صدى التمر — الواجهة الأمامية (Frontend)

واجهة React + Vite لنظام إدارة مزادات التمور، موصولة بالـ FastAPI backend في مجلد `../backend`.
التصميم نظام Glassmorphism عربي (RTL) بلوحة ألوان التمر/الصحراء، وخط **ثمانية (Thmanyah Sans)**
مستضاف محلياً في `public/fonts/` (٥ أوزان)، بدون أي إطار CSS خارجي — كل الأنماط في `src/index.css`.

## المتطلبات

- **Node.js 18+** (مثبّت على `C:\Program Files\nodejs`)
- الـ backend يعمل على `http://127.0.0.1:8000`

## التشغيل (تطوير)

```bash
cd frondend
npm install
npm run dev
```

ثم افتح http://localhost:5173

أثناء التطوير يُمرّر Vite الطلبات `/api` و `/ws` تلقائياً إلى `127.0.0.1:8000`
(انظر `vite.config.js`)، فلا حاجة لإعداد CORS إضافي.

## الإنتاج

```bash
npm run build      # يُخرج إلى dist/
npm run preview    # معاينة محلية للبناء
```

للإنتاج انسخ `.env.example` إلى `.env` واضبط:

```
VITE_API_BASE=https://api.example.com
VITE_WS_BASE=wss://api.example.com
```

## البنية

```
src/
  api/         عميل axios (client.js) + كل نقاط الـ API (endpoints.js)
  context/     AuthContext — حالة المصادقة وفكّ توكن JWT
  hooks/       useAudioRecorder (تسجيل المايك) + useWebSocket (بث لحظي)
  components/  Layout (الشريط الجانبي), TopBar, ProtectedRoute, ui.jsx (Icon/Logo/Avatar/Sparkline)
  pages/       Login, Home (لوحة التحكم), LiveSession (المزاد), Reports (التحليلات), Voiceprint
  lib/         format.js — تنسيق العملة/التواريخ وتسميات الحالة
```

## الميزات

- **مصادقة JWT** — دخول/تسجيل بشاشة واحدة، حماية المسارات، تنظيف التوكن المنتهي.
- **المزاد المباشر** — تسجيل صوتي من المتصفح → رفع إلى `/api/auctions/process-audio`
  → فقاعات تفريغ لحظية + بطاقة بيانات مستخرجة + بث المزادات عبر WebSocket.
- **لوحة التحكم** — بطاقات KPI زجاجية مع Sparklines، اتجاه الإيراد، أعلى الأصناف، أحدث المزادات.
- **التحليلات** — مخطط SVG للإيراد التراكمي + متوسط السعر حسب الصنف + جدول وتصدير CSV.
- **البصمة الصوتية** — تسجيل/رفع صوت الدلّال للتحقق من الهوية.
- **تصميم Glassmorphism عربي RTL** متجاوب بالكامل (شريط جانبي على الكمبيوتر يتحوّل لشريط علوي على الجوال).

> ملاحظة: اسم المجلد `frondend` (بدل `frontend`) مكتوب هكذا في المشروع الأصلي.
> يمكن إعادة تسميته دون أي تغيير في الكود — لا توجد مراجع له في الـ backend.
