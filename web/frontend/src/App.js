import React, { Suspense, lazy, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { ProfileProvider } from "./contexts/ProfileContext";
import { SettingsProvider } from "./contexts/SettingsContext";
import { LocationProvider } from "./contexts/LocationContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RootRoute } from "./components/RootRoute";
import { LoadingState } from "./components/LoadingState";
import { RouteErrorBoundary } from "./components/RouteErrorBoundary";
import { SITE_TITLE } from "./config/branding";
import "./App.css";
import "./styles/Responsive.css";
import OfflineBanner from "./components/OfflineBanner";

/**
 * Route-level code splitting (§68.4).
 *
 * Every page below is fetched as its own chunk on first navigation instead of
 * riding in the initial bundle. Before this, App.js statically imported all 51
 * pages and the first paint cost 406 KB gzipped — most of it pages a given
 * visitor never opens, plus `leaflet` (one dialog) and `react-markdown` (no
 * dashboard). Sibling effects, both free: the markdown stack now lands in a
 * shared async chunk because every page that uses it is lazy, and a signed-out
 * visitor no longer downloads the signed-in app.
 *
 * Pages export their component by name; some also have a default. `page()`
 * takes either, so the call sites below stay one line each.
 */
const page = (loader, name) =>
  lazy(() => loader().then((m) => ({ default: m[name] || m.default })));

const LoginPage = page(() => import("./pages/LoginPage"), "LoginPage");
const RegisterPage = page(() => import("./pages/RegisterPage"), "RegisterPage");
const ProfileSelectionPage = page(
  () => import("./pages/ProfileSelectionPage"),
  "ProfileSelectionPage"
);
const DashboardPage = page(() => import("./pages/DashboardPage"), "DashboardPage");
const BirthChartPage = page(() => import("./pages/BirthChartPage"), "BirthChartPage");
const CompatibilityPage = page(() => import("./pages/CompatibilityPage"), "CompatibilityPage");
const DhasaPage = page(() => import("./pages/DhasaPage"), "DhasaPage");
const TransitPage = page(() => import("./pages/TransitPage"), "TransitPage");
const SarvatobhadraPage = page(() => import("./pages/SarvatobhadraPage"), "SarvatobhadraPage");
const LearnChartPage = page(() => import("./pages/LearnChartPage"), "LearnChartPage");
const VarshaphalPage = page(() => import("./pages/VarshaphalPage"), "VarshaphalPage");
const TithiPraveshaPage = page(() => import("./pages/TithiPraveshaPage"), "TithiPraveshaPage");
const PanchaPakshiPage = page(() => import("./pages/PanchaPakshiPage"), "PanchaPakshiPage");
const BirthTimeRectificationPage = page(
  () => import("./pages/BirthTimeRectificationPage"),
  "BirthTimeRectificationPage"
);
const AlmanacPage = page(() => import("./pages/AlmanacPage"), "AlmanacPage");
const AdvancedPage = page(() => import("./pages/AdvancedPage"), "AdvancedPage");
const ComparePage = page(() => import("./pages/ComparePage"), "ComparePage");
const SharedChartPage = page(() => import("./pages/SharedChartPage"), "SharedChartPage");
const PredictionsPage = page(() => import("./pages/PredictionsPage"), "PredictionsPage");
const AskAstrologerPage = page(() => import("./pages/AskAstrologerPage"), "AskAstrologerPage");
const AiToolsPage = page(() => import("./pages/AiToolsPage"), "AiToolsPage");
const SensitivePointsPage = page(
  () => import("./pages/SensitivePointsPage"),
  "SensitivePointsPage"
);
const VedicClockPage = page(() => import("./pages/VedicClockPage"), "VedicClockPage");
const SettingsPage = page(() => import("./pages/SettingsPage"), "SettingsPage");
const HelpPage = page(() => import("./pages/HelpPage"), "HelpPage");
const MuhurtaPage = page(() => import("./pages/MuhurtaPage"), "MuhurtaPage");
const PrashnaPage = page(() => import("./pages/PrashnaPage"), "PrashnaPage");
const BhriguMarkersPage = page(() => import("./pages/BhriguMarkersPage"), "BhriguMarkersPage");
const NadiPage = page(() => import("./pages/NadiPage"), "NadiPage");
const TimelinePage = page(() => import("./pages/TimelinePage"), "TimelinePage");
const StrengthPage = page(() => import("./pages/StrengthPage"), "StrengthPage");
const SadeSatiPage = page(() => import("./pages/SadeSatiPage"), "SadeSatiPage");
const RemediesPage = page(() => import("./pages/RemediesPage"), "RemediesPage");
const DailyDigestPage = page(() => import("./pages/DailyDigestPage"), "DailyDigestPage");
const FortnightlyDigestPage = page(
  () => import("./pages/PeriodDigestPage"),
  "FortnightlyDigestPage"
);
const MonthlyDigestPage = page(() => import("./pages/PeriodDigestPage"), "MonthlyDigestPage");
const HistoryPage = page(() => import("./pages/HistoryPage"), "HistoryPage");
const ForgotPasswordPage = page(() => import("./pages/ForgotPasswordPage"), "ForgotPasswordPage");
const ResetPasswordPage = page(() => import("./pages/ResetPasswordPage"), "ResetPasswordPage");
const DigestConsentPage = page(() => import("./pages/DigestConsentPage"), "DigestConsentPage");
const EphemerisPage = page(() => import("./pages/EphemerisPage"), "EphemerisPage");
const BhavaChartPage = page(() => import("./pages/BhavaChartPage"), "BhavaChartPage");
const FullReportPage = page(() => import("./pages/FullReportPage"), "FullReportPage");
const KPPage = page(() => import("./pages/KPPage"), "KPPage");
const JaiminiPage = page(() => import("./pages/JaiminiPage"), "JaiminiPage");
const NowChartPage = page(() => import("./pages/NowChartPage"), "NowChartPage");
const NakshatraProfilePage = page(
  () => import("./pages/NakshatraProfilePage"),
  "NakshatraProfilePage"
);
const GocharaPhalaPage = page(() => import("./pages/GocharaPhalaPage"), "GocharaPhalaPage");
const JournalPage = page(() => import("./pages/JournalPage"), "JournalPage");
const LifeReportPage = page(() => import("./pages/LifeReportPage"), "LifeReportPage");
const AdminPage = page(() => import("./pages/AdminPage"), "AdminPage");

/**
 * Warm a small set of chunks once the app is idle.
 *
 * Splitting the routes trades one cost for another: a page you have never
 * opened is not in the cache, so it is unavailable offline (`public/sw.js`
 * caches static assets stale-while-revalidate — i.e. only what has actually
 * been fetched once). Precaching all 51 chunks would hand the download back to
 * everyone on every deploy, which is the thing this change exists to stop. So
 * warm only the handful a signed-in user reaches on nearly every visit, at
 * idle, after the first paint has already happened. `import()` is memoised by
 * webpack, so this costs nothing when the page is opened for real.
 */
const warmCoreRoutes = () => {
  const load = () =>
    Promise.all([
      import("./pages/DashboardPage"),
      import("./pages/BirthChartPage"),
      import("./pages/DailyDigestPage"),
      import("./pages/AskAstrologerPage"),
    ]).catch(() => {});
  if ("requestIdleCallback" in window) window.requestIdleCallback(load, { timeout: 5000 });
  else setTimeout(load, 2000);
};

function App() {
  // Reflect the configurable brand name in the browser tab + PWA/meta tags at
  // runtime. index.html carries build-time %REACT_APP_SITE_TITLE% substitution,
  // but this also covers the case where that var wasn't set at build time.
  useEffect(() => {
    document.title = SITE_TITLE;
    const setMeta = (selector, value) => {
      const el = document.querySelector(selector);
      if (el) el.setAttribute("content", value);
    };
    setMeta('meta[name="apple-mobile-web-app-title"]', SITE_TITLE);
    setMeta('meta[name="description"]', `${SITE_TITLE} - Vedic Astrology Web Application`);
    warmCoreRoutes();
  }, []);

  return (
    <Router>
      <OfflineBanner />
      <AuthProvider>
        <ProfileProvider>
          <SettingsProvider>
            <LocationProvider>
              {/* One boundary for every lazy route (§68.4). Pages are fetched on
              first navigation; until a chunk lands the shared spinner holds the
              frame, so a slow network reads as loading rather than as a blank
              screen. */}
              <RouteErrorBoundary>
                <Suspense fallback={<LoadingState />}>
                  <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                    <Route path="/reset-password" element={<ResetPasswordPage />} />
                    <Route path="/digest/confirm" element={<DigestConsentPage mode="confirm" />} />
                    <Route
                      path="/digest/unsubscribe"
                      element={<DigestConsentPage mode="unsubscribe" />}
                    />
                    <Route path="/share/:token" element={<SharedChartPage />} />

                    <Route
                      path="/profile-selection"
                      element={
                        <ProtectedRoute>
                          <ProfileSelectionPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/dashboard"
                      element={
                        <ProtectedRoute>
                          <DashboardPage />
                        </ProtectedRoute>
                      }
                    />

                    {/* Admin console (§44). ProtectedRoute requires a session; AdminPage
                itself redirects non-admins. The API enforces admin server-side. */}
                    <Route
                      path="/admin"
                      element={
                        <ProtectedRoute>
                          <AdminPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/birth-chart"
                      element={
                        <ProtectedRoute>
                          <BirthChartPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/compatibility"
                      element={
                        <ProtectedRoute>
                          <CompatibilityPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/dhasa"
                      element={
                        <ProtectedRoute>
                          <DhasaPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/transit"
                      element={
                        <ProtectedRoute>
                          <TransitPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/ephemeris"
                      element={
                        <ProtectedRoute>
                          <EphemerisPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/bhava"
                      element={
                        <ProtectedRoute>
                          <BhavaChartPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/report"
                      element={
                        <ProtectedRoute>
                          <FullReportPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/almanac"
                      element={
                        <ProtectedRoute>
                          <AlmanacPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/muhurta"
                      element={
                        <ProtectedRoute>
                          <MuhurtaPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/prashna"
                      element={
                        <ProtectedRoute>
                          <PrashnaPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/bhrigu-markers"
                      element={
                        <ProtectedRoute>
                          <BhriguMarkersPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/nadi"
                      element={
                        <ProtectedRoute>
                          <NadiPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/timeline"
                      element={
                        <ProtectedRoute>
                          <TimelinePage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/strength"
                      element={
                        <ProtectedRoute>
                          <StrengthPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/sade-sati"
                      element={
                        <ProtectedRoute>
                          <SadeSatiPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/remedies"
                      element={
                        <ProtectedRoute>
                          <RemediesPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/daily-digest"
                      element={
                        <ProtectedRoute>
                          <DailyDigestPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/fortnightly-digest"
                      element={
                        <ProtectedRoute>
                          <FortnightlyDigestPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/monthly-digest"
                      element={
                        <ProtectedRoute>
                          <MonthlyDigestPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/kp"
                      element={
                        <ProtectedRoute>
                          <KPPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/jaimini"
                      element={
                        <ProtectedRoute>
                          <JaiminiPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/now"
                      element={
                        <ProtectedRoute>
                          <NowChartPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/nakshatra"
                      element={
                        <ProtectedRoute>
                          <NakshatraProfilePage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/gochara"
                      element={
                        <ProtectedRoute>
                          <GocharaPhalaPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/journal"
                      element={
                        <ProtectedRoute>
                          <JournalPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/life-report"
                      element={
                        <ProtectedRoute>
                          <LifeReportPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/advanced"
                      element={
                        <ProtectedRoute>
                          <AdvancedPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/compare"
                      element={
                        <ProtectedRoute>
                          <ComparePage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/predictions"
                      element={
                        <ProtectedRoute>
                          <PredictionsPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/ask-astrologer"
                      element={
                        <ProtectedRoute>
                          <AskAstrologerPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/ai-tools"
                      element={
                        <ProtectedRoute>
                          <AiToolsPage />
                        </ProtectedRoute>
                      }
                    />

                    {/* The page now hosts three chakras (Sarvatobhadra / Kota / Tripataki),
                so /chakras is the name-matching URL. /sarvatobhadra is kept as an
                alias — existing bookmarks, share links and saved readings
                (conversations SOURCE_META) still point at it. */}
                    <Route
                      path="/chakras"
                      element={
                        <ProtectedRoute>
                          <SarvatobhadraPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/sarvatobhadra"
                      element={
                        <ProtectedRoute>
                          <SarvatobhadraPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/learn"
                      element={
                        <ProtectedRoute>
                          <LearnChartPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/varshaphal"
                      element={
                        <ProtectedRoute>
                          <VarshaphalPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/tithi-pravesha"
                      element={
                        <ProtectedRoute>
                          <TithiPraveshaPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/pancha-pakshi"
                      element={
                        <ProtectedRoute>
                          <PanchaPakshiPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/rectify"
                      element={
                        <ProtectedRoute>
                          <BirthTimeRectificationPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/sensitive-points"
                      element={
                        <ProtectedRoute>
                          <SensitivePointsPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/vedic-clock"
                      element={
                        <ProtectedRoute>
                          <VedicClockPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route
                      path="/settings"
                      element={
                        <ProtectedRoute>
                          <SettingsPage />
                        </ProtectedRoute>
                      }
                    />
                    {/* Help is reachable without a chart selected — someone who is lost
                should never have to pick a profile before reading the FAQ.
                `/faq` is an alias people type. */}
                    <Route
                      path="/help"
                      element={
                        <ProtectedRoute>
                          <HelpPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/faq"
                      element={
                        <ProtectedRoute>
                          <HelpPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/history"
                      element={
                        <ProtectedRoute>
                          <HistoryPage />
                        </ProtectedRoute>
                      }
                    />

                    <Route path="/" element={<RootRoute />} />
                  </Routes>
                </Suspense>
              </RouteErrorBoundary>
            </LocationProvider>
          </SettingsProvider>
        </ProfileProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
