import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BUTTON_SMALL } from "../lib/controls";

/**
 * Shows who's logged in, their role and their company, with a button to log
 * out. It replaced RoleSwitcher: roles can't be switched any more - they come
 * from the account you logged in with.
 */
export default function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  if (!user) return null;

  async function signOut() {
    setSigningOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="min-w-0">
        <p className="text-meta font-medium text-ink-muted">Signed in as</p>
        <p
          className="truncate text-body font-medium text-ink"
          title={user.email}
        >
          {user.display_name}
        </p>
        <p className="truncate text-meta text-ink-muted" title={user.email}>
          {user.email}
        </p>
      </div>

      <dl className="space-y-0.5 text-meta">
        <div className="flex gap-2">
          <dt className="w-12 shrink-0 text-ink-muted">Role</dt>
          <dd className="min-w-0 truncate text-ink">{user.role_label}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-12 shrink-0 text-ink-muted">Tenant</dt>
          <dd className="min-w-0 truncate text-ink">
            {user.tenant_name ?? "All tenants"}
          </dd>
        </div>
      </dl>

      <button type="button" onClick={signOut} disabled={signingOut} className={`${BUTTON_SMALL} w-full`}>
        {signingOut ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}
