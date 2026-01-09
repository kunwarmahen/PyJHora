import React, { createContext, useContext, useState, useEffect } from 'react';

const ProfileContext = createContext();

export const useProfile = () => {
  const context = useContext(ProfileContext);
  if (!context) {
    throw new Error('useProfile must be used within a ProfileProvider');
  }
  return context;
};

export const ProfileProvider = ({ children }) => {
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Load profiles from server
  const loadProfiles = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/profiles/list`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      const data = await response.json();
      if (data.success) {
        setProfiles(data.profiles);
      }
    } catch (err) {
      console.error('Failed to load profiles:', err);
    } finally {
      setLoading(false);
    }
  };

  // Save a new profile
  const saveProfile = async (profileName, birthDetails) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          profile_name: profileName,
          birth_details: birthDetails
        })
      });

      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        return { success: true };
      }
      return { success: false, error: data.message };
    } catch (err) {
      return { success: false, error: 'Failed to save profile' };
    }
  };

  // Update a profile
  const updateProfile = async (profileId, profileName, birthDetails) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/${profileId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          profile_name: profileName,
          birth_details: birthDetails
        })
      });

      const data = await response.json();
      if (data.success) {
        await loadProfiles();
        // If updated profile was selected, update it
        if (selectedProfile?._id === profileId) {
          const updatedProfile = {
            ...selectedProfile,
            profile_name: profileName,
            birth_details: birthDetails
          };
          setSelectedProfile(updatedProfile);
          localStorage.setItem('selectedProfile', JSON.stringify(updatedProfile));
        }
        return { success: true };
      }
      return { success: false, error: data.message };
    } catch (err) {
      return { success: false, error: 'Failed to update profile' };
    }
  };

  // Delete a profile
  const deleteProfile = async (profileId) => {
    try {
      const response = await fetch(`${API_URL}/api/profiles/${profileId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
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
      return { success: false, error: 'Failed to delete profile' };
    }
  };

  // Select a profile
  const selectProfile = (profile) => {
    setSelectedProfile(profile);
    // Store in localStorage for persistence
    localStorage.setItem('selectedProfile', JSON.stringify(profile));
  };

  // Clear selected profile
  const clearProfile = () => {
    setSelectedProfile(null);
    localStorage.removeItem('selectedProfile');
  };

  // Load selected profile from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('selectedProfile');
    if (stored) {
      try {
        setSelectedProfile(JSON.parse(stored));
      } catch (err) {
        console.error('Failed to parse stored profile:', err);
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
    selectProfile,
    clearProfile
  };

  return (
    <ProfileContext.Provider value={value}>
      {children}
    </ProfileContext.Provider>
  );
};
