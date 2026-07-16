import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";
import { astrologyService } from "../services/api";
import { PLANET_ABBR } from "../constants/jyotish";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { ChakraAiPanel } from "./ChakraAiPanel";

// Kaala Chakra (§2.7) — the wheel of directions. Four stars at the hub and eight
// spokes of three, each spoke a compass direction; a graha on a spoke colours
// that direction. Self-contained (own fetch) so a failure can't blank the page.
//
// The wheel keeps the ENGINE'S OWN orientation (its 90deg spoke is labelled East,
// not north) so the layout matches desktop JHora rather than a compass rose.
const R_HUB = 62;
const R_SPOKE = 190;
const SIZE = 520;
const C = SIZE / 2;

// Engine angles are anticlockwise from +x with y inverted (screen coords).
const pt = (angleDeg, r) => {
  const rad = (angleDeg * Math.PI) / 180;
  return [C + r * Math.cos(rad), C - r * Math.sin(rad)];
};

export const KaalaChakra = ({ birthDetails, profile, transitDate, transitTime, transitTz, ayanamsa }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!birthDetails) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    astrologyService
      .getKaalaChakra(birthDetails, {
        currentDate: transitDate,
        currentTime: transitTime,
        currentTz: transitTz,
        ayanamsa,
      })
      .then((r) => !cancelled && setData(r.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || t("kaala.error")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [birthDetails, transitDate, transitTime, transitTz, ayanamsa, t]);

  if (loading) return <LoadingState message={t("kaala.loading")} />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="fade-in">
      <p className="card-note">{t("kaala.intro")}</p>

      <div className="info-pills">
        <span className="info-pill">
          {t("kaala.baseStar")}: <strong className="text-saffron">{data.base_star.name}</strong>
        </span>
        {data.favourable.length > 0 && (
          <span className="info-pill">
            {t("kaala.favourable")}:{" "}
            <strong className="kaala-good">{data.favourable.join(", ")}</strong>
          </span>
        )}
        {data.avoid.length > 0 && (
          <span className="info-pill">
            {t("kaala.avoid")}: <strong className="kaala-bad">{data.avoid.join(", ")}</strong>
          </span>
        )}
      </div>

      <div className="kaala-wrap">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="kaala-svg" role="img" aria-label={t("kaala.title")}>
          <circle cx={C} cy={C} r={R_HUB} className="kaala-hub" />

          {/* Eight spokes = eight directions */}
          {data.directions.map((d) => {
            const [x1, y1] = pt(d.angle, R_HUB);
            const [x2, y2] = pt(d.angle, R_SPOKE);
            const [lx, ly] = pt(d.angle, R_SPOKE + 42);
            return (
              <g key={d.direction} className={`kaala-dir kaala-dir--${d.tone}`}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} className="kaala-spoke" />
                {d.cells.map((c, j) => {
                  const [cx, cy] = pt(d.angle, R_HUB + ((R_SPOKE - R_HUB) / 3) * (j + 0.6));
                  const grahas = c.planets.map((p) => PLANET_ABBR[p.name] || p.name).join(" ");
                  return (
                    <g key={c.star}>
                      <title>{c.star}</title>
                      <circle cx={cx} cy={cy} r={15} className="kaala-cell" />
                      {grahas && (
                        <text x={cx} y={cy + 4} className="kaala-graha" textAnchor="middle">
                          {grahas}
                        </text>
                      )}
                    </g>
                  );
                })}
                <text x={lx} y={ly} className="kaala-dirlabel" textAnchor="middle">
                  {t(`kaala.dir.${d.direction.toLowerCase()}`, d.direction)}
                </text>
              </g>
            );
          })}

          {/* Four hub stars */}
          {data.inner.map((c) => {
            const [x, y] = pt(c.angle, R_HUB * 0.55);
            const grahas = c.planets.map((p) => PLANET_ABBR[p.name] || p.name).join(" ");
            return (
              <g key={c.star}>
                <title>{c.star}</title>
                <text x={x} y={y} className="kaala-inner" textAnchor="middle">
                  {grahas || "·"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Direction table — the actual reading */}
      <div className="ui-card ui-card--pad-lg">
        <h4 className="ui-card-header ui-card-header--sm">
          <Compass size={18} />
          {t("kaala.directions")}
        </h4>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("kaala.direction")}</th>
                <th>{t("kaala.stars")}</th>
                <th>{t("kaala.grahas")}</th>
                <th>{t("kaala.verdict")}</th>
              </tr>
            </thead>
            <tbody>
              {data.directions.map((d) => (
                <tr key={d.direction} className={`kaala-row kaala-row--${d.tone}`}>
                  <td className="fw-700">{t(`kaala.dir.${d.direction.toLowerCase()}`, d.direction)}</td>
                  <td className="text-secondary">{d.cells.map((c) => c.star).join(", ")}</td>
                  <td>
                    {d.cells.flatMap((c) =>
                      c.planets.map((p) => (
                        <span
                          key={p.name}
                          className={`kota-graha${p.malefic ? " is-malefic" : " is-benefic"}`}
                        >
                          {PLANET_ABBR[p.name] || p.name}
                          {p.retrograde ? "℞" : ""}
                        </span>
                      ))
                    )}
                  </td>
                  <td className={`kaala-tone kaala-tone--${d.tone}`}>{t(`kaala.tone.${d.tone}`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="card-note">{t("kaala.legend")}</p>
      </div>

      <ChakraAiPanel
        chakra="kaala"
        birthDetails={birthDetails}
        profile={profile}
        transitDate={transitDate}
        transitTime={transitTime}
        transitTz={transitTz}
        ayanamsa={ayanamsa}
      />
    </div>
  );
};
