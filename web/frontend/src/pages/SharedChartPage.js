import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Star, Calendar, Clock, MapPin } from "lucide-react";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { formatDate, orDash } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { SITE_TITLE } from "../config/branding";

/** Public, read-only view of a shared chart (no auth required). */
export const SharedChartPage = () => {
  const { token } = useParams();
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    astrologyService
      .getSharedChart(token)
      .then((r) => !cancelled && setData(r.data))
      .catch((e) => {
        if (!cancelled)
          setError(e.response?.status === 404 ? t("shared.notFound") : t("shared.loadFailed"));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const chart = data?.chart;
  const bd = data?.birth_details || {};
  const title = data?.profile_name || bd.name || t("shared.defaultTitle");

  return (
    <div className="dashboard-container mandala-bg">
      <nav className="navbar">
        <div className="navbar-brand">
          <Star className="brand-icon" size={28} />
          <h1>{SITE_TITLE}</h1>
        </div>
        <div className="nav-right">
          <Link to="/login" className="change-profile-btn">
            <Star size={16} />
            <span>{t("shared.openApp", { brand: SITE_TITLE })}</span>
          </Link>
        </div>
      </nav>

      <div className="dashboard-content">
        <div className="fade-in readonly-banner">{t("shared.readOnlyBanner")}</div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("shared.loading")} />
          </Card>
        ) : chart ? (
          <>
            <Card title={title} icon={<Star size={24} />}>
              <div className="ui-field-grid">
                <DataField
                  label={t("common.dateOfBirth")}
                  icon={<Calendar size={16} />}
                  value={formatDate(bd.dob)}
                />
                <DataField
                  label={t("common.timeOfBirth")}
                  icon={<Clock size={16} />}
                  value={orDash(bd.tob)}
                />
                <DataField
                  label={t("common.place")}
                  icon={<MapPin size={16} />}
                  value={orDash(bd.place)}
                />
                <DataField
                  label={t("common.lagna")}
                  icon={<Star size={16} />}
                  value={chart.lagna?.sign_name || "—"}
                />
              </div>
            </Card>

            <NorthIndianChart
              chartData={chart}
              title={t("birthChart.rasiChart")}
              subtitle="D1"
              exportable
            />

            {chart.d9_chart && chart.d9_lagna && (
              <NorthIndianChart
                planets={chart.d9_chart}
                lagna={chart.d9_lagna}
                title={t("shared.navamsaChart")}
                subtitle="D9"
                exportable
              />
            )}

            <p className="text-center text-secondary mt-xl">
              {t("shared.cta")}{" "}
              <Link to="/register" className="text-saffron fw-600">
                {t("shared.ctaLink")}
              </Link>
              .
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
};

export default SharedChartPage;
