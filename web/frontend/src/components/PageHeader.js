import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, HelpCircle } from "lucide-react";
import { NavDrawer } from "./NavDrawer";
import { AdvancedNotice } from "./AdvancedOnly";
import { ThemeToggle } from "./ThemeToggle";
import { helpLinkForPath } from "../config/help";
import "../styles/Shared.css";

/**
 * Shared page navbar: optional back button, an accent icon, a title + subtitle,
 * and an optional `right` slot. Replaces the inline-styled <nav> copy-pasted
 * across BirthChart / Dhasa / Transit / Compatibility / Ask.
 *
 * accent: "saffron" | "indigo" | "terracotta" | "gold"
 */
export const PageHeader = ({
  icon,
  title,
  subtitle,
  accent = "saffron",
  backTo = "/dashboard",
  right,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  return (
    <>
      {/* Bypass block (WCAG 2.4.1). The drawer behind the hamburger is ~40
          entries; without this a keyboard or screen-reader user walks all of it
          on every page. `.skip-link` is off-screen until focused. The target is
          the <main> each page wraps its content in. */}
      <a className="skip-link" href="#page-content">
        {t("common.skipToContent")}
      </a>
      <header className="navbar" role="banner">
        <div className="navbar-brand">
          {backTo && (
            <button type="button" className="page-back-btn" onClick={() => navigate(backTo)}>
              <ArrowLeft size={20} />
              <span>{t("common.back")}</span>
            </button>
          )}
          <div className="page-header-title">
            {icon && <div className={`page-header-icon page-header-icon--${accent}`}>{icon}</div>}
            <div>
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>
        </div>
        <div className="nav-right">
          {right}
          {/* Always-present way out for someone who doesn't understand the page
              they're on. Icon-only: it must never crowd the page's own actions. */}
          <button
            type="button"
            className="page-help-btn"
            onClick={() => navigate(helpLinkForPath(location.pathname))}
            title={t("nav.help")}
            aria-label={t("nav.help")}
          >
            <HelpCircle size={18} />
          </button>
          <ThemeToggle />
          <NavDrawer />
        </div>
      </header>
      {/* One mount point covers every feature page: PageHeader is on all of
          them, and the notice renders itself only on an advanced route reached
          while in Essentials mode. */}
      <AdvancedNotice />
    </>
  );
};

export default PageHeader;
