import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Menu,
  X,
  LayoutDashboard,
  Calendar,
  Clock,
  Orbit,
  Sparkles,
  Heart,
  MessageCircle,
  Star,
  LogOut,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import "../styles/NavDrawer.css";

const LINKS = [
  { to: "/dashboard", label: "Dashboard", icon: <LayoutDashboard size={20} /> },
  { to: "/birth-chart", label: "Birth Chart", icon: <Calendar size={20} /> },
  { to: "/dhasa", label: "Dhasa Periods", icon: <Clock size={20} /> },
  { to: "/transit", label: "Transits", icon: <Orbit size={20} /> },
  { to: "/advanced", label: "Advanced Details", icon: <Sparkles size={20} /> },
  { to: "/compatibility", label: "Compatibility", icon: <Heart size={20} /> },
  { to: "/ask-astrologer", label: "Ask AI Astrologer", icon: <MessageCircle size={20} /> },
];

/** Hamburger button + slide-in feature drawer. The button only shows on phones
 * (CSS); on larger screens navigation stays via the dashboard cards. */
export const NavDrawer = () => {
  const [open, setOpen] = useState(false);
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
      <button className="nav-drawer-toggle" aria-label="Open menu" onClick={() => setOpen(true)}>
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
            aria-label="Close menu"
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
              <span>{l.label}</span>
            </button>
          ))}
        </nav>

        <div className="nav-drawer-footer">
          <button className="nav-drawer-link" onClick={handleChangeChart}>
            <Sparkles size={20} />
            <span>Change Chart</span>
          </button>
          <button className="nav-drawer-link logout" onClick={handleLogout}>
            <LogOut size={20} />
            <span>Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default NavDrawer;
