import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Ban } from "lucide-react";
import { astrologyService } from "../services/api";
import { PLANET_ABBR, RASI_ABBR } from "../constants/jyotish";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { ChakraAiPanel } from "./ChakraAiPanel";

// Tripataki Chakra (§2.7) — the twelve rasis around a 5x5 grid, crossed by the
// three "pataki" (banner) lines. The engine only ever shipped this as a drawing
// (no vedha/scoring), so this renders the faithful diagram and stops there.
const PAD = 44; // px around the grid
const STEP = 96; // px per grid unit (grid coords run 1..5)

const px = (n) => PAD + (n - 1) * STEP;

export const TripatakiChakra = ({ birthDetails, profile, transitDate, transitTime, transitTz, ayanamsa }) => {
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
      .getTripatakiChakra(birthDetails, {
        currentDate: transitDate,
        currentTime: transitTime,
        currentTz: transitTz,
        ayanamsa,
      })
      .then((r) => !cancelled && setData(r.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || t("tripataki.error")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [birthDetails, transitDate, transitTime, transitTz, ayanamsa, t]);

  if (loading) return <LoadingState message={t("tripataki.loading")} />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  const size = PAD * 2 + (data.grid.width - 1) * STEP;

  return (
    <div className="fade-in">
      <p className="card-note">{t("tripataki.intro")}</p>
      <div className="info-pills">
        <span className="info-pill">
          {t("tripataki.natalLagna")}: <strong className="text-saffron">{data.natal_lagna}</strong>
        </span>
        <span className="info-pill">
          {t("tripataki.transitMoon")}: <strong className="text-indigo">{data.transit_moon}</strong>
        </span>
      </div>

      <div className="tripataki-wrap">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="tripataki-svg"
          role="img"
          aria-label={t("tripataki.title")}
        >
          {/* The three pataki (banner) lines */}
          {data.lines.map((l, i) => (
            <line
              key={i}
              x1={px(l.from[0])}
              y1={px(l.from[1])}
              x2={px(l.to[0])}
              y2={px(l.to[1])}
              className="tripataki-line"
            />
          ))}

          {/* The twelve rasis */}
          {data.cells.map((c) => {
            const cx = px(c.x);
            const cy = px(c.y);
            const grahas = c.transit.map((p) => PLANET_ABBR[p.name] || p.name);
            const cls =
              `tripataki-cell${c.is_lagna ? " is-lagna" : ""}` +
              `${c.is_moon ? " is-moon" : ""}${c.casts_vedha ? " casts-vedha" : ""}`;
            return (
              <g key={c.sign} className={cls}>
                <title>
                  {c.sign_name} · {t(`tripataki.class.${c.sign_class}`)}
                  {c.casts_vedha ? ` · ${t("tripataki.castsVedha")}` : ""}
                </title>
                <circle cx={cx} cy={cy} r={26} className="tripataki-node" />
                <text x={cx} y={cy - 4} className="tripataki-rasi" textAnchor="middle">
                  {RASI_ABBR[c.sign - 1] || c.sign_name}
                </text>
                <text x={cx} y={cy + 9} className="tripataki-house" textAnchor="middle">
                  {c.house_from_lagna}
                </text>
                {grahas.length > 0 && (
                  <text x={cx} y={cy + 40} className="tripataki-grahas" textAnchor="middle">
                    {grahas.join(" ")}
                  </text>
                )}
                {c.natal.length > 0 && (
                  <text x={cx} y={cy + 54} className="tripataki-natal" textAnchor="middle">
                    {c.natal.map((n) => PLANET_ABBR[n] || n).join(" ")}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Vedha — the point of the chakra: what obstructs the Moon and the Lagna. */}
      {data.vedha?.length > 0 && (
        <div className="ui-card ui-card--pad-lg">
          <h4 className="ui-card-header ui-card-header--sm">
            <Ban size={18} />
            {t("tripataki.vedhaTitle")}
          </h4>
          <p className="card-note">{t("tripataki.vedhaIntro")}</p>
          {data.vedha.map((v) => (
            <div key={v.target} className={`trip-vedha trip-vedha--${v.tone}`}>
              <div className="trip-vedha__head">
                <strong>{t(`tripataki.target.${v.target.toLowerCase()}`, v.target)}</strong>{" "}
                <span className="text-secondary">
                  {t("tripataki.inSign", { sign: v.sign })} ({t(`tripataki.class.${v.sign_class}`)})
                </span>
              </div>
              {v.obstructed_by.length === 0 ? (
                <p className="trip-vedha__clear">{t("tripataki.noVedha")}</p>
              ) : (
                <ul className="detail-list">
                  {v.obstructed_by.map((h) => (
                    <li key={h.planet} className={h.benefic ? "is-benefic" : "is-malefic"}>
                      {t("tripataki.obstructedBy", { planet: h.planet, sign: h.from_sign })}{" "}
                      <span className="text-muted">
                        ({t(h.benefic ? "tripataki.benefic" : "tripataki.malefic")})
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="card-note">
                {t("tripataki.vedhaFrom", { signs: v.vedha_signs.join(", ") })}
              </p>
            </div>
          ))}
        </div>
      )}

      <p className="card-note">{t("tripataki.legend")}</p>
      <p className="card-note">{t("tripataki.sourceNote")}</p>

      <ChakraAiPanel
        chakra="tripataki"
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
