import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sparkles, Grid3x3, Compass, Gauge, HeartPulse, ShieldAlert, Hourglass } from "lucide-react";
import ReactMarkdown from "react-markdown";
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
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const RASI_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];

// Flag tone → chip colour (benefic green / challenging vermillion / neutral gray).
const TONE_COLOR = { benefic: "#2E9E5B", challenging: "#e34234", neutral: "#8b8fa8" };

const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl:
      providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

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

  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const [av, setAv] = useState(null);
  const [details, setDetails] = useState(null);
  const [shadbala, setShadbala] = useState(null);
  const [aspects, setAspects] = useState(null);
  const [longevity, setLongevity] = useState(null);
  const [conditions, setConditions] = useState(null);
  const [avasthas, setAvasthas] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Planet-conditions AI reading (self-contained on this card).
  const [pcAi, setPcAi] = useState("");
  const [pcAiModel, setPcAiModel] = useState("");
  const [pcAiLoading, setPcAiLoading] = useState(false);
  const [pcAiError, setPcAiError] = useState("");

  // Avasthas AI reading (self-contained on this card).
  const [avAi, setAvAi] = useState("");
  const [avAiModel, setAvAiModel] = useState("");
  const [avAiLoading, setAvAiLoading] = useState(false);
  const [avAiError, setAvAiError] = useState("");

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
    setConditions(null);
    setAvasthas(null);
    setPcAi("");
    setPcAiError("");
    setAvAi("");
    setAvAiError("");
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
    // Planet conditions load independently too.
    astrologyService
      .getPlanetConditions(birthDetails, ayanamsa)
      .then((r) => !cancelled && setConditions(r.data))
      .catch(() => {});
    // Avasthas load independently.
    astrologyService
      .getAvasthas(birthDetails, ayanamsa)
      .then((r) => !cancelled && setAvasthas(r.data))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate, ayanamsa]);

  const handleConditionsAi = async () => {
    if (!birthDetails) return;
    setPcAiLoading(true);
    setPcAiError("");
    try {
      const res = await astrologyService.analyzePlanetConditionsAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setPcAi(res.data.ai_analysis || "");
      setPcAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setPcAiError(err.response?.data?.detail || t("conditions.aiError"));
    } finally {
      setPcAiLoading(false);
    }
  };

  const handleAvasthasAi = async () => {
    if (!birthDetails) return;
    setAvAiLoading(true);
    setAvAiError("");
    try {
      const res = await astrologyService.analyzeAvasthasAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAvAi(res.data.ai_analysis || "");
      setAvAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAvAiError(err.response?.data?.detail || t("avasthas.aiError"));
    } finally {
      setAvAiLoading(false);
    }
  };

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

            {/* Planet conditions (combustion, vargottama, gandanta, …) */}
            {conditions && (
              <Card
                title={t("conditions.title")}
                icon={<ShieldAlert size={24} />}
                accent="indigo"
              >
                <p className="card-intro">{t("conditions.intro")}</p>
                {(conditions.flagged || []).length === 0 ? (
                  <p className="card-note">{t("conditions.none")}</p>
                ) : (
                  <div className="pc-list">
                    {conditions.flagged.map((p) => (
                      <div key={p.planet} className="pc-row">
                        <div className="pc-row__planet">
                          <span className="pc-row__name">{p.planet}</span>
                          <span className="pc-row__pos">
                            {p.sign_name} · {t("conditions.house", { n: p.house })}
                          </span>
                        </div>
                        <div className="pc-row__flags">
                          {p.flags.map((f, i) => (
                            <span
                              key={i}
                              className="pc-flag"
                              style={{ background: TONE_COLOR[f.tone] || TONE_COLOR.neutral }}
                              title={f.tone}
                            >
                              {f.label}
                              {f.partner ? ` · ${f.partner} (${f.separation}°)` : ""}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* AI reading */}
                <div className="mt-lg">
                  <ErrorBanner message={pcAiError} />
                  {!pcAi && !pcAiLoading && (
                    <p className="ai-panel__hint">{t("conditions.aiHint")}</p>
                  )}
                  {pcAiLoading && <LoadingState message={t("conditions.aiLoading")} />}
                  {pcAi && !pcAiLoading && (
                    <div className="sbc-ai-markdown ai-panel__reading">
                      <ReactMarkdown>{pcAi}</ReactMarkdown>
                      {pcAiModel && (
                        <div className="ai-panel__meta">
                          {t("conditions.aiModel", { model: pcAiModel })}
                        </div>
                      )}
                    </div>
                  )}
                  {!pcAiLoading && (
                    <button className="ui-btn ui-btn--ai" onClick={handleConditionsAi}>
                      <Sparkles size={18} />
                      {pcAi ? t("conditions.aiRegenerate") : t("conditions.aiGenerate")}
                    </button>
                  )}
                </div>
                <p className="card-note">{t("conditions.disclaimer")}</p>
              </Card>
            )}

            {/* Avasthas (Baladi / Jagradadi / Deeptadi planetary states) */}
            {avasthas?.planets?.length > 0 && (
              <Card title={t("avasthas.title")} icon={<Hourglass size={24} />} accent="terracotta">
                <p className="card-intro">{t("avasthas.intro")}</p>
                <div className="table-scroll">
                  <table className="data-table av-table">
                    <thead>
                      <tr>
                        <th>{t("avasthas.planet")}</th>
                        <th>{t("avasthas.baladi")}</th>
                        <th>{t("avasthas.jagradadi")}</th>
                        <th>{t("avasthas.deeptadi")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {avasthas.planets.map((p) => (
                        <tr key={p.planet}>
                          <td className="fw-700 text-indigo">
                            {p.planet}
                            <span className="av-sub">
                              {" "}
                              {p.sign_name} · {p.dignity}
                            </span>
                          </td>
                          <td>
                            {p.baladi.state}
                            <span className="av-sub"> {p.baladi.strength}</span>
                          </td>
                          <td>
                            {p.jagradadi.state}
                            <span className="av-sub"> {p.jagradadi.meaning}</span>
                          </td>
                          <td>
                            <span
                              className="pc-flag"
                              style={{ background: TONE_COLOR[p.deeptadi.tone] || TONE_COLOR.neutral }}
                            >
                              {p.deeptadi.state}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* AI reading */}
                <div className="mt-lg">
                  <ErrorBanner message={avAiError} />
                  {!avAi && !avAiLoading && <p className="ai-panel__hint">{t("avasthas.aiHint")}</p>}
                  {avAiLoading && <LoadingState message={t("avasthas.aiLoading")} />}
                  {avAi && !avAiLoading && (
                    <div className="sbc-ai-markdown ai-panel__reading">
                      <ReactMarkdown>{avAi}</ReactMarkdown>
                      {avAiModel && (
                        <div className="ai-panel__meta">
                          {t("avasthas.aiModel", { model: avAiModel })}
                        </div>
                      )}
                    </div>
                  )}
                  {!avAiLoading && (
                    <button className="ui-btn ui-btn--ai" onClick={handleAvasthasAi}>
                      <Sparkles size={18} />
                      {avAi ? t("avasthas.aiRegenerate") : t("avasthas.aiGenerate")}
                    </button>
                  )}
                </div>
                <p className="card-note">{t("avasthas.disclaimer")}</p>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AdvancedPage;
