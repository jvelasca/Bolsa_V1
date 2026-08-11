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
