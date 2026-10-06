import React, { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Calendar, Clock, MapPin, ArrowLeft, ArrowRight, AlertCircle } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { onboardingService } from "../services/api";
import LocationSearch from "../components/LocationSearch";
import MapPicker from "../components/MapPicker";
import { SITE_TITLE } from "../config/branding";
import { loadHandoff, clearHandoff } from "../config/previewHandoff";
import { todayISO } from "../utils/format";
import "../styles/Auth.css";
import "../styles/Welcome.css";

// "I'm not sure" saves noon with time_accuracy "unknown": the time field is
// required everywhere else, and noon keeps the Moon within half a day of any real
// time. The first look then withholds what the clock decides (backend
// get_first_look), so the guess is never presented as a fact.
const UNKNOWN_TIME = "12:00:00";

/**
 * Welcome (§76.2) — three questions, one per screen, for an account with no
 * profile yet: when, what time, where. Timezone and coordinates come from the
 * place search; the profile is named after the account; notify email, current
 * location and the rest wait for Settings. Lands on /start.
 *
 * The full form (ProfileSelectionPage) stays for second profiles, imports and
 * anyone who wants every field.
 */
export const WelcomePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { saveProfile, loadProfiles, selectProfile } = useProfile();

  // Details from the landing page's preview, if this tab has them (§76.7).
  const handoff = useMemo(() => loadHandoff(), []);
  const [step, setStep] = useState(handoff ? 3 : 0); // 3 = confirm a handed-over set
  const [dob, setDob] = useState(handoff?.dob || "");
  const [tob, setTob] = useState(handoff && handoff.time_accuracy !== "unknown" ? handoff.tob : "");
  const [unknownTime, setUnknownTime] = useState(handoff?.time_accuracy === "unknown");
  const [place, setPlace] = useState(
    handoff
      ? {
          place: handoff.place || "",
          latitude: Number(handoff.latitude),
          longitude: Number(handoff.longitude),
          timezone: Number(handoff.timezone),
        }
      : null
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const name = (user?.name || user?.username || "").trim() || t("welcome.defaultName");

  const finish = async () => {
    setSaving(true);
    setError("");
    const birthDetails = {
      name,
      dob,
      tob: unknownTime ? UNKNOWN_TIME : tob.length === 5 ? `${tob}:00` : tob,
      place: place.place,
      latitude: place.latitude,
      longitude: place.longitude,
      timezone: place.timezone,
      time_accuracy: unknownTime ? "unknown" : "exact",
    };
    const result = await saveProfile(name, birthDetails);
    if (!result.success) {
      setSaving(false);
      setError(result.error || t("welcome.saveError"));
      return;
    }
    const list = (await loadProfiles()) || [];
    const mine = list.find((p) => p.profile_name === name) || list[list.length - 1];
    if (mine) selectProfile(mine);
    clearHandoff();
    Promise.resolve(onboardingService.welcomeDone()).catch(() => {});
    navigate("/start", { replace: true });
  };

  const steps = [
    {
      icon: <Calendar size={28} />,
      title: t("welcome.dateTitle"),
      hint: t("welcome.dateHint"),
      body: (
        <input
          type="date"
          className="welcome__input"
          value={dob}
          max={todayISO()}
          onChange={(e) => setDob(e.target.value)}
          aria-label={t("welcome.dateTitle")}
          autoFocus
        />
      ),
      ready: /^\d{4}-\d{2}-\d{2}$/.test(dob),
    },
    {
      icon: <Clock size={28} />,
      title: t("welcome.timeTitle"),
      hint: t("welcome.timeHint"),
      body: (
        <>
          <input
            type="time"
            className="welcome__input"
            value={tob}
            onChange={(e) => {
              setTob(e.target.value);
              setUnknownTime(false);
            }}
            aria-label={t("welcome.timeTitle")}
            disabled={unknownTime}
          />
          <button
            type="button"
            className={`welcome__unsure${unknownTime ? " is-on" : ""}`}
            aria-pressed={unknownTime}
            onClick={() => setUnknownTime((v) => !v)}
          >
            {t("welcome.notSure")}
          </button>
          {unknownTime && <p className="welcome__note">{t("welcome.notSureNote")}</p>}
        </>
      ),
      ready: unknownTime || /^\d{1,2}:\d{2}/.test(tob),
    },
    {
      icon: <MapPin size={28} />,
      title: t("welcome.placeTitle"),
      hint: t("welcome.placeHint"),
      body: (
        <>
          <LocationSearch onLocationSelect={setPlace} />
          <MapPicker
            onLocationSelect={setPlace}
            latitude={place?.latitude}
            longitude={place?.longitude}
          />
          {place?.place && (
            <p className="welcome__picked">
              <MapPin size={16} aria-hidden="true" /> {place.place}
            </p>
          )}
        </>
      ),
      ready: !!place && Number.isFinite(place.latitude) && Number.isFinite(place.timezone),
    },
  ];

  const confirming = step === 3;
  const current = steps[step];
  const last = step === steps.length - 1;

  return (
    <div className="auth-container">
      <main id="page-content" className="auth-card welcome">
        <h1>{SITE_TITLE}</h1>
        {confirming ? (
          <>
            <p className="subtitle">{t("welcome.handoffTitle")}</p>
            <ul className="welcome__summary">
              <li>
                <Calendar size={16} aria-hidden="true" /> {dob}
              </li>
              <li>
                <Clock size={16} aria-hidden="true" />{" "}
                {unknownTime ? t("welcome.timeUnknown") : tob.slice(0, 5)}
              </li>
              <li>
                <MapPin size={16} aria-hidden="true" /> {place?.place}
              </li>
            </ul>
            {error && (
              <div className="error-message">
                <AlertCircle size={16} /> <span>{error}</span>
              </div>
            )}
            <button type="button" className="submit-btn" onClick={finish} disabled={saving}>
              {saving ? t("welcome.saving") : t("welcome.finish")}
            </button>
            <button type="button" className="welcome__back" onClick={() => setStep(0)}>
              {t("welcome.change")}
            </button>
          </>
        ) : (
          <>
            <p className="subtitle">{t("welcome.step", { n: step + 1, total: steps.length })}</p>
            <div className="welcome__progress" aria-hidden="true">
              {steps.map((s, i) => (
                <span key={s.title} className={i <= step ? "is-on" : undefined} />
              ))}
            </div>
            <section className="welcome__step" aria-labelledby="welcome-q">
              <div className="welcome__icon">{current.icon}</div>
              <h2 id="welcome-q">{current.title}</h2>
              <p className="welcome__hint">{current.hint}</p>
              {current.body}
            </section>
            {error && (
              <div className="error-message">
                <AlertCircle size={16} /> <span>{error}</span>
              </div>
            )}
            <div className="welcome__nav">
              {step > 0 && (
                <button type="button" className="welcome__back" onClick={() => setStep(step - 1)}>
                  <ArrowLeft size={16} /> {t("welcome.back")}
                </button>
              )}
              <button
                type="button"
                className="submit-btn"
                disabled={!current.ready || saving}
                onClick={() => (last ? finish() : setStep(step + 1))}
              >
                {last ? (saving ? t("welcome.saving") : t("welcome.finish")) : t("welcome.next")}{" "}
                {!last && <ArrowRight size={16} />}
              </button>
            </div>
          </>
        )}
        <p className="auth-link">
          <Link to="/profile-selection">{t("welcome.fullForm")}</Link>
        </p>
      </main>
    </div>
  );
};

export default WelcomePage;
