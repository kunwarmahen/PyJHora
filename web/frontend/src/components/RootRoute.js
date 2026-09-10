import React, { Suspense, lazy } from "react";
import { useAuth } from "../contexts/AuthContext";
import { StartupRedirect } from "./StartupRedirect";
import { LoadingState } from "./LoadingState";

// Lazy for the same reason App.js's routes are (§68.4): the landing page is
// marketing copy a signed-in visitor never sees, and a signed-out one is the
// only visitor who should pay for it.
const LandingPage = lazy(() =>
  import("../pages/LandingPage").then((m) => ({ default: m.LandingPage || m.default }))
);

/**
 * The app's "/" entry point.
 *
 * Signed-in visitors resume straight into the app (StartupRedirect → their
 * profile's dashboard, exactly as before). Signed-out visitors get the public
 * marketing landing page instead of being bounced to /login — the landing page
 * carries its own Log in / Get started calls-to-action.
 *
 * While auth is still resolving we render nothing rather than flashing the
 * landing page to a user who is about to be redirected.
 */
export const RootRoute = () => {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (user) return <StartupRedirect />;
  return (
    <Suspense fallback={<LoadingState />}>
      <LandingPage />
    </Suspense>
  );
};

export default RootRoute;
