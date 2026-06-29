import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import {
  Calendar,
  Heart,
  Clock,
  MessageCircle,
  LogOut,
  Star,
  Sparkles,
  Orbit,
  GitCompareArrows,
  Wrench,
} from "lucide-react";
import { ProfileBanner } from "../components/ProfileBanner";
import { NavDrawer } from "../components/NavDrawer";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import "../styles/Dashboard.css";

export const DashboardPage = () => {
  const { user, logout } = useAuth();
  const { selectedProfile, clearProfile } = useProfile();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = () => {
    logout();
    clearProfile();
    navigate("/login");
  };

  const handleChangeProfile = () => {
    clearProfile();
    navigate("/profile-selection");
  };

  // `key` resolves the title/description from dashboard.features.* so the cards
  // follow the selected language; icon/path/gradient stay code-side.
  const features = [
    {
      key: "birthChart",
      icon: <Calendar size={32} />,
      path: "/birth-chart",
      gradient: "linear-gradient(135deg, #FF9933 0%, #FFB347 100%)",
    },
    {
      key: "ask",
      icon: <MessageCircle size={32} />,
      path: "/ask-astrologer",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
    },
    {
      key: "compatibility",
      icon: <Heart size={32} />,
      path: "/compatibility",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
    },
    {
      key: "dhasa",
      icon: <Clock size={32} />,
      path: "/dhasa",
      gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
    },
    {
      key: "transit",
      icon: <Orbit size={32} />,
      path: "/transit",
      gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
    },
    {
      key: "advanced",
      icon: <Sparkles size={32} />,
      path: "/advanced",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #E27B5A 100%)",
    },
    {
      key: "compare",
      icon: <GitCompareArrows size={32} />,
      path: "/compare",
      gradient: "linear-gradient(135deg, #2D3561 0%, #E27B5A 100%)",
    },
    {
      key: "aiTools",
      icon: <Wrench size={32} />,
      path: "/ai-tools",
      gradient: "linear-gradient(135deg, #3D4571 0%, #5A5F7A 100%)",
    },
  ];

  return (
    <div className="dashboard-container mandala-bg">
      <nav className="navbar">
        <div className="navbar-brand">
          <Star className="brand-icon" size={28} />
          <h1>PyJHora</h1>
        </div>
        <div className="nav-right">
          <div className="user-info">
            <span className="welcome-text">{t("dashboard.welcome")}</span>
            <span className="username">{user?.username}</span>
          </div>
          <LanguageSwitcher />
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
                {feature.icon}
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
      </div>
    </div>
  );
};
