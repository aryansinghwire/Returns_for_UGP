import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { AppProvider } from "./context/AppContext";
import "./index.css";
import App from "./App.tsx";

/**
 * Errors that won't go away if you ask again: not logged in (401), not
 * allowed (403) and not found (404). Retrying them just sends a second 401,
 * which sets off the "your session has expired" handling twice.
 *
 * It checks the error's `status` rather than using `instanceof ApiError`.
 * When the dev server reloads api/client.ts after an edit, the old errors no
 * longer count as `instanceof` the new class, so that check would quietly
 * stop working and 401s would be retried again.
 */
function isTerminal(error: unknown): boolean {
  const status = (error as { status?: unknown } | null)?.status;
  return status === 401 || status === 403 || status === 404;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (failureCount, error) => !isTerminal(error) && failureCount < 1,
    },
    mutations: { retry: false },
  },
});

// BrowserRouter goes outside the providers so AuthProvider can change pages.
// QueryClientProvider goes outside everything, because AuthProvider uses it.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppProvider>
            <App />
          </AppProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
