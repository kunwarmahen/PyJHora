import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Moon, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { astrologyService } from "../services/api";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingState } from "./LoadingState";

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

/**
 * Tithi Pravesha — the annual *lunar*-return chart.
 *
 * Cast for the moment the native's natal tithi AND lunar month recur (~354 days),
 * this is the lunar counterpart of the solar-return Varshaphal. Classically the
 * two are read **together**, so this sits as its own section on the Varshaphal
 * page rather than replacing the solar annual chart.
 *
 * Self-contained: fetches on expand, has its own AI reading, and defaults to open
 * when the user's global pravesha basis is "lunar".
 */
export const TithiPraveshaCard = ({ birthDetails, year, ayanamsa, basis = "solar", profileId }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(basis === "lunar");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tp, setTp] = useState(null);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  const load = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    try {
      const res = await astrologyService.getTithiPravesha(birthDetails, { year, ayanamsa });
      setTp(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("tithiPravesha.error"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, year, ayanamsa, t]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeTithiPraveshaAI(
        birthDetails,
        { year, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("tithiPravesha.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  const w = tp?.window;

  return (
    <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
      <h3
        className="ui-card-header ui-card-header--sm"
        style={{ cursor: "pointer", justifyContent: "space-between" }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Moon size={18} /> {t("tithiPravesha.title")}
        </span>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </h3>
      <p className="card-note">{t("tithiPravesha.intro")}</p>

      {open && (
        <>
          <ErrorBanner message={error} />
          {loading ? (
            <LoadingState message={t("tithiPravesha.loading")} />
          ) : tp ? (
            <div className="fade-in">
              <div className="detail-list digest-details">
                <div>
                  <span className="kv-label">{t("tithiPravesha.window")}</span>
                  <span className="kv-value">
                    {w?.start} → {w?.end} ({w?.span_days}d)
                  </span>
                </div>
                <div>
                  <span className="kv-label">{t("tithiPravesha.entryTithi")}</span>
                  <span className="kv-value">{tp.label}</span>
                </div>
                <div>
                  <span className="kv-label">{t("tithiPravesha.lagna")}</span>
                  <span className="kv-value">
                    {tp.lagna?.sign_name} {tp.lagna?.degrees}°
                  </span>
                </div>
                <div>
                  <span className="kv-label">{t("tithiPravesha.muntha")}</span>
                  <span className="kv-value">
                    {tp.muntha?.sign_name} · {t("tithiPravesha.house", { n: tp.muntha?.house })}
                  </span>
                </div>
                {tp.year_lord && (
                  <div>
                    <span className="kv-label">{t("tithiPravesha.yearLord")}</span>
                    <span className="kv-value">{tp.year_lord.planet}</span>
                  </div>
                )}
              </div>

              {tp.planets && (
                <table className="data-table mt-md">
                  <thead>
                    <tr>
                      <th>{t("tithiPravesha.planet")}</th>
                      <th>{t("tithiPravesha.sign")}</th>
                      <th>{t("tithiPravesha.degrees")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(tp.planets).map(([p, v]) => (
                      <tr key={p}>
                        <td>{p}</td>
                        <td>{v.sign_name}</td>
                        <td>{v.degrees}°</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tp.tajaka_yogas?.length > 0 && (
                <>
                  <p className="kv-label mt-md">{t("tithiPravesha.tajakaYogas")}</p>
                  <ul className="digest-highlights">
                    {tp.tajaka_yogas.map((y, i) => (
                      <li key={i} className="digest-hl">
                        <strong>{y.name}</strong>
                        {y.pair ? ` (${y.pair.join(" / ")})` : ""}
                        {y.description ? ` — ${y.description}` : ""}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {/* AI reading */}
              <div className="mt-xl">
                <ErrorBanner message={aiError} />
                {aiLoading && <LoadingState message={t("tithiPravesha.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && <div className="ai-panel__meta">{t("tithiPravesha.aiModel", { model: aiModel })}</div>}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("tithiPravesha.aiRegenerate") : t("tithiPravesha.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("tithiPravesha.disclaimer")}</p>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
};

export default TithiPraveshaCard;
