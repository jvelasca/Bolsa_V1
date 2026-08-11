/**
 * Base URL de la API para fetch en el navegador.
 *
 * En desarrollo con Vite, dejar vacío usa el proxy `/api` → :8000 del PC servidor,
 * así otros equipos en la LAN pueden abrir http://IP:5173 sin apuntar a localhost:8000.
 */
export function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL?.trim();
  if (configured) {
    if (
      typeof window !== "undefined" &&
      configured.includes("localhost") &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1"
    ) {
      return "";
    }
    return configured.replace(/\/$/, "");
  }
  if (import.meta.env.DEV) return "";
  return "http://localhost:8000";
}
