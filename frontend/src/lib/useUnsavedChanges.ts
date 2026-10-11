import { useEffect } from "react";

/**
 * Warns before the tab is closed or reloaded while a form has unsaved changes.
 *
 * It only covers closing or reloading the tab - not moving to another page
 * within the app, which the app's current routing setup can't intercept.
 * Closing the tab is the case that actually loses what someone typed, so this
 * covers the most important part; changing the routing setup would cover the
 * rest.
 */
export function useUnsavedChanges(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;

    function onBeforeUnload(event: BeforeUnloadEvent) {
      // Browsers show their own standard warning; setting returnValue is what makes
      // it appear.
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [enabled]);
}
