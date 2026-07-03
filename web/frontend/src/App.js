import React from "react";
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
import "./App.css";
import "./styles/Responsive.css";

function App() {
  return (
    <Router>
      <AuthProvider>
        <ProfileProvider>
          <SettingsProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
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
              path="/almanac"
              element={
                <ProtectedRoute>
                  <AlmanacPage />
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

            <Route path="/" element={<Navigate to="/profile-selection" replace />} />
          </Routes>
          </SettingsProvider>
        </ProfileProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
