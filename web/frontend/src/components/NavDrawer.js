import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Menu, X, Sparkles, LogOut, ShieldAlert, HelpCircle } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { visibleFeatures, groupedFeatures } from "../config/features";
import { UiModeToggle } from "./UiModeToggle";
import { BrandLogo } from "./BrandLogo";
import { SITE_TITLE } from "../config/branding";
import "../styles/NavDrawer.css";
import { returnHere } from "../utils/returnTo";

/** Hamburger button + slide-in feature drawer. Shown on every screen size so
 * you can jump between features from any page without returning to the
 * dashboard. Mounted in PageHeader (all feature pages) and the Dashboard nav. */
export const NavDrawer = () => {
  const [open, setOpen] = useState(false);
  const drawerRef = useRef(null);
  const toggleRef = useRef(null);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { clearProfile } = useProfile();
  const { settings } = useSettings();
  const visible = visibleFeatures(settings.uiMode);
  // Features flagged `footer` (Settings) live down with Help/Logout — they're
  // account-level actions, not places to explore.
  const sections = groupedFeatures(visible.filter((f) => !f.footer));
  const footerLinks = visible.filter((f) => f.footer);

  // The drawer is only translated off-screen when closed, so every one of its
  // ~40 links stayed in the tab order — a keyboard user tabbed through the whole
  // invisible menu on every page. `inert` takes the subtree out of focus AND out
  // of the accessibility tree; it is set on the DOM node because React 18 does
  // not pass an `inert` prop through. Escape closes, and focus goes back to the
  // hamburger that opened it (§68.8).
  useEffect(() => {
    const node = drawerRef.current;
    if (node) {
      if (open) node.removeAttribute("inert");
      else node.setAttribute("inert", "");
    }
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

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
    navigate("/profile-selection", returnHere());
  };

  return (
    <>
      <button
        type="button"
        ref={toggleRef}
        className="nav-drawer-toggle"
        aria-label={t("nav.openMenu")}
        aria-expanded={open}
        aria-controls="nav-drawer"
        onClick={() => setOpen(true)}
      >
        <Menu size={22} />
      </button>

      {open && (
        <div className="nav-drawer-overlay" onClick={() => setOpen(false)} aria-hidden="true" />
      )}

      <aside
        id="nav-drawer"
        ref={drawerRef}
        className={`nav-drawer ${open ? "open" : ""}`}
        aria-label={t("nav.menu")}
      >
        <div className="nav-drawer-head">
          <div className="nav-drawer-brand">
            <BrandLogo size={26} />
            <span>{SITE_TITLE}</span>
          </div>
          <button
            type="button"
            className="nav-drawer-close"
            aria-label={t("nav.closeMenu")}
            onClick={() => setOpen(false)}
          >
            <X size={22} />
          </button>
        </div>

        <UiModeToggle />

        <nav className="nav-drawer-links" aria-label={t("nav.features")}>
          {/* Same sections, same order as the dashboard tiles — a 38-item flat
              list gave no hint which entries belong to the same reading. */}
          {sections.map((section) => (
            <div key={section.key} className="nav-drawer-section">
              <div className="nav-drawer-section-title">{t(`nav.groups.${section.key}`)}</div>
              {section.features.map(({ key, path, Icon }) => (
                <button
                  key={path}
                  type="button"
                  aria-current={location.pathname === path ? "page" : undefined}
                  className={`nav-drawer-link ${location.pathname === path ? "active" : ""}`}
                  onClick={() => go(path)}
                >
                  <Icon size={20} />
                  <span>{t(`nav.${key}`)}</span>
                </button>
              ))}
            </div>
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
          <button type="button" className="nav-drawer-link" onClick={handleChangeChart}>
            <Sparkles size={20} />
            <span>{t("common.changeChart")}</span>
          </button>
          {footerLinks.map(({ key, path, Icon }) => (
            <button
              key={path}
              type="button"
              aria-current={location.pathname === path ? "page" : undefined}
              className={`nav-drawer-link ${location.pathname === path ? "active" : ""}`}
              onClick={() => go(path)}
            >
              <Icon size={20} />
              <span>{t(`nav.${key}`)}</span>
            </button>
          ))}
          {/* Help sits in the footer next to the other always-available actions
              rather than in the feature list — it isn't a feature, it's the way
              out when a feature doesn't make sense. */}
          <button
            type="button"
            aria-current={location.pathname === "/help" ? "page" : undefined}
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
              type="button"
              aria-current={location.pathname === "/admin" ? "page" : undefined}
              className={`nav-drawer-link ${location.pathname === "/admin" ? "active" : ""}`}
              onClick={() => go("/admin")}
            >
              <ShieldAlert size={20} />
              <span>Admin console</span>
            </button>
          )}
          <button type="button" className="nav-drawer-link logout" onClick={handleLogout}>
            <LogOut size={20} />
            <span>{t("common.logout")}</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default NavDrawer;
