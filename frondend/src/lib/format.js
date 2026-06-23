// أدوات تنسيق موحّدة (أرقام، عملة، تواريخ، تسميات الحالة بالعربية)

export function formatCurrency(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ar-SA", {
    style: "currency",
    currency: "SAR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatNumber(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ar-SA").format(Number(value));
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("ar-SA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("ar-SA", { timeStyle: "short" }).format(
    new Date(iso)
  );
}

export function formatDuration(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// تسميات حالة الجلسة / المزاد بالعربية + ألوان Tailwind
export const SESSION_STATUS = {
  active: { label: "مفتوحة", cls: "bg-green-100 text-green-700" },
  closed: { label: "مغلقة", cls: "bg-gray-100 text-gray-600" },
};

export const AUCTION_STATUS = {
  pending: { label: "بالانتظار", cls: "bg-amber-100 text-amber-700" },
  active: { label: "نشط", cls: "bg-green-100 text-green-700" },
  closed: { label: "مُغلق", cls: "bg-gray-100 text-gray-600" },
};

export const CONFIDENCE = {
  high: { label: "ثقة عالية", cls: "bg-green-100 text-green-700" },
  medium: { label: "ثقة متوسطة", cls: "bg-amber-100 text-amber-700" },
  low: { label: "ثقة منخفضة", cls: "bg-red-100 text-red-700" },
};
