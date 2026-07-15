import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Menu,
  X,
  LayoutDashboard,
  Calendar,
  Clock,
  Orbit,
  CalendarClock,
  Moon,
  Sparkles,
  Heart,
  MessageCircle,
  Grid3x3,
  GitCompareArrows,
  GraduationCap,
  CalendarDays,
  Clock4,
  Bird,
  Crosshair,
  Timer,
  Settings,
  LogOut,
  CalendarCheck,
  HelpCircle,
  Sun,
  Waypoints,
  GanttChartSquare,
  Gem,
  History,
  CalendarRange,
  Home,
  FileText,
  Compass,
  Layers,
  Globe,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { BrandLogo } from "./BrandLogo";
import { SITE_TITLE } from "../config/branding";
import "../styles/NavDrawer.css";

// `labelKey` is resolved through i18next at render time so the drawer follows
// the selected language.
const LINKS = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: <LayoutDashboard size={20} /> },
  { to: "/birth-chart", labelKey: "nav.birthChart", icon: <Calendar size={20} /> },
  { to: "/dhasa", labelKey: "nav.dhasa", icon: <Clock size={20} /> },
  { to: "/transit", labelKey: "nav.transit", icon: <Orbit size={20} /> },
  { to: "/ephemeris", labelKey: "nav.ephemeris", icon: <CalendarRange size={20} /> },
  { to: "/bhava", labelKey: "nav.bhava", icon: <Home size={20} /> },
  { to: "/report", labelKey: "nav.report", icon: <FileText size={20} /> },
  { to: "/varshaphal", labelKey: "nav.varshaphal", icon: <CalendarClock size={20} /> },
  { to: "/tithi-pravesha", labelKey: "nav.tithiPravesha", icon: <Moon size={20} /> },
  { to: "/almanac", labelKey: "nav.almanac", icon: <CalendarDays size={20} /> },
  { to: "/daily-digest", labelKey: "nav.dailyDigest", icon: <Sun size={20} /> },
  { to: "/fortnightly-digest", labelKey: "nav.fortnightlyDigest", icon: <CalendarDays size={20} /> },
  { to: "/monthly-digest", labelKey: "nav.monthlyDigest", icon: <CalendarRange size={20} /> },
  { to: "/muhurta", labelKey: "nav.muhurta", icon: <CalendarCheck size={20} /> },
  { to: "/prashna", labelKey: "nav.prashna", icon: <HelpCircle size={20} /> },
  { to: "/timeline", labelKey: "nav.timeline", icon: <GanttChartSquare size={20} /> },
  { to: "/bhrigu-markers", labelKey: "nav.bhrigu", icon: <Waypoints size={20} /> },
  { to: "/remedies", labelKey: "nav.remedies", icon: <Gem size={20} /> },
  { to: "/pancha-pakshi", labelKey: "nav.panchaPakshi", icon: <Bird size={20} /> },
  { to: "/sarvatobhadra", labelKey: "nav.sarvatobhadra", icon: <Grid3x3 size={20} /> },
  { to: "/sensitive-points", labelKey: "nav.sensitivePoints", icon: <Crosshair size={20} /> },
  { to: "/vedic-clock", labelKey: "nav.vedicClock", icon: <Timer size={20} /> },
  { to: "/kp", labelKey: "nav.kp", icon: <Compass size={20} /> },
  { to: "/jaimini", labelKey: "nav.jaimini", icon: <Layers size={20} /> },
  { to: "/now", labelKey: "nav.now", icon: <Globe size={20} /> },
  { to: "/advanced", labelKey: "nav.advanced", icon: <Sparkles size={20} /> },
  { to: "/compare", labelKey: "nav.compare", icon: <GitCompareArrows size={20} /> },
  { to: "/rectify", labelKey: "nav.rectify", icon: <Clock4 size={20} /> },
  { to: "/compatibility", labelKey: "nav.compatibility", icon: <Heart size={20} /> },
  { to: "/learn", labelKey: "nav.learn", icon: <GraduationCap size={20} /> },
  { to: "/ask-astrologer", labelKey: "nav.ask", icon: <MessageCircle size={20} /> },
  { to: "/history", labelKey: "nav.history", icon: <History size={20} /> },
  { to: "/settings", labelKey: "nav.settings", icon: <Settings size={20} /> },
];

/** Hamburger button + slide-in feature drawer. The button only shows on phones
 * (CSS); on larger screens navigation stays via the dashboard cards. */
export const NavDrawer = () => {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { clearProfile } = useProfile();

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

        <nav className="nav-drawer-links">
          {LINKS.map((l) => (
            <button
              key={l.to}
              className={`nav-drawer-link ${location.pathname === l.to ? "active" : ""}`}
              onClick={() => go(l.to)}
            >
              {l.icon}
              <span>{t(l.labelKey)}</span>
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
