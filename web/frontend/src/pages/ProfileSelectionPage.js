import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import {
  User,
  Plus,
  Calendar,
  MapPin,
  Clock,
  Trash2,
  ChevronRight,
  Star,
  Edit2,
} from "lucide-react";
import LocationSearch from "../components/LocationSearch";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import "../styles/ProfileSelection.css";

export const ProfileSelectionPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const {
    profiles,
    loading,
    loadProfiles,
    saveProfile,
    updateProfile,
    deleteProfile,
    selectProfile,
  } = useProfile();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState(null);
  const [formData, setFormData] = useState({
    profile_name: "",
    name: "",
    dob: "",
    tob: "",
    place: "",
    latitude: null,
    longitude: null,
    timezone: "5.5",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleLocationSelect = (location) => {
    setFormData((prev) => ({
      ...prev,
      place: location.place,
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: location.timezone,
    }));
  };

  const handleEditProfile = (e, profile) => {
    e.stopPropagation();
    setEditingProfile(profile);
    setFormData({
      profile_name: profile.profile_name,
      name: profile.birth_details.name,
      dob: profile.birth_details.dob,
      tob: profile.birth_details.tob,
      place: profile.birth_details.place,
      latitude: profile.birth_details.latitude,
      longitude: profile.birth_details.longitude,
      timezone: profile.birth_details.timezone,
    });
    setShowCreateForm(true);
  };

  const handleCreateProfile = async (e) => {
    e.preventDefault();
    if (!formData.profile_name.trim()) {
      setError(t("profile.errEnterName"));
      return;
    }
    if (
      formData.latitude == null ||
      formData.longitude == null ||
      formData.latitude === "" ||
      formData.longitude === ""
    ) {
      setError(t("profile.errSelectPlace"));
      return;
    }

    setSaving(true);
    setError("");

    const birthDetails = {
      name: formData.name,
      dob: formData.dob,
      tob: formData.tob,
      place: formData.place,
      latitude: formData.latitude ? parseFloat(formData.latitude) : null,
      longitude: formData.longitude ? parseFloat(formData.longitude) : null,
      timezone: parseFloat(formData.timezone),
    };

    let result;
    if (editingProfile) {
      result = await updateProfile(editingProfile._id, formData.profile_name, birthDetails);
    } else {
      result = await saveProfile(formData.profile_name, birthDetails);
    }
    setSaving(false);

    if (result.success) {
      setShowCreateForm(false);
      setEditingProfile(null);
      setFormData({
        profile_name: "",
        name: "",
        dob: "",
        tob: "",
        place: "",
        latitude: null,
        longitude: null,
        timezone: "5.5",
      });
    } else {
      setError(result.error || t("profile.errSaveFailed"));
    }
  };

  const handleSelectProfile = (profile) => {
    selectProfile(profile);
    navigate("/dashboard");
  };

  const handleDeleteProfile = async (e, profileId) => {
    e.stopPropagation();
    if (window.confirm(t("profile.confirmDelete"))) {
      await deleteProfile(profileId);
    }
  };

  const timezones = [
    { value: "-12", label: "UTC-12 (Baker Island)" },
    { value: "-11", label: "UTC-11 (Samoa)" },
    { value: "-10", label: "UTC-10 (Hawaii)" },
    { value: "-8", label: "UTC-8 (PST)" },
    { value: "-5", label: "UTC-5 (EST)" },
    { value: "0", label: "UTC-0 (GMT)" },
    { value: "1", label: "UTC+1 (CET)" },
    { value: "5.5", label: "UTC+5:30 (IST - India)" },
    { value: "8", label: "UTC+8 (CST - China)" },
    { value: "9", label: "UTC+9 (JST)" },
  ];

  return (
    <div className="profile-selection-page mandala-bg">
      <div className="profile-lang-switch">
        <LanguageSwitcher />
      </div>
      <div className="profile-selection-container">
        <div className="page-header-section fade-in">
          <div className="mandala-icon">
            <Star size={48} />
          </div>
          <h1 className="text-gradient">{t("profile.selectTitle")}</h1>
          <p className="subtitle">{t("profile.selectSubtitle")}</p>
        </div>

        {!showCreateForm ? (
          <div className="profiles-section">
            {loading ? (
              <div className="loading-state">
                <div className="spinner"></div>
                <p>{t("profile.loading")}</p>
              </div>
            ) : (
              <>
                <div className="profiles-grid">
                  {profiles.map((profile, index) => (
                    <div
                      key={profile._id}
                      className={`profile-card fade-in stagger-${Math.min(index + 1, 5)}`}
                      onClick={() => handleSelectProfile(profile)}
                    >
                      <div className="profile-card-header">
                        <div className="profile-avatar">
                          <User size={24} />
                        </div>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="edit-btn"
                            onClick={(e) => handleEditProfile(e, profile)}
                            aria-label={t("profile.editAria")}
                          >
                            <Edit2 size={16} />
                          </button>
                          <button
                            className="delete-btn"
                            onClick={(e) => handleDeleteProfile(e, profile._id)}
                            aria-label={t("profile.deleteAria")}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                      <h3>{profile.profile_name}</h3>
                      <div className="profile-details">
                        <div className="detail-item">
                          <User size={14} />
                          <span>{profile.birth_details.name || t("common.anonymous")}</span>
                        </div>
                        <div className="detail-item">
                          <Calendar size={14} />
                          <span>{formatDate(profile.birth_details.dob)}</span>
                        </div>
                        <div className="detail-item">
                          <Clock size={14} />
                          <span>{orDash(profile.birth_details.tob)}</span>
                        </div>
                        <div className="detail-item">
                          <MapPin size={14} />
                          <span>{orDash(profile.birth_details.place)}</span>
                        </div>
                      </div>
                      <div className="select-indicator">
                        <span>{t("profile.continueWith")}</span>
                        <ChevronRight size={18} />
                      </div>
                    </div>
                  ))}

                  <div
                    className={`profile-card create-new-card fade-in stagger-${Math.min(profiles.length + 1, 5)}`}
                    onClick={() => setShowCreateForm(true)}
                  >
                    <div className="create-icon">
                      <Plus size={48} />
                    </div>
                    <h3>{t("profile.createNew")}</h3>
                    <p>{t("profile.createNewSub")}</p>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="create-profile-form fade-in">
            <div className="form-header">
              <h2>{editingProfile ? t("profile.editTitle") : t("profile.createTitle")}</h2>
              <button
                className="back-btn"
                onClick={() => {
                  setShowCreateForm(false);
                  setEditingProfile(null);
                  setFormData({
                    profile_name: "",
                    name: "",
                    dob: "",
                    tob: "",
                    place: "",
                    latitude: null,
                    longitude: null,
                    timezone: "5.5",
                  });
                }}
              >
                {t("profile.backToProfiles")}
              </button>
            </div>

            <form onSubmit={handleCreateProfile}>
              <div className="form-group">
                <label>
                  <Star size={18} />
                  {t("profile.profileName")} *
                </label>
                <input
                  type="text"
                  name="profile_name"
                  value={formData.profile_name}
                  onChange={handleInputChange}
                  placeholder={t("profile.profileNamePlaceholder")}
                  required
                />
                <small>{t("profile.profileNameHint")}</small>
              </div>

              <div className="form-group">
                <label>
                  <User size={18} />
                  {t("profile.fullName")}
                </label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder={t("profile.fullNamePlaceholder")}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>
                    <Calendar size={18} />
                    {t("common.dateOfBirth")} *
                  </label>
                  <input
                    type="date"
                    name="dob"
                    value={formData.dob}
                    onChange={handleInputChange}
                    required
                  />
                </div>

                <div className="form-group">
                  <label>
                    <Clock size={18} />
                    {t("common.timeOfBirth")} *
                  </label>
                  <input
                    type="time"
                    name="tob"
                    value={formData.tob}
                    onChange={handleInputChange}
                    step="1"
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label>
                  <MapPin size={18} />
                  {t("profile.placeOfBirth")} *
                </label>
                <LocationSearch onLocationSelect={handleLocationSelect} />
                {formData.latitude && formData.longitude && (
                  <div className="location-info">
                    <MapPin size={16} />
                    <div>
                      <strong>{formData.place}</strong>
                      <br />
                      <small>
                        Lat: {formData.latitude}°, Lon: {formData.longitude}°, TZ: UTC+
                        {formData.timezone}
                      </small>
                    </div>
                  </div>
                )}
              </div>

              {/* Coordinates & timezone are auto-filled from the location search above.
                  These fields are an optional manual override for advanced users. */}
              <details className="advanced-coordinates">
                <summary>{t("profile.advancedToggle")}</summary>
                <div className="form-row">
                  <div className="form-group">
                    <label>{t("profile.latitude")}</label>
                    <input
                      type="number"
                      name="latitude"
                      value={formData.latitude ?? ""}
                      onChange={handleInputChange}
                      placeholder={t("profile.autoFilled")}
                      step="0.0001"
                    />
                  </div>

                  <div className="form-group">
                    <label>{t("profile.longitude")}</label>
                    <input
                      type="number"
                      name="longitude"
                      value={formData.longitude ?? ""}
                      onChange={handleInputChange}
                      placeholder={t("profile.autoFilled")}
                      step="0.0001"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label>{t("profile.timezoneLabel")}</label>
                  <select name="timezone" value={formData.timezone} onChange={handleInputChange}>
                    {timezones.map((tz) => (
                      <option key={tz.value} value={tz.value}>
                        {tz.label}
                      </option>
                    ))}
                  </select>
                </div>
              </details>

              {error && <div className="error-message">{error}</div>}

              <button type="submit" className="submit-btn" disabled={saving}>
                {saving
                  ? editingProfile
                    ? t("profile.updating")
                    : t("profile.creating")
                  : editingProfile
                    ? t("profile.update")
                    : t("profile.create")}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
