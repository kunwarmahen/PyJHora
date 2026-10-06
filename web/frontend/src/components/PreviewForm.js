import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapPin } from "lucide-react";
import { onboardingService } from "../services/api";
import LocationSearch from "./LocationSearch";
import { FirstLook } from "./FirstLook";
import { saveHandoff } from "../config/previewHandoff";
import { todayISO } from "../utils/format";
import "../styles/PreviewForm.css";

const UNKNOWN_TIME = "12:00:00";

/**
 * Try before signing up (§76.7) — the landing page's "see your chart free".
 *
 * Takes the same three answers as the welcome flow and shows the same
 * plain-words cards (`FirstLook`), with no account. Nothing is stored on the
 * server (the public route computes and forgets); the details wait in this tab
 * (config/previewHandoff.js) so that signing up carries them straight into the
 * welcome flow. The AI stays behind login — the card's next step is sign-up.
 */
export const PreviewForm = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [dob, setDob] = useState("");
  const [tob, setTob] = useState("");
  const [unknownTime, setUnknownTime] = useState(false);
  const [place, setPlace] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ready =
    /^\d{4}-\d{2}-\d{2}$/.test(dob) &&
    (unknownTime || /^\d{1,2}:\d{2}/.test(tob)) &&
    place &&
    Number.isFinite(place.latitude);

  const details = () => ({
    name: "Preview",
    dob,
    tob: unknownTime ? UNKNOWN_TIME : tob.length === 5 ? `${tob}:00` : tob,
    place: place?.place || "",
    latitude: place?.latitude,
    longitude: place?.longitude,
    timezone: place?.timezone,
    time_accuracy: unknownTime ? "unknown" : "exact",
  });

  const submit = async (e) => {
    e.preventDefault();
    if (!ready) return;
    setLoading(true);
    setError("");
    try {
      const r = await onboardingService.previewFirstLook(details());
      setData(r.data);
    } catch (err) {
      setError(
        err.response?.status === 429
          ? t("preview.busy")
          : err.response?.data?.detail || t("firstLook.error")
      );
    } finally {
      setLoading(false);
    }
  };

  const signUp = () => {
    saveHandoff(details());
    navigate("/register");
  };

  return (
    <div className="preview">
      <form className="preview__form" onSubmit={submit}>
        <label>
          <span>{t("preview.date")}</span>
          <input
            type="date"
            value={dob}
            max={todayISO()}
            onChange={(e) => setDob(e.target.value)}
          />
        </label>
        <label>
          <span>{t("preview.time")}</span>
          <input
            type="time"
            value={tob}
            disabled={unknownTime}
            onChange={(e) => setTob(e.target.value)}
          />
          <button
            type="button"
            className={`preview__unsure${unknownTime ? " is-on" : ""}`}
            aria-pressed={unknownTime}
            onClick={() => setUnknownTime((v) => !v)}
          >
            {t("welcome.notSure")}
          </button>
        </label>
        <div className="preview__place">
          <span>{t("preview.place")}</span>
          <LocationSearch onLocationSelect={setPlace} />
          {place?.place && (
            <small>
              <MapPin size={14} aria-hidden="true" /> {place.place}
            </small>
          )}
        </div>
        <button className="btn btn-primary" type="submit" disabled={!ready || loading}>
          {loading ? t("firstLook.loading") : t("preview.submit")}
        </button>
        <p className="preview__privacy">{t("preview.privacy")}</p>
      </form>

      {error && (
        <p className="preview__error" role="alert">
          {error}
        </p>
      )}

      {data && (
        <div className="preview__result">
          <FirstLook
            data={data}
            footer={
              <div className="preview__cta">
                <p>{t("preview.ctaText")}</p>
                <button type="button" className="btn btn-primary" onClick={signUp}>
                  {t("preview.cta")}
                </button>
              </div>
            }
          />
        </div>
      )}
    </div>
  );
};

export default PreviewForm;
