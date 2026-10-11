import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import FullPageSpinner from "./FullPageSpinner";

export default function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  // While the app is still asking the server who's logged in (/auth/me), show
  // neither the app nor the login page. Sending people to log in now would
  // flash the login form at every logged-in user each time they reload.
  if (status === "loading") return <FullPageSpinner />;

  if (status === "unauthenticated") {
    return (
      <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
    );
  }

  return <Outlet />;
}
