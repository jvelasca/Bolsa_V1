import { useEffect, useState } from "react";

/**
 * V2.47 — lectura segura de `matchMedia`.
 *
 * `window.matchMedia` NO existe en entornos sin DOM real (jsdom, prerender) ni en
 * navegadores muy antiguos. Sin este guardia el hook lanzaba `TypeError` al primer
 * render y tumbaba el componente (y cualquier test que lo montase sin stub).
 *
 * Fail-safe: sin capacidad de medir devuelve `false` (= «no cumple la query»).
 * Para las queries de este repo (`min-width` = ancho, `max-width` = estrecho) el
 * `false` cae siempre del lado CONSERVADOR: nunca se asume el layout ancho.
 */
export function mediaQueryMatches(query: string): boolean {
  if (typeof window === "undefined") return false;
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia(query).matches;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => mediaQueryMatches(query));

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const sync = () => setMatches(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, [query]);

  return matches;
}
