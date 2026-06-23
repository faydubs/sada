/*
 * يربط أسماء المناطق في ملف GeoJSON (shapeName بالإنجليزية) بالأسماء العربية
 * المخزَّنة في users.region والمستخدمة في تحليلات المسؤول.
 */
export const SHAPE_TO_AR = {
  "Riyadh Region": "الرياض",
  "Al-Qassim Region": "القصيم",
  "Makkah Region": "مكة المكرمة",
  "Al Madinah Region": "المدينة المنورة",
  "Al Bahah Region": "الباحة",
  "Eastern Region": "المنطقة الشرقية",
  "'Asir Region": "عسير",
  "Jazan Region": "جازان",
  "Najran Region": "نجران",
  "Tabuk Region": "تبوك",
  "Hayel Region": "حائل",
  "Northern Borders Region": "الحدود الشمالية",
  "Al Jawf Region": "الجوف",
};

export function arOfShape(shapeName) {
  return SHAPE_TO_AR[shapeName] || shapeName;
}

// تدرّج لوني أخضر حسب شدّة الإيراد (choropleth)
export function revenueFill(value, max) {
  if (!value || !max) return "#EAE0CE"; // رملي فاتح للمناطق بلا بيانات
  const t = Math.min(1, value / max);
  // من أخضر فاتح إلى أخضر غامق
  const light = [132, 199, 154]; // --green-500
  const dark = [36, 92, 59];     // --green-900
  const c = light.map((l, i) => Math.round(l + (dark[i] - l) * t));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}
