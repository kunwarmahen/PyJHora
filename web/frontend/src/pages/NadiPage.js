import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ScrollText, Sparkles, Compass, Users, CalendarClock } from "lucide-react";
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
import { useSettings } from "../contexts/SettingsContext";
import { intlLocale } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { useLocalizeName } from "../i18n/localizeName";

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

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
};

export const NadiPage = () => {
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  // Spouse-karaka selector: unset (null) → default to Venus on the backend.
  const [gender, setGender] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.gender != null) setGender(String(r.context.gender));
    setPendingReading({ reading: r.reading, model: r.model });
  });
  useEffect(() => {
    if (pendingReading && !loading) {
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
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

  const genderNum = gender === "" ? undefined : parseInt(gender, 10);

  const load = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    setAiError("");
    try {
      const res = await astrologyService.getNadiReading(birthDetails, {
        gender: genderNum,
        ayanamsa,
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("nadi.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, genderNum, ayanamsa, t]);

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
      const res = await astrologyService.analyzeNadiReadingAI(
        birthDetails,
        { gender: genderNum, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("nadi.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const karakas = data?.karakas || [];
  const themes = data?.themes || [];
  const triggers = data?.triggers || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<ScrollText size={24} />}
        title={t("nadi.title")}
        subtitle={t("nadi.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="nadi" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <p className="card-note">{t("nadi.intro")}</p>

        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("nadi.spouseKaraka")}</label>
            <select
              className="control-input"
              value={gender}
              onChange={(e) => setGender(e.target.value)}
            >
              <option value="">{t("nadi.genderUnset")}</option>
              <option value="0">{t("nadi.genderMale")}</option>
              <option value="1">{t("nadi.genderFemale")}</option>
            </select>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("nadi.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Chart summary pills */}
            <div className="info-pills">
              <span className="info-pill">
                <Compass size={14} />{" "}
                {t("nadi.ascendant", {
                  sign: ln(data.ascendant?.sign_name, "rasi"),
                  lord: ln(data.ascendant?.sign_lord, "graha"),
                })}
              </span>
              <span className="info-pill">
                {t("nadi.moonSign", { sign: ln(data.moon_sign, "rasi") })}
              </span>
              <span className="info-pill">
                {t("nadi.spouseKarakaIs", { planet: ln(data.spouse_karaka, "graha") })}
              </span>
            </div>

            {/* Karakas & significators */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <Compass size={18} /> {t("nadi.karakasTitle")}
              </h3>
              <p className="card-note">{t("nadi.karakasIntro")}</p>
              <div className="nadi-karaka-grid">
                {karakas.map((k) => (
                  <div key={k.planet} className="nadi-karaka">
                    <div className="nadi-karaka__head">
                      <span className="nadi-karaka__planet">{ln(k.planet, "graha")}</span>
                      <span className="nadi-karaka__sign">
                        {ln(k.sign_name, "rasi")}{" "}
                        <span className="text-secondary">({ln(k.sign_lord, "graha")})</span>
                      </span>
                    </div>
                    <div className="nadi-karaka__signifies">
                      {k.significations.slice(0, 3).join(" · ")}
                    </div>
                    <div className="nadi-karaka__meta">
                      <span>{t("nadi.star", { nak: k.nakshatra, lord: ln(k.star_lord, "graha") })}</span>
                      {k.conjunct.length > 0 && (
                        <span className="nadi-karaka__conj">
                          <Users size={12} />{" "}
                          {k.conjunct.map((c) => ln(c, "graha")).join(", ")}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Life themes */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <ScrollText size={18} /> {t("nadi.themesTitle")}
              </h3>
              <p className="card-note">{t("nadi.themesIntro")}</p>
              <ul className="nadi-theme-list">
                {themes.map((th, i) => (
                  <li key={i} className="nadi-theme">
                    <div className="nadi-theme__area">{th.area}</div>
                    <div className="nadi-theme__karakas">
                      {th.karakas.map((kk, j) => (
                        <span key={j} className="nadi-theme__karaka">
                          {ln(kk.planet, "graha")}{" "}
                          <span className="text-secondary">
                            {t("nadi.inSign", { sign: ln(kk.sign_name, "rasi") })}
                          </span>
                          {kk.conjunct.length > 0 && (
                            <span className="text-secondary">
                              {" "}
                              · {kk.conjunct.map((c) => ln(c, "graha")).join(", ")}
                            </span>
                          )}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Transit triggers */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <CalendarClock size={18} /> {t("nadi.triggersTitle")}
              </h3>
              <p className="card-note">{t("nadi.triggersIntro")}</p>
              {triggers.length === 0 ? (
                <p className="card-note">{t("nadi.noTriggers")}</p>
              ) : (
                <ul className="bhrigu-activation-list">
                  {triggers.map((a, i) => (
                    <li key={i} className="bhrigu-activation">
                      <span className="bhrigu-activation__date">{formatDate(a.date, locale)}</span>
                      <span className="bhrigu-activation__text">
                        {t("nadi.triggerRow", {
                          planet: ln(a.planet, "graha"),
                          sign: ln(a.sign_name, "rasi"),
                          karaka: a.karaka,
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("nadi.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("nadi.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("nadi.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("nadi.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("nadi.aiRegenerate") : t("nadi.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("nadi.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default NadiPage;
