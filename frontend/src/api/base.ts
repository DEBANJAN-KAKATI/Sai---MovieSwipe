/**
 * Where the backend lives.
 *
 * - Web build served by FastAPI or the Vite dev proxy: same origin ("").
 * - Android app (Capacitor): an absolute server URL, defaulting to VITE_API_BASE from build time
 *   and changeable in the app (stored on the device).
 */

const KEY = "movieswipe-server";

export const isNative: boolean =
  typeof window !== "undefined" &&
  !!(window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } }).Capacitor?.isNativePlatform?.();

function read(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function normalizeServer(input: string): string {
  let s = input.trim().replace(/\/+$/, "");
  if (!s) return "";
  if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
  return s;
}

export function getApiBase(): string {
  // In a browser the page is always served next to the API (FastAPI or the Vite proxy).
  if (!isNative) return "";
  const stored = read();
  if (stored !== null) return stored;
  return normalizeServer((import.meta.env.VITE_API_BASE as string | undefined) ?? "");
}

export function setApiBase(url: string): void {
  try {
    localStorage.setItem(KEY, normalizeServer(url));
  } catch {
    /* storage unavailable */
  }
}

/** Origin used for links you share with other people (invites, public lists, calendar files). */
export function shareOrigin(): string {
  return getApiBase() || location.origin;
}

export async function checkServer(base = getApiBase(), timeoutMs = 4000): Promise<boolean> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}/api/health`, { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

/** Artwork comes back as a server-relative "/api/img?..." URL; the Android app needs the server prefix. */
export function imgSrc(url: string): string {
  return url.startsWith("/") ? `${getApiBase()}${url}` : url;
}
