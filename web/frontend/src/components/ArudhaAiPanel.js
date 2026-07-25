import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Sparkles } from "lucide-react";
import { astrologyService } from "../services/api";
import { errorMessage } from "../utils/format";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingState } from "./LoadingState";

// On-demand AI reading of the bhava arudhas (the *projected* chart: how each area
// of life appears, as against how it is). Which arudhas get read is the user's
// choice — AL/UL/A10/A11 are pre-ticked because they carry the most distinct
// classical meaning, and reading all twelve turns a reading into a list.
const DEFAULT_SELECTED = ["AL", "UL", "A10", "A11"];

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

export const ArudhaAiPanel = ({ arudhas, birthDetails, profile, ayanamsa, restored }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [model, setModel] = useState("");
  const [selected, setSelected] = useState(DEFAULT_SELECTED);

  // Reopening a saved reading from History: show the snapshot verbatim and put
  // the chips back the way they were when it was generated, so the controls match
  // the text rather than silently showing the defaults.
  useEffect(() => {
    if (!restored) return;
    setAnalysis(restored.reading || "");
    setModel(restored.model || "");
    if (Array.isArray(restored.selected) && restored.selected.length) {
      setSelected(restored.selected);
    }
  }, [restored]);

  if (!arudhas || arudhas.length === 0) return null;

  const toggle = (short) =>
    setSelected((prev) =>
      prev.includes(short) ? prev.filter((s) => s !== short) : [...prev, short]
    );

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.analyzeArudhas(
        birthDetails,
        {
          profileId: profile?._id,
          personName: profile?.birth_details?.name || profile?.profile_name,
          // Send in chart order so the reading follows AL → A2 … → UL, not click order.
          selected: arudhas.map((a) => a.short).filter((s) => selected.includes(s)),
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAnalysis(res.data.ai_analysis || "");
      setModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setError(errorMessage(err, t("arudhaAi.error")));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-panel">
      <h4 className="ai-panel__title">
        <Sparkles size={20} style={{ color: "var(--saffron)" }} />
        {t("arudhaAi.title")}
      </h4>

      <ErrorBanner message={error} />

      <p className="ai-panel__hint">{t("arudhaAi.hint")}</p>

      <div className="arudha-picker" role="group" aria-label={t("arudhaAi.pickLabel")}>
        {arudhas.map((a) => (
          <button
            key={a.short}
            type="button"
            className={`arudha-chip${selected.includes(a.short) ? " is-active" : ""}`}
            aria-pressed={selected.includes(a.short)}
            onClick={() => toggle(a.short)}
          >
            <span className="arudha-chip__code">{a.short}</span>
            <span className="arudha-chip__sign">{a.sign_name}</span>
          </button>
        ))}
      </div>

      {loading && <LoadingState message={t("arudhaAi.loading")} />}

      {analysis && !loading && (
        <div className="sbc-ai-markdown ai-panel__reading">
          <ReactMarkdown>{analysis}</ReactMarkdown>
          {model && <div className="ai-panel__meta">{t("arudhaAi.model", { model })}</div>}
        </div>
      )}

      {!loading && (
        <button className="ui-btn ui-btn--ai" onClick={run} disabled={selected.length === 0}>
          <Sparkles size={18} />
          {analysis ? t("arudhaAi.regenerate") : t("arudhaAi.generate")}
        </button>
      )}
    </div>
  );
};
