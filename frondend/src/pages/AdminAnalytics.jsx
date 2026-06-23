import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import geoUrl from "../assets/saudi-regions.geojson?url";
import { insightsApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { arOfShape, revenueFill } from "../lib/saudiRegions.js";
import { formatCurrency, formatNumber } from "../lib/format.js";
import TopBar from "../components/TopBar.jsx";
import { Icon, Spinner } from "../components/ui.jsx";

/*
 * تحليلات المسؤول — خريطة السعودية الإدارية (choropleth حسب الإيراد).
 * الضغط على منطقة يفتح تفاصيلها الكاملة + دلّاليها ومبيعاتهم.
 */
export default function AdminAnalytics() {
  const [regions, setRegions] = useState([]);
  const [groups, setGroups] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await insightsApi.adminRegions();
        setRegions(data.regions);
        setGroups(data.groups);
      } catch (e) {
        setError(apiError(e, "تعذّر تحميل بيانات المناطق"));
      }
    })();
  }, []);

  const byAr = useMemo(() => Object.fromEntries(regions.map((r) => [r.region, r])), [regions]);
  const maxRev = useMemo(() => Math.max(1, ...regions.map((r) => r.total_revenue)), [regions]);

  async function selectRegion(ar) {
    setSelected(ar);
    setLoadingDetail(true);
    setDetail(null);
    try {
      const { data } = await insightsApi.adminRegionDetail(ar);
      setDetail(data);
    } catch (e) {
      setError(apiError(e, "تعذّر تحميل تفاصيل المنطقة"));
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <div>
      <TopBar title="التحليلات والخريطة" sub="توزيع المبيعات على مناطق السعودية الإدارية — اضغط منطقة لتفاصيلها" />

      {error && <div className="banner banner-error" style={{ marginBottom: 18 }}>{error}</div>}

      <div className="kpi-grid">
        {/* الخريطة */}
        <div className="glass glass-2 panel span-7">
          <div className="panel-head">
            <h3 style={{ fontSize: 16, color: "var(--brown-800)" }}>خريطة المناطق</h3>
            <span className="chip chip-muted">{hover ? hover : "تدرّج اللون = حجم الإيراد"}</span>
          </div>
          <div style={{ position: "relative" }}>
            <ComposableMap
              projection="geoMercator"
              projectionConfig={{ center: [45.5, 24.2], scale: 1250 }}
              width={560}
              height={520}
              style={{ width: "100%", height: "auto" }}
            >
              <Geographies geography={geoUrl}>
                {({ geographies }) =>
                  geographies.map((geo) => {
                    const ar = arOfShape(geo.properties.shapeName);
                    const d = byAr[ar];
                    const isSel = selected === ar;
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        onClick={() => selectRegion(ar)}
                        onMouseEnter={() => setHover(ar)}
                        onMouseLeave={() => setHover(null)}
                        stroke={isSel ? "#43271B" : "#FBF6EE"}
                        strokeWidth={isSel ? 1.8 : 0.7}
                        style={{
                          default: { fill: revenueFill(d?.total_revenue, maxRev), outline: "none" },
                          hover: { fill: "var(--brown-600)", outline: "none", cursor: "pointer" },
                          pressed: { fill: "var(--brown-700)", outline: "none" },
                        }}
                      />
                    );
                  })
                }
              </Geographies>
            </ComposableMap>
          </div>

          {/* ملخّص المجموعات الجغرافية */}
          <div className="panel-head" style={{ marginTop: 12, marginBottom: 10 }}>
            <h3 style={{ fontSize: 14, color: "var(--brown-800)" }}>حسب المجموعة الجغرافية</h3>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
            {groups.map((g) => (
              <div key={g.group} className="glass-inset" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--brown-800)" }}>{g.group}</div>
                <div className="num" style={{ fontSize: 13, color: "var(--green-800)", marginTop: 4 }}>{formatCurrency(g.total_revenue)}</div>
                <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>{formatNumber(g.dallals_count)} دلّال</div>
              </div>
            ))}
          </div>
        </div>

        {/* لوحة التفاصيل */}
        <div className="glass glass-2 panel span-5">
          {!selected ? (
            <div style={{ display: "grid", placeItems: "center", minHeight: 360, textAlign: "center", color: "var(--ink-soft)", gap: 10 }}>
              <Icon name="chart" size={40} style={{ color: "var(--green-700)", opacity: 0.6 }} />
              <div>اضغط منطقة على الخريطة لعرض تحليلاتها الكاملة ودلّاليها.</div>
            </div>
          ) : loadingDetail ? (
            <div style={{ display: "grid", placeItems: "center", minHeight: 360 }}><Spinner style={{ width: 26, height: 26, color: "var(--brown-700)" }} /></div>
          ) : detail ? (
            <div>
              <div className="panel-head">
                <div>
                  <h3 style={{ fontSize: 19, color: "var(--brown-800)" }}>{detail.region}</h3>
                  <div style={{ fontSize: 12.5, color: "var(--ink-faint)" }}>المجموعة: {detail.group}</div>
                </div>
                <span className="chip chip-green">{formatNumber(detail.dallals_count)} دلّال</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
                <Mini label="الإيراد" value={formatCurrency(detail.summary.total_revenue)} />
                <Mini label="المزادات" value={formatNumber(detail.summary.auctions_count)} />
                <Mini label="متوسط السعر" value={detail.summary.avg_price != null ? formatCurrency(detail.summary.avg_price) : "—"} />
                <Mini label="مشترون" value={formatNumber(detail.summary.unique_buyers)} />
              </div>

              <div className="panel-head" style={{ marginBottom: 8 }}><h3 style={{ fontSize: 14 }}>الدلّالون ومبيعاتهم</h3></div>
              <div className="tbl-wrap" style={{ maxHeight: 220, overflowY: "auto" }}>
                <table className="tbl">
                  <thead><tr><th>الدلّال</th><th>المزادات</th><th>الإيراد</th></tr></thead>
                  <tbody>
                    {detail.dallals.length === 0 && (
                      <tr><td colSpan={3} style={{ textAlign: "center", color: "var(--ink-faint)" }}>لا يوجد دلّالون في هذه المنطقة</td></tr>
                    )}
                    {detail.dallals.map((d) => (
                      <tr key={d.id}>
                        <td>{d.username}</td>
                        <td className="num">{formatNumber(d.auctions_count)}</td>
                        <td className="num" style={{ color: "var(--green-800)" }}>{formatCurrency(d.total_revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="glass-inset" style={{ padding: "12px 14px" }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{label}</div>
      <div className="num" style={{ fontSize: 20, fontWeight: 300, color: "var(--brown-800)", marginTop: 2 }}>{value}</div>
    </div>
  );
}
