import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import {
  User,
  Plus,
  Calendar,
  MapPin,
  Mail,
  Clock,
  Trash2,
  ChevronRight,
  Star,
  Edit2,
  Download,
  Upload,
  CheckSquare,
  Square,
  X,
} from "lucide-react";
import LocationSearch from "../components/LocationSearch";
import MapPicker from "../components/MapPicker";
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
    setDefaultProfile,
    exportProfiles,
    importProfiles,
    selectProfile,
  } = useProfile();
  const fileInputRef = useRef(null);
  const [exportMode, setExportMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState(null);
  const [formData, setFormData] = useState({
    profile_name: "",
    name: "",
    notify_email: "",
    dob: "",
    tob: "",
    place: "",
    latitude: null,
    longitude: null,
    timezone: "5.5",
    time_accuracy: "exact",
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
      notify_email: profile.notify_email || "",
      dob: profile.birth_details.dob,
      tob: profile.birth_details.tob,
      place: profile.birth_details.place,
      latitude: profile.birth_details.latitude,
      longitude: profile.birth_details.longitude,
      timezone: profile.birth_details.timezone,
      time_accuracy: profile.birth_details.time_accuracy || "exact",
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
      time_accuracy: formData.time_accuracy || "exact",
    };

    const notifyEmail = (formData.notify_email || "").trim() || null;
    let result;
    if (editingProfile) {
      result = await updateProfile(
        editingProfile._id, formData.profile_name, birthDetails, notifyEmail);
    } else {
      result = await saveProfile(formData.profile_name, birthDetails, notifyEmail);
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
        time_accuracy: "exact",
      });
    } else {
      setError(result.error || t("profile.errSaveFailed"));
    }
  };

  const handleSelectProfile = (profile) => {
    if (exportMode) {
      toggleSelected(profile._id);
      return;
    }
    selectProfile(profile);
    navigate("/dashboard");
  };

  const toggleSelected = (profileId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(profileId)) next.delete(profileId);
      else next.add(profileId);
      return next;
    });
  };

  const handleDeleteProfile = async (e, profileId) => {
    e.stopPropagation();
    if (window.confirm(t("profile.confirmDelete"))) {
      await deleteProfile(profileId);
    }
  };

  const handleToggleDefault = async (e, profile) => {
    e.stopPropagation();
    await setDefaultProfile(profile._id, !profile.is_default);
  };

  // Enter export-selection mode (all profiles pre-selected for convenience)
  const handleExport = () => {
    if (!profiles.length) {
      window.alert(t("profile.exportEmpty"));
      return;
    }
    setSelectedIds(new Set(profiles.map((p) => p._id)));
    setExportMode(true);
  };

  const cancelExport = () => {
    setExportMode(false);
    setSelectedIds(new Set());
  };

  const toggleSelectAll = () => {
    setSelectedIds((prev) =>
      prev.size === profiles.length ? new Set() : new Set(profiles.map((p) => p._id)),
    );
  };

  const handleExportSelected = () => {
    const chosen = profiles.filter((p) => selectedIds.has(p._id));
    if (!chosen.length) return;
    exportProfiles(chosen);
    cancelExport();
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-importing the same file
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const result = await importProfiles(parsed);
      if (result.success) {
        window.alert(t("profile.importDone", { imported: result.imported, skipped: result.skipped }));
      } else {
        window.alert(result.error || t("profile.importFailed"));
      }
    } catch (err) {
      window.alert(t("profile.importFailed"));
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
                {exportMode ? (
                  <div className="profiles-toolbar export-mode">
                    <span className="export-hint">
                      {t("profile.exportSelectHint", { count: selectedIds.size })}
                    </span>
                    <button className="toolbar-btn" onClick={toggleSelectAll}>
                      {selectedIds.size === profiles.length
                        ? t("profile.selectNone")
                        : t("profile.selectAll")}
                    </button>
                    <button className="toolbar-btn" onClick={cancelExport}>
                      <X size={16} />
                      <span>{t("profile.cancel")}</span>
                    </button>
                    <button
                      className="toolbar-btn primary"
                      onClick={handleExportSelected}
                      disabled={!selectedIds.size}
                    >
                      <Download size={16} />
                      <span>{t("profile.exportSelected", { count: selectedIds.size })}</span>
                    </button>
                  </div>
                ) : (
                  <div className="profiles-toolbar">
                    <button className="toolbar-btn" onClick={handleImportClick}>
                      <Upload size={16} />
                      <span>{t("profile.import")}</span>
                    </button>
                    <button
                      className="toolbar-btn"
                      onClick={handleExport}
                      disabled={!profiles.length}
                    >
                      <Download size={16} />
                      <span>{t("profile.export")}</span>
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="application/json,.json"
                      onChange={handleImportFile}
                      style={{ display: "none" }}
                    />
                  </div>
                )}
                <div className="profiles-grid">
                  {profiles.map((profile, index) => (
                    <div
                      key={profile._id}
                      className={`profile-card fade-in stagger-${Math.min(index + 1, 5)}${
                        exportMode && selectedIds.has(profile._id) ? " selected-for-export" : ""
                      }`}
                      onClick={() => handleSelectProfile(profile)}
                    >
                      <div className="profile-card-header">
                        <div className="profile-avatar">
                          <User size={24} />
                        </div>
                        {exportMode ? (
                          <div
                            className="export-checkbox"
                            aria-label={t("profile.exportSelectAria")}
                          >
                            {selectedIds.has(profile._id) ? (
                              <CheckSquare size={22} />
                            ) : (
                              <Square size={22} />
                            )}
                          </div>
                        ) : (
                          <div style={{ display: "flex", gap: "8px" }}>
                            <button
                              className={`default-btn${profile.is_default ? " is-default" : ""}`}
                              onClick={(e) => handleToggleDefault(e, profile)}
                              aria-label={
                                profile.is_default
                                  ? t("profile.unsetDefaultAria")
                                  : t("profile.setDefaultAria")
                              }
                              title={
                                profile.is_default
                                  ? t("profile.unsetDefaultAria")
                                  : t("profile.setDefaultAria")
                              }
                            >
                              <Star
                                size={16}
                                fill={profile.is_default ? "currentColor" : "none"}
                              />
                            </button>
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
                        )}
                      </div>
                      <h3>
                        {profile.profile_name}
                        {profile.is_default && (
                          <span className="default-badge">
                            <Star size={12} fill="currentColor" />
                            {t("profile.defaultBadge")}
                          </span>
                        )}
                      </h3>
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
                        {profile.notify_email && (
                          <div className="detail-item">
                            <Mail size={14} />
                            <span>{profile.notify_email}</span>
                            {profile.notify_status &&
                              profile.notify_status !== "owner" && (
                                <span
                                  className={`digest-status digest-status--${profile.notify_status}`}
                                >
                                  {t(`profile.digestStatus.${profile.notify_status}`)}
                                </span>
                              )}
                          </div>
                        )}
                      </div>
                      <div className="select-indicator">
                        <span>
                          {exportMode
                            ? selectedIds.has(profile._id)
                              ? t("profile.selectedForExport")
                              : t("profile.tapToSelect")
                            : t("profile.continueWith")}
                        </span>
                        <ChevronRight size={18} />
                      </div>
                    </div>
                  ))}

                  <div
                    className={`profile-card create-new-card fade-in stagger-${Math.min(profiles.length + 1, 5)}`}
                    onClick={() => setShowCreateForm(true)}
                    style={{ display: exportMode ? "none" : undefined }}
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
                    time_accuracy: "exact",
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

              <div className="form-group">
                <label>
                  <Mail size={18} />
                  {t("profile.notifyEmail")}
                </label>
                <input
                  type="email"
                  name="notify_email"
                  value={formData.notify_email}
                  onChange={handleInputChange}
                  placeholder={t("profile.notifyEmailPlaceholder")}
                />
                <small>{t("profile.notifyEmailHint")}</small>
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
                  <Clock size={18} />
                  {t("profile.timeAccuracy")}
                </label>
                <select
                  name="time_accuracy"
                  value={formData.time_accuracy}
                  onChange={handleInputChange}
                >
                  <option value="exact">{t("profile.accuracyExact")}</option>
                  <option value="approximate">{t("profile.accuracyApproximate")}</option>
                  <option value="unknown">{t("profile.accuracyUnknown")}</option>
                </select>
                {formData.time_accuracy !== "exact" && (
                  <p className="form-hint">{t("profile.accuracyHint")}</p>
                )}
              </div>

              <div className="form-group">
                <label>
                  <MapPin size={18} />
                  {t("profile.placeOfBirth")} *
                </label>
                <LocationSearch onLocationSelect={handleLocationSelect} />
                <MapPicker
                  onLocationSelect={handleLocationSelect}
                  latitude={formData.latitude}
                  longitude={formData.longitude}
                />
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
