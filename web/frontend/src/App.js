import React, { useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { ProfileProvider } from "./contexts/ProfileContext";
import { SettingsProvider } from "./contexts/SettingsContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ProfileSelectionPage } from "./pages/ProfileSelectionPage";
import { DashboardPage } from "./pages/DashboardPage";
import { BirthChartPage } from "./pages/BirthChartPage";
import { CompatibilityPage } from "./pages/CompatibilityPage";
import { DhasaPage } from "./pages/DhasaPage";
import { TransitPage } from "./pages/TransitPage";
import { SarvatobhadraPage } from "./pages/SarvatobhadraPage";
import { LearnChartPage } from "./pages/LearnChartPage";
import { VarshaphalPage } from "./pages/VarshaphalPage";
import { TithiPraveshaPage } from "./pages/TithiPraveshaPage";
import { PanchaPakshiPage } from "./pages/PanchaPakshiPage";
import { BirthTimeRectificationPage } from "./pages/BirthTimeRectificationPage";
import { AlmanacPage } from "./pages/AlmanacPage";
import { AdvancedPage } from "./pages/AdvancedPage";
import { ComparePage } from "./pages/ComparePage";
import { SharedChartPage } from "./pages/SharedChartPage";
import { PredictionsPage } from "./pages/PredictionsPage";
import { AskAstrologerPage } from "./pages/AskAstrologerPage";
import { AiToolsPage } from "./pages/AiToolsPage";
import { SensitivePointsPage } from "./pages/SensitivePointsPage";
import { VedicClockPage } from "./pages/VedicClockPage";
import { SettingsPage } from "./pages/SettingsPage";
import { MuhurtaPage } from "./pages/MuhurtaPage";
import { PrashnaPage } from "./pages/PrashnaPage";
import { BhriguMarkersPage } from "./pages/BhriguMarkersPage";
import { RemediesPage } from "./pages/RemediesPage";
import { DailyDigestPage } from "./pages/DailyDigestPage";
import { FortnightlyDigestPage, MonthlyDigestPage } from "./pages/PeriodDigestPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { EphemerisPage } from "./pages/EphemerisPage";
import { BhavaChartPage } from "./pages/BhavaChartPage";
import { FullReportPage } from "./pages/FullReportPage";
import { KPPage } from "./pages/KPPage";
import { JaiminiPage } from "./pages/JaiminiPage";
import { NowChartPage } from "./pages/NowChartPage";
import { SITE_TITLE } from "./config/branding";
import "./App.css";
import "./styles/Responsive.css";

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
  }, []);

  return (
    <Router>
      <AuthProvider>
        <ProfileProvider>
          <SettingsProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
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
            <Route
              path="/history"
              element={
                <ProtectedRoute>
                  <HistoryPage />
                </ProtectedRoute>
              }
            />

            <Route path="/" element={<Navigate to="/profile-selection" replace />} />
          </Routes>
          </SettingsProvider>
        </ProfileProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
