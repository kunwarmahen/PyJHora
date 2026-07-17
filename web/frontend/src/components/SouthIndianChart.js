import React, { useRef } from "react";
import { useTranslation } from "react-i18next";
// RASI_NAMES resolves a sign number to its canonical English name; ln() then renders it
// in the active language.
import { RASI_NAMES, RASI_GLYPHS, ASPECT_COLORS } from "../constants/jyotish";
import { useLocalizeName } from "../i18n/localizeName";
import { useSettings } from "../contexts/SettingsContext";
import { signLabelParts } from "../config/signLabel";
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
 *   - `title` / `subtitle` for the heading and the caption under the grid
 */
export const SouthIndianChart = ({
  chartData,
  planets: planetsProp,
  lagna: lagnaProp,
  title = "Rasi Chart",
  subtitle = "South Indian",
  exportable = false,
  aspects = null,
  showAspects = false,
  focusPlanet = null,
  arudhas = null,
  showArudhas = false,
  conditions = null,
  onSelectPlanet = null,
}) => {
  const wrapRef = useRef(null);
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { settings } = useSettings();
  const labelParts = signLabelParts(settings.signLabel);
  const planets = planetsProp || chartData?.planets;
  const lagna = lagnaProp || chartData?.lagna;

  if (!planets) {
    return <div className="chart-empty">No chart data</div>;
  }

  // Planet-condition flags: fullName -> { tone, labels[] }.
  const flagsByPlanet = {};
  (conditions || []).forEach((p) => {
    const tones = (p.flags || []).map((f) => f.tone);
    const tone = tones.includes("challenging")
      ? "challenging"
      : tones.includes("benefic")
        ? "benefic"
        : "neutral";
    flagsByPlanet[p.planet] = {
      tone,
      labels: (p.flags || []).map((f) => f.label + (f.partner ? ` (${f.partner})` : "")),
    };
  });
  const CONDITION_TONE_COLOR = {
    benefic: "#2E9E5B",
    challenging: "#e34234",
    neutral: "#8b8fa8",
  };

  // Centre of a sign's fixed cell in the 0..4 overlay grid coordinate system.
  const cellCenter = (signNum) => {
    const pos = SIGN_POS[signNum];
    return pos ? { x: pos.col - 0.5, y: pos.row - 0.5 } : null;
  };

  // Items (lagna + planets) occupying a given zodiac sign (1–12)
  const itemsForSign = (signNum) => {
    const items = [];
    if (lagna && lagna.house === signNum) {
      items.push({ name: t("common.lagnaAbbr"), type: "lagna", degrees: lagna.degrees });
    }
    Object.entries(planets).forEach(([name, data]) => {
      if (data.house === signNum) {
        items.push({
          // `name` is display text; `fullName` stays canonical English because it keys
          // flagsByPlanet / onSelectPlanet and must not follow the UI language.
          name: ln(name, "graha", { abbr: true }),
          type: "planet",
          fullName: name,
          degrees: data.degrees,
        });
      }
    });
    // Arudha padas (AL/UL/A2..) that fall in this sign, shown when toggled on.
    if (showArudhas && arudhas) {
      arudhas
        .filter((a) => a.sign === signNum)
        .forEach((a) => items.push({ name: a.short, type: "arudha" }));
    }
    return items;
  };

  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <h3 className="chart-card-title">
          {title}
          {subtitle && <span className="chart-card-sub">{subtitle}</span>}
        </h3>
        {exportable && <ChartExportButtons targetRef={wrapRef} title={`${title} ${subtitle}`} />}
      </div>
      {/* The export target is this wrapper, not the grid, so the caption below
          travels with the image — same reason the North chart keeps its caption
          inside the <svg>. */}
      <div className="si-export-wrap" ref={wrapRef}>
        <div className="si-grid" role="img" aria-label={`${title} (${subtitle})`}>
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
                {/* Sign label. Signs are FIXED in this style, so the numeral here
                  was never ambiguous the way the North chart's was — but it
                  follows the same setting so the two styles read alike. The
                  full name is always one hover away. */}
                <span className="si-sign" title={ln(RASI_NAMES[signNum - 1], "rasi")}>
                  {labelParts.number && <span className="si-sign-num">{signNum}</span>}
                  {labelParts.glyph && (
                    <span className="si-sign-glyph">{RASI_GLYPHS[signNum - 1]}</span>
                  )}
                  {labelParts.abbr && ln(RASI_NAMES[signNum - 1], "rasi", { abbr: true })}
                </span>
                <div className="si-planets">
                  {items.map((item, idx) => {
                    const cond = item.fullName ? flagsByPlanet[item.fullName] : null;
                    const clickable = onSelectPlanet && item.type === "planet" && item.fullName;
                    return (
                      <span
                        key={idx}
                        className={`si-pl${item.type === "lagna" ? " si-pl-lagna" : ""}${
                          item.type === "arudha" ? " si-pl-arudha" : ""
                        }${clickable ? " si-pl-clickable" : ""}`}
                        title={
                          cond
                            ? `${ln(item.fullName, "graha")}: ${cond.labels.join(", ")}`
                            : undefined
                        }
                        onClick={
                          clickable
                            ? (e) => {
                                e.stopPropagation();
                                onSelectPlanet(item.fullName);
                              }
                            : undefined
                        }
                      >
                        {item.name}
                        {item.degrees != null && (
                          <em className="si-deg">{item.degrees.toFixed(1)}°</em>
                        )}
                        {cond && (
                          <span
                            className="si-cond-dot"
                            style={{ color: CONDITION_TONE_COLOR[cond.tone] }}
                          >
                            ●
                          </span>
                        )}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* Graha drishti (aspect) lines. Aspect houses are 1-based from the Lagna;
            convert to the fixed sign, then to its cell centre. The overlay uses a
            0..4 grid so it scales with the chart (non-uniform-safe). */}
          {showAspects && aspects && lagna && (
            <svg
              className="si-aspect-overlay"
              viewBox="0 0 4 4"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              {aspects.flatMap((a) => {
                const data = planets[a.planet];
                if (!data || !data.house) return [];
                if (focusPlanet && focusPlanet !== a.planet) return [];
                const src = cellCenter(data.house);
                if (!src) return [];
                const color = ASPECT_COLORS[a.planet] || "#37474f";
                return (a.aspects_houses || []).map((h) => {
                  const sign = ((lagna.house - 1 + (h.house - 1)) % 12) + 1;
                  const tgt = cellCenter(sign);
                  if (!tgt) return null;
                  // Weight the line by aspect strength (0-100%).
                  const f = Math.max(0, Math.min(100, h.strength || 0)) / 100;
                  const width = (focusPlanet ? 1.4 : 0.8) + f * (focusPlanet ? 2.0 : 1.4);
                  const opacity = (focusPlanet ? 0.4 : 0.18) + f * (focusPlanet ? 0.55 : 0.42);
                  return (
                    <line
                      key={`${a.planet}-${h.house}`}
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke={color}
                      strokeWidth={width}
                      strokeOpacity={opacity}
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  );
                });
              })}
            </svg>
          )}
        </div>
        <div className="si-caption">{subtitle ? `${title} · ${subtitle}` : title}</div>
      </div>
    </div>
  );
};
