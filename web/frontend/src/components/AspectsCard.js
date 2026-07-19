import React from "react";
import { useTranslation } from "react-i18next";
import { Eye } from "lucide-react";
import "../styles/Aspects.css";

/**
 * Graha Drishti (aspects) table. One row per aspecting graha: the houses and
 * planets it aspects (with the Parashari sphuta strength %), plus rasi-drishti
 * targets. Reused on the Birth Chart and Advanced pages.
 *
 * Optional interactivity:
 *   - `onFocus(planetName | null)` fires on row hover (drives chart highlighting)
 *   - `focusPlanet` marks the active row
 *   - `headerExtra` renders controls (e.g. a "show on chart" toggle) in the header
 */
export const AspectsCard = ({ aspects, onFocus, focusPlanet, headerExtra }) => {
  const { t } = useTranslation();
  if (!aspects || aspects.length === 0) return null;

  // Colour a strength % from weak (muted) to strong (vermillion).
  const strengthStyle = (pct) => {
    const p = Math.max(0, Math.min(100, pct || 0));
    const alpha = 0.12 + (p / 100) * 0.55;
    return { background: `rgba(204, 51, 0, ${alpha.toFixed(2)})` };
  };

  return (
    <div className="ui-card ui-card--accent ui-card--flush mt-xl aspects-card">
      <h3 className="ui-card-header aspects-card__head">
        <span className="aspects-card__title">
          <Eye size={22} />
          {t("aspects.title")}
        </span>
        {headerExtra}
      </h3>
      <p className="card-note">{t("aspects.intro")}</p>
      <div className="aspects-table-wrap">
        <table className="data-table aspects-table">
          <thead>
            <tr>
              <th>{t("aspects.graha")}</th>
              <th>{t("aspects.houses")}</th>
              <th>{t("aspects.planets")}</th>
              <th>{t("aspects.rasiDrishti")}</th>
            </tr>
          </thead>
          <tbody>
            {aspects.map((a) => {
              const active = focusPlanet === a.planet;
              return (
                <tr
                  key={a.planet}
                  className={`aspects-row${active ? " is-active" : ""}`}
                  onMouseEnter={() => onFocus && onFocus(a.planet)}
                  onMouseLeave={() => onFocus && onFocus(null)}
                >
                  <td className="aspects-graha">
                    {a.planet}
                    {a.special_aspect && (
                      <span className="aspects-special" title={t("aspects.specialTip")}>
                        ★
                      </span>
                    )}
                  </td>
                  <td>
                    {a.aspects_houses && a.aspects_houses.length ? (
                      <span className="aspects-pl-list">
                        {a.aspects_houses.map((h) => (
                          <span
                            key={h.house}
                            className="aspects-pl"
                            style={strengthStyle(h.strength)}
                            title={`${h.strength}% strength`}
                          >
                            {h.house}
                          </span>
                        ))}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {a.aspects_planets && a.aspects_planets.length ? (
                      <span className="aspects-pl-list">
                        {a.aspects_planets.map((p) => (
                          <span
                            key={p.planet}
                            className="aspects-pl"
                            style={strengthStyle(p.strength)}
                          >
                            {p.planet} {p.strength}%
                          </span>
                        ))}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="aspects-rasi">
                    {a.rasi_drishti_planets && a.rasi_drishti_planets.length
                      ? a.rasi_drishti_planets.join(", ")
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="card-note aspects-card__foot">{t("aspects.note")}</p>
    </div>
  );
};
