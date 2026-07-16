import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { X, Sparkles } from "lucide-react";
import "../styles/PlanetExplorer.css";

// Sign (0-based rasi) owned by each graha — used to derive the houses it lords.
const RULERSHIP = {
  Sun: [4],
  Moon: [3],
  Mars: [0, 7],
  Mercury: [2, 5],
  Jupiter: [8, 11],
  Venus: [1, 6],
  Saturn: [9, 10],
};
const GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];
const ORD = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th"];

/**
 * §5.5 Interactive chart explorer. A strip of planet chips under the Kundali;
 * clicking one slides in a panel with that graha's placement, dignity signals,
 * nakshatra, houses owned, aspects cast/received and any condition flags — all
 * assembled from data the Birth Chart page already loaded (no new endpoints) —
 * plus an "Ask AI about this placement" deep-link into the Ask flow.
 */
export const PlanetExplorer = ({
  chart,
  aspects,
  conditions,
  personName,
  selected: selectedProp,
  onSelect,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  // Controlled (from chart clicks) when `onSelect` is provided; else self-managed.
  const [selfSelected, setSelfSelected] = useState(null);
  const selected = onSelect ? selectedProp : selfSelected;
  const setSelected = onSelect || setSelfSelected;

  const d1 = chart?.d1_chart || {};
  const lagnaRasi = (chart?.lagna?.house ?? 1) - 1; // 0-based ascendant sign

  const houseFromLagna = (rasi) => (((rasi - lagnaRasi) % 12) + 12) % 12; // 0..11

  const detailFor = (name) => {
    const p = d1[name];
    if (!p) return null;
    const asp = (aspects || []).find((a) => a.planet === name);
    const cond = (conditions || []).find((c) => c.planet === name);
    const owned = (RULERSHIP[name] || []).map((r) => ORD[houseFromLagna(r)]);
    return {
      name,
      sign: p.sign_name,
      degrees: p.degrees,
      house: ORD[houseFromLagna(p.rasi)],
      nakshatra: p.nakshatra,
      pada: p.nakshatra_pada,
      owned,
      aspectsHouses: (asp?.aspects_houses || []).map((h) => ORD[h.house - 1] || `H${h.house}`),
      aspectsPlanets: (asp?.aspects_planets || []).map((x) => x.planet || x),
      rasiDrishti: asp?.rasi_drishti_planets || [],
      flags: cond?.flags || [],
    };
  };

  const info = selected ? detailFor(selected) : null;

  const askAI = () => {
    if (!info) return;
    const q = t("explorer.askPrefill", {
      planet: info.name,
      sign: info.sign,
      house: info.house,
      name: personName || t("explorer.thisChart"),
    });
    navigate("/ask-astrologer", { state: { prefillQuestion: q } });
  };

  return (
    <div className="pex">
      <div className="pex-hint">{t("explorer.stripLabel")}</div>
      <div className="pex-strip" role="tablist" aria-label={t("explorer.stripLabel")}>
        {GRAHAS.filter((g) => d1[g]).map((g) => (
          <button
            key={g}
            className={`pex-chip${selected === g ? " pex-chip--active" : ""}`}
            onClick={() => setSelected(selected === g ? null : g)}
          >
            {g}
          </button>
        ))}
      </div>

      {info && (
        <>
          <div className="pex-overlay" onClick={() => setSelected(null)} />
          <aside className="pex-panel" role="dialog" aria-label={info.name}>
            <div className="pex-panel__head">
              <h3>{info.name}</h3>
              <button className="pex-close" aria-label={t("common.close")} onClick={() => setSelected(null)}>
                <X size={20} />
              </button>
            </div>
            <div className="pex-panel__body">
              <Row label={t("explorer.placement")} value={`${info.sign} ${info.degrees}° · ${info.house} ${t("explorer.house")}`} />
              <Row label={t("explorer.nakshatra")} value={`${info.nakshatra} · ${t("explorer.pada")} ${info.pada}`} />
              {info.owned.length > 0 && (
                <Row label={t("explorer.housesOwned")} value={info.owned.join(", ")} />
              )}
              {info.aspectsHouses.length > 0 && (
                <Row label={t("explorer.aspectsHouses")} value={info.aspectsHouses.join(", ")} />
              )}
              {info.aspectsPlanets.length > 0 && (
                <Row label={t("explorer.aspectsPlanets")} value={info.aspectsPlanets.join(", ")} />
              )}
              {info.rasiDrishti.length > 0 && (
                <Row label={t("explorer.rasiDrishti")} value={info.rasiDrishti.join(", ")} />
              )}
              {info.flags.length > 0 && (
                <div className="pex-flags">
                  <span className="pex-row__label">{t("explorer.conditions")}</span>
                  <div className="pex-flags__row">
                    {info.flags.map((f, i) => (
                      <span key={i} className={`pex-flag pex-flag--${f.tone}`}>
                        {f.label}
                        {f.partner ? ` (${f.partner})` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <button className="ui-btn ui-btn--ai pex-ask" onClick={askAI}>
                <Sparkles size={18} />
                {t("explorer.askAI")}
              </button>
            </div>
          </aside>
        </>
      )}
    </div>
  );
};

const Row = ({ label, value }) => (
  <div className="pex-row">
    <span className="pex-row__label">{label}</span>
    <span className="pex-row__value">{value}</span>
  </div>
);

export default PlanetExplorer;
