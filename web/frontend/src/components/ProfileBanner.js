import React from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { User, Star } from "lucide-react";
import { formatDate, orDash } from "../utils/format";

/**
 * Shared profile banner shown under the navbar on every chart page.
 * Renders nothing when no profile is selected.
 *
 * onChangeProfile: optional override for the "Change Chart" button
 * (Dashboard clears the profile first; other pages just navigate).
 * actions: optional custom right-side content; when provided it replaces the
 * default "Change Chart" button entirely (e.g. the Ask page's action group).
 */
export const ProfileBanner = ({ profile, onChangeProfile, changeIcon, actions }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  if (!profile) return null;

  const handleChange = onChangeProfile || (() => navigate("/profile-selection"));
  const details = profile.birth_details || {};

  return (
    <div className="profile-banner fade-in">
      <div className="profile-banner-left">
        <div className="profile-avatar-large">
          <User size={32} />
        </div>
        <div className="profile-info">
          <h2>{profile.profile_name}</h2>
          <div className="profile-meta">
            <span>{details.name || t("common.anonymous")}</span>
            <span className="separator">•</span>
            <span>{formatDate(details.dob)}</span>
            <span className="separator">•</span>
            <span>{orDash(details.place)}</span>
          </div>
        </div>
      </div>
      {actions || (
        <button onClick={handleChange} className="change-profile-btn">
          {changeIcon || <Star size={16} />}
          <span>{t("common.changeChart")}</span>
        </button>
      )}
    </div>
  );
};

export default ProfileBanner;
