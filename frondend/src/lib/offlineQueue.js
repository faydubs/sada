/*
 * طابور التسجيلات دون اتصال — يُخزَّن في IndexedDB (الـ Blob كبير على localStorage).
 * كل عنصر: { id, file (Blob), sessionId (number|null), durationSec, createdAt }.
 */
import { openDB } from "idb";

const DB_NAME = "sada-offline";
const STORE = "pending-recordings";

function getDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    },
  });
}

export async function addPending(item) {
  const db = await getDB();
  return db.add(STORE, { ...item, createdAt: Date.now() });
}

export async function getAllPending() {
  const db = await getDB();
  return db.getAll(STORE);
}

export async function removePending(id) {
  const db = await getDB();
  return db.delete(STORE, id);
}

export async function countPending() {
  const db = await getDB();
  return db.count(STORE);
}

/* ───────────────────────────────────────────────────────────────────────────
 * تسجيل معلّق افتراضي (بروتوتايب) — يحاكي ما يحدث عند التسجيل أثناء انقطاع
 * الإنترنت: يُحفظ محلياً ثم يظهر في بانر "جلسة معلّقة"، وعند الضغط على "تحليل"
 * تُعرض نتيجة جاهزة دون اتصال بالخادم (item.demo === true).
 * ─────────────────────────────────────────────────────────────────────────── */
const DEMO_FLAG = "sada_demo_pending_seeded_v1";

// نتيجة تحليل جاهزة تطابق شكل استجابة /process-audio (transcription نص + extracted + trace).
export const DEMO_RESULT = {
  transcription:
    "بسم الله نفتح السوم على تمر السكري الفاخر من مزارع القصيم، البداية مية وعشرين ريال… زايد مية وثلاثين… مية وأربعين… خمسة وأربعين… بيع! مبروك على أبو فهد",
  extracted: {
    product: "سكري",
    price: 145,
    unit: "كرتون",
    quantity: 1,
    confidence: "high",
    action: "إغلاق",
    source: "demo_offline",
  },
  voiceprint: {
    is_match: true,
    best_score: 0.93,
    label: "registered_auctioneer",
    status: "ok",
    enabled: true,
    note: "الصوت يطابق بصمة الدلّال المسجّل (وضع العرض).",
  },
  trace: [
    { skill: "gemini_audio", status: "ok", confidence: 0.95 },
    { step: "decision_route", route_chosen: "gemini_audio", status: "ok" },
    { skill: "verify_voiceprint", status: "ok", is_match: true, best_score: 0.93 },
  ],
  // المخطط الغني (نفس شكل حقل analysis من /process-audio)
  analysis: {
    product_type: "سكري",
    seller_name: "أبو سلطان",
    buyer_name: "أبو فهد",
    winner: "أبو فهد",
    opening_price: 120,
    final_price: 145,
    bids: [
      { price: 120, bidder: null },
      { price: 130, bidder: null },
      { price: 140, bidder: null },
      { price: 145, bidder: "أبو فهد" },
    ],
    currency: "SAR",
    status: "sold",
    quantity: 1,
    unit: "كرتون",
    confidence: 0.95,
    notes: "تمر سكري فاخر من مزارع القصيم.",
    model_used: "gemini-2.5-flash",
  },
  auction_created: null,
};

function demoItem() {
  return {
    file: new Blob(["demo-offline-recording"], { type: "audio/webm" }),
    sessionId: null,
    durationSec: 18,
    demo: true,
    demoResult: DEMO_RESULT,
    createdAt: Date.now(),
  };
}

/**
 * يزرع تسجيلاً معلّقاً تجريبياً واحداً.
 * - تلقائياً (force=false): مرة واحدة فقط على هذا الجهاز، وفقط إن لم يكن
 *   هناك تسجيل تجريبي بالطابور أصلاً — حتى لا يزعج المستخدم بتكرار.
 * - يدوياً (force=true): يضيف واحداً جديداً دائماً (زر "تجربة").
 * يعيد true إذا أُضيف عنصر.
 */
export async function seedDemoPending(force = false) {
  if (!force && localStorage.getItem(DEMO_FLAG)) return false;
  const db = await getDB();
  if (!force) {
    const all = await db.getAll(STORE);
    if (all.some((x) => x.demo)) {
      localStorage.setItem(DEMO_FLAG, "1");
      return false;
    }
  }
  await db.add(STORE, demoItem());
  localStorage.setItem(DEMO_FLAG, "1");
  return true;
}
