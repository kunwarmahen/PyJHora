import React from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { NavDrawer } from "./NavDrawer";
import { AdvancedNotice } from "./AdvancedOnly";
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
  const { t } = useTranslation();
  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">
          {backTo && (
            <button className="page-back-btn" onClick={() => navigate(backTo)}>
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
          <NavDrawer />
        </div>
      </nav>
      {/* One mount point covers every feature page: PageHeader is on all of
          them, and the notice renders itself only on an advanced route reached
          while in Essentials mode. */}
      <AdvancedNotice />
    </>
  );
};

export default PageHeader;
