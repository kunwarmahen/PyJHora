import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../contexts/AuthContext";
import { Mail, Lock, User, AlertCircle } from "lucide-react";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import "../styles/Auth.css";

export const RegisterPage = () => {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { register, error } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      alert(t("auth.passwordsNoMatch"));
      return;
    }

    setIsLoading(true);
    const success = await register(username, email, password);
    setIsLoading(false);
    if (success) {
      navigate("/profile-selection");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-lang">
        <LanguageSwitcher />
      </div>
      <div className="auth-card">
        <h1>PyJHora</h1>
        <p className="subtitle">{t("auth.createAccount")}</p>

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

        <p className="auth-link">
          {t("auth.haveAccount")} <Link to="/login">{t("auth.loginHere")}</Link>
        </p>
      </div>
    </div>
  );
};
