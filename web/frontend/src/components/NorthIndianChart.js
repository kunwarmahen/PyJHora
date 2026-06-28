import React, { useState } from "react";
import { PLANET_ABBR, RASI_NAMES } from "../constants/jyotish";
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
}) => {
  const [hoveredHouse, setHoveredHouse] = useState(null);

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

    return items;
  };

  // SVG geometry
  const width = 600;
  const height = 600;
  const size = 480;
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
    getCentroid([topMid, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }, center, { x: topRight.x - size * 0.25, y: topRight.y + size * 0.25 }]),
    getCentroid([topLeft, topMid, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }]),
    getCentroid([topLeft, { x: topLeft.x + size * 0.25, y: topLeft.y + size * 0.25 }, leftMid]),
    getCentroid([leftMid, { x: leftMid.x + size * 0.25, y: topLeft.y + size * 0.25 }, center, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }]),
    getCentroid([leftMid, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, bottomLeft]),
    getCentroid([bottomLeft, { x: leftMid.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, bottomMid]),
    getCentroid([bottomMid, { x: bottomLeft.x + size * 0.25, y: bottomLeft.y - size * 0.25 }, center, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }]),
    getCentroid([bottomMid, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }, bottomRight]),
    getCentroid([bottomRight, { x: bottomRight.x - size * 0.25, y: bottomRight.y - size * 0.25 }, rightMid]),
    getCentroid([rightMid, { x: rightMid.x - size * 0.25, y: bottomRight.y - size * 0.25 }, center, { x: rightMid.x - size * 0.25, y: topRight.y + size * 0.25 }]),
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
  const muted = "var(--text-secondary)";

  return (
    <div className="chart-card">
      <h3 className="chart-card-title">{title}</h3>
      <div className="chart-card-svg-wrap">
        <svg
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
          <rect x={squareX} y={squareY} width={size} height={size} fill="white" stroke="url(#chartGradient)" strokeWidth="3" />

          {/* Diagonals */}
          <line x1={topLeft.x} y1={topLeft.y} x2={bottomRight.x} y2={bottomRight.y} stroke={indigo} strokeWidth="2" />
          <line x1={topRight.x} y1={topRight.y} x2={bottomLeft.x} y2={bottomLeft.y} stroke={indigo} strokeWidth="2" />

          {/* Inner diamond */}
          <line x1={topMid.x} y1={topMid.y} x2={rightMid.x} y2={rightMid.y} stroke={indigo} strokeWidth="2" />
          <line x1={rightMid.x} y1={rightMid.y} x2={bottomMid.x} y2={bottomMid.y} stroke={indigo} strokeWidth="2" />
          <line x1={bottomMid.x} y1={bottomMid.y} x2={leftMid.x} y2={leftMid.y} stroke={indigo} strokeWidth="2" />
          <line x1={leftMid.x} y1={leftMid.y} x2={topMid.x} y2={topMid.y} stroke={indigo} strokeWidth="2" />

          {houses.map((house) => {
            const planetsInHouse = getPlanetsInHouse(house.num);
            const isHovered = hoveredHouse === house.num;

            return (
              <g key={house.num}>
                {/* House number */}
                <text x={house.cx} y={house.cy - 25} textAnchor="middle" fill={muted} fontSize="11" fontWeight="600">
                  {house.num}
                </text>

                {/* Sign name — shown on hover/tap */}
                <text
                  x={house.cx}
                  y={house.cy - 10}
                  textAnchor="middle"
                  fill={indigo}
                  fontSize="10"
                  fontWeight="500"
                  opacity={isHovered ? 1 : 0}
                  style={{ transition: "opacity 0.2s ease" }}
                >
                  {RASI_NAMES[getSignForVisualHouse(house.num) - 1]}
                </text>

                {/* Planets — one compact line each (name + inline degree),
                    spacing/size tightens when a house is crowded */}
                {(() => {
                  const total = planetsInHouse.length;
                  const step = total > 3 ? 14 : 18;
                  const fs = total > 3 ? 11 : 13;
                  const startY = house.cy - ((total - 1) * step) / 2 + 4;
                  return planetsInHouse.map((item, idx) => (
                    <text
                      key={idx}
                      x={house.cx}
                      y={startY + idx * step}
                      textAnchor="middle"
                      fill={item.type === "lagna" ? accent : indigo}
                      fontSize={fs}
                      fontWeight="700"
                    >
                      {item.name}
                      {item.degrees != null && (
                        <tspan dx="3" fontSize={fs - 4} fontWeight="400" fill={muted}>
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
          <text x={center.x} y={center.y - 5} textAnchor="middle" fill={indigo} fontSize="12" fontWeight="700">
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
