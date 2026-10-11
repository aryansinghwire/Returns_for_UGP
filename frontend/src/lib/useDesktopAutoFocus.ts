import { useEffect, type RefObject } from "react";

/**
 * Puts the cursor in the main box when the page opens - but only on a
 * computer with a mouse, not on a phone.
 *
 * On a phone, doing this pops the on-screen keyboard up over the page before
 * the person has even read it. Checking for a mouse is the best simple way to
 * tell "this has a real keyboard, and nothing will be covered".
 */
export function useDesktopAutoFocus(ref: RefObject<HTMLElement | null>, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    ref.current?.focus();
  }, [enabled, ref]);
}
