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
  Sparkles,
  Orbit,
  CalendarClock,
  Moon,
  Grid3x3,
  GitCompareArrows,
  GraduationCap,
  CalendarDays,
  Clock4,
  Bird,
  Crosshair,
  Timer,
  Settings,
  CalendarCheck,
  HelpCircle,
  Sun,
  Waypoints,
  Gem,
  History,
  CalendarRange,
  GanttChartSquare,
  Gauge,
  Home,
  FileText,
  Compass,
  Layers,
  Globe,
} from "lucide-react";
import { ProfileBanner } from "../components/ProfileBanner";
import { NavDrawer } from "../components/NavDrawer";
import { NowChartWidget } from "../components/NowChartWidget";
import { BrandLogo } from "../components/BrandLogo";
import { SITE_TITLE } from "../config/branding";
import "../styles/Dashboard.css";

export const DashboardPage = () => {
  const { user, logout } = useAuth();
  const { selectedProfile, clearProfile } = useProfile();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = async () => {
    await logout();
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
      key: "ephemeris",
      icon: <CalendarRange size={32} />,
      path: "/ephemeris",
      gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
    },
    {
      key: "bhava",
      icon: <Home size={32} />,
      path: "/bhava",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
    },
    {
      key: "report",
      icon: <FileText size={32} />,
      path: "/report",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #FF9933 100%)",
    },
    {
      key: "varshaphal",
      icon: <CalendarClock size={32} />,
      path: "/varshaphal",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #2D3561 100%)",
    },
    {
      key: "tithiPravesha",
      icon: <Moon size={32} />,
      path: "/tithi-pravesha",
      gradient: "linear-gradient(135deg, #2D3561 0%, #FF9933 100%)",
    },
    {
      key: "almanac",
      icon: <CalendarDays size={32} />,
      path: "/almanac",
      gradient: "linear-gradient(135deg, #FFB347 0%, #D4AF37 100%)",
    },
    {
      key: "dailyDigest",
      icon: <Sun size={32} />,
      path: "/daily-digest",
      gradient: "linear-gradient(135deg, #FF9933 0%, #E27B5A 100%)",
    },
    {
      key: "fortnightlyDigest",
      icon: <CalendarDays size={32} />,
      path: "/fortnightly-digest",
      gradient: "linear-gradient(135deg, #F0883E 0%, #D4AF37 100%)",
    },
    {
      key: "monthlyDigest",
      icon: <CalendarRange size={32} />,
      path: "/monthly-digest",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #B5651D 100%)",
    },
    {
      key: "muhurta",
      icon: <CalendarCheck size={32} />,
      path: "/muhurta",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
    },
    {
      key: "prashna",
      icon: <HelpCircle size={32} />,
      path: "/prashna",
      gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
    },
    {
      key: "timeline",
      icon: <GanttChartSquare size={32} />,
      path: "/timeline",
      gradient: "linear-gradient(135deg, #2D3561 0%, #E27B5A 100%)",
    },
    {
      key: "strength",
      icon: <Gauge size={32} />,
      path: "/strength",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #2E9E5B 100%)",
    },
    {
      key: "bhrigu",
      icon: <Waypoints size={32} />,
      path: "/bhrigu-markers",
      gradient: "linear-gradient(135deg, #5A5F7A 0%, #D4AF37 100%)",
    },
    {
      key: "remedies",
      icon: <Gem size={32} />,
      path: "/remedies",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
    },
    {
      key: "panchaPakshi",
      icon: <Bird size={32} />,
      path: "/pancha-pakshi",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #FFB347 100%)",
    },
    {
      key: "sarvatobhadra",
      icon: <Grid3x3 size={32} />,
      path: "/sarvatobhadra",
      gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
    },
    {
      key: "learn",
      icon: <GraduationCap size={32} />,
      path: "/learn",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #D4AF37 100%)",
    },
    {
      key: "sensitivePoints",
      icon: <Crosshair size={32} />,
      path: "/sensitive-points",
      gradient: "linear-gradient(135deg, #2D3561 0%, #D4AF37 100%)",
    },
    {
      key: "vedicClock",
      icon: <Timer size={32} />,
      path: "/vedic-clock",
      gradient: "linear-gradient(135deg, #5A5F7A 0%, #FF9933 100%)",
    },
    {
      key: "kp",
      icon: <Compass size={32} />,
      path: "/kp",
      gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
    },
    {
      key: "jaimini",
      icon: <Layers size={32} />,
      path: "/jaimini",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
    },
    {
      key: "now",
      icon: <Globe size={32} />,
      path: "/now",
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
      key: "rectify",
      icon: <Clock4 size={32} />,
      path: "/rectify",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #2D3561 100%)",
    },
    {
      key: "history",
      icon: <History size={32} />,
      path: "/history",
      gradient: "linear-gradient(135deg, #FF9933 0%, #2D3561 100%)",
    },
  ];

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
