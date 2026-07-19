import React, { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Mail, AlertCircle, CheckCircle } from "lucide-react";
import { authService } from "../services/api";
import { SITE_TITLE } from "../config/branding";
import "../styles/Auth.css";

export const ForgotPasswordPage = () => {
  const { t } = useTranslation();
  const [identifier, setIdentifier] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [emailConfigured, setEmailConfigured] = useState(true);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      const res = await authService.forgotPassword(identifier.trim());
      setEmailConfigured(res.data?.email_configured !== false);
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || t("auth.forgot.error"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>{SITE_TITLE}</h1>
        <p className="subtitle">{t("auth.forgot.subtitle")}</p>

        {sent ? (
          <div>
            <div className="success-message">
              <CheckCircle size={16} />
              <span>{t("auth.forgot.sent")}</span>
            </div>
            {!emailConfigured && <p className="auth-note">{t("auth.forgot.noEmailConfigured")}</p>}
            <p className="auth-link">
              <Link to="/login">{t("auth.forgot.backToLogin")}</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && (
              <div className="error-message">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}
            <p className="auth-note">{t("auth.forgot.intro")}</p>
            <div className="form-group">
              <label>{t("auth.forgot.identifier")}</label>
              <div className="input-wrapper">
                <Mail size={18} />
                <input
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={t("auth.forgot.identifierPlaceholder")}
                  required
                />
              </div>
            </div>
            <button type="submit" className="submit-btn" disabled={isLoading}>
              {isLoading ? t("auth.forgot.sending") : t("auth.forgot.submit")}
            </button>
            <p className="auth-link">
              <Link to="/login">{t("auth.forgot.backToLogin")}</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
