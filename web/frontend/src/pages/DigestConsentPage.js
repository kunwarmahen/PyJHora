import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle, BellOff, AlertCircle } from "lucide-react";
import { notificationsService } from "../services/api";
import { SITE_TITLE } from "../config/branding";
import "../styles/Auth.css";

/**
 * Public landing page for the confirm / unsubscribe links carried in digest
 * emails. It needs no login: it reads the token from the query string, calls the
 * matching public endpoint once on mount, and reports the outcome. `mode` is
 * "confirm" or "unsubscribe" (set by the route).
 */
export const DigestConsentPage = ({ mode = "confirm" }) => {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [state, setState] = useState({ status: "working", email: "" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) {
        if (!cancelled) setState({ status: "invalid", email: "" });
        return;
      }
      try {
        const call =
          mode === "unsubscribe"
            ? notificationsService.unsubscribeDigest
            : notificationsService.confirmDigest;
        const res = await call(token);
        if (!cancelled) setState({ status: res.data.status, email: res.data.email || "" });
      } catch (err) {
        if (!cancelled) setState({ status: "invalid", email: "" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, mode]);

  const view = () => {
    switch (state.status) {
      case "working":
        return { icon: null, title: t("digestConsent.working"), body: "" };
      case "confirmed":
        return {
          icon: <CheckCircle size={40} className="digest-consent-icon digest-consent-icon--ok" />,
          title: t("digestConsent.confirmedTitle"),
          body: t("digestConsent.confirmedBody", { email: state.email }),
        };
      case "unsubscribed":
        return {
          icon: <BellOff size={40} className="digest-consent-icon digest-consent-icon--muted" />,
          title: t("digestConsent.unsubscribedTitle"),
          body: t("digestConsent.unsubscribedBody", { email: state.email }),
        };
      default:
        return {
          icon: <AlertCircle size={40} className="digest-consent-icon digest-consent-icon--warn" />,
          title: t("digestConsent.invalidTitle"),
          body: t("digestConsent.invalidBody"),
        };
    }
  };

  const v = view();

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <h1>{SITE_TITLE}</h1>
        {v.icon}
        <h2 style={{ marginTop: v.icon ? 12 : 0 }}>{v.title}</h2>
        {v.body && <p className="subtitle">{v.body}</p>}
        {state.status !== "working" && (
          <p className="auth-link">
            <Link to="/login">{t("digestConsent.backToApp", { site: SITE_TITLE })}</Link>
          </p>
        )}
      </div>
    </div>
  );
};

export default DigestConsentPage;
