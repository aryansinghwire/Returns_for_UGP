/**
 * Safe access to the browser's saved settings, which can never crash the page.
 *
 * If a browser blocks sites from saving data, even trying to read it causes an
 * error rather than just returning nothing - which could take down the whole
 * page. These functions catch that and carry on.
 *
 * There are two kinds of storage, and they're not the same. sessionStorage
 * only lasts until the tab is closed - right for "this banner was dismissed".
 * localStorage lasts between visits - right for a remembered choice, but not
 * for anything to do with who's logged in.
 */

export function sessionGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function sessionSet(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // Saving is blocked. The setting still works until the page is reloaded;
    // it just won't be remembered after that - which is fine.
  }
}


export function localGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function localSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Saving is blocked; the setting still works until the page is reloaded.
  }
}

export function localRemove(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // If storage can't be reached, there's nothing to delete.
  }
}
