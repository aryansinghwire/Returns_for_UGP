import { useId } from "react";
import { NavLink } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { useAuth } from "../context/AuthContext";
import { useTenants } from "../api/hooks";
import { ADMIN_AREA_ROLES } from "../api/types";
import { CONTROL, LABEL } from "../lib/controls";
import UserMenu from "./UserMenu";

const linkBase = "block rounded-[2px] px-2 py-1.5 text-body transition-colors";
const linkActive = "bg-ink font-medium text-paper";
const linkInactive = "text-ink hover:bg-panel";

export default function NavSidebar() {
  const id = useId();
  const { tenant, setTenant } = useApp();
  const { user } = useAuth();
  const { data: tenants } = useTenants();
  const isAdmin = user?.role === "admin";
  // The same list the pages check, so a link never appears for a role that
  // RequireRole would then turn away.
  const canSeeAdmin = user ? ADMIN_AREA_ROLES.includes(user.role) : false;

  return (
    /* 208px, down from 256. A short menu never needed a quarter of the
       screen, and the extra space goes to the table's reason column. */
    <aside className="flex h-full w-52 shrink-0 flex-col gap-5 overflow-y-auto border-r border-rule bg-panel px-3 py-4">
      <div>
        <h1 className="text-head font-semibold text-balance">Returns Risk Engine</h1>
        <p className="font-condensed text-meta text-ink-muted">Ops dashboard prototype</p>
      </div>

      {/* Only the Platform Admin, who can see every company, gets a company
          picker here. Ops Analysts and Tenant Admins belong to exactly one
          company, set on their account, so there's nothing to choose. */}
      {isAdmin && (
        <div>
          <label htmlFor={`${id}-tenant`} className={LABEL}>
            Viewing tenant
          </label>
          <select
            id={`${id}-tenant`}
            value={tenant ?? ""}
            onChange={(e) => setTenant(e.target.value || null)}
            className={`mt-1 w-full ${CONTROL}`}
          >
            <option value="">All tenants</option>
            {(tenants ?? []).map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <nav aria-label="Main" className="flex flex-col gap-0.5">
        <NavLink to="/dashboard" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Dashboard
        </NavLink>
        <NavLink to="/queue" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Queue
        </NavLink>
        <NavLink to="/alerts" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
          Alerts
        </NavLink>
        {canSeeAdmin && (
          <NavLink to="/escalations" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
            Escalations
          </NavLink>
        )}
        {canSeeAdmin && (
          <NavLink to="/admin" className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}>
            Admin
          </NavLink>
        )}
      </nav>

      <div className="mt-auto border-t border-rule pt-3">
        <UserMenu />
      </div>
    </aside>
  );
}
