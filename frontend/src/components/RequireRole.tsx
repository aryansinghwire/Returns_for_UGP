import { Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABELS, type Role } from "../api/types";

/**
 * Stops people without the right role from opening a page. The server is what
 * really enforces this. This just means that if someone opens a bookmarked
 * page they're not allowed to see, it explains why, instead of filling up
 * with "not allowed" errors.
 */
export default function RequireRole({ allow }: { allow: Role[] }) {
  const { user } = useAuth();
  if (!user) return null; // RequireAuth has already dealt with this

  if (!allow.includes(user.role)) {
    return (
      <div className="p-4">
        <div className="rounded-[2px] border border-rule bg-panel px-3 py-2 text-body text-ink">
          <strong>Not available to your role.</strong> You are signed in as{" "}
          {ROLE_LABELS[user.role]}; this page requires{" "}
          {allow.map((r) => ROLE_LABELS[r]).join(" or ")}.
        </div>
      </div>
    );
  }
  return <Outlet />;
}
