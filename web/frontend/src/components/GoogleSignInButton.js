import React, { useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

// Client ID is baked into the build. Must equal the backend's GOOGLE_CLIENT_ID.
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || "";
const GSI_SRC = "https://accounts.google.com/gsi/client";

// Load the Google Identity Services script once, shared across mounts.
let gsiPromise = null;
const loadGsi = () => {
  if (gsiPromise) return gsiPromise;
  gsiPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load Google sign-in"));
    document.head.appendChild(s);
  });
  return gsiPromise;
};

/**
 * Renders Google's official "Sign in with Google" button. Renders nothing when
 * REACT_APP_GOOGLE_CLIENT_ID is unset, so password-only deployments are unaffected.
 * On success it exchanges Google's ID token for our JWT pair and navigates to the
 * profile-selection screen (same as a normal login).
 */
export const GoogleSignInButton = ({ redirectTo = "/profile-selection" }) => {
  const divRef = useRef(null);
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const handleCredential = useCallback(
    async (response) => {
      if (!response?.credential) return;
      const ok = await loginWithGoogle(response.credential, true);
      if (ok) navigate(redirectTo);
    },
    [loginWithGoogle, navigate, redirectTo]
  );

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGsi()
      .then(() => {
        if (cancelled || !divRef.current || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleCredential,
        });
        window.google.accounts.id.renderButton(divRef.current, {
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with",
          logo_alignment: "center",
        });
      })
      .catch((e) => console.error(e));
    return () => {
      cancelled = true;
    };
  }, [handleCredential]);

  if (!GOOGLE_CLIENT_ID) return null;

  return (
    <div className="google-signin">
      <div className="google-signin__divider">
        <span>or</span>
      </div>
      <div className="google-signin__button" ref={divRef} />
    </div>
  );
};

export default GoogleSignInButton;
