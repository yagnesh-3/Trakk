import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import TopBar from "./components/TopBar";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import LoginPage from "./pages/LoginPage";
import BoardView from "./pages/project/BoardView";
import DashboardView from "./pages/project/DashboardView";
import ListView from "./pages/project/ListView";
import ProjectLayout from "./pages/project/ProjectLayout";
import SettingsView from "./pages/project/SettingsView";
import ProjectsPage from "./pages/ProjectsPage";
import TokensPage from "./pages/TokensPage";
import UsersPage from "./pages/UsersPage";

function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />;
  return (
    <div className="app-shell">
      <TopBar />
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/p/:projectKey" element={<ProjectLayout />}>
          <Route index element={<BoardView />} />
          <Route path="list" element={<ListView />} />
          <Route path="dashboard" element={<DashboardView />} />
          <Route path="settings" element={<SettingsView />} />
        </Route>
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/settings/tokens" element={<TokensPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
