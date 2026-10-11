import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import RequireAuth from "./components/RequireAuth";
import RequireRole from "./components/RequireRole";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import DashboardPage from "./pages/DashboardPage";
import QueuePage from "./pages/QueuePage";
import OrderDetailPage from "./pages/OrderDetailPage";
import AlertsPage from "./pages/AlertsPage";
import AdminPage from "./pages/AdminPage";
import EscalationsPage from "./pages/EscalationsPage";
import NotFoundPage from "./pages/NotFoundPage";
import { ADMIN_AREA_ROLES } from "./api/types";

export default function App() {
  return (
    <Routes>
      {/* Logged out: no sidebar, no banner, nowhere to go yet. */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/orders/:orderId" element={<OrderDetailPage />} />
          {/* The reporting page is switched off. Its code and the server's
              /api/reporting addresses are kept, so it can be turned back on
              by putting back this route and its menu link. */}
          <Route path="/reporting" element={<Navigate to="/queue" replace />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route element={<RequireRole allow={ADMIN_AREA_ROLES} />}>
            <Route path="/escalations" element={<EscalationsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>
          {/* Inside the layout, so a logged-in user who mistypes an address
              still sees the sidebar and menu. A logged-out one goes to /login. */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
