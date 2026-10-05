/** Rutas del shell — trading usa dock; el resto pantalla completa. */
export function isTradingRoute(pathname: string) {
  return (
    pathname === "/trading" || pathname === "/workspace" || pathname === "/"
  );
}

/** Hubs con paneles redimensionables: llenan el viewport (sin scroll del main). */
export function isFillHubRoute(pathname: string) {
  return pathname.startsWith("/backtests") || pathname.startsWith("/screeners");
}

/** Espacio AUTO (ADR-044): workspace con sub-navegación propia. */
export function isAutoRoute(pathname: string) {
  return pathname === "/auto" || pathname.startsWith("/auto/");
}
