import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import ErrorBoundary from './components/ErrorBoundary';
import DashboardLayout from './components/DashboardLayout';
import { LanguageProvider } from './context/LanguageContext';
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Reports from './pages/Reports'
import Alert from './pages/Alert'
import About from './pages/About'
import SystemSettings from './pages/SystemSettings'
import Feeding from './pages/Feeding';
import HistoryOverview from './pages/HistoryOverview';
import GrowthDashboard from './pages/GrowthDashboard';
import GrowthSettings from './pages/GrowthSettings';

import WeatherLayout from './pages/weather/WeatherLayout';
import WeatherHome from './pages/weather/WeatherHome';
import WeatherDetails from './pages/weather/WeatherDetails';
import WeatherAbout from './pages/weather/WeatherAbout';
import WeatherSettings from './pages/weather/WeatherSettings';
import WeatherAnalytics from './pages/weather/WeatherAnalytics';


const ProtectedRoute = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    try {
      const token = localStorage.getItem('access_token');
      setIsAuthenticated(!!token);
    } catch (e) {
      console.error('[App] Error accessing localStorage', e);
      setIsAuthenticated(false);
    }
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-cyan-50">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

function App() {
  return (
    <LanguageProvider>
      <Router>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected routes with shared dashboard layout */}
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <DashboardLayout><Dashboard /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/settings" element={
              <ProtectedRoute>
                <DashboardLayout><SystemSettings /></DashboardLayout>
              </ProtectedRoute>
            } />

            <Route
              path="/weather"
              element={
                <ProtectedRoute>
                  <DashboardLayout><WeatherLayout /></DashboardLayout>
                </ProtectedRoute>
              }
            >
              <Route index element={<WeatherHome />} />
              <Route path="details" element={<WeatherDetails />} />
              <Route path="analytics" element={<WeatherAnalytics />} />
              <Route path="settings" element={<WeatherSettings />} />
              <Route path="about" element={<WeatherAbout />} />
            </Route>
            <Route path="/reports" element={
              <ProtectedRoute>
                <DashboardLayout><Reports /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/alerts" element={
              <ProtectedRoute>
                <DashboardLayout><Alert /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/feeding" element={
              <ProtectedRoute>
                <DashboardLayout><Feeding /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/history" element={
              <ProtectedRoute>
                <DashboardLayout><HistoryOverview /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/growth-dashboard" element={
              <ProtectedRoute>
                <DashboardLayout><GrowthDashboard /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/growth-dashboard/:seasonId" element={
              <ProtectedRoute>
                <DashboardLayout><GrowthDashboard /></DashboardLayout>
              </ProtectedRoute>
            } />
            <Route path="/growth-settings" element={
              <ProtectedRoute>
                <DashboardLayout><GrowthSettings /></DashboardLayout>
              </ProtectedRoute>
            } />

            <Route path="/about" element={
              <ProtectedRoute>
                <DashboardLayout><About /></DashboardLayout>
              </ProtectedRoute>
            } />

            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </ErrorBoundary>
      </Router>
    </LanguageProvider>
  )
}

export default App
