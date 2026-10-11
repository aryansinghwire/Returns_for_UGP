import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { localGet, localRemove, localSet } from "../lib/storage";

interface AppContextValue {
  /** The company being *viewed*; null means all of them. Only the platform admin
   *  can change it - everyone else always sees their own company. */
  tenant: string | null;
  setTenant: (tenant: string | null) => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

/**
 * Old settings that earlier versions of the app saved in people's browsers,
 * and that nothing should read any more. They're deleted when the app loads.
 *
 * They come from older versions - from before the project was renamed, and
 * from before logins existed, when you picked your role from a menu. An old
 * role left lying around could cause confusion if anything read it.
 *
 * DON'T RENAME THESE. They're the exact names to delete, so they must match
 * what's actually saved in someone's browser.
 *
 * (An old "banner dismissed" setting isn't listed: it was saved somewhere that
 * clears itself. At worst the demo banner shows once more.)
 */
const LEGACY_KEYS = [
  "rto-dashboard.role",
  "rto-dashboard.tenant",
  "rto-dashboard.actorTenant",
  "rto-dashboard.actorName",
  "rto-dashboard.v2.viewTenant",
  "returns-dashboard.role",
  "returns-dashboard.tenant",
  "returns-dashboard.actorTenant",
  "returns-dashboard.actorName",
];

// This runs as soon as the file loads, not inside a component: the old
// settings must be gone before anything reads them, and it only needs to
// happen once per page load.
for (const key of LEGACY_KEYS) localRemove(key);

// A new name rather than the old one, so a company chosen in an older version
// of the app doesn't carry over.
const VIEW_TENANT_KEY = "returns-dashboard.v2.viewTenant";

function readStored<T>(key: string, fallback: T): T {
  const raw = localGet(key);
  if (raw === null) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    // Something is saved, but it can't be read - an old format, or edited by
    // hand. Falling back to the default is the safe choice.
    return fallback;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [viewTenant, setViewTenant] = useState<string | null>(() =>
    readStored(VIEW_TENANT_KEY, null),
  );

  useEffect(() => {
    localSet(VIEW_TENANT_KEY, JSON.stringify(viewTenant));
  }, [viewTenant]);

  // Everyone except the platform admin belongs to one company, so the company
  // they're viewing is always their own. It's worked out directly, not stored
  // separately, so there's nothing to fall out of step. The server enforces the
  // same rule (deps.py); this just stops the website asking for something the
  // server would refuse.
  const isAdmin = user?.role === "admin";
  const tenant = isAdmin ? viewTenant : (user?.tenant_slug ?? null);

  const value = useMemo(() => ({ tenant, setTenant: setViewTenant }), [tenant]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
