import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi, type AuthUser, type SignupInput } from "../api/auth";
import { onUnauthorized } from "../api/authEvents";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  /** True when a login expired while in use (not when the user never logged
   *  in), so the login page can explain why it appeared. */
  sessionExpired: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  signup: (input: SignupInput) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Who's logged in.
 *
 * Kept in ordinary React state, not in the data cache. Logging in and out
 * empties the cache, and if "who's logged in" were stored there, emptying it
 * would make the app keep re-checking the login in a loop.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  // A copy of the login status that the "logged out" handler below can read
  // without having to re-attach itself on every change. It's updated after each
  // render rather than during it, which is the safe way to do this in React.
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  // The website can't read the login cookie, so the only way to know if someone
  // is logged in is to ask the server. Until it answers, show a loading screen,
  // not the login page - otherwise every refresh would flash a login form at
  // someone who's already logged in.
  useEffect(() => {
    const controller = new AbortController();
    let ignore = false;
    authApi
      .me(controller.signal)
      .then((me) => {
        if (!ignore) {
          setUser(me);
          setStatus("authenticated");
        }
      })
      .catch(() => {
        if (!ignore) {
          setUser(null);
          setStatus("unauthenticated");
        }
      });
    return () => {
      ignore = true;
      controller.abort();
    };
  }, []);

  // Any request that comes back "not logged in" means the login expired or was
  // cancelled. A page waiting on nine requests will hear this nine times, so
  // running it again must be harmless.
  useEffect(
    () =>
      onUnauthorized(() => {
        if (statusRef.current !== "authenticated") return;
        // The order matters. Marking the user as logged out first stops every
        // request; only then is it safe to empty the cache. The other way round,
        // the requests would retry with the expired login, fail, and run this again.
        setStatus("unauthenticated");
        setUser(null);
        setSessionExpired(true);
        qc.clear();
      }),
    [qc],
  );

  const adopt = useCallback(
    (me: AuthUser) => {
      // Everything saved so far belongs to the previous user. Emptying it is what
      // stops the next person seeing the last person's orders, even briefly.
      qc.clear();
      setUser(me);
      setStatus("authenticated");
      setSessionExpired(false);
      return me;
    },
    [qc],
  );

  const login = useCallback(
    async (email: string, password: string) => adopt(await authApi.login(email, password)),
    [adopt],
  );

  const signup = useCallback(async (input: SignupInput) => adopt(await authApi.signup(input)), [adopt]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Log out here even if the server didn't answer - someone who clicks "log
      // out" must end up logged out of this browser either way.
      setStatus("unauthenticated");
      setUser(null);
      setSessionExpired(false);
      qc.clear();
    }
  }, [qc]);

  const value = useMemo(
    () => ({ status, user, sessionExpired, login, signup, logout }),
    [status, user, sessionExpired, login, signup, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
