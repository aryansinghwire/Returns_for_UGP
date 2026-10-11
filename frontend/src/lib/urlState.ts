import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Keeps a page's settings - filters, sort order, page number - in the web
 * address, instead of only in memory.
 *
 * That way a filtered view can be bookmarked, shared as a link, and undone
 * with the Back button. Without it, sending someone a link to "orders from one
 * country" would show them every order.
 *
 * Define `read` and `write` outside the component, so they don't change on
 * every render. `write` gets a copy of the current address settings and only
 * changes the ones it's responsible for, leaving the rest alone.
 */
export function useUrlState<T>(
  read: (params: URLSearchParams) => T,
  write: (value: T, params: URLSearchParams) => void,
): [T, UrlStateSetter<T>] {
  const [searchParams, setSearchParams] = useSearchParams();

  const value = useMemo(() => read(searchParams), [read, searchParams]);

  const setValue = useCallback(
    (next: T | ((current: T) => T), options?: { replace?: boolean }) => {
      const resolved =
        typeof next === "function" ? (next as (current: T) => T)(read(searchParams)) : next;
      const params = new URLSearchParams(searchParams);
      write(resolved, params);
      // Picking from a menu adds a step to the browser history, so Back undoes it
      // as you'd expect. Typing doesn't - see `replace` below.
      setSearchParams(params, { replace: options?.replace ?? false });
    },
    [read, searchParams, setSearchParams, write],
  );

  return [value, setValue];
}

/**
 * `replace: true` is for things the user *types*, rather than picks.
 *
 * Normally each change adds a step to the browser history. That's right for a
 * dropdown - one choice, one Back press to undo it. It's wrong for a text box:
 * typing "0.75" would add four steps, needing four Back presses to get out.
 * Typed fields use `replace` together with `useDebouncedDraft`, so the address
 * still ends up with the value (and can still be shared), without recording
 * every keystroke.
 */
export type UrlStateSetter<T> = (
  next: T | ((current: T) => T),
  options?: { replace?: boolean },
) => void;

/** Sets one address setting, or removes it if it's empty or the default. */
export function setParam(
  params: URLSearchParams,
  key: string,
  value: string | number | boolean | undefined | null,
): void {
  if (value === undefined || value === null || value === "") {
    params.delete(key);
  } else {
    params.set(key, String(value));
  }
}

/** Reads an address setting as a number, or `undefined` if it's missing or
 *  not a valid number. */
export function numberParam(params: URLSearchParams, key: string): number | undefined {
  const raw = params.get(key);
  if (raw === null || raw.trim() === "") return undefined;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/** Reads an address setting that must be one of a fixed list - so someone
 *  editing the address by hand can't break the page. */
export function enumParam<T extends string>(
  params: URLSearchParams,
  key: string,
  allowed: readonly T[],
): T | undefined {
  const raw = params.get(key);
  return raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : undefined;
}
