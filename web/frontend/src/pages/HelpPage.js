import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDown, HelpCircle, Search, Sparkles, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { filterHelp } from "../config/help";
import { GLOSSARY } from "../constants/glossary";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Help.css";

/**
 * Help & FAQ (§14) — written for someone who has never read a chart.
 *
 * Structure comes from `config/help.js`, words from the `help.*` i18n block, so
 * adding a question is one id plus two strings.
 *
 * Answers are collapsed by default: the value of this page is being able to
 * scan every question at once and open only the one you came for. A `#id` in
 * the URL opens and scrolls to that answer, which is what lets other pages link
 * to a specific explanation.
 */
export const HelpPage = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(() => new Set());

  // Searching on the rendered text, not our ids, so results match what's read.
  const searchText = useMemo(() => (id) => `${t(`help.q.${id}`)} ${t(`help.a.${id}`)}`, [t]);
  const sections = useMemo(() => filterHelp(query, searchText), [query, searchText]);

  // Deep link: /help#aiModes opens that answer and scrolls to it.
  useEffect(() => {
    const id = location.hash.replace("#", "");
    if (!id) return;
    setOpen((prev) => new Set(prev).add(id));
    // After the answer has been rendered open, not before.
    const timer = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 60);
    return () => clearTimeout(timer);
  }, [location.hash]);

  const toggle = (id) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const allIds = sections.flatMap((s) => s.items.map((i) => i.id));
  const allOpen = allIds.length > 0 && allIds.every((id) => open.has(id));

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<HelpCircle size={24} />}
        title={t("help.title")}
        subtitle={t("help.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <p className="help-intro">{t("help.intro")}</p>

        <div className="help-toolbar">
          <div className="help-search">
            <Search size={16} className="help-search__icon" />
            <input
              className="control-input help-search__input"
              type="search"
              value={query}
              placeholder={t("help.search")}
              onChange={(e) => setQuery(e.target.value)}
              aria-label={t("help.search")}
            />
            {query && (
              <button
                type="button"
                className="help-search__clear"
                onClick={() => setQuery("")}
                aria-label={t("help.clearSearch")}
              >
                <X size={14} />
              </button>
            )}
          </div>
          <button
            type="button"
            className="ui-btn ui-btn--ghost help-expand"
            onClick={() => setOpen(allOpen ? new Set() : new Set(allIds))}
          >
            {allOpen ? t("help.collapseAll") : t("help.expandAll")}
          </button>
        </div>

        {sections.length === 0 && <p className="help-empty">{t("help.noResults", { query })}</p>}

        {sections.map((section) => (
          <section key={section.id} className="help-section" id={`section-${section.id}`}>
            <h2 className="help-section__title">{t(`help.sections.${section.id}.title`)}</h2>
            <p className="help-section__blurb">{t(`help.sections.${section.id}.blurb`)}</p>

            <div className="help-list">
              {section.items.map((item) => {
                const isOpen = open.has(item.id);
                return (
                  <div
                    key={item.id}
                    id={item.id}
                    className={`help-item${isOpen ? " is-open" : ""}`}
                  >
                    <button
                      type="button"
                      className="help-item__q"
                      aria-expanded={isOpen}
                      onClick={() => toggle(item.id)}
                    >
                      <ChevronDown size={16} className="help-item__chevron" />
                      <span>{t(`help.q.${item.id}`)}</span>
                    </button>
                    {isOpen && (
                      <div className="help-item__a">
                        <p>{t(`help.a.${item.id}`)}</p>
                        {item.to && (
                          <Link to={item.to} className="help-item__link">
                            {t("help.openLink")} →
                          </Link>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}

        {/* Glossary — rendered from the same table the hover definitions use, so
            the two can never drift apart. */}
        {!query && (
          <section className="help-section" id="section-glossary">
            <h2 className="help-section__title">{t("help.glossary.title")}</h2>
            <p className="help-section__blurb">{t("help.glossary.blurb")}</p>
            <dl className="help-glossary">
              {Object.entries(GLOSSARY).map(([term, def]) => (
                <div className="help-glossary__row" key={term}>
                  <dt>{term}</dt>
                  <dd>{def}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        <div className="help-stuck">
          <Sparkles size={18} className="help-stuck__icon" />
          <div>
            <strong>{t("help.stillStuck.title")}</strong>
            <p>{t("help.stillStuck.body")}</p>
          </div>
          <Link to="/ask-astrologer" className="ui-btn ui-btn--ai help-stuck__cta">
            {t("help.stillStuck.cta")}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default HelpPage;
