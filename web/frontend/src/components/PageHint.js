import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Lightbulb, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useSettings } from "../contexts/SettingsContext";
import { firstSentence, hintIdFor, hintPath, hintsEnabled, parseSeen } from "../config/pageHints";
import "../styles/PageHint.css";

/**
 * "What am I looking at?" (§76.5) — one dismissable line on the first visit to a
 * page, taken from that page's own Help answer. Mounted once, by PageHeader, so
 * every page gets it without opting in. See config/pageHints.js.
 */
export const PageHint = () => {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { settings, updateSetting } = useSettings();

  const path = hintPath(pathname);
  const id = hintIdFor(path);
  if (!id || !hintsEnabled(settings.pageHints, user?.created_at)) return null;
  const seen = parseSeen(settings.hintsSeen);
  if (seen.has(path)) return null;
  const text = firstSentence(t(`help.a.${id}`));
  if (!text) return null;

  const dismiss = () => {
    seen.add(path);
    updateSetting("hintsSeen", [...seen].join(","));
  };

  return (
    <aside className="page-hint" aria-label={t("pageHint.label")}>
      <Lightbulb size={16} aria-hidden="true" />
      <p>
        <strong>{t("pageHint.label")}</strong> {text}{" "}
        <Link to={`/help#${id}`}>{t("pageHint.more")}</Link>
      </p>
      <button
        type="button"
        className="page-hint__close"
        onClick={dismiss}
        aria-label={t("pageHint.dismiss")}
        title={t("pageHint.dismiss")}
      >
        <X size={16} />
      </button>
    </aside>
  );
};

export default PageHint;
