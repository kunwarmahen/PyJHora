import React, { createContext, useContext, useState, useEffect } from "react";
import { API_URL } from "../services/api";
import {
  readLastProfileId,
  readStartupProfileMode,
  resolveStartupProfile,
} from "../config/startupProfile";

const ProfileContext = createContext();

export const useProfile = () => {
  const context = useContext(ProfileContext);
  if (!context) {
    throw new Error("useProfile must be used within a ProfileProvider");
  }
  return context;
};

export const ProfileProvider = ({ children }) => {
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load profiles from server. Returns the list as well as storing it: callers
  // that must act on it immediately (resumeProfile) can't wait for the state.
  const loadProfiles = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/profiles/list`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });
      const data = await response.json();
      if (data.success) {
        setProfiles(data.profiles);
        return data.profiles;
      }
      return [];
    } catch (err) {
      console.error("Failed to load profiles:", err);
      return [];
    } finally {
      setLoading(false);
    }
  };

  // Save a new profile
  const saveProfile = async (profileName, birthDetails, notifyEmail = null,
                             digestFrequency = null) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          profile_name: profileName,
          birth_details: birthDetails,
          notify_email: notifyEmail || null,
          digest_frequency: digestFrequency || null,
        }),
      });

      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        return { success: true };
      }
      return { success: false, error: data.message };
    } catch (err) {
      return { success: false, error: "Failed to save profile" };
    }
  };

  // Update a profile. `notifyEmail` is only sent when explicitly passed
  // (undefined = leave the stored value untouched), so callers that just tweak
  // birth details — e.g. the rectification page — never wipe the digest email.
  const updateProfile = async (profileId, profileName, birthDetails,
                               notifyEmail = undefined, digestFrequency = undefined) => {
    try {
      const body = {
        profile_name: profileName,
        birth_details: birthDetails,
      };
      if (notifyEmail !== undefined) body.notify_email = notifyEmail || null;
      if (digestFrequency !== undefined) body.digest_frequency = digestFrequency || null;

      const response = await fetch(`${API_URL}/api/profiles/${profileId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        // If updated profile was selected, update it
        if (selectedProfile?._id === profileId) {
          const updatedProfile = {
            ...selectedProfile,
            profile_name: profileName,
            birth_details: birthDetails,
            ...(notifyEmail !== undefined ? { notify_email: notifyEmail || null } : {}),
            ...(digestFrequency !== undefined
              ? { digest_frequency: digestFrequency || null }
              : {}),
          };
          setSelectedProfile(updatedProfile);
          localStorage.setItem("selectedProfile", JSON.stringify(updatedProfile));
        }
        return { success: true };
      }
      return { success: false, error: data.message };
    } catch (err) {
      return { success: false, error: "Failed to update profile" };
    }
  };

  // Delete a profile
  const deleteProfile = async (profileId) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/${profileId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        // If deleted profile was selected, clear selection
        if (selectedProfile?._id === profileId) {
          setSelectedProfile(null);
        }
        return { success: true };
      }
      return { success: false, error: data.message };
    } catch (err) {
      return { success: false, error: "Failed to delete profile" };
    }
  };

  // Mark a profile as the default (or clear it). At most one is ever default.
  const setDefaultProfile = async (profileId, isDefault = true) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/${profileId}/default`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ is_default: isDefault }),
      });
      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        return { success: true };
      }
      return { success: false, error: data.detail || data.message };
    } catch (err) {
      return { success: false, error: "Failed to update default profile" };
    }
  };

  // Export profiles to a downloadable JSON file. Pass a subset to export only
  // those; omit to export all.
  const exportProfiles = (subset) => {
    const list = Array.isArray(subset) && subset.length ? subset : profiles;
    const envelope = {
      app: "Jyotir AI",
      type: "profiles",
      version: 1,
      exported_at: new Date().toISOString(),
      count: list.length,
      profiles: list.map((p) => ({
        profile_name: p.profile_name,
        birth_details: p.birth_details,
        is_default: p.is_default || false,
      })),
    };
    const blob = new Blob([JSON.stringify(envelope, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    a.href = url;
    a.download = `jyotirai-profiles-${stamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { success: true, count: list.length };
  };

  // Import profiles from a parsed JSON file (envelope or bare array)
  const importProfiles = async (parsed) => {
    const list = Array.isArray(parsed) ? parsed : parsed?.profiles;
    if (!Array.isArray(list) || list.length === 0) {
      return { success: false, error: "No profiles found in file" };
    }
    // Keep only the fields the backend expects
    const clean = list
      .filter((p) => p && p.profile_name && p.birth_details)
      .map((p) => ({
        profile_name: p.profile_name,
        birth_details: p.birth_details,
        is_default: false,
      }));
    if (clean.length === 0) {
      return { success: false, error: "File does not contain valid profiles" };
    }
    try {
      const response = await fetch(`${API_URL}/api/profiles/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ profiles: clean }),
      });
      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        return { success: true, imported: data.imported, skipped: data.skipped };
      }
      return { success: false, error: data.detail || data.message };
    } catch (err) {
      return { success: false, error: "Failed to import profiles" };
    }
  };

  // Select a profile
  const selectProfile = (profile) => {
    setSelectedProfile(profile);
    // Store in localStorage for persistence
    localStorage.setItem("selectedProfile", JSON.stringify(profile));
  };

  // Clear selected profile
  const clearProfile = () => {
    setSelectedProfile(null);
    localStorage.removeItem("selectedProfile");
  };

  /**
   * Where to land someone who has just arrived (login, register, reset, or the
   * app's root). Selects the resumed profile as a side effect and returns the
   * path to navigate to: the dashboard when a profile resolved, the picker when
   * one didn't. See config/startupProfile.js for the rule.
   *
   * The mode is read from localStorage rather than SettingsContext on purpose:
   * on login the context is still pulling the server copy of the preferences, so
   * reading it here would race that fetch and could ask a "resume" user to pick.
   */
  const resumeProfile = async () => {
    const list = await loadProfiles();
    const target = resolveStartupProfile(list, {
      mode: readStartupProfileMode(),
      lastId: readLastProfileId(),
    });
    if (!target) return "/profile-selection";
    selectProfile(target);
    return "/dashboard";
  };

  // Load selected profile from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem("selectedProfile");
    if (stored) {
      try {
        setSelectedProfile(JSON.parse(stored));
      } catch (err) {
        console.error("Failed to parse stored profile:", err);
      }
    }
  }, []);

  // Deep-link: any page opened with ?profile=<id> selects that profile. This is
  // what the per-person buttons in the digest emails point at, so "Open Naina's
  // day" lands on her chart, not whoever was last selected.
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("profile");
    if (!wanted) return;
    (async () => {
      const list = await loadProfiles();
      const match = list.find((p) => p._id === wanted);
      if (match) selectProfile(match);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = {
    selectedProfile,
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
    clearProfile,
    resumeProfile,
  };

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
};
