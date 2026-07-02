import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sparkles, Grid3x3, Compass, Gauge, HeartPulse } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { GlossaryTerm } from "../components/GlossaryTerm";
import { AspectsCard } from "../components/AspectsCard";
import { AYANAMSAS, DEFAULT_AYANAMSA } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const RASI_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];

// Map a Sarva Ashtakavarga bindu count (~25–40) to a saffron tint for a heatmap.
const savColor = (v) => {
  const lo = 18,
    hi = 40;
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
  const alpha = 0.12 + t * 0.6;
  return `rgba(255, 153, 51, ${alpha.toFixed(2)})`;
};

export const AdvancedPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();

  const [ayanamsa, setAyanamsa] = useState(
    () => localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA
  );
  const [av, setAv] = useState(null);
  const [details, setDetails] = useState(null);
  const [shadbala, setShadbala] = useState(null);
  const [aspects, setAspects] = useState(null);
  const [longevity, setLongevity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const birthDetails = useMemo(
    () =>
      selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: parseFloat(selectedProfile.birth_details.latitude),
            longitude: parseFloat(selectedProfile.birth_details.longitude),
            timezone: parseFloat(selectedProfile.birth_details.timezone),
          }
        : null,
    [selectedProfile]
  );

  const changeAyanamsa = (value) => {
    setAyanamsa(value);
    localStorage.setItem("ayanamsa", value);
  };

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    // Each section loads independently so one failure won't blank the others.
    setLoading(true);
    setError("");
    setAv(null);
    setDetails(null);
    setShadbala(null);
    setAspects(null);
    setLongevity(null);
    let cancelled = false;
    const done = { av: false, d: false, sb: false, asp: false };
    const settle = () => {
      if (!cancelled && done.av && done.d && done.sb && done.asp) setLoading(false);
    };
    astrologyService
      .getAshtakavarga(birthDetails, ayanamsa)
      .then((r) => !cancelled && setAv(r.data))
      .catch(() => {})
      .finally(() => {
        done.av = true;
        settle();
      });
    astrologyService
      .getChartDetails(birthDetails, ayanamsa)
      .then((r) => !cancelled && setDetails(r.data))
      .catch(() => {})
      .finally(() => {
        done.d = true;
        settle();
      });
    astrologyService
      .getShadbala(birthDetails, ayanamsa)
      .then((r) => !cancelled && setShadbala(r.data))
      .catch((e) => !cancelled && setError(e.response?.data?.detail || ""))
      .finally(() => {
        done.sb = true;
        settle();
      });
    astrologyService
      .getAspects(birthDetails, ayanamsa)
      .then((r) => !cancelled && setAspects(r.data?.planets || null))
      .catch(() => {})
      .finally(() => {
        done.asp = true;
        settle();
      });
    // Longevity loads independently (does not gate the page spinner).
    astrologyService
      .getLongevity(birthDetails, ayanamsa)
      .then((r) => !cancelled && setLongevity(r.data))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate, ayanamsa]);

  if (!selectedProfile) return null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Sparkles size={24} />}
        title={t("advanced.title")}
        subtitle={t("advanced.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <div className="controls-end">
          <label className="ayanamsa-select">
            <span>{t("birthChart.ayanamsa")}</span>
            <select value={ayanamsa} onChange={(e) => changeAyanamsa(e.target.value)}>
              {AYANAMSAS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("advanced.loading")} />
          </Card>
        ) : (
          <>
            {/* Ashtakavarga */}
            {av && (
              <Card
                title={<GlossaryTerm>Ashtakavarga</GlossaryTerm>}
                icon={<Grid3x3 size={24} />}
                accent="saffron"
              >
                <p className="card-intro">
                  {t("advanced.savIntro")} <strong>{av.sarva_total}</strong>.
                </p>
                <div className="table-scroll">
                  <table className="adv-table">
                    <thead>
                      <tr>
                        <th>{t("advanced.contributor")}</th>
                        {RASI_ABBR.map((r) => (
                          <th key={r}>{r}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="fw-700">
                          <GlossaryTerm term="Sarva">Sarva (SAV)</GlossaryTerm>
                        </td>
                        {av.sarva.map((v, i) => (
                          <td key={i} className="fw-700" style={{ background: savColor(v) }}>
                            {v}
                          </td>
                        ))}
                      </tr>
                      {Object.entries(av.bhinna).map(([planet, row]) => (
                        <tr key={planet}>
                          <td>{planet}</td>
                          {row.map((v, i) => (
                            <td key={i}>{v}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* Advanced chart details */}
            {details && (
              <Card title={t("advanced.chartFactors")} icon={<Compass size={24} />} accent="indigo">
                <h4 className="adv-subhead">
                  <GlossaryTerm term="Arudha">Arudha</GlossaryTerm> {t("advanced.padas")}
                </h4>
                <div className="ui-field-grid">
                  {details.arudha_padas.map((a) => (
                    <DataField key={a.bhava} label={a.label} value={a.sign_name} />
                  ))}
                </div>

                <h4 className="adv-subhead">
                  {t("advanced.chara")} <GlossaryTerm term="Karaka">Karakas</GlossaryTerm> (Jaimini)
                </h4>
                <div className="ui-field-grid">
                  {details.chara_karakas.map((k) => (
                    <DataField key={k.karaka} label={k.karaka} value={k.planet} />
                  ))}
                </div>

                <h4 className="adv-subhead">
                  {t("advanced.special")} <GlossaryTerm term="Lagna">Lagnas</GlossaryTerm>
                </h4>
                <div className="ui-field-grid">
                  {details.special_lagnas.map((s) => (
                    <DataField key={s.name} label={s.name} value={`${s.sign_name} ${s.degrees}°`} />
                  ))}
                </div>

                <h4 className="adv-subhead">
                  <GlossaryTerm term="Upagraha">Upagrahas</GlossaryTerm> ({t("advanced.subPlanets")}
                  )
                </h4>
                <div className="ui-field-grid">
                  {details.upagrahas.map((u) => (
                    <DataField key={u.name} label={u.name} value={`${u.sign_name} ${u.degrees}°`} />
                  ))}
                </div>
              </Card>
            )}

            {/* Shadbala */}
            {shadbala && (
              <Card
                title={
                  <>
                    <GlossaryTerm>Shadbala</GlossaryTerm> (Planetary Strength)
                  </>
                }
                icon={<Gauge size={24} />}
                accent="vermillion"
              >
                <p className="card-intro">{t("advanced.shadbalaIntro")}</p>
                <div className="table-scroll">
                  <table className="adv-table">
                    <thead>
                      <tr>
                        <th>{t("common.planet")}</th>
                        <th>Sthana</th>
                        <th>Kaala</th>
                        <th>Dig</th>
                        <th>Cheshta</th>
                        <th>Naisargika</th>
                        <th>Drik</th>
                        <th>{t("advanced.colTotal")}</th>
                        <th>{t("advanced.colRequired")}</th>
                        <th>{t("advanced.colRatio")}</th>
                        <th>{t("advanced.colRank")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shadbala.planets.map((p) => (
                        <tr key={p.planet}>
                          <td className="fw-700">{p.planet}</td>
                          <td>{p.sthana}</td>
                          <td>{p.kaala}</td>
                          <td>{p.dig}</td>
                          <td>{p.cheshta}</td>
                          <td>{p.naisargika}</td>
                          <td>{p.drik}</td>
                          <td className="fw-700">{p.total_rupa}</td>
                          <td>{p.required_rupa}</td>
                          <td className={`fw-700 ${p.sufficient ? "text-saffron" : "text-vermillion"}`}>
                            {p.strength_ratio}
                          </td>
                          <td>{p.rank}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* Graha Drishti (aspects) — table only (no chart on this page) */}
            <AspectsCard aspects={aspects} />

            {/* Ayu / longevity indication (gentle, conditional) */}
            {longevity && (
              <Card
                title={t("advanced.longevity.title")}
                icon={<HeartPulse size={24} />}
                accent="terracotta"
              >
                <p className="card-intro">{t("advanced.longevity.intro")}</p>
                <div className="ayu-band">
                  {[
                    [0, t("advanced.longevity.alpa")],
                    [1, t("advanced.longevity.madhya")],
                    [2, t("advanced.longevity.purna")],
                  ].map(([val, label]) => (
                    <div
                      key={val}
                      className={`ayu-band__seg${longevity.category === val ? " is-active" : ""}`}
                    >
                      {label}
                    </div>
                  ))}
                </div>
                {longevity.factors?.length > 0 && (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("advanced.longevity.pair")}</th>
                          <th>{t("advanced.longevity.signs")}</th>
                          <th>{t("advanced.longevity.verdict")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {longevity.factors.map((f, i) => (
                          <tr key={i}>
                            <td className="fw-600 text-indigo">{f.pair}</td>
                            <td className="text-secondary">{(f.signs || []).join(" · ")}</td>
                            <td className="fw-600 text-saffron">{f.verdict}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="card-note">{t("advanced.longevity.disclaimer")}</p>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AdvancedPage;
