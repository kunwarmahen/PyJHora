import React, { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useSettings } from "../contexts/SettingsContext";
import {
  TAB_PARAM,
  resolveActiveTab,
  shouldWriteTab,
  visibleTabs,
} from "../config/tabs";
import "../styles/Tabs.css";

/**
 * The one tab bar (§15).
 *
 * Before this, Settings, Admin and KP each had their own bar with its own CSS
 * and its own idea of what a tab looks like. Everything tabbed now goes through
 * here.
 *
 * The selected tab lives in the URL (`?tab=`), so Back/Forward work, a refresh
 * keeps your place, and a tab is linkable — which matters because AI readings
 * and digests already deep-link into pages, and content that moved behind a tab
 * needs its link to open that tab.
 *
 * Tabs flagged `advanced` are hidden in Essentials mode, except when the URL
 * names one: deep-links must never dead-end.
 */
export const useTabs = (tabs, { param = TAB_PARAM } = {}) => {
  const { settings } = useSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get(param);
  const uiMode = settings.uiMode;

  const shown = useMemo(
    () => visibleTabs(tabs, uiMode, requested),
    [tabs, uiMode, requested]
  );
  const active = useMemo(
    () => resolveActiveTab(tabs, uiMode, requested),
    [tabs, uiMode, requested]
  );

  const setActive = useCallback(
    (key) => {
      if (!shouldWriteTab(requested, key)) return;
      const next = new URLSearchParams(searchParams);
      next.set(param, key);
      // Push rather than replace: a tab change is a navigation the user can undo
      // with Back. The initial resolve never lands here, so arriving on a page
      // costs no history entry.
      setSearchParams(next);
    },
    [requested, searchParams, setSearchParams, param]
  );

  return { tabs: shown, active, setActive };
};

/**
 * The bar itself. Pair it with `useTabs`:
 *
 *   const { tabs, active, setActive } = useTabs(TABS);
 *   <Tabs tabs={tabs} active={active} onChange={setActive} />
 *   {active === "chart" && <ChartPanel />}
 *
 * `label` is already-translated text; `icon` is optional.
 */
export const Tabs = ({ tabs, active, onChange, ariaLabel }) => {
  if (!tabs || tabs.length < 2) return null; // one tab is not a choice

  return (
    <div className="ui-tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((t) => {
        const on = t.key === active;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={on}
            className={`ui-tab${on ? " ui-tab--on" : ""}`}
            onClick={() => onChange(t.key)}
          >
            {t.icon}
            <span>{t.label}</span>
            {t.count != null && <span className="ui-tab__count">{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
};

export default Tabs;
