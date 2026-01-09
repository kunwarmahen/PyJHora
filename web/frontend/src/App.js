import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProfileProvider } from './contexts/ProfileContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ProfileSelectionPage } from './pages/ProfileSelectionPage';
import { DashboardPage } from './pages/DashboardPage';
import { BirthChartPage } from './pages/BirthChartPage';
import { CompatibilityPage } from './pages/CompatibilityPage';
import { DhasaPage } from './pages/DhasaPage';
import { PredictionsPage } from './pages/PredictionsPage';
import { AskAstrologerPage } from './pages/AskAstrologerPage';
import { ChartTestPage } from './pages/ChartTestPage';
import './App.css';

function App() {
  return (
    <Router>
      <AuthProvider>
        <ProfileProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

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
              path="/chart-test"
              element={
                <ProtectedRoute>
                  <ChartTestPage />
                </ProtectedRoute>
              }
            />

            <Route path="/" element={<Navigate to="/profile-selection" replace />} />
          </Routes>
        </ProfileProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
