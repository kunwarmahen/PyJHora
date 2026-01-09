import React, { createContext, useState, useContext, useEffect } from "react";
import { authService } from "../services/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      loadUserProfile();
    } else {
      setIsLoading(false);
    }
  }, []);

  const loadUserProfile = async () => {
    try {
      const response = await authService.getProfile();
      setUser(response.data);
      setError(null);
    } catch (err) {
      console.error("Failed to load profile:", err);
      localStorage.removeItem("access_token");
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const getErrorMessage = (err) => {
    if (typeof err === "string") {
      return err;
    }
    if (err?.response?.data?.detail) {
      const detail = err.response.data.detail;
      if (typeof detail === "string") {
        return detail;
      }
      return JSON.stringify(detail);
    }
    return "An error occurred";
  };

  const login = async (username, password) => {
    setIsLoading(true);
    try {
      const response = await authService.login(username, password);
      localStorage.setItem("access_token", response.data.access_token);
      await loadUserProfile();
      return true;
    } catch (err) {
      setError(getErrorMessage(err));
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (username, email, password) => {
    setIsLoading(true);
    try {
      const response = await authService.register(username, email, password);
      localStorage.setItem("access_token", response.data.access_token);
      await loadUserProfile();
      return true;
    } catch (err) {
      setError(getErrorMessage(err));
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    setError(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, isLoading, error, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
