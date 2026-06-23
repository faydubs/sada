import { useEffect, useMemo, useState } from "react";
import { insightsApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { formatCurrency, formatNumber } from "../lib/format.js";
import TopBar from "../components/TopBar.jsx";
import { Icon, Spinner, Avatar } from "../components/ui.jsx";

/*
 * لوحة المسؤول (سطح المكتب) — منصّة إشرافية على كل الدلّالين.
 * مؤشرات عامة + بحث في الدلّالين (بالاسم/المنطقة/المجموعة) ومبيعاتهم التراكمية.
 */
export default function Admin() {
  const [overview, setOverview] = useState(null);
  const [dallals, setDallals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [ov, dl] = await Promise.all([insightsApi.adminOverview(), insightsApi.adminDallals()]);
        setOverview(ov.data);
        setDallals(dl.data.dallals);
      } catch (e) {
        setError(apiError(e, "تعذّر تحميل لوحة المسؤول"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const term = q.trim();
    if (!term) return dallals;
    return dallals.filter(
      (d) =>
        d.username.includes(term) ||
        (d.region || "").includes(term) ||
        (d.group || "").includes(term)
    );
  }, [q, dallals]);

  if (loading) {
    return <div style={{ display: "grid", placeItems: "center", height: "60vh" }}><Spinner style={{ width: 28, height: 28, color: "var(--brown-700)" }} /></div>;
  }

  const ov = overview || {};

  return (
    <div>
      <TopBar title="لوحة المسؤول" sub="إشراف على جميع الدلّالين والمناطق والمبيعات" />

      {error && <div className="banner banner-error" style={{ marginBottom: 18 }}>{error}</div>}

      <div className="kpi-row">
        <Kpi icon="users" label="الدلّالون" value={formatNumber(ov.dallals_count)} />
        <Kpi icon="coins" label="إجمالي الإيراد" value={formatCurrency(ov.total_revenue)} green />
        <Kpi icon="scale" label="المزادات" value={formatNumber(ov.auctions_count)} />
        <Kpi icon="grid" label="الجلسات" value={formatNumber(ov.sessions_count)} />
        <Kpi icon="trend" label="المناطق النشطة" value={`${formatNumber(ov.regions_active)}/${formatNumber(ov.regions_total)}`} green />
      </div>

      <div className="glass glass-2 panel">
        <div className="panel-head">
          <h3 style={{ fontSize: 17, color: "var(--brown-800)" }}>الدلّالون</h3>
          <label className="field" style={{ width: 280, padding: "9px 14px" }}>
            <span className="ico"><Icon name="search" size={17} /></span>
            <input placeholder="ابحث بالاسم أو المنطقة…" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
        </div>

        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>الدلّال</th><th>المنطقة</th><th>المجموعة</th>
                <th>المزادات</th><th>متوسط السعر</th><th>الإيراد</th><th>البصمة</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--ink-faint)", padding: 24 }}>لا نتائج مطابقة</td></tr>
              )}
              {filtered.map((d) => (
                <tr key={d.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <Avatar name={d.username.charAt(0)} size={28} />
                      <span style={{ fontWeight: 600 }}>{d.username}</span>
                    </div>
                  </td>
                  <td>{d.region}</td>
                  <td><span className="chip chip-muted" style={{ padding: "3px 9px", fontSize: 11.5 }}>{d.group}</span></td>
                  <td className="num">{formatNumber(d.auctions_count)}</td>
                  <td className="num">{d.avg_price != null ? formatCurrency(d.avg_price) : "—"}</td>
                  <td className="num" style={{ color: "var(--green-800)", fontWeight: 600 }}>{formatCurrency(d.total_revenue)}</td>
                  <td>
                    {d.voiceprint_registered
                      ? <span className="chip chip-green" style={{ padding: "3px 9px", fontSize: 11 }}><Icon name="check" size={12} /> نعم</span>
                      : <span className="chip chip-muted" style={{ padding: "3px 9px", fontSize: 11 }}>لا</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Kpi({ icon, label, value, green }) {
  return (
    <div className="glass glass-2 kpi">
      <div className="kpi-head">
        <div className="kpi-ico" style={{ color: green ? "var(--green-700)" : "var(--brown-700)" }}><Icon name={icon} size={19} /></div>
      </div>
      <div className="kpi-val">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
