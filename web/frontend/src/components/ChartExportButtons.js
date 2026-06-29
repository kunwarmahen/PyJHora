import React, { useState } from "react";
import { Download, FileText } from "lucide-react";
import { exportChartPng, exportChartPdf } from "../utils/exportChart";

/** Small PNG / PDF export buttons for a chart. `targetRef` points at the chart
 * <svg> or its container element (auto-detected by the export util). */
export const ChartExportButtons = ({ targetRef, title = "chart" }) => {
  const [busy, setBusy] = useState("");

  const run = async (kind) => {
    const el = targetRef.current;
    if (!el) return;
    setBusy(kind);
    try {
      if (kind === "png") await exportChartPng(el, title);
      else await exportChartPdf(el, title);
    } catch (e) {
      // best-effort; export failure shouldn't break the page
      // eslint-disable-next-line no-console
      console.error("Chart export failed", e);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="chart-export-btns">
      <button
        className="chart-export-btn"
        onClick={() => run("png")}
        disabled={!!busy}
        title="Download as PNG"
      >
        <Download size={14} />
        <span>{busy === "png" ? "…" : "PNG"}</span>
      </button>
      <button
        className="chart-export-btn"
        onClick={() => run("pdf")}
        disabled={!!busy}
        title="Download as PDF"
      >
        <FileText size={14} />
        <span>{busy === "pdf" ? "…" : "PDF"}</span>
      </button>
    </div>
  );
};

export default ChartExportButtons;
