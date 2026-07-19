import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Menu, X, Sparkles, LogOut, ShieldAlert, HelpCircle } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { visibleFeatures } from "../config/features";
import { UiModeToggle } from "./UiModeToggle";
import { BrandLogo } from "./BrandLogo";
import { SITE_TITLE } from "../config/branding";
import "../styles/NavDrawer.css";

/** Hamburger button + slide-in feature drawer. Shown on every screen size so
 * you can jump between features from any page without returning to the
 * dashboard. Mounted in PageHeader (all feature pages) and the Dashboard nav. */
export const NavDrawer = () => {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { clearProfile } = useProfile();
  const { settings } = useSettings();
  const links = visibleFeatures(settings.uiMode);

  const go = (to) => {
    setOpen(false);
    navigate(to);
  };

  const handleLogout = async () => {
    setOpen(false);
    await logout();
    clearProfile();
    navigate("/login");
  };

  const handleChangeChart = () => {
    setOpen(false);
    clearProfile();
    navigate("/profile-selection");
  };

  return (
    <>
      <button
        className="nav-drawer-toggle"
        aria-label={t("nav.openMenu")}
        onClick={() => setOpen(true)}
      >
        <Menu size={22} />
      </button>

      {open && <div className="nav-drawer-overlay" onClick={() => setOpen(false)} />}

      <aside className={`nav-drawer ${open ? "open" : ""}`} aria-hidden={!open}>
        <div className="nav-drawer-head">
          <div className="nav-drawer-brand">
            <BrandLogo size={26} />
            <span>{SITE_TITLE}</span>
          </div>
          <button
            className="nav-drawer-close"
            aria-label={t("nav.closeMenu")}
            onClick={() => setOpen(false)}
          >
            <X size={22} />
          </button>
        </div>

        <UiModeToggle />

        <nav className="nav-drawer-links">
          {links.map(({ key, path, Icon }) => (
            <button
              key={path}
              className={`nav-drawer-link ${location.pathname === path ? "active" : ""}`}
              onClick={() => go(path)}
            >
              <Icon size={20} />
              <span>{t(`nav.${key}`)}</span>
            </button>
          ))}
        </nav>

        <div className="nav-drawer-footer">
          {user && (
            <div className="nav-drawer-account">
              <span className="nav-drawer-account-name">{user.name || user.username}</span>
              {user.name && user.email && (
                <span className="nav-drawer-account-sub">{user.email}</span>
              )}
            </div>
          )}
          <button className="nav-drawer-link" onClick={handleChangeChart}>
            <Sparkles size={20} />
            <span>{t("common.changeChart")}</span>
          </button>
          {/* Help sits in the footer next to the other always-available actions
              rather than in the feature list — it isn't a feature, it's the way
              out when a feature doesn't make sense. */}
          <button
            className={`nav-drawer-link ${location.pathname === "/help" ? "active" : ""}`}
            onClick={() => go("/help")}
          >
            <HelpCircle size={20} />
            <span>{t("nav.help")}</span>
          </button>
          {/* Admin console (§44): only shown to the deployer's allowlisted
              accounts. The route + every API call are enforced server-side. */}
          {user?.is_admin && (
            <button
              className={`nav-drawer-link ${location.pathname === "/admin" ? "active" : ""}`}
              onClick={() => go("/admin")}
            >
              <ShieldAlert size={20} />
              <span>Admin console</span>
            </button>
          )}
          <button className="nav-drawer-link logout" onClick={handleLogout}>
            <LogOut size={20} />
            <span>{t("common.logout")}</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default NavDrawer;
