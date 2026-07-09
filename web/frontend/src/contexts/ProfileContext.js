import React, { createContext, useContext, useState, useEffect } from "react";
import { API_URL } from "../services/api";

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

  // Load profiles from server
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
      }
    } catch (err) {
      console.error("Failed to load profiles:", err);
    } finally {
      setLoading(false);
    }
  };

  // Save a new profile
  const saveProfile = async (profileName, birthDetails) => {
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

  // Update a profile
  const updateProfile = async (profileId, profileName, birthDetails) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/${profileId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          profile_name: profileName,
          birth_details: birthDetails,
        }),
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

  // Export all profiles to a downloadable JSON file
  const exportProfiles = () => {
    const envelope = {
      app: "Jyotir AI",
      type: "profiles",
      version: 1,
      exported_at: new Date().toISOString(),
      count: profiles.length,
      profiles: profiles.map((p) => ({
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
    return { success: true, count: profiles.length };
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

  const value = {
    selectedProfile,
    profiles,
    loading,
    loadProfiles,
    saveProfile,
    updateProfile,
    deleteProfile,
    exportProfiles,
    importProfiles,
    selectProfile,
    clearProfile,
  };

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
};
