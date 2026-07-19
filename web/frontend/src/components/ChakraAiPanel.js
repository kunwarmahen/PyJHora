import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Sparkles } from "lucide-react";
import { astrologyService } from "../services/api";
import { errorMessage } from "../utils/format";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingState } from "./LoadingState";

// Shared on-demand AI reading panel for the Kota / Tripataki chakras (§2.7).
// Kept in one place so both chakras behave identically and neither duplicates
// the model-config + request plumbing. Uses the model picked in Settings → AI;
// the server resolves the actual API key, so no key handling happens here.
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

export const ChakraAiPanel = ({
  chakra, // "kota" | "tripataki" -> /api/astrology/{chakra}-chakra-analysis
  birthDetails,
  profile,
  transitDate,
  transitTime,
  transitTz,
  basis,
  year,
  ayanamsa,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [model, setModel] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.analyzeChakraAI(
        chakra,
        birthDetails,
        {
          personName: profile?.birth_details?.name || profile?.profile_name,
          currentDate: transitDate,
          currentTime: transitTime,
          currentTz: transitTz,
          basis,
          year,
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAnalysis(res.data.ai_analysis || "");
      setModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setError(errorMessage(err, t("chakraAi.error")));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-panel">
      <h4 className="ai-panel__title">
        <Sparkles size={20} style={{ color: "var(--saffron)" }} />
        {t("chakraAi.title")}
      </h4>

      <ErrorBanner message={error} />

      {!analysis && !loading && <p className="ai-panel__hint">{t(`chakraAi.hint.${chakra}`)}</p>}
      {loading && <LoadingState message={t("chakraAi.loading")} />}

      {analysis && !loading && (
        <div className="sbc-ai-markdown ai-panel__reading">
          <ReactMarkdown>{analysis}</ReactMarkdown>
          {model && <div className="ai-panel__meta">{t("chakraAi.model", { model })}</div>}
        </div>
      )}

      {!loading && (
        <button className="ui-btn ui-btn--ai" onClick={run}>
          <Sparkles size={18} />
          {analysis ? t("chakraAi.regenerate") : t("chakraAi.generate")}
        </button>
      )}
    </div>
  );
};
