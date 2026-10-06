import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useSettings } from "../contexts/SettingsContext";
import { hubForPath, visibleHubMembers } from "../config/features";
import "../styles/HubNav.css";

/**
 * The section strip under a hub member's header (§79).
 *
 * Related pages — the five period charts, the four transit views — used to be
 * five drawer rows you had to know existed. A hub gives them one entry and this
 * strip, so arriving on any one of them shows the others next to it.
 *
 * Route links, deliberately not a tablist: each member is its own page with its
 * own URL (and often its own `?tab=` bar inside), so this is navigation and
 * says so with `aria-current="page"`. Renders nothing off a hub, and nothing when
 * Essentials leaves fewer than two members to choose between.
 */
export const HubNav = () => {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const { settings } = useSettings();
  const hub = hubForPath(pathname);
  if (!hub) return null;
  const members = visibleHubMembers(hub.key, settings.uiMode, pathname);
  if (members.length < 2) return null;

  const title = t(`nav.hubs.${hub.key}`);
  return (
    <nav className="hub-nav" aria-label={title}>
      <span className="hub-nav__title">
        <hub.Icon size={16} aria-hidden="true" />
        {title}
      </span>
      <div className="hub-nav__links">
        {members.map((m) => {
          const here = m.path === pathname;
          return (
            <Link
              key={m.path}
              to={m.path}
              aria-current={here ? "page" : undefined}
              className={`hub-nav__link${here ? " hub-nav__link--on" : ""}`}
            >
              {t(`nav.${m.key}`)}
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default HubNav;
