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
  Sparkles,
  Heart,
  MessageCircle,
  Wrench,
  Star,
  Grid3x3,
  GitCompareArrows,
  GraduationCap,
  CalendarDays,
  Clock4,
  LogOut,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import "../styles/NavDrawer.css";

// `labelKey` is resolved through i18next at render time so the drawer follows
// the selected language.
const LINKS = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: <LayoutDashboard size={20} /> },
  { to: "/birth-chart", labelKey: "nav.birthChart", icon: <Calendar size={20} /> },
  { to: "/dhasa", labelKey: "nav.dhasa", icon: <Clock size={20} /> },
  { to: "/transit", labelKey: "nav.transit", icon: <Orbit size={20} /> },
  { to: "/varshaphal", labelKey: "nav.varshaphal", icon: <CalendarClock size={20} /> },
  { to: "/almanac", labelKey: "nav.almanac", icon: <CalendarDays size={20} /> },
  { to: "/sarvatobhadra", labelKey: "nav.sarvatobhadra", icon: <Grid3x3 size={20} /> },
  { to: "/advanced", labelKey: "nav.advanced", icon: <Sparkles size={20} /> },
  { to: "/compare", labelKey: "nav.compare", icon: <GitCompareArrows size={20} /> },
  { to: "/rectify", labelKey: "nav.rectify", icon: <Clock4 size={20} /> },
  { to: "/compatibility", labelKey: "nav.compatibility", icon: <Heart size={20} /> },
  { to: "/learn", labelKey: "nav.learn", icon: <GraduationCap size={20} /> },
  { to: "/ask-astrologer", labelKey: "nav.ask", icon: <MessageCircle size={20} /> },
  { to: "/ai-tools", labelKey: "nav.aiTools", icon: <Wrench size={20} /> },
];

/** Hamburger button + slide-in feature drawer. The button only shows on phones
 * (CSS); on larger screens navigation stays via the dashboard cards. */
export const NavDrawer = () => {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();
  const { clearProfile } = useProfile();

  const go = (to) => {
    setOpen(false);
    navigate(to);
  };

  const handleLogout = () => {
    setOpen(false);
    logout();
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
            <Star size={22} />
            <span>PyJHora</span>
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
