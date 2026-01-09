import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { Calendar, Heart, Clock, MessageCircle, LogOut, User, Star, Sparkles } from "lucide-react";
import "../styles/Dashboard.css";

export const DashboardPage = () => {
  const { user, logout } = useAuth();
  const { selectedProfile, clearProfile } = useProfile();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    clearProfile();
    navigate("/login");
  };

  const handleChangeProfile = () => {
    clearProfile();
    navigate("/profile-selection");
  };

  const features = [
    {
      icon: <Calendar size={32} />,
      title: "Birth Chart",
      description: "Explore your Rasi and Navamsa charts with detailed planetary positions",
      path: "/birth-chart",
      gradient: "linear-gradient(135deg, #FF9933 0%, #FFB347 100%)",
    },
    {
      icon: <MessageCircle size={32} />,
      title: "Ask AI Astrologer",
      description: "Chat with AI to get personalized Vedic astrology insights and guidance",
      path: "/ask-astrologer",
      gradient: "linear-gradient(135deg, #E27B5A 0%, #E34234 100%)",
    },
    {
      icon: <Heart size={32} />,
      title: "Compatibility",
      description: "Check marriage compatibility and relationship harmony analysis",
      path: "/compatibility",
      gradient: "linear-gradient(135deg, #D4AF37 0%, #FFB347 100%)",
    },
    {
      icon: <Clock size={32} />,
      title: "Dasha Periods",
      description: "Explore your planetary periods and life timing predictions",
      path: "/dhasa",
      gradient: "linear-gradient(135deg, #2D3561 0%, #5A5F7A 100%)",
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
            <span className="welcome-text">Welcome,</span>
            <span className="username">{user?.username}</span>
          </div>
          <button onClick={handleLogout} className="logout-btn">
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </nav>

      <div className="dashboard-content">
        {selectedProfile && (
          <div className="profile-banner fade-in">
            <div className="profile-banner-left">
              <div className="profile-avatar-large">
                <User size={32} />
              </div>
              <div className="profile-info">
                <h2>{selectedProfile.profile_name}</h2>
                <div className="profile-meta">
                  <span>{selectedProfile.birth_details.name || 'Anonymous'}</span>
                  <span className="separator">•</span>
                  <span>{selectedProfile.birth_details.dob.split('T')[0]}</span>
                  <span className="separator">•</span>
                  <span>{selectedProfile.birth_details.place}</span>
                </div>
              </div>
            </div>
            <button onClick={handleChangeProfile} className="change-profile-btn">
              <Sparkles size={16} />
              <span>Change Chart</span>
            </button>
          </div>
        )}

        <div className="section-header fade-in">
          <h3>Explore Your Cosmic Journey</h3>
          <p className="section-subtitle">Choose a service to dive deeper into your Vedic astrology insights</p>
        </div>

        <div className="features-grid">
          {features.map((feature, index) => (
            <Link
              key={index}
              to={feature.path}
              className={`feature-card fade-in stagger-${index + 1}`}
            >
              <div className="feature-icon" style={{ background: feature.gradient }}>
                {feature.icon}
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
              <div className="feature-arrow">
                <span>Explore</span>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M6 3L11 8L6 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};
