import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Sparkles, Star, ChevronDown, ChevronRight } from "lucide-react";
import Markdown from "./Markdown";
import { astrologyService } from "../services/api";
import { errorMessage, intlLocale, parseLocalDate } from "../utils/format";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingState } from "./LoadingState";
import { useLocalizeName } from "../i18n/localizeName";
import "../styles/Nakshatra.css";

/**
 * Nakshatra gochara (§75) — the star each graha is transiting, the dated window
 * it holds that star for, and how the star lands on this native.
 *
 * The verdict shown here is the backend's: tarabala from the birth star, the
 * graha's own nature, its houses and whether its dasha is running. The deity and
 * symbol are printed under a heading that says they are imagery, because the
 * tradition supplies no "graha X transiting star Y" result table and this page
 * must not look like it is quoting one.
 */

// Backend tone -> the shared tone classes in Nakshatra.css.
const TONE_CLASS = {
  very_good: "nak-tone--vgood",
  good: "nak-tone--good",
  caution: "nak-tone--caution",
  bad: "nak-tone--bad",
};

const SUPPORT_CLASS = {
  supportive: "nak-tone--vgood",
  mixed: "nak-tone--neutral",
  pressured: "nak-tone--bad",
};

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

export const NakshatraGochara = ({
  data,
  birthDetails,
  profile,
  profileId,
  transitDate,
  transitTime,
  transitTz,
  ayanamsa,
}) => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const locale = intlLocale(i18n.language);
  const [open, setOpen] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState("");
  const [model, setModel] = useState("");

  const fmt = (iso) => {
    if (!iso) return null;
    try {
      return parseLocalDate(iso).toLocaleDateString(locale, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch (e) {
      return iso;
    }
  };

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.analyzeNakshatraGocharaAI(
        birthDetails,
        {
          personName: profile?.birth_details?.name || profile?.profile_name,
          profileId,
          currentDate: transitDate,
          currentTime: transitTime,
          currentTz: transitTz,
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAnalysis(res.data.ai_analysis || "");
      setModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setError(errorMessage(err, t("nakGochara.error")));
    } finally {
      setLoading(false);
    }
  };

  if (!data) return null;
  const grahas = data.grahas || [];

  // The window line: a star with both ends is a period, one end is open-ended,
  // and the Moon has neither because a daily star change is not a window.
  const windowText = (g) => {
    const w = g.window;
    if (!w) return t("nakGochara.noWindow");
    if (w.entered && w.leaves) return `${fmt(w.entered)} → ${fmt(w.leaves)}`;
    if (w.leaves) return t("nakGochara.until", { date: fmt(w.leaves) });
    if (w.entered) return t("nakGochara.since", { date: fmt(w.entered) });
    return "—";
  };

  return (
    <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
      <h3 className="ui-card-header ui-card-header--sm">
        <Star size={18} />
        {t("nakGochara.title")}
      </h3>
      <p className="nakg-intro">
        {t("nakGochara.intro", {
          star: ln(data.janma?.nakshatra, "nakshatra"),
        })}
      </p>

      <div className="nakg-list">
        {grahas.map((g) => {
          const isOpen = open === g.planet;
          return (
            <div key={g.planet} className="nakg-row">
              <button
                type="button"
                className="nakg-row__head"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : g.planet)}
              >
                {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                <span className="nakg-row__planet">
                  {ln(g.planet, "graha")}
                  {g.retrograde && (
                    <span className="retro-badge" title={t("transit.retrograde")}>
                      ℞
                    </span>
                  )}
                </span>
                <span className="nakg-row__star">{ln(g.nakshatra, "nakshatra")}</span>
                <span className={`nakg-chip ${TONE_CLASS[g.tarabala?.tone] || ""}`}>
                  {g.tarabala?.name}
                </span>
                <span className="nakg-row__window">{windowText(g)}</span>
              </button>

              {isOpen && (
                <div className="nakg-row__body">
                  <dl className="nakg-facts">
                    <dt>{t("nakGochara.tara")}</dt>
                    <dd>
                      <span className={`nakg-chip ${TONE_CLASS[g.tarabala?.tone] || ""}`}>
                        {g.tarabala?.name}
                      </span>{" "}
                      {g.tarabala?.meaning}
                    </dd>

                    <dt>{t("nakGochara.verdict")}</dt>
                    <dd>
                      <span className={`nakg-chip ${SUPPORT_CLASS[g.support] || ""}`}>
                        {t(`nakGochara.support.${g.support}`)}
                      </span>{" "}
                      {(g.support_reasons || []).join("; ")}
                    </dd>

                    <dt>{t("nakGochara.placement")}</dt>
                    <dd>
                      {t("nakGochara.placementText", {
                        sign: ln(g.sign_name, "rasi"),
                        lagna: g.house_from_lagna,
                        moon: g.house_from_moon,
                        lord: ln(g.nakshatra_lord, "graha"),
                      })}
                      {g.owns_houses?.length > 0 &&
                        ` · ${t("nakGochara.owns", { houses: g.owns_houses.join(", ") })}`}
                    </dd>

                    {g.emphasis?.length > 0 && (
                      <>
                        <dt>{t("nakGochara.live")}</dt>
                        <dd>{g.emphasis.join("; ")}</dd>
                      </>
                    )}

                    {g.upcoming?.length > 0 && (
                      <>
                        <dt>{t("nakGochara.next")}</dt>
                        <dd>
                          <ul className="nakg-next">
                            {g.upcoming.map((u, i) => (
                              <li key={`${u.nakshatra}-${u.enters}-${i}`}>
                                <strong>{ln(u.nakshatra, "nakshatra")}</strong> {fmt(u.enters)}
                                {u.retrograde_reentry && ` (${t("nakGochara.backInto")})`}
                                <span className="text-muted"> · {u.tarabala}</span>
                              </li>
                            ))}
                          </ul>
                        </dd>
                      </>
                    )}

                    {/* Deliberately last and deliberately labelled: nothing above
                        was computed from it. */}
                    <dt>{t("nakGochara.imagery")}</dt>
                    <dd className="nakg-imagery">
                      {t("nakGochara.imageryText", {
                        deity: g.symbolism?.deity,
                        symbol: g.symbolism?.symbol,
                        theme: g.symbolism?.theme,
                      })}
                    </dd>
                  </dl>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="nakg-note">{t("nakGochara.moonNote")}</p>
      {/* The sign-level sibling of this card. Different reference frame, different
        question — see improvements-2026-07.md §5.6. */}
      <p className="nakg-note">
        {t("nakGochara.vsGochara")}{" "}
        <button type="button" className="ui-link" onClick={() => navigate("/gochara")}>
          {t("nakGochara.vsGocharaLink")}
        </button>
      </p>

      <div className="ai-panel">
        <h4 className="ai-panel__title">
          <Sparkles size={20} style={{ color: "var(--saffron)" }} />
          {t("nakGochara.aiTitle")}
        </h4>
        <ErrorBanner message={error} />
        {!analysis && !loading && <p className="ai-panel__hint">{t("nakGochara.aiHint")}</p>}
        {loading && <LoadingState message={t("nakGochara.aiLoading")} />}
        {analysis && !loading && (
          <div className="sbc-ai-markdown ai-panel__reading">
            <Markdown>{analysis}</Markdown>
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
    </div>
  );
};
