import { useEffect, useState } from "react";

export const DESKTOP_QUERY = "(min-width: 1024px)";

/** True while the viewport matches the media query (re-renders on resize / rotation). */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}

export const useIsDesktop = () => useMediaQuery(DESKTOP_QUERY);
