import React from "react";
import { AlertCircle } from "lucide-react";
import "../styles/Shared.css";

/** Shared inline error banner. Renders nothing when `message` is falsy. */
export const ErrorBanner = ({ message }) => {
  if (!message) return null;
  return (
    // role="alert" so the failure is announced when it appears, rather than
    // sitting silently above a form the user is still filling in (§68.8).
    <div className="error-banner" role="alert">
      <AlertCircle size={20} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
};

export default ErrorBanner;
