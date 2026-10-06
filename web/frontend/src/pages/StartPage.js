import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass, MessageCircle } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { onboardingService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { FirstLook } from "../components/FirstLook";
import { useChecklist } from "../hooks/useChecklist";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { returnHere } from "../utils/returnTo";

/**
 * Start here (§76.3) — "your chart in plain words" for the selected profile.
 *
 * Where the welcome flow lands, and a tile anyone can come back to. No model
 * call: the cards are computed data + reference tables, so the page is instant;
 * the AI enters only through the starter questions, which open Ask with the
 * question already typed.
 */
export const StartPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const checklist = useChecklist();

  const birthDetails = useMemo(() => {
    if (!selectedProfile) return null;
    const b = selectedProfile.birth_details;
    return {
      name: b.name,
      dob: b.dob,
      tob: b.tob,
      place: b.place,
      latitude: parseFloat(b.latitude),
      longitude: parseFloat(b.longitude),
      timezone: parseFloat(b.timezone),
      time_accuracy: b.time_accuracy || "exact",
    };
  }, [selectedProfile]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection", returnHere());
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    onboardingService
      .firstLook(birthDetails, settings.ayanamsa)
      .then((r) => {
        if (cancelled) return;
        setData(r.data);
      })
      .catch((e) => !cancelled && setError(e.response?.data?.detail || t("firstLook.error")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [selectedProfile, birthDetails, settings.ayanamsa, navigate, t]);

  // Ticked once the reading has actually loaded (§76.4). Its own effect, keyed
  // on the data only: `mark` changes identity with every settings write, and in
  // the fetch effect's deps it would refetch on its own tick.
  useEffect(() => {
    if (data) checklist.mark("chart");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  if (!selectedProfile) return null;

  const ask = (key) =>
    navigate("/ask-astrologer", { state: { prefillQuestion: t(`firstLook.starters.${key}`) } });

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Compass size={24} />}
        title={t("firstLook.title")}
        subtitle={t("firstLook.subtitle")}
        accent="saffron"
      />
      <main id="page-content" className="page-main">
        <div className="dashboard-content">
          <ProfileBanner profile={selectedProfile} />
          <ErrorBanner message={error} />
          {loading ? (
            <Card>
              <LoadingState message={t("firstLook.loading")} />
            </Card>
          ) : (
            <FirstLook
              data={data}
              footer={
                <section className="first-look__ask" aria-labelledby="fl-ask">
                  <h2 id="fl-ask">
                    <MessageCircle size={18} aria-hidden="true" /> {t("firstLook.askTitle")}
                  </h2>
                  <p>{t("firstLook.askIntro")}</p>
                  <div className="first-look__starters">
                    {["career", "strengths", "decisions"].map((key) => (
                      <button
                        key={key}
                        type="button"
                        className="first-look__starter"
                        onClick={() => ask(key)}
                      >
                        {t(`firstLook.starters.${key}`)}
                      </button>
                    ))}
                  </div>
                  <p>
                    <Link to="/birth-chart">{t("firstLook.more")} →</Link>
                  </p>
                </section>
              }
            />
          )}
        </div>
      </main>
    </div>
  );
};

export default StartPage;
