import React, { useRef } from "react";
import { PLANET_ABBR, RASI_ABBR } from "../constants/jyotish";
import { ChartExportButtons } from "./ChartExportButtons";
import "../styles/NorthIndianChart.css";

// South Indian chart: signs sit in FIXED cells of a 4x4 grid (houses rotate, not signs).
// Map sign number (1=Aries … 12=Pisces) -> grid column/row. Aries is top row, 2nd cell,
// then clockwise. The inner 2x2 is the label area.
const SIGN_POS = {
  1: { col: 2, row: 1 },
  2: { col: 3, row: 1 },
  3: { col: 4, row: 1 },
  4: { col: 4, row: 2 },
  5: { col: 4, row: 3 },
  6: { col: 4, row: 4 },
  7: { col: 3, row: 4 },
  8: { col: 2, row: 4 },
  9: { col: 1, row: 4 },
  10: { col: 1, row: 3 },
  11: { col: 1, row: 2 },
  12: { col: 1, row: 1 },
};

/**
 * Reusable South Indian chart. Same props as NorthIndianChart:
 *   - `chartData` (reads .planets / .lagna), or explicit `planets` + `lagna`
 *   - `title` / `subtitle` for the center label
 */
export const SouthIndianChart = ({
  chartData,
  planets: planetsProp,
  lagna: lagnaProp,
  title = "Rasi Chart",
  subtitle = "South Indian",
  exportable = false,
}) => {
  const gridRef = useRef(null);
  const planets = planetsProp || chartData?.planets;
  const lagna = lagnaProp || chartData?.lagna;

  if (!planets) {
    return <div className="chart-empty">No chart data</div>;
  }

  // Items (lagna + planets) occupying a given zodiac sign (1–12)
  const itemsForSign = (signNum) => {
    const items = [];
    if (lagna && lagna.house === signNum) {
      items.push({ name: "As", type: "lagna", degrees: lagna.degrees });
    }
    Object.entries(planets).forEach(([name, data]) => {
      if (data.house === signNum) {
        items.push({ name: PLANET_ABBR[name] || name, type: "planet", degrees: data.degrees });
      }
    });
    return items;
  };

  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <h3 className="chart-card-title">{title}</h3>
        {exportable && <ChartExportButtons targetRef={gridRef} title={`${title} ${subtitle}`} />}
      </div>
      <div className="si-grid" ref={gridRef} role="img" aria-label={`${title} (${subtitle})`}>
        {Object.keys(SIGN_POS).map((key) => {
          const signNum = Number(key);
          const { col, row } = SIGN_POS[signNum];
          const items = itemsForSign(signNum);
          const isLagna = lagna && lagna.house === signNum;
          const isCrowded = items.length > 3;
          return (
            <div
              key={signNum}
              className={`si-cell${isLagna ? " si-lagna" : ""}${isCrowded ? " si-crowded" : ""}`}
              style={{ gridColumn: col, gridRow: row }}
            >
              <span className="si-sign">{RASI_ABBR[signNum - 1]}</span>
              <div className="si-planets">
                {items.map((item, idx) => (
                  <span key={idx} className={item.type === "lagna" ? "si-pl si-pl-lagna" : "si-pl"}>
                    {item.name}
                    {item.degrees != null && <em className="si-deg">{item.degrees.toFixed(1)}°</em>}
                  </span>
                ))}
              </div>
            </div>
          );
        })}

        <div className="si-center">
          <div className="si-center-title">{title}</div>
          <div className="si-center-sub">{subtitle}</div>
        </div>
      </div>
    </div>
  );
};
