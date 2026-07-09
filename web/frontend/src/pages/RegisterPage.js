import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { Mail, Lock, User, AlertCircle } from "lucide-react";
import { SITE_TITLE } from "../config/branding";
import { GoogleSignInButton } from "../components/GoogleSignInButton";
import "../styles/Auth.css";

export const RegisterPage = () => {
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { register, error } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  // Lightweight password-strength hint (no external lib): scores length +
  // character variety into weak / fair / strong.
  const strength = (() => {
    if (!password) return null;
    if (password.length < 6) return "short";
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    if (score <= 1) return "weak";
    if (score <= 3) return "fair";
    return "strong";
  })();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      alert(t("auth.passwordsNoMatch"));
      return;
    }

    setIsLoading(true);
    const success = await register(username, email, password, name.trim(), true);
    setIsLoading(false);
    if (success) {
      navigate("/profile-selection");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>{SITE_TITLE}</h1>
        <p className="subtitle">{t("auth.createAccount")}</p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="error-message">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className="form-group">
            <label>{t("auth.name")}</label>
            <div className="input-wrapper">
              <User size={18} />
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("auth.namePlaceholder")}
                autoComplete="name"
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>{t("auth.username")}</label>
            <div className="input-wrapper">
              <User size={18} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t("auth.chooseUsername")}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>{t("auth.email")}</label>
            <div className="input-wrapper">
              <Mail size={18} />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("auth.emailPlaceholder")}
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
                placeholder={t("auth.createPassword")}
                required
              />
            </div>
            {strength && (
              <div className={`pw-strength pw-strength--${strength}`}>
                <span className="pw-strength-bar" />
                <span className="pw-strength-label">{t(`auth.pwStrength.${strength}`)}</span>
              </div>
            )}
          </div>

          <div className="form-group">
            <label>{t("auth.confirmPassword")}</label>
            <div className="input-wrapper">
              <Lock size={18} />
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder={t("auth.confirmPasswordPlaceholder")}
                required
              />
            </div>
          </div>

          <button type="submit" className="submit-btn" disabled={isLoading}>
            {isLoading ? t("auth.registering") : t("auth.register")}
          </button>
        </form>

        <GoogleSignInButton redirectTo="/profile-selection" />

        <p className="auth-link">
          {t("auth.haveAccount")} <Link to="/login">{t("auth.loginHere")}</Link>
        </p>
      </div>
    </div>
  );
};
