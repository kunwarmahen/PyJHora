import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { Mail, Lock, AlertCircle } from "lucide-react";
import { SITE_TITLE, SITE_TAGLINE } from "../config/branding";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
import "../styles/Auth.css";

export const LoginPage = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const { login, error } = useAuth();
  const { resumeProfile } = useProfile();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    const success = await login(username, password, rememberMe);
    if (success) {
      navigate(await resumeProfile());
    }
    setIsLoading(false);
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>{SITE_TITLE}</h1>
        <p className="subtitle">{SITE_TAGLINE || t("auth.tagline")}</p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="error-message">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label>{t("auth.username")}</label>
            <div className="input-wrapper">
              <Mail size={18} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("auth.usernamePlaceholder")}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>{t("auth.password")}</label>
            <div className="input-wrapper">
              <Lock size={18} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("auth.passwordPlaceholder")}
                required
              />
            </div>
          </div>

          <label className="remember-me">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <span>{t("auth.rememberMe")}</span>
          </label>

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? t("auth.loggingIn") : t("auth.login")}
          </button>

          <p className="auth-link auth-link--forgot">
            <Link to="/forgot-password">{t("auth.forgotPassword")}</Link>
          </p>
        </form>

        <GoogleSignInButton />

        <p className="auth-link">
          {t("auth.noAccount")} <Link to="/register">{t("auth.registerHere")}</Link>
        </p>
      </div>
    </div>
  );
};
