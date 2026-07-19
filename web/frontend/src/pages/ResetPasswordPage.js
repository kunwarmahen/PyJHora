import React, { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Lock, AlertCircle } from "lucide-react";
import { authService, setTokens } from "../services/api";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { SITE_TITLE } from "../config/branding";
import "../styles/Auth.css";

export const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const { reloadUser } = useAuth();
  const { resumeProfile } = useProfile();

  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!token) {
      setError(t("auth.reset.missingToken"));
      return;
    }
    if (pw.length < 6) {
      setError(t("auth.reset.tooShort"));
      return;
    }
    if (pw !== confirm) {
      setError(t("auth.reset.mismatch"));
      return;
    }
    setIsLoading(true);
    try {
      const res = await authService.resetPassword(token, pw);
      // The reset signs the user straight in (fresh token pair).
      setTokens(res.data);
      if (reloadUser) await reloadUser();
      navigate(await resumeProfile());
    } catch (err) {
      setError(err.response?.data?.detail || t("auth.reset.error"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>{SITE_TITLE}</h1>
        <p className="subtitle">{t("auth.reset.subtitle")}</p>

        <form onSubmit={handleSubmit}>
          {error && (
            <div className="error-message">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
          {!token && <p className="auth-note">{t("auth.reset.missingToken")}</p>}
          <div className="form-group">
            <label>{t("auth.reset.newPassword")}</label>
            <div className="input-wrapper">
              <Lock size={18} />
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder={t("auth.reset.newPasswordPlaceholder")}
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label>{t("auth.reset.confirm")}</label>
            <div className="input-wrapper">
              <Lock size={18} />
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder={t("auth.reset.confirmPlaceholder")}
                required
              />
            </div>
          </div>
          <button type="submit" className="submit-btn" disabled={isLoading || !token}>
            {isLoading ? t("auth.reset.saving") : t("auth.reset.submit")}
          </button>
          <p className="auth-link">
            <Link to="/login">{t("auth.reset.backToLogin")}</Link>
          </p>
        </form>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
