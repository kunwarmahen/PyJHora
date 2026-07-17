import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useProfile } from "../contexts/ProfileContext";

/**
 * The app's root: send an arriving user to their resumed profile's dashboard, or
 * to the picker. Mounted at "/" so that reopening the app with a live session —
 * not just a fresh login — resumes too. Which is the common case: the PWA icon
 * and a bookmarked root both land here.
 *
 * Renders nothing while it resolves (one profiles fetch). A spinner would be a
 * flash of chrome on the way to a page that has its own loading state.
 */
export const StartupRedirect = () => {
  const { resumeProfile } = useProfile();
  const [target, setTarget] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const path = await resumeProfile();
      if (!cancelled) setTarget(path);
    })();
    return () => {
      cancelled = true;
    };
    // Once, on mount: resumeProfile is re-created on every context render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!target) return null;
  return <Navigate to={target} replace />;
};
