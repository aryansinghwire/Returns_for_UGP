import { useEffect, useRef, useState } from "react";

/**
 * For a text or number box: keeps what's being typed to itself, and only
 * passes it on once the person stops typing.
 *
 * Otherwise every keystroke would update the address and reload the data -
 * typing "0.75" would reload the order list four times. Dropdowns don't have
 * this problem (one choice is one change), so only typed boxes need this.
 *
 * If the value changes from outside - "Clear filters", the Back button, or a
 * shared link - the box updates to match, even if someone is typing in it.
 */
export function useDebouncedDraft<T>(
  committed: T,
  commit: (value: T) => void,
  delay = 350,
): [T, (next: T) => void] {
  const [draft, setDraft] = useState(committed);

  // Kept to one side so the "wait until typing stops" timer doesn't restart
  // every time the page redraws. It's updated after each redraw rather than
  // during it, which is the safe way to do this in React.
  const commitRef = useRef(commit);
  useEffect(() => {
    commitRef.current = commit;
  });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // A change from outside (Clear filters, Back, a shared link) wins over what's
  // being typed. It compares against the last saved value, not the box's
  // contents, on purpose - the box is *supposed* to differ while typing, and
  // resetting it then would fight the person's keystrokes.
  const lastCommitted = useRef(committed);
  useEffect(() => {
    if (lastCommitted.current !== committed) {
      lastCommitted.current = committed;
      clearTimeout(timer.current);
      setDraft(committed);
    }
  }, [committed]);

  useEffect(() => () => clearTimeout(timer.current), []);

  function set(next: T) {
    setDraft(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      lastCommitted.current = next;
      commitRef.current(next);
    }, delay);
  }

  return [draft, set];
}
