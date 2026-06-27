import React from "react";

// Astronomical glyphs for the grahas
const GLYPH = {
  Lagna: "Asc",
  Sun: "☉",
  Moon: "☽",
  Mars: "♂",
  Mercury: "☿",
  Jupiter: "♃",
  Venus: "♀",
  Saturn: "♄",
  Rahu: "☊",
  Ketu: "☋",
};

// Fixed display order — lagna first, then luminaries outward
const ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];

// Degrees-within-sign (float) -> "06°47′"
const formatDeg = (d) => {
  if (d == null || Number.isNaN(d)) return "—";
  let deg = Math.floor(d);
  let min = Math.round((d - deg) * 60);
  if (min === 60) {
    min = 0;
    deg += 1;
  }
  return `${String(deg).padStart(2, "0")}°${String(min).padStart(2, "0")}′`;
};

const Row = ({ name, data, isLagna }) => (
  <tr className={isLagna ? "jl-row-lagna" : undefined}>
    <td>
      <span className="jl-glyph">{GLYPH[name] || ""}</span>
      <span className="jl-body-name">{isLagna ? "Lagna" : name}</span>
    </td>
    <td>{data.sign_name || "—"}</td>
    <td>{data.nakshatra || "—"}</td>
    <td className="jl-num">{data.nakshatra_pada || "—"}</td>
    <td className="jl-num jl-deg">{formatDeg(data.degrees)}</td>
  </tr>
);

/**
 * Ephemeris-style table of planetary positions.
 * `lagna` is the ascendant object; `planets` is the d1_chart map.
 */
export const GrahaTable = ({ lagna, planets = {} }) => (
  <div className="jl-table-wrap">
    <table className="jl-table">
      <thead>
        <tr>
          <th>Body</th>
          <th>Sign</th>
          <th>Nakshatra</th>
          <th className="jl-num">Pada</th>
          <th className="jl-num">Degree</th>
        </tr>
      </thead>
      <tbody>
        {lagna && <Row name="Lagna" data={lagna} isLagna />}
        {ORDER.filter((p) => planets[p]).map((p) => (
          <Row key={p} name={p} data={planets[p]} />
        ))}
      </tbody>
    </table>
  </div>
);
