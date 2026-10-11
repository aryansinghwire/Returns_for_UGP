import { useId, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useCreateTenant, useTenants } from "../api/hooks";
import { BUTTON_PRIMARY, CONTROL_STACKED, LABEL } from "../lib/controls";
import RulesForm from "../components/RulesForm";
import AuditLogTable from "../components/AuditLogTable";

function TenantSection() {
  const id = useId();
  const { user } = useAuth();
  const { data: tenants } = useTenants();
  const createTenant = useCreateTenant();
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setNameError("Give the tenant a name.");
      nameRef.current?.focus();
      return;
    }
    setNameError(null);
    createTenant.mutate({ name }, { onSuccess: () => setName("") });
  }

  return (
    <section className="space-y-3">
      <h3 className="text-body font-semibold text-ink">
        Tenants{" "}
        <span className="font-normal text-ink-muted">
          (demo brands, simulated for the multi-tenant demo)
        </span>
      </h3>

      {(tenants ?? []).length === 0 ? (
        <p className="text-body text-ink-muted">No tenants yet.</p>
      ) : (
        <ul className="space-y-1 text-body">
          {(tenants ?? []).map((t) => (
            <li key={t.id} className="rounded-[4px] border border-rule px-2 py-1">
              {t.name}{" "}
              <span className="text-meta text-ink-muted" translate="no">
                ({t.slug})
              </span>
            </li>
          ))}
        </ul>
      )}

      {user?.role === "admin" ? (
        <form onSubmit={submit} noValidate className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor={`${id}-name`} className={LABEL}>New tenant name</label>
            <input
              id={`${id}-name`}
              ref={nameRef}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError(null);
              }}
              autoComplete="off"
              aria-invalid={nameError ? true : undefined}
              aria-describedby={nameError ? `${id}-name-error` : undefined}
              placeholder="e.g. Meridian Living…"
              className={CONTROL_STACKED}
            />
            {nameError && (
              <p id={`${id}-name-error`} role="alert" className="mt-1 text-meta text-alarm">
                {nameError}
              </p>
            )}
          </div>
          <button type="submit" disabled={createTenant.isPending} className={BUTTON_PRIMARY}>
            {createTenant.isPending ? "Onboarding…" : "Onboard tenant"}
          </button>

          {/* This used to fail without saying anything: if the name was already
              taken, the server refused it and the form just did nothing. */}
          <div aria-live="polite" className="basis-full">
            {createTenant.isError && (
              <p role="alert" className="text-meta text-alarm">
                {(createTenant.error as { status?: number }).status === 409
                  ? "A tenant with that name already exists. Pick a different name."
                  : `Could not onboard the tenant: ${(createTenant.error as Error).message}.`}
              </p>
            )}
            {createTenant.isSuccess && !createTenant.isPending && (
              <p className="text-meta text-ink-muted">Tenant onboarded.</p>
            )}
          </div>
        </form>
      ) : (
        <p className="text-meta text-ink-muted">
          Onboarding a new tenant requires the Platform Admin role.
        </p>
      )}
    </section>
  );
}

/* Both versions of the notice look the same. They used to differ only in
   colour (amber for the platform admin, teal for a company admin), but the
   words already say which one you are. */
const NOTICE = "rounded-[2px] border border-rule bg-panel px-3 py-2 text-meta text-ink";

/** Says plainly which company's settings you're allowed to change, so the
 *  page never looks like it's changing settings for everyone. */
function ScopeNotice() {
  const { user } = useAuth();

  if (user?.role === "admin") {
    return (
      <p className={NOTICE}>
        <strong>Platform Admin.</strong> You are working across all tenants — the tenant selector at
        the top-left decides whose configuration you are editing.
      </p>
    );
  }

  // The logged-in user's details already include their company's name, so there's nothing to look up.
  const name = user?.tenant_name ?? user?.tenant_slug;
  return (
    <p className={NOTICE}>
      <strong>Tenant Admin{name ? ` — ${name}` : ""}.</strong> Score windows are configured per tenant.
      You can only see and change your own; other tenants&rsquo; settings are not reachable from this account.
    </p>
  );
}

export default function AdminPage() {
  const { user } = useAuth();
  // RequireRole already stops anyone else reaching this page, so this is always
  // true here. It's kept as a second line of defence, and so the message below
  // still makes sense if that page guard is ever loosened.
  const canManage = user?.role === "tenant_admin" || user?.role === "admin";

  return (
    <div className="space-y-8 p-4">
      <h2 className="text-title font-semibold text-balance text-ink">Admin</h2>

      <ScopeNotice />

      <TenantSection />

      <section className="space-y-3">
        <h3 className="text-body font-semibold text-ink">
          Automated Score Windows
        </h3>
        {canManage ? (
          <RulesForm />
        ) : (
          <p className="text-meta text-ink-muted">
            Managing score windows requires Tenant Admin or Platform Admin.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-body font-semibold text-ink">Audit log</h3>
        {canManage ? (
          <AuditLogTable />
        ) : (
          <p className="text-meta text-ink-muted">
            Viewing the audit log requires Tenant Admin or Platform Admin.
          </p>
        )}
      </section>
    </div>
  );
}
