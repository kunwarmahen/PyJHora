import React from "react";
import { AlertCircle } from "lucide-react";
import "../styles/Shared.css";

/** Shared inline error banner. Renders nothing when `message` is falsy. */
export const ErrorBanner = ({ message }) => {
  if (!message) return null;
  return (
    <div className="error-banner">
      <AlertCircle size={20} />
      <span>{message}</span>
    </div>
  );
};

export default ErrorBanner;
