import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass, Sparkles, Star, HelpCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

// Browser geolocation → {latitude, longitude, timezone} (best-effort, for horary).
const currentLocation = () =>
  new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          timezone: -new Date().getTimezoneOffset() / 60,
        }),
      () => resolve(null),
      { timeout: 8000 }
    );
  });

export const KPPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [tab, setTab] = useState("natal");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  // Horary state
  const [horNumber, setHorNumber] = useState("");
  const [horQuestion, setHorQuestion] = useState("");
  const [horData, setHorData] = useState(null);
  const [horLoading, setHorLoading] = useState(false);
  const [horError, setHorError] = useState("");
  const [horReading, setHorReading] = useState("");
  const [horModel, setHorModel] = useState("");

  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) =>
    setPendingReading({ reading: r.reading, model: r.model, source: r.source, context: r.context })
  );
  useEffect(() => {
    if (pendingReading && !loading) {
      if (pendingReading.source === "kp_horary") {
        setTab("horary");
        setHorReading(pendingReading.reading);
        setHorModel(pendingReading.model);
        const c = pendingReading.context || {};
        if (c.number) {
          setHorNumber(String(c.number));
          setHorQuestion(c.question || "");
        }
      } else {
        setTab("natal");
        setAiAnalysis(pendingReading.reading);
        setAiModel(pendingReading.model);
      }
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

  const birthDetails = useMemo(
    () =>
      selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : null,
    [selectedProfile]
  );

  const load = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    try {
      const res = await astrologyService.getKpDetails(birthDetails);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("kp.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeKpAI(
        birthDetails,
        { personName: birthDetails.name, profileId: selectedProfile?._id },
        readModelConfig()
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("kp.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  const castHorary = async () => {
    const n = parseInt(horNumber, 10);
    if (!n || n < 1 || n > 249) {
      setHorError(t("kp.horary.numError"));
      return;
    }
    setHorLoading(true);
    setHorError("");
    setHorReading("");
    try {
      const loc = (await currentLocation()) || {
        latitude: birthDetails?.latitude,
        longitude: birthDetails?.longitude,
        timezone: birthDetails?.timezone,
      };
      const res = await astrologyService.getKpHorary({ number: n, ...loc });
      setHorData(res.data);
    } catch (err) {
      setHorError(err.response?.data?.detail || t("kp.horary.castError"));
    } finally {
      setHorLoading(false);
    }
  };

  const horaryAi = async () => {
    const n = parseInt(horNumber, 10);
    if (!n) return;
    setHorLoading(true);
    setHorError("");
    try {
      const loc = (await currentLocation()) || {
        latitude: birthDetails?.latitude,
        longitude: birthDetails?.longitude,
        timezone: birthDetails?.timezone,
      };
      const res = await astrologyService.analyzeKpHoraryAI(
        { number: n, question: horQuestion, ...loc },
        readModelConfig()
      );
      setHorReading(res.data.reading || "");
      setHorModel(res.data.model || res.data.provider || "");
      if (res.data.chart) setHorData(res.data.chart);
    } catch (err) {
      setHorError(err.response?.data?.detail || t("kp.aiError"));
    } finally {
      setHorLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const planets = data?.planets || [];
  const cusps = data?.cusps || [];
  const houseSig = data?.house_significators || {};
  const rp = data?.ruling_planets || {};

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Compass size={24} />}
        title={t("kp.title")}
        subtitle={t("kp.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="kp" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <div className="chart-toggle" style={{ marginBottom: "var(--space-lg)" }}>
          <button className={`chart-toggle__btn ${tab === "natal" ? "is-active" : ""}`} onClick={() => setTab("natal")}>
            <Star size={16} /> {t("kp.tabs.natal")}
          </button>
          <button className={`chart-toggle__btn ${tab === "horary" ? "is-active" : ""}`} onClick={() => setTab("horary")}>
            <HelpCircle size={16} /> {t("kp.tabs.horary")}
          </button>
        </div>

        {tab === "natal" && (
          <>
            <p className="card-note">{t("kp.ayanamsaNote")}</p>
            <ErrorBanner message={error} />
            {loading ? (
              <Card>
                <LoadingState message={t("kp.loading")} />
              </Card>
            ) : data ? (
              <div className="fade-in">
                {/* Planet sub-lords */}
                <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">{t("kp.subLordsHeader")}</h3>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("kp.body")}</th>
                          <th>{t("kp.sign")}</th>
                          <th>{t("kp.house")}</th>
                          <th>{t("kp.signLord")}</th>
                          <th>{t("kp.starLord")}</th>
                          <th>{t("kp.subLord")}</th>
                          <th>{t("kp.subSubLord")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {planets.map((p) => (
                          <tr key={p.body}>
                            <td><strong>{p.body}</strong></td>
                            <td>{p.sign_name} {p.degrees}°</td>
                            <td>{p.house}</td>
                            <td>{p.sign_lord}</td>
                            <td>{p.star_lord}</td>
                            <td><strong>{p.sub_lord}</strong></td>
                            <td className="text-secondary">{p.sub_sub_lord}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Cuspal sub-lords */}
                <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
                  <h3 className="ui-card-header ui-card-header--sm">{t("kp.cuspsHeader")}</h3>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("kp.cusp")}</th>
                          <th>{t("kp.sign")}</th>
                          <th>{t("kp.signLord")}</th>
                          <th>{t("kp.starLord")}</th>
                          <th>{t("kp.subLord")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cusps.map((c) => (
                          <tr key={c.house}>
                            <td><strong>{c.house}</strong></td>
                            <td>{c.sign_name} {c.degrees}°</td>
                            <td>{c.sign_lord}</td>
                            <td>{c.star_lord}</td>
                            <td><strong>{c.sub_lord}</strong></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* House significators (4-fold) */}
                <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
                  <h3 className="ui-card-header ui-card-header--sm">{t("kp.sigHeader")}</h3>
                  <p className="card-note">{t("kp.sigNote")}</p>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("kp.house")}</th>
                          <th>A</th>
                          <th>B</th>
                          <th>C</th>
                          <th>D</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Array.from({ length: 12 }, (_, i) => i + 1).map((h) => {
                          const s = houseSig[h] || {};
                          return (
                            <tr key={h}>
                              <td><strong>{h}</strong></td>
                              <td>{(s.A || []).join(", ") || "—"}</td>
                              <td>{(s.B || []).join(", ") || "—"}</td>
                              <td>{(s.C || []).join(", ") || "—"}</td>
                              <td>{(s.D || []).join(", ") || "—"}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Ruling planets */}
                <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
                  <h3 className="ui-card-header ui-card-header--sm">{t("kp.rpHeader")}</h3>
                  <div className="info-pills">
                    {(rp.planets || []).map((p) => (
                      <span key={p} className="info-pill">{p}</span>
                    ))}
                  </div>
                  <p className="card-note">
                    {t("kp.rpAsOf", { time: data.ruling_time })} · {t("kp.rpDayLord")}: {rp.day_lord}
                  </p>
                </div>

                {/* AI reading */}
                <div className="mt-xl">
                  <Card title={t("kp.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                    <ErrorBanner message={aiError} />
                    {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("kp.aiHint")}</p>}
                    {aiLoading && <LoadingState message={t("kp.aiLoading")} />}
                    {aiAnalysis && !aiLoading && (
                      <div className="sbc-ai-markdown ai-panel__reading">
                        <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                        {aiModel && <div className="ai-panel__meta">{t("kp.aiModel", { model: aiModel })}</div>}
                      </div>
                    )}
                    {!aiLoading && (
                      <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                        <Sparkles size={18} />
                        {aiAnalysis ? t("kp.aiRegenerate") : t("kp.aiGenerate")}
                      </button>
                    )}
                  </Card>
                </div>
              </div>
            ) : null}
          </>
        )}

        {tab === "horary" && (
          <div className="fade-in">
            <div className="ui-card ui-card--accent ui-card--pad-lg">
              <h3 className="ui-card-header ui-card-header--sm">{t("kp.horary.title")}</h3>
              <p className="card-note">{t("kp.horary.intro")}</p>
              <div className="page-controls">
                <div className="controls-group">
                  <label className="control-label">{t("kp.horary.number")}</label>
                  <input
                    className="control-input"
                    type="number"
                    min="1"
                    max="249"
                    value={horNumber}
                    onChange={(e) => setHorNumber(e.target.value)}
                    placeholder="1–249"
                  />
                </div>
                <div className="controls-group" style={{ flex: 1 }}>
                  <label className="control-label">{t("kp.horary.question")}</label>
                  <input
                    className="control-input"
                    type="text"
                    value={horQuestion}
                    onChange={(e) => setHorQuestion(e.target.value)}
                    placeholder={t("kp.horary.questionPlaceholder")}
                  />
                </div>
              </div>
              <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap", marginTop: "var(--space-md)" }}>
                <button className="ui-btn ui-btn--primary" onClick={castHorary} disabled={horLoading}>
                  {horLoading ? t("kp.horary.casting") : t("kp.horary.cast")}
                </button>
                <button className="ui-btn ui-btn--ai" onClick={horaryAi} disabled={horLoading || !horNumber}>
                  <Sparkles size={18} /> {t("kp.horary.judge")}
                </button>
              </div>
              <ErrorBanner message={horError} />
            </div>

            {horData && (
              <div className="ui-card ui-card--accent-indigo ui-card--pad-lg mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  {t("kp.horary.chartHeader", { number: horData.number })}
                </h3>
                <div className="score-box">
                  <div className="score-box__label">{t("kp.horary.ascendant")}</div>
                  <div className="score-box__status">
                    {horData.ascendant?.sign_name} {horData.ascendant?.degrees}° ·{" "}
                    {t("kp.subLord")}: <strong>{horData.ascendant?.sub_lord}</strong>
                  </div>
                </div>
                {horData.chart && (
                  <div className="chart-grid" style={{ marginTop: "var(--space-lg)" }}>
                    <Card title={t("kp.horary.moment")} accent="indigo">
                      <Kundali planets={horData.chart.planets} lagna={horData.chart.lagna} title={t("kp.horary.moment")} />
                    </Card>
                  </div>
                )}
                <div className="info-pills" style={{ marginTop: "var(--space-md)" }}>
                  <span className="text-secondary">{t("kp.rpHeader")}:</span>
                  {(horData.ruling_planets?.planets || []).map((p) => (
                    <span key={p} className="info-pill">{p}</span>
                  ))}
                </div>
              </div>
            )}

            {horReading && (
              <div className="mt-xl">
                <Card title={t("kp.horary.judgement")} icon={<Sparkles size={24} />} accent="indigo">
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{horReading}</ReactMarkdown>
                    {horModel && <div className="ai-panel__meta">{t("kp.aiModel", { model: horModel })}</div>}
                  </div>
                </Card>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default KPPage;
