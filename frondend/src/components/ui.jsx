/* ui.jsx — shared building blocks (Icon, Logo, Brand, Watermark, Avatar, Sparkline) */

const PATHS = {
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  activity: "M3 12h4l3 8 4-16 3 8h4",
  chart: "M4 19V5M4 19h16M8 16v-5M12 16V8M16 16v-8M20 16v-3",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20a8 8 0 0 1 16 0",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  lock: "M6 11V8a6 6 0 0 1 12 0v3M5 11h14v9H5z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  arrowL: "M19 12H5M11 6l-6 6 6 6",
  download: "M12 3v12M7 11l5 5 5-5M5 21h14",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  search: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM20 20l-4-4",
  coins: "M8 8m-5 0a5 3 0 1 0 10 0a5 3 0 1 0-10 0M3 8v5c0 1.6 2.2 3 5 3M13 13c2.8 0 5-1.3 5-3s-2.2-3-5-3M21 11v5c0 1.6-2.2 3-5 3",
  trophy: "M7 4h10v5a5 5 0 0 1-10 0V4zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M9 19h6M10 15v4M14 15v4",
  scale: "M12 4v16M7 8h10M5 8l-2 6h6l-2-6M19 8l-2 6h6l-2-6M3 20h18",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M17 11a4 4 0 0 0 0-8M22 21a7 7 0 0 0-5-6.7",
  box: "M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10",
  bell: "M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M10 20a2 2 0 0 0 4 0",
  check: "M5 13l4 4L19 7",
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
  sound: "M4 9v6h4l5 4V5L8 9H4zM17 8a5 5 0 0 1 0 8M19.5 6a8 8 0 0 1 0 12",
  filter: "M3 5h18l-7 8v5l-4 2v-7L3 5z",
  calendar: "M4 6h16v15H4zM4 10h16M8 3v4M16 3v4",
  dollar: "M12 2v20M17 6a4 4 0 0 0-4-3H10a3.5 3.5 0 0 0 0 7h4a3.5 3.5 0 0 1 0 7h-3a4 4 0 0 1-4-3",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  spark: "M12 3l1.8 5.6L19 9l-4.5 3.3L16 18l-4-3-4 3 1.5-5.7L5 9l5.2-.4z",
  play: "M7 4v16l13-8z",
  stop: "M6 6h12v12H6z",
  refresh: "M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2M18 4v5h-5M6 20v-5h5",
};

export function Icon({ name, size = 20, stroke = 1.7, style = {}, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      <path d={PATHS[name] || ""} />
    </svg>
  );
}

/* الشعار الرسمي: تمرة بنّية + موجة صوتية بيضاء + أقواس صوتية خضراء (SVG متجه) */
const WAVE_BARS = [
  [42.2, 7], [44.8, 12], [47.4, 8], [50.0, 16], [52.6, 6], [55.2, 13], [57.8, 9],
];

export function Logo({ size = 44 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="صدى التمر"
      style={{ filter: "drop-shadow(0 6px 14px rgba(67,37,26,0.20))" }}
    >
      {/* أقواس الصدى الخضراء — يسار */}
      <g stroke="#6E8B3D" strokeWidth="3.1" fill="none" strokeLinecap="round">
        <path d="M26 38 Q18 50 26 62" />
        <path d="M22 32 Q11 50 22 68" />
        <path d="M18 27 Q4 50 18 73" />
        {/* أقواس الصدى الخضراء — يمين */}
        <path d="M74 38 Q82 50 74 62" />
        <path d="M78 32 Q89 50 78 68" />
        <path d="M82 27 Q96 50 82 73" />
      </g>
      {/* جسم التمرة */}
      <ellipse cx="50" cy="50" rx="16.5" ry="24.5" fill="#7A3E29" />
      {/* الموجة الصوتية البيضاء داخل التمرة */}
      <g fill="#FBF6EE">
        {WAVE_BARS.map(([x, h], i) => (
          <rect key={i} x={x - 1.1} y={50 - h} width="2.2" height={h * 2} rx="1.1" />
        ))}
      </g>
    </svg>
  );
}

export function Brand({ size = 44, showTag = true, light = false }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <Logo size={size} />
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
        <span style={{ fontWeight: 700, fontSize: size * 0.42, color: light ? "#FBF6EE" : "var(--brown-700)" }}>
          صدى التمر
        </span>
        {showTag && (
          <span style={{ fontSize: size * 0.2, color: light ? "rgba(251,246,238,.8)" : "var(--green-700)" }}>
            صوت المزاد .. بيانات تدوم
          </span>
        )}
      </div>
    </div>
  );
}

export function Watermark({ opacity = 0.05, size = "52vmin", pos = { bottom: "-8%", left: "-6%" } }) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        width: size,
        height: size,
        opacity,
        pointerEvents: "none",
        userSelect: "none",
        zIndex: 0,
        ...pos,
      }}
    >
      <Logo size="100%" />
    </div>
  );
}

export function Avatar({ name = "ض", size = 38 }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        flex: "0 0 auto",
        display: "grid",
        placeItems: "center",
        fontWeight: 600,
        fontSize: size * 0.4,
        color: "#FBF6EE",
        background: "linear-gradient(135deg, var(--green-600), var(--green-900))",
        boxShadow: "0 4px 12px -4px rgba(31,61,43,0.5), inset 0 1px 0 rgba(255,255,255,0.2)",
      }}
    >
      {name}
    </div>
  );
}

export function Sparkline({ data, w = 96, h = 30, color = "var(--brown-600)", fill = true }) {
  if (!data || data.length < 2) return <svg width={w} height={h} />;
  const max = Math.max(...data),
    min = Math.min(...data);
  const span = max - min || 1;
  const pts = data.map((d, i) => [(i / (data.length - 1)) * w, h - ((d - min) / span) * (h - 4) - 2]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${w} ${h} L0 ${h} Z`;
  const gid = "sg" + Math.random().toString(36).slice(2, 7);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", overflow: "visible" }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${gid})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="2.6" fill={color} />
    </svg>
  );
}

/* small spinner used in buttons */
export function Spinner({ style }) {
  return <span className="spinner" style={style} role="status" aria-label="جارٍ التحميل" />;
}
