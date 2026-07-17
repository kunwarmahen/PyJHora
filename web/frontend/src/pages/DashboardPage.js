import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { LogOut, Sparkles, Settings } from "lucide-react";
import { ProfileBanner } from "../components/ProfileBanner";
import { NavDrawer } from "../components/NavDrawer";
import { NowChartWidget } from "../components/NowChartWidget";
import { UiModeToggle } from "../components/UiModeToggle";
import { BrandLogo } from "../components/BrandLogo";
import { SITE_TITLE } from "../config/branding";
import { visibleFeatures } from "../config/features";
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
  const features = visibleFeatures(settings.uiMode).filter((f) => !f.navOnly);

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
          <button
            onClick={() => navigate("/settings")}
            className="logout-btn"
            title={t("nav.settings")}
            aria-label={t("nav.settings")}
          >
            <Settings size={18} />
          </button>
          <button onClick={handleLogout} className="logout-btn">
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

        <NowChartWidget />

        <div className="section-header fade-in">
          <h3>{t("dashboard.sectionTitle")}</h3>
          <p className="section-subtitle">{t("dashboard.sectionSubtitle")}</p>
        </div>

        <div className="features-grid">
          {features.map((feature, index) => (
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

        {/* Below the tiles, not hidden in Settings: the dashboard is where
            someone in Essentials discovers there is more, and switches. */}
        <UiModeToggle variant="dashboard" />
      </div>
    </div>
  );
};
