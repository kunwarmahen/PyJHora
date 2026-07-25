import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Crosshair, Sparkles, Target, ShieldAlert, Compass } from "lucide-react";
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
import { Tabs, useTabs } from "../components/Tabs";
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

export const SensitivePointsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const ln = useLocalizeName();

  const POINT_TABS = useMemo(
    () => [
      { key: "special", label: t("sensitive.tabs.special") },
      { key: "sphuta", label: t("sensitive.tabs.sphuta") },
      { key: "sahams", label: t("sensitive.tabs.sahams") },
      { key: "argala", label: t("sensitive.tabs.argala") },
    ],
    [t]
  );
  const { tabs: visibleTabs, active: tab, setActive: setTab } = useTabs(POINT_TABS);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const varnadaMethod = settings.varnadaMethod;

  const [data, setData] = useState(null);
  const [special, setSpecial] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  // Reopen a saved reading from History (apply the saved text once load settles).
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => setPendingReading({ reading: r.reading, model: r.model }));
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

  const load = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    setAiError("");
    try {
      // The two calls are independent; a failure of the special-points table
      // must not blank out the sphutas/sahams the page has always shown.
      const [res, sp] = await Promise.allSettled([
        astrologyService.getSensitivePoints(birthDetails, ayanamsa),
        astrologyService.getSpecialPoints(birthDetails, ayanamsa, varnadaMethod),
      ]);
      if (res.status === "rejected") throw res.reason;
      setData(res.value.data);
      setSpecial(sp.status === "fulfilled" ? sp.value.data : null);
    } catch (err) {
      setError(err.response?.data?.detail || t("sensitive.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, ayanamsa, varnadaMethod, t]);

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
      const res = await astrologyService.analyzeSensitivePointsAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("sensitive.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const sphutas = data?.sphuta?.sphutas || [];
  const sahams = data?.sahams?.sahams || [];
  const argala = (data?.argala?.houses || []).filter(
    (h) => h.net !== "none" && h.net !== "balanced"
  );

  const netLabel = (net) =>
    net === "argala"
      ? t("sensitive.netArgala")
      : net === "virodhargala"
        ? t("sensitive.netVirodha")
        : t("sensitive.netBalanced");

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Crosshair size={24} />}
        title={t("sensitive.title")}
        subtitle={t("sensitive.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="sensitive_points" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        {loading && (
          <Card>
            <LoadingState message={t("sensitive.loading")} />
          </Card>
        )}
        <ErrorBanner message={error} />

        {!loading && !error && data && (
          <div className="fade-in">
            <p className="card-intro">{t("sensitive.intro")}</p>

            <Tabs
              tabs={visibleTabs}
              active={tab}
              onChange={setTab}
              ariaLabel={t("sensitive.title")}
            />

            {tab === "special" && (
              <>
                <Card
                  title={t("sensitive.specialLagnaTitle")}
                  icon={<Compass size={22} />}
                  accent="saffron"
                  count={special?.special_lagnas?.length || 0}
                >
                  <p className="card-note">{t("sensitive.specialLagnaNote")}</p>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("sensitive.colPoint")}</th>
                          <th>{t("sensitive.colMeaning")}</th>
                          <th>{t("sensitive.colSign")}</th>
                          <th>{t("sensitive.colHouse")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(special?.special_lagnas || []).map((s) => (
                          <tr key={s.name}>
                            <td className="fw-700">{s.name}</td>
                            <td className="text-secondary">{s.significance}</td>
                            <td>
                              {ln(s.sign_name, "rasi")} {s.degrees}°
                            </td>
                            <td>{s.house}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>

                <div className="mt-xl">
                  <Card
                    title={t("sensitive.upagrahaTitle")}
                    icon={<ShieldAlert size={22} />}
                    accent="indigo"
                    count={special?.upagrahas?.length || 0}
                  >
                    <p className="card-note">{t("sensitive.upagrahaNote")}</p>
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("sensitive.colPoint")}</th>
                            <th>{t("sensitive.colMeaning")}</th>
                            <th>{t("sensitive.colSign")}</th>
                            <th>{t("sensitive.colHouse")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(special?.upagrahas || []).map((u) => (
                            <tr key={u.name}>
                              <td className="fw-700">{u.name}</td>
                              <td className="text-secondary">{u.significance}</td>
                              <td>
                                {ln(u.sign_name, "rasi")} {u.degrees}°
                              </td>
                              <td>{u.house}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>

                <div className="mt-xl">
                  <Card
                    title={t("sensitive.varnadaTitle")}
                    icon={<Crosshair size={22} />}
                    accent="saffron"
                    count={special?.varnadas?.length || 0}
                  >
                    <p className="card-note">
                      {t("sensitive.varnadaNote", {
                        method: special?.varnada_method_name || "",
                      })}
                    </p>
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("sensitive.colPoint")}</th>
                            <th>{t("sensitive.colSign")}</th>
                            <th>{t("sensitive.colHouse")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(special?.varnadas || []).map((v) => (
                            <tr key={v.name}>
                              <td className="fw-700">{v.name}</td>
                              <td>
                                {ln(v.sign_name, "rasi")} {v.degrees}°
                              </td>
                              <td>{v.house}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>
              </>
            )}

            {tab === "sphuta" && (
              <>
                {/* Sphutas */}
                <Card
                  title={t("sensitive.sphutaTitle")}
                  icon={<Target size={22} />}
                  accent="saffron"
                  count={sphutas.length}
                >
                  <p className="card-note">{t("sensitive.sphutaNote")}</p>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("sensitive.colPoint")}</th>
                          <th>{t("sensitive.colMeaning")}</th>
                          <th>{t("sensitive.colSign")}</th>
                          <th>{t("sensitive.colHouse")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sphutas.map((s) => (
                          <tr key={s.name}>
                            <td className="fw-700">{s.name}</td>
                            <td className="text-secondary">{s.significance}</td>
                            <td>
                              {ln(s.sign_name, "rasi")} {s.degrees}°
                            </td>
                            <td>{s.house}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            )}

            {tab === "sahams" && (
              <>
                {/* Sahams */}
                <div className="mt-xl">
                  <Card
                    title={t("sensitive.sahamTitle")}
                    icon={<Sparkles size={22} />}
                    accent="gold"
                    count={sahams.length}
                  >
                    <p className="card-note">{t("sensitive.sahamNote")}</p>
                    <div className="table-scroll">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>{t("sensitive.colSaham")}</th>
                            <th>{t("sensitive.colMeaning")}</th>
                            <th>{t("sensitive.colSign")}</th>
                            <th>{t("sensitive.colHouse")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sahams.map((s) => (
                            <tr key={s.name}>
                              <td className="fw-700">{s.name}</td>
                              <td className="text-secondary">{s.significance}</td>
                              <td>
                                {ln(s.sign_name, "rasi")} {s.degrees}°
                              </td>
                              <td>{s.house}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                </div>
              </>
            )}

            {tab === "argala" && (
              <>
                {/* Argala */}
                <div className="mt-xl">
                  <Card
                    title={t("sensitive.argalaTitle")}
                    icon={<ShieldAlert size={22} />}
                    accent="vermillion"
                    count={argala.length}
                  >
                    <p className="card-note">{t("sensitive.argalaNote")}</p>
                    {argala.length === 0 ? (
                      <p className="text-secondary">{t("sensitive.argalaEmpty")}</p>
                    ) : (
                      <div className="table-scroll">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>{t("sensitive.colHouse")}</th>
                              <th>{t("sensitive.colSign")}</th>
                              <th>{t("sensitive.colArgala")}</th>
                              <th>{t("sensitive.colVirodha")}</th>
                              <th>{t("sensitive.colNet")}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {argala.map((h) => (
                              <tr key={h.bhava}>
                                <td className="fw-700">{h.bhava}</td>
                                <td>{ln(h.sign_name, "rasi")}</td>
                                <td>
                                  {h.argala
                                    .map((a) => `${a.planets.join(", ")} (${a.from})`)
                                    .join("; ") || "—"}
                                </td>
                                <td>
                                  {h.virodhargala
                                    .map((a) => `${a.planets.join(", ")} (${a.from})`)
                                    .join("; ") || "—"}
                                </td>
                                <td>
                                  <span className={`sp-net sp-net--${h.net}`}>
                                    {netLabel(h.net)}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              </>
            )}

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("sensitive.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("sensitive.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("sensitive.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("sensitive.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("sensitive.aiRegenerate") : t("sensitive.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("sensitive.disclaimer")}</p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SensitivePointsPage;
