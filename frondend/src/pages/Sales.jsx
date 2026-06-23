import { useEffect, useRef, useState } from "react";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { insightsApi } from "../api/endpoints.js";
import { apiError } from "../api/client.js";
import { formatCurrency, formatNumber } from "../lib/format.js";
import { Brand, Icon, Spinner, Sparkline } from "../components/ui.jsx";

/*
 * تبويب "مبيعاتي" للدلّال — تحليلات تراكمية عبر كل جلساته (insightsApi.mySales)
 * مع تصدير الصفحة كملف PDF (jspdf + html2canvas).
 */
export default function Sales() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const printRef = useRef(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await insightsApi.mySales();
        if (alive) setData(res.data);
      } catch (e) {
        if (alive) setError(apiError(e, "تعذّر تحميل التحليلات"));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  async function exportPdf() {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const canvas = await html2canvas(printRef.current, {
        scale: 2,
        backgroundColor: "#FBF6EE",
        useCORS: true,
      });
      const img = canvas.toDataURL("image/png");
      const pdf = new jsPDF({ unit: "pt", format: "a4" });
      const pw = pdf.internal.pageSize.getWidth();
      const ph = pdf.internal.pageSize.getHeight();
      const iw = pw;
      const ih = (canvas.height * pw) / canvas.width;

      let heightLeft = ih;
      let position = 0;
      pdf.addImage(img, "PNG", 0, position, iw, ih);
      heightLeft -= ph;
      while (heightLeft > 0) {
        position -= ph;
        pdf.addPage();
        pdf.addImage(img, "PNG", 0, position, iw, ih);
        heightLeft -= ph;
      }
      pdf.save(`مبيعاتي-${data?.dallal?.username || "dallal"}.pdf`);
    } catch (e) {
      setError("تعذّر إنشاء ملف PDF");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return <div style={{ display: "grid", placeItems: "center", minHeight: "60vh", color: "var(--ink-soft)" }}><Spinner /></div>;
  }

  const s = data?.summary || {};
  const byProduct = data?.by_product || [];
  const monthly = data?.monthly || [];
  const recent = data?.recent || [];
  const maxRev = Math.max(1, ...byProduct.map((p) => p.revenue));
  const empty = (s.auctions_count || 0) === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
        <Brand size={34} showTag={false} />
        <span className="chip chip-green"><Icon name="chart" size={14} /> مبيعاتي</span>
      </header>

      {error && <div className="banner banner-error">{error}</div>}

      <button className="btn btn-green" style={{ width: "100%", padding: 14 }} onClick={exportPdf} disabled={exporting || empty}>
        {exporting ? <><Spinner /> جارٍ إنشاء الملف…</> : <><Icon name="download" size={18} /> تصدير التقرير PDF</>}
      </button>

      {/* المنطقة المطبوعة */}
      <div ref={printRef} style={{ display: "flex", flexDirection: "column", gap: 16, padding: 2 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Kpi icon="coins" label="إجمالي الإيراد" value={formatCurrency(s.total_revenue)} />
          <Kpi icon="scale" label="عدد المزادات" value={formatNumber(s.auctions_count)} />
          <Kpi icon="trend" label="متوسط السعر" value={s.avg_price != null ? formatCurrency(s.avg_price) : "—"} />
          <Kpi icon="users" label="مشترون مختلفون" value={formatNumber(s.unique_buyers)} />
        </div>

        {empty ? (
          <div className="glass glass-2 panel" style={{ textAlign: "center", color: "var(--ink-soft)", padding: 30 }}>
            لا توجد مبيعات بعد. ابدأ تسجيل مزاد من تبويب «تسجيل مزاد» وستظهر تحليلاتك هنا.
          </div>
        ) : (
          <>
            {monthly.length > 1 && (
              <div className="glass glass-2 panel">
                <div className="panel-head"><h3 style={{ fontSize: 16 }}>الإيراد الشهري</h3></div>
                <Sparkline data={monthly.map((m) => m.revenue)} w={300} h={64} color="var(--green-700)" />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink-faint)", marginTop: 6 }}>
                  <span>{monthly[0].month}</span><span>{monthly[monthly.length - 1].month}</span>
                </div>
              </div>
            )}

            <div className="glass glass-2 panel">
              <div className="panel-head"><h3 style={{ fontSize: 16 }}>أعلى الأصناف إيراداً</h3></div>
              <div className="barrow">
                {byProduct.slice(0, 6).map((p) => (
                  <div className="row" key={p.product_name}>
                    <span style={{ fontSize: 14 }}>{p.product_name}</span>
                    <span className="num" style={{ fontSize: 13, color: "var(--green-800)" }}>{formatCurrency(p.revenue)}</span>
                    <div className="bar-track"><div className="bar-fill g" style={{ width: `${(p.revenue / maxRev) * 100}%` }} /></div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass glass-2 panel">
              <div className="panel-head"><h3 style={{ fontSize: 16 }}>أحدث المزادات</h3></div>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead><tr><th>الصنف</th><th>السعر</th><th>المشتري</th></tr></thead>
                  <tbody>
                    {recent.map((a) => (
                      <tr key={a.id}>
                        <td>{a.product_name}</td>
                        <td className="num">{a.final_price != null ? formatCurrency(a.final_price) : "—"}</td>
                        <td style={{ color: "var(--ink-soft)" }}>{a.buyer_name || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Kpi({ icon, label, value }) {
  return (
    <div className="glass glass-2 kpi" style={{ minHeight: 0, padding: 16 }}>
      <div className="kpi-head">
        <div className="kpi-ico" style={{ width: 34, height: 34, color: "var(--green-700)" }}><Icon name={icon} size={17} /></div>
      </div>
      <div className="kpi-val" style={{ fontSize: 24 }}>{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}
