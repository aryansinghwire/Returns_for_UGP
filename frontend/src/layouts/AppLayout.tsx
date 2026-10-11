import { Outlet } from "react-router-dom";
import NavSidebar from "../components/NavSidebar";
import PrototypeBanner from "../components/PrototypeBanner";

/**
 * The frame around every page once you're logged in: the sidebar, the banner
 * and the main area. It's separate from App.tsx so the login and sign-up
 * pages can appear without it.
 *
 * PrototypeBanner goes here, not on every page, because it calls useMeta(),
 * which only works when you're logged in. On the login page it would always
 * be refused.
 */
export default function AppLayout() {
  return (
    <div
      className="flex h-dvh flex-col bg-paper text-ink"
      /* The banner below can be closed, so the space kept clear for a phone's
         notch goes on this outer frame. Otherwise closing the banner would
         slide the sidebar under the notch. */
      style={{
        paddingTop: "env(safe-area-inset-top)",
        paddingLeft: "env(safe-area-inset-left)",
        paddingRight: "env(safe-area-inset-right)",
      }}
    >
      {/* The first thing Tab reaches. Without this "skip" link, keyboard users
          would have to tab past the sidebar's three links and company picker
          on every page. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-[2px] focus:bg-ink focus:px-3 focus:py-2 focus:text-body focus:font-medium focus:text-paper"
      >
        Skip to main content
      </a>

      <PrototypeBanner />
      <div className="flex flex-1 overflow-hidden">
        <NavSidebar />
        {/* tabIndex=-1 lets the skip link actually move focus here. Without it,
            the browser scrolls down but focus stays on the link. */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-auto focus:outline-none"
          style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
