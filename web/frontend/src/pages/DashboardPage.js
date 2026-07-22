import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { LogOut, Sparkles, Settings, HelpCircle, Search, X } from "lucide-react";
import { ProfileBanner } from "../components/ProfileBanner";
import { LocationPrompt } from "../components/LocationPrompt";
import { NavDrawer } from "../components/NavDrawer";
import { ThemeToggle } from "../components/ThemeToggle";
import { NowChartWidget } from "../components/NowChartWidget";
import { UiModeToggle } from "../components/UiModeToggle";
import { BrandLogo } from "../components/BrandLogo";
import { SITE_TITLE } from "../config/branding";
import { visibleFeatures, FEATURE_ALIASES } from "../config/features";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";

export const DashboardPage = () => {
  const { user, logout } = useAuth();
  const { selectedProfile, clearProfile } = useProfile();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { settings } = useSettings();

  const handleLogout = async () => {
    await logout();
    clearProfile();
    navigate("/login");
  };

  const handleChangeProfile = () => {
    clearProfile();
    navigate("/profile-selection");
  };

  // Tiles come from the feature registry (config/features.js) filtered by the
  // Essentials/Everything mode — the same list the NavDrawer renders, so the two
  // can no longer disagree about what exists. `navOnly` entries (Dashboard,
  // Settings) live in the drawer/navbar and don't get a tile.
  const features = useMemo(
    () => visibleFeatures(settings.uiMode).filter((f) => !f.navOnly),
    [settings.uiMode]
  );

  // Type-to-filter launcher. Collapsed to a single icon by default; it opens
  // when the icon is clicked OR the moment someone starts typing anywhere on the
  // page (the first keystroke opens the box and seeds the query, then the input
  // handles the rest natively). Esc clears + collapses; blurring an empty box
  // collapses it too. Enter opens the top match. The haystack is the localized
  // title + description plus the English keyword aliases from the registry, so
  // intuitive words like "marriage" find Compatibility even though the tile
  // never says it.
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const searchRef = useRef(null);

  // Focus the box whenever it opens (via click or ambient typing).
  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return features;
    const tokens = q.split(/\s+/);
    return features.filter((f) => {
      const hay = [
        t(`dashboard.features.${f.key}.title`),
        t(`dashboard.features.${f.key}.description`),
        FEATURE_ALIASES[f.key] || "",
      ]
        .join(" ")
        .toLowerCase();
      return tokens.every((tok) => hay.includes(tok));
    });
  }, [features, query, t]);

  const closeSearch = () => {
    setQuery("");
    setOpen(false);
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = document.activeElement;
      const typing =
        el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);
      if (e.key === "Escape") {
        if (open || query) closeSearch();
        return;
      }
      // Once the search box is focused it handles its own keystrokes natively;
      // only seed from ambient typing when focus is elsewhere.
      if (typing) return;
      if (e.key.length === 1 && /\S/.test(e.key)) {
        e.preventDefault();
        setQuery((prev) => prev + e.key);
        setOpen(true); // the [open] effect focuses the box once it renders
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, query]);

  const onSearchKeyDown = (e) => {
    if (e.key === "Enter" && filtered.length > 0) {
      navigate(filtered[0].path);
    } else if (e.key === "Escape") {
      closeSearch();
    }
  };

  // Collapse back to the icon when the user tabs/clicks away from an empty box.
  const onSearchBlur = () => {
    if (!query.trim()) setOpen(false);
  };

  return (
    <div className="dashboard-container mandala-bg">
      <nav className="navbar">
        <div className="navbar-brand">
          <BrandLogo className="brand-icon" size={32} />
          <h1>{SITE_TITLE}</h1>
        </div>
        <div className="nav-right">
          <div className="user-info">
            <span className="welcome-text">{t("dashboard.welcome")}</span>
            <span className="username">{user?.name || user?.username}</span>
          </div>
          <ThemeToggle />
          <button
            onClick={() => navigate("/help")}
            className="logout-btn"
            title={t("nav.help")}
            aria-label={t("nav.help")}
          >
            <HelpCircle size={18} />
          </button>
          <button
            onClick={() => navigate("/settings")}
            className="logout-btn"
            title={t("nav.settings")}
            aria-label={t("nav.settings")}
          >
            <Settings size={18} />
          </button>
          <button
            onClick={handleLogout}
            className="logout-btn"
            title={t("common.logout")}
            aria-label={t("common.logout")}
          >
            <LogOut size={18} />
            <span>{t("common.logout")}</span>
          </button>
          <NavDrawer />
        </div>
      </nav>

      <div className="dashboard-content">
        <ProfileBanner
          profile={selectedProfile}
          onChangeProfile={handleChangeProfile}
          changeIcon={<Sparkles size={16} />}
        />

        <LocationPrompt />

        <NowChartWidget />

        <div className="section-header fade-in">
          <h3>{t("dashboard.sectionTitle")}</h3>
          <p className="section-subtitle">{t("dashboard.sectionSubtitle")}</p>
        </div>

        <div className="dashboard-search-bar fade-in">
          {open || query ? (
            <div className="dashboard-search">
              <Search size={18} className="dashboard-search__icon" />
              <input
                ref={searchRef}
                type="text"
                className="dashboard-search__input"
                placeholder={t("dashboard.search.placeholder")}
                aria-label={t("dashboard.search.placeholder")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onSearchKeyDown}
                onBlur={onSearchBlur}
              />
              <button
                type="button"
                className="dashboard-search__clear"
                onClick={closeSearch}
                aria-label={t("dashboard.search.clear")}
              >
                <X size={16} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="dashboard-search-toggle"
              onClick={() => setOpen(true)}
              aria-label={t("dashboard.search.open")}
              title={t("dashboard.search.open")}
            >
              <Search size={16} />
              <span>{t("dashboard.search.toggleLabel")}</span>
            </button>
          )}
        </div>

        {query && filtered.length === 0 ? (
          <p className="dashboard-search__empty fade-in">
            {t("dashboard.search.noResults", { query })}
          </p>
        ) : (
        <div className="features-grid">
          {filtered.map((feature, index) => (
            <Link
              key={feature.key}
              to={feature.path}
              className={`feature-card fade-in stagger-${index + 1}`}
            >
              <div className="feature-icon" style={{ background: feature.gradient }}>
                <feature.Icon size={32} />
              </div>
              <h3>{t(`dashboard.features.${feature.key}.title`)}</h3>
              <p>{t(`dashboard.features.${feature.key}.description`)}</p>
              <div className="feature-arrow">
                <span>{t("dashboard.explore")}</span>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M6 3L11 8L6 13"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </Link>
          ))}
        </div>
        )}

        {/* Below the tiles, not hidden in Settings: the dashboard is where
            someone in Essentials discovers there is more, and switches. */}
        <UiModeToggle variant="dashboard" />
      </div>
    </div>
  );
};
