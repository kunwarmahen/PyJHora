import React, { useState, useRef } from "react";
import { PLANET_ABBR, RASI_NAMES, RASI_ABBR, ASPECT_COLORS } from "../constants/jyotish";
import { ChartExportButtons } from "./ChartExportButtons";
import "../styles/NorthIndianChart.css";

/**
 * Reusable North Indian (diamond) chart.
 *
 * Accepts either:
 *   - `chartData={...}` (backward compatible: reads chartData.planets / chartData.lagna), or
 *   - explicit `planets` and `lagna` props (used to render divisional charts like D9).
 *
 * `title` / `subtitle` label the center of the chart.
 */
export const NorthIndianChart = ({
  chartData,
  planets: planetsProp,
  lagna: lagnaProp,
  title = "Rasi Chart",
  subtitle = "North Indian",
  exportable = false,
  aspects = null,
  showAspects = false,
  focusPlanet = null,
  arudhas = null,
  showArudhas = false,
}) => {
  const [hoveredHouse, setHoveredHouse] = useState(null);
  const svgRef = useRef(null);

  const planets = planetsProp || chartData?.planets;
  const lagna = lagnaProp || chartData?.lagna;

  if (!planets) {
    return <div className="chart-empty">No chart data</div>;
  }

  // Which zodiac sign sits in a given visual house position (1 = where Lagna is)
  const getSignForVisualHouse = (visualHouseNum) => {
    if (!lagna) return visualHouseNum;
    const lagnaSign = lagna.house; // e.g. 4 for Cancer
    let signNum = lagnaSign + visualHouseNum - 1;
    if (signNum > 12) signNum -= 12;
    return signNum;
  };

  // Planets + lagna occupying a specific visual house position
  const getPlanetsInHouse = (visualHouseNum) => {
    const items = [];
    const signAtThisPosition = getSignForVisualHouse(visualHouseNum);

    if (lagna && lagna.house === signAtThisPosition) {
      items.push({ name: "As", type: "lagna", degrees: lagna.degrees });
    }

    Object.entries(planets).forEach(([name, data]) => {
      if (data.house === signAtThisPosition) {
        items.push({
          name: PLANET_ABBR[name] || name,
          type: "planet",
          fullName: name,
          degrees: data.degrees,
        });
      }
    });

    // Arudha padas (AL/UL/A2..) that fall in this sign, shown on one line when toggled on.
    if (showArudhas && arudhas) {
      const labels = arudhas.filter((a) => a.sign === signAtThisPosition).map((a) => a.short);
      if (labels.length) items.push({ name: labels.join(" "), type: "arudha" });
    }

    return items;
  };

  // SVG geometry. The diamond fills nearly the whole viewBox (small inset only
  // to keep the outer stroke from clipping) so it matches the South Indian grid.
  const width = 600;
  const height = 600;
  const size = 580;
  const offset = (width - size) / 2;

  const squareX = offset;
  const squareY = offset;

  const topLeft = { x: squareX, y: squareY };
  const topRight = { x: squareX + size, y: squareY };
  const bottomLeft = { x: squareX, y: squareY + size };
  const bottomRight = { x: squareX + size, y: squareY + size };
  const topMid = { x: squareX + size / 2, y: squareY };
  const rightMid = { x: squareX + size, y: squareY + size / 2 };
  const bottomMid = { x: squareX + size / 2, y: squareY + size };
  const leftMid = { x: squareX, y: squareY + size / 2 };
  const center = { x: squareX + size / 2, y: squareY + size / 2 };

  const getCentroid = (points) => {
    const n = points.length;
    let cx = 0;
    let cy = 0;
    for (let i = 0; i < n; i++) {
      cx += points[i].x;
      cy += points[i].y;
    }
    return { x: cx / n, y: cy / n };
  };

  const housePolygons = [
    getCentroid([
      topMid,
      { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 },
      center,
      { x: topRight.x - size * 0.25, y: topRight.y + size * 0.25 },
    ]),
    getCentroid([topLeft, topMid, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }]),
    getCentroid([topLeft, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }, leftMid]),
    getCentroid([
      leftMid,
      { x: leftMid.x + size * 0.25, y: topLeft.y + size * 0.25 },
      center,
      { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 },
    ]),
    getCentroid([
      leftMid,
      { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 },
      bottomLeft,
    ]),
    getCentroid([
      bottomLeft,
      { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 },
      bottomMid,
    ]),
    getCentroid([
      bottomMid,
      { x: bottomLeft.x + size * 0.25, y: bottomLeft.y - size * 0.25 },
      center,
      { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 },
    ]),
    getCentroid([
      bottomMid,
      { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 },
      bottomRight,
    ]),
    getCentroid([
      bottomRight,
      { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 },
      rightMid,
    ]),
    getCentroid([
      rightMid,
      { x: rightMid.x - size * 0.25, y: bottomRight.y - size * 0.25 },
      center,
      { x: rightMid.x - size * 0.25, y: topRight.y + size * 0.25 },
    ]),
    getCentroid([rightMid, { x: rightMid.x - size * 0.25, y: topRight.y + size * 0.25 }, topRight]),
    getCentroid([topRight, { x: topRight.x - size * 0.25, y: topRight.y + size * 0.25 }, topMid]),
  ];

  const houses = housePolygons.map((centroid, index) => ({
    num: index + 1,
    cx: centroid.x,
    cy: centroid.y,
  }));

  const accent = "var(--saffron)";
  const indigo = "var(--cosmic-indigo)";
  const gold = "var(--temple-gold)";
  const muted = "var(--text-secondary)";
  const planetColor = "var(--planet-color)";

  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <h3 className="chart-card-title">{title}</h3>
        {exportable && <ChartExportButtons targetRef={svgRef} title={`${title} ${subtitle}`} />}
      </div>
      <div className="chart-card-svg-wrap">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          style={{ maxWidth: "600px", height: "auto" }}
          role="img"
          aria-label={`${title} (${subtitle})`}
        >
          <defs>
            <linearGradient id="chartGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: "var(--saffron)", stopOpacity: 1 }} />
              <stop offset="100%" style={{ stopColor: "var(--vermillion)", stopOpacity: 1 }} />
            </linearGradient>
          </defs>

          {/* Outer square */}
          <rect
            x={squareX}
            y={squareY}
            width={size}
            height={size}
            fill="white"
            stroke="url(#chartGradient)"
            strokeWidth="3"
          />

          {/* Diagonals */}
          <line
            x1={topLeft.x}
            y1={topLeft.y}
            x2={bottomRight.x}
            y2={bottomRight.y}
            stroke={indigo}
            strokeWidth="2"
          />
          <line
            x1={topRight.x}
            y1={topRight.y}
            x2={bottomLeft.x}
            y2={bottomLeft.y}
            stroke={indigo}
            strokeWidth="2"
          />

          {/* Inner diamond */}
          <line
            x1={topMid.x}
            y1={topMid.y}
            x2={rightMid.x}
            y2={rightMid.y}
            stroke={indigo}
            strokeWidth="2"
          />
          <line
            x1={rightMid.x}
            y1={rightMid.y}
            x2={bottomMid.x}
            y2={bottomMid.y}
            stroke={indigo}
            strokeWidth="2"
          />
          <line
            x1={bottomMid.x}
            y1={bottomMid.y}
            x2={leftMid.x}
            y2={leftMid.y}
            stroke={indigo}
            strokeWidth="2"
          />
          <line
            x1={leftMid.x}
            y1={leftMid.y}
            x2={topMid.x}
            y2={topMid.y}
            stroke={indigo}
            strokeWidth="2"
          />

          {/* Graha drishti (aspect) lines — from each aspecting graha's house to
              the houses it aspects. Houses in the aspect data are 1-based from the
              Lagna, which is exactly the visual house numbering here. */}
          {showAspects && aspects && lagna && (
            <g className="aspect-lines">
              {aspects.flatMap((a) => {
                const data = planets[a.planet];
                if (!data || !data.house) return [];
                const srcVisual = ((data.house - lagna.house + 12) % 12) + 1;
                const src = houses[srcVisual - 1];
                if (!src) return [];
                const dim = focusPlanet && focusPlanet !== a.planet;
                if (focusPlanet && dim) return [];
                const color = ASPECT_COLORS[a.planet] || indigo;
                return (a.aspects_houses || []).map((h) => {
                  const tgt = houses[h.house - 1];
                  if (!tgt) return null;
                  // Weight the line by aspect strength (0-100%): full aspects draw
                  // bold/solid, partial ones thin/faint.
                  const f = Math.max(0, Math.min(100, h.strength || 0)) / 100;
                  const width = (focusPlanet ? 1.4 : 0.8) + f * (focusPlanet ? 2.0 : 1.4);
                  const opacity = (focusPlanet ? 0.4 : 0.18) + f * (focusPlanet ? 0.55 : 0.42);
                  return (
                    <line
                      key={`${a.planet}-${h.house}`}
                      x1={src.cx}
                      y1={src.cy}
                      x2={tgt.cx}
                      y2={tgt.cy}
                      stroke={color}
                      strokeWidth={width}
                      strokeOpacity={opacity}
                      strokeLinecap="round"
                    />
                  );
                });
              })}
            </g>
          )}

          {houses.map((house) => {
            const planetsInHouse = getPlanetsInHouse(house.num);
            const isHovered = hoveredHouse === house.num;
            const sign = getSignForVisualHouse(house.num);

            // Sign label rides the outer edge of the house so the centroid stays
            // clear for planets. Every centroid sits on the center→edge ray, so a
            // single outward push works for both the diamond and corner houses;
            // the clamp keeps it off the frame in the tight corners.
            const pad = 26;
            const k = 0.4;
            const labelX = Math.max(
              squareX + pad,
              Math.min(squareX + size - pad, house.cx + k * (house.cx - center.x))
            );
            const labelY = Math.max(
              squareY + pad,
              Math.min(squareY + size - pad, house.cy + k * (house.cy - center.y))
            );
            // Grow the (hover-expanded) label inward from whichever edge it hugs:
            // left-side houses anchor at start, right-side at end, top/bottom middle.
            const dx = labelX - center.x;
            const labelAnchor = Math.abs(dx) < size * 0.15 ? "middle" : dx < 0 ? "start" : "end";

            return (
              <g key={house.num}>
                {/* Header line: house number + sign label, pinned to the house's
                    outer edge so it never competes with planets for the centroid.
                    The sign abbreviation is always visible (parity with the South
                    chart); on hover it expands to the full sign name. */}
                <text x={labelX} y={labelY} textAnchor={labelAnchor}>
                  <tspan fill={muted} fontSize="11" fontWeight="600">
                    {house.num}
                  </tspan>
                  <tspan
                    dx="5"
                    fill={indigo}
                    fontSize="10"
                    fontWeight="500"
                    opacity={isHovered ? 1 : 0.65}
                  >
                    {isHovered ? RASI_NAMES[sign - 1] : RASI_ABBR[sign - 1]}
                  </tspan>
                </text>

                {/* Planets — one compact line each (name + inline degree),
                    spacing/size tightens in graduated steps as a house fills up,
                    mirroring the South chart's crowded-cell handling. */}
                {(() => {
                  const total = planetsInHouse.length;
                  const fs = total <= 3 ? 13 : total <= 5 ? 11 : 10;
                  const step = total <= 3 ? 18 : total <= 5 ? 14 : 12;
                  const degFs = Math.max(fs - 3, 8);
                  const startY = house.cy - ((total - 1) * step) / 2;
                  return planetsInHouse.map((item, idx) => (
                    <text
                      key={idx}
                      x={house.cx}
                      y={startY + idx * step}
                      textAnchor="middle"
                      fill={
                        item.type === "lagna" ? accent : item.type === "arudha" ? gold : planetColor
                      }
                      fontSize={item.type === "arudha" ? Math.max(fs - 2, 9) : fs}
                      fontWeight="700"
                      fontStyle={item.type === "arudha" ? "italic" : "normal"}
                    >
                      {item.name}
                      {item.degrees != null && (
                        <tspan dx="3" fontSize={degFs} fontWeight="400">
                          {item.degrees.toFixed(1)}°
                        </tspan>
                      )}
                    </text>
                  ));
                })()}

                {/* Hit area drives hover/tap state */}
                <circle
                  cx={house.cx}
                  cy={house.cy}
                  r="50"
                  fill="transparent"
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHoveredHouse(house.num)}
                  onMouseLeave={() => setHoveredHouse(null)}
                  onClick={() => setHoveredHouse((prev) => (prev === house.num ? null : house.num))}
                />
              </g>
            );
          })}

          {/* Center label */}
          <text
            x={center.x}
            y={center.y - 5}
            textAnchor="middle"
            fill={indigo}
            fontSize="12"
            fontWeight="700"
          >
            {title}
          </text>
          <text x={center.x} y={center.y + 10} textAnchor="middle" fill={muted} fontSize="10">
            {subtitle}
          </text>
        </svg>
      </div>
    </div>
  );
};
