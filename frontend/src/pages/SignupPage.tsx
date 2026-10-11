import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import AuthLayout from "../layouts/AuthLayout";
import FullPageSpinner from "../components/FullPageSpinner";
import { useAuth } from "../context/AuthContext";
import { authApi } from "../api/auth";
import { ROLE_LABELS, SIGNUP_ROLES, type Role, type Tenant } from "../api/types";
import { BUTTON_PRIMARY, CONTROL_STACKED, HINT, LABEL, LINK } from "../lib/controls";
import { useUnsavedChanges } from "../lib/useUnsavedChanges";

/** Copies passwords.MIN_PASSWORD_LENGTH on the server, which is what actually
 *  enforces it. Checking here too just saves waiting for the server to say no. */
const MIN_PASSWORD = 8;

type FieldErrors = { tenant?: string; email?: string; password?: string };

export default function SignupPage() {
  const { status, signup } = useAuth();
  const navigate = useNavigate();

  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [tenantsError, setTenantsError] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("ops_analyst");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const tenantRef = useRef<HTMLSelectElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useUnsavedChanges(!submitting && (email.trim().length > 0 || password.length > 0));

  // This server address works without logging in, so it's called directly
  // rather than through react-query. This page sits outside the logged-in part
  // of the app, and react-query's saved results are cleared as soon as sign-up
  // succeeds anyway.
  useEffect(() => {
    let ignore = false;
    authApi
      .tenants()
      .then((rows) => {
        if (ignore) return;
        setTenants(rows);
        setTenantSlug((current) => current || rows[0]?.slug || "");
      })
      .catch((e) => {
        if (!ignore) setTenantsError((e as Error).message);
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (status === "loading") return <FullPageSpinner />;
  if (status === "authenticated") return <Navigate to="/dashboard" replace />;

  /** Each error message goes next to its own field, rather than all three
   *  being lumped into one message above the form. */
  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!tenantSlug) next.tenant = "Choose the tenant you work for.";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) next.email = "Enter a valid email address.";
    if (password.length < MIN_PASSWORD) {
      next.password = `Use at least ${MIN_PASSWORD} characters — this one has ${password.length}.`;
    }
    return next;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next = validate();
    if (Object.keys(next).length > 0) {
      setFieldErrors(next);
      setError(null);
      const target = next.tenant ? tenantRef : next.email ? emailRef : passwordRef;
      target.current?.focus();
      return;
    }

    setFieldErrors({});
    setError(null);
    setSubmitting(true);
    try {
      await signup({ tenant_slug: tenantSlug, email: email.trim(), password, role });
      navigate("/dashboard", { replace: true }); // signing up also logs you in
    } catch (err) {
      const code = (err as { status?: number }).status;
      if (code === 409) {
        setFieldErrors({ email: "An account with that email already exists. Sign in instead." });
        emailRef.current?.focus();
      } else {
        setError((err as Error).message || "Could not create the account. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Create an account"
      subtitle="Accounts belong to one tenant and see only that tenant's data."
    >
      <form onSubmit={submit} noValidate className="space-y-3">
        <div>
          <label htmlFor="signup-tenant" className={LABEL}>Tenant</label>
          <select
            id="signup-tenant"
            ref={tenantRef}
            name="tenant"
            value={tenantSlug}
            disabled={!tenants}
            aria-invalid={fieldErrors.tenant ? true : undefined}
            aria-describedby={`signup-tenant-hint${fieldErrors.tenant ? " signup-tenant-error" : ""}`}
            onChange={(e) => {
              setTenantSlug(e.target.value);
              if (fieldErrors.tenant) setFieldErrors((f) => ({ ...f, tenant: undefined }));
            }}
            className={`${CONTROL_STACKED} w-full`}
          >
            {!tenants && <option value="">Loading tenants…</option>}
            {tenants?.map((t) => (
              <option key={t.slug} value={t.slug}>{t.name}</option>
            ))}
          </select>
          <p id="signup-tenant-hint" className={HINT}>
            Pick an existing tenant. New tenants are onboarded by a Platform Admin, not at
            signup — a new one would have no orders to review.
          </p>
          {fieldErrors.tenant && (
            <p id="signup-tenant-error" role="alert" className="mt-1 text-meta text-alarm">
              {fieldErrors.tenant}
            </p>
          )}
          {tenantsError && (
            <p role="alert" className="mt-1 text-meta text-alarm">
              Could not load tenants: {tenantsError}. Check that the API is running, then reload.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="signup-email" className={LABEL}>Email</label>
          <input
            id="signup-email"
            ref={emailRef}
            type="email"
            name="email"
            inputMode="email"
            autoComplete="username"
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="you@example.com"
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={fieldErrors.email ? "signup-email-error" : undefined}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined }));
            }}
            className={`${CONTROL_STACKED} w-full`}
          />
          {fieldErrors.email && (
            <p id="signup-email-error" role="alert" className="mt-1 text-meta text-alarm">
              {fieldErrors.email}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="signup-password" className={LABEL}>Password</label>
          <input
            id="signup-password"
            ref={passwordRef}
            type="password"
            name="new-password"
            autoComplete="new-password"
            spellCheck={false}
            minLength={MIN_PASSWORD}
            aria-invalid={fieldErrors.password ? true : undefined}
            aria-describedby={`signup-password-hint${fieldErrors.password ? " signup-password-error" : ""}`}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined }));
            }}
            className={`${CONTROL_STACKED} w-full`}
          />
          <p id="signup-password-hint" className={HINT}>At least {MIN_PASSWORD} characters.</p>
          {fieldErrors.password && (
            <p id="signup-password-error" role="alert" className="mt-1 text-meta text-alarm">
              {fieldErrors.password}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="signup-role" className={LABEL}>Role</label>
          <select
            id="signup-role"
            name="role"
            value={role}
            aria-describedby="signup-role-hint"
            onChange={(e) => setRole(e.target.value as Role)}
            className={`${CONTROL_STACKED} w-full`}
          >
            {SIGNUP_ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
          {/* Said openly rather than left unexplained. An unexplained gap looks
              like a mistake; an explained one looks like a deliberate choice. */}
          <p id="signup-role-hint" className={HINT}>
            <strong>Prototype:</strong> choosing your own role here is a demo affordance. A real
            deployment would invite users at a set role, or have a Tenant Admin approve them.
          </p>
        </div>

        <div aria-live="polite">
          {error && (
            <p
              role="alert"
              className="rounded-[4px] border border-alarm px-3 py-2 text-meta text-alarm"
            >
              {error}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting || !tenants}
          className={`${BUTTON_PRIMARY} w-full py-2`}
        >
          {submitting ? "Creating account…" : "Create Account"}
        </button>
      </form>

      <p className="mt-4 text-meta text-ink-muted">
        Already have an account? <Link to="/login" className={LINK}>Sign in</Link>
      </p>
    </AuthLayout>
  );
}
