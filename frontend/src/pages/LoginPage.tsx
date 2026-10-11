import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import AuthLayout from "../layouts/AuthLayout";
import FullPageSpinner from "../components/FullPageSpinner";
import { useAuth } from "../context/AuthContext";
import { authApi, type DemoCredentials } from "../api/auth";
import { BUTTON_PRIMARY, CONTROL_STACKED, LABEL, LINK } from "../lib/controls";
import { useDesktopAutoFocus } from "../lib/useDesktopAutoFocus";

/** `from` is the page to go back to after logging in. It comes from the
 *  browser's history, so it mustn't be allowed to send someone to another
 *  website. Anything that isn't a page in this app goes to the dashboard. */
function safeFrom(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  if (typeof from !== "string") return "/dashboard";
  if (!from.startsWith("/") || from.startsWith("//")) return "/dashboard";
  if (from === "/login" || from === "/signup") return "/dashboard";
  return from;
}

export default function LoginPage() {
  const { status, login, sessionExpired } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [demo, setDemo] = useState<DemoCredentials | null>(null);

  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  useDesktopAutoFocus(emailRef, status === "unauthenticated");

  // Asked from the server rather than written in here, so the login details
  // shown on the page always match the account the server really creates.
  useEffect(() => {
    let ignore = false;
    authApi
      .demoCredentials()
      .then((d) => {
        if (!ignore) setDemo(d);
      })
      .catch(() => {
        if (!ignore) setDemo(null);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const from = safeFrom(location.state);

  if (status === "loading") return <FullPageSpinner />;
  if (status === "authenticated") return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();

    // Checked here, rather than by greying out the button. A greyed-out button
    // doesn't say what's wrong; this jumps to the first field that needs fixing.
    const next: { email?: string; password?: string } = {};
    if (!email.trim()) next.email = "Enter the email address on your account.";
    if (!password) next.password = "Enter your password.";
    if (next.email || next.password) {
      setFieldErrors(next);
      setError(null);
      (next.email ? emailRef : passwordRef).current?.focus();
      return;
    }

    setFieldErrors({});
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      const code = (err as { status?: number }).status;
      setError(
        code === 401
          ? "Email or password is incorrect. Check both, then try again."
          : code === 403
            ? (err as Error).message
            : (err as Error).message || "Could not sign in. Check that the API is running.",
      );
      passwordRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle="Your role and tenant come from your account.">
      {sessionExpired && (
        <p className="mb-4 rounded-[2px] border border-rule bg-panel px-3 py-2 text-meta text-ink">
          Your session expired. Sign in again to continue.
        </p>
      )}

      <form onSubmit={submit} noValidate className="space-y-3">
        <div>
          <label htmlFor="login-email" className={LABEL}>Email</label>
          <input
            id="login-email"
            ref={emailRef}
            type="email"
            name="email"
            inputMode="email"
            autoComplete="username"
            /* An email address isn't a sentence, so spell-check underlines are just noise. */
            spellCheck={false}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="you@example.com"
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={fieldErrors.email ? "login-email-error" : undefined}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined }));
            }}
            className={`${CONTROL_STACKED} w-full`}
          />
          {fieldErrors.email && (
            <p id="login-email-error" role="alert" className="mt-1 text-meta text-alarm">
              {fieldErrors.email}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="login-password" className={LABEL}>Password</label>
          <input
            id="login-password"
            ref={passwordRef}
            type="password"
            name="password"
            autoComplete="current-password"
            spellCheck={false}
            aria-invalid={fieldErrors.password ? true : undefined}
            aria-describedby={fieldErrors.password ? "login-password-error" : undefined}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined }));
            }}
            className={`${CONTROL_STACKED} w-full`}
          />
          {fieldErrors.password && (
            <p id="login-password-error" role="alert" className="mt-1 text-meta text-alarm">
              {fieldErrors.password}
            </p>
          )}
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

        <button type="submit" disabled={submitting} className={`${BUTTON_PRIMARY} w-full py-2`}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {/* The platform admin's login is shown on purpose. This is a demo, and
          the point is that anyone given the link can get in and look around. */}
      {demo && (
        <div className="mt-5 rounded-[4px] border border-dashed border-rule bg-panel p-3">
          <p className="text-meta font-semibold text-ink">
            Demo — Platform Admin
          </p>
          <dl className="mt-2 space-y-0.5 text-meta text-ink">
            <div className="flex gap-2">
              <dt className="w-16 shrink-0 text-ink">Email</dt>
              <dd className="min-w-0">
                <code className="break-all" translate="no">{demo.email}</code>
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-16 shrink-0 text-ink">Password</dt>
              <dd className="min-w-0">
                <code className="break-all" translate="no">{demo.password}</code>
              </dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={() => {
              // Fills in the form rather than logging in straight away, so you
              // can see which details were used - that's why they're shown.
              setEmail(demo.email);
              setPassword(demo.password);
              setFieldErrors({});
              setError(null);
            }}
            className="mt-2 rounded-[2px] border border-rule-strong px-2 py-1 text-meta font-medium text-ink hover:bg-rule"
          >
            Fill Demo Admin Credentials
          </button>
          <p className="mt-2 text-meta text-ink">{demo.notice}</p>
        </div>
      )}

      <p className="mt-4 text-meta text-ink-muted">
        No account? <Link to="/signup" className={LINK}>Create one</Link>
      </p>
    </AuthLayout>
  );
}
