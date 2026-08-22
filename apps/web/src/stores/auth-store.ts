import { create } from "zustand";
import { persist } from "zustand/middleware";
import { resolveApiBaseUrl } from "@/lib/api-base-url";
import { clearVisualizationSession } from "@/stores/visualization-store";

const API_URL = resolveApiBaseUrl();
const AUTH_STATUS_TIMEOUT_MS = 8_000;

interface AuthState {
  authEnabled: boolean;
  authenticated: boolean;
  isHydrated: boolean;
  bootstrapError: string | null;
  setSession: (authEnabled: boolean, authenticated?: boolean) => void;
  clearSession: () => void;
  setHydrated: () => void;
  clearBootstrapError: () => void;
  checkAuthRequired: () => Promise<boolean>;
  login: (password: string, login?: string) => Promise<void>;
}

async function fetchAuthStatus(): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    AUTH_STATUS_TIMEOUT_MS,
  );
  try {
    return await fetch(`${API_URL}/api/auth/status`, {
      signal: controller.signal,
      credentials: "include",
    });
  } finally {
    clearTimeout(timeout);
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      authEnabled: false,
      authenticated: false,
      isHydrated: false,
      bootstrapError: null,
      setSession: (authEnabled, authenticated = authEnabled) =>
        set({ authEnabled, authenticated, bootstrapError: null }),
      clearSession: () => {
        clearVisualizationSession();
        set({ authEnabled: false, authenticated: false });
        // R-8B.2: la sesión es una cookie HttpOnly del backend; hay que pedir
        // al servidor que la borre. Si el login falla, la cookie queda huérfana
        // pero no bloqueamos la UI (es solo una petición best-effort).
        void fetch(`${API_URL}/api/auth/logout`, {
          method: "POST",
          credentials: "include",
        }).catch(() => undefined);
      },
      setHydrated: () => set({ isHydrated: true }),
      clearBootstrapError: () => set({ bootstrapError: null }),
      checkAuthRequired: async () => {
        try {
          const response = await fetchAuthStatus();

          if (response.status === 404) {
            set({
              authEnabled: false,
              bootstrapError: `El backend en ${API_URL} no expone /api/auth/status (¿API TypeScript legacy en :3001?). Usa pnpm dev para arrancar la API Python en :8000.`,
            });
            return false;
          }

          if (!response.ok) {
            set({
              authEnabled: false,
              bootstrapError: `La API respondió con error ${response.status}. Comprueba ${API_URL}/api/health`,
            });
            return false;
          }

          const body = (await response.json()) as {
            data: { authEnabled: boolean; authenticated?: boolean };
          };
          set({
            authEnabled: body.data.authEnabled,
            authenticated: body.data.authEnabled
              ? (body.data.authenticated ?? false)
              : false,
            bootstrapError: null,
          });
          return body.data.authEnabled;
        } catch (error) {
          const timedOut =
            error instanceof DOMException && error.name === "AbortError";
          set({
            authEnabled: false,
            bootstrapError: timedOut
              ? `La API en ${API_URL} no responde (timeout ${AUTH_STATUS_TIMEOUT_MS / 1000}s). Arranca con pnpm dev desde la raíz del monorepo.`
              : `No se pudo conectar con ${API_URL}. Comprueba que la API Python esté en marcha (puerto 8000) y que VITE_API_URL apunte al backend correcto.`,
          });
          return false;
        }
      },
      login: async (password: string, login?: string) => {
        const trimmedLogin = login?.trim();
        const payload = trimmedLogin
          ? { login: trimmedLogin, password }
          : { password };
        const response = await fetch(`${API_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as {
            detail?: string;
          } | null;
          throw new Error(body?.detail ?? "Contraseña incorrecta");
        }
        // R-8B.2: el token ya no viaja en el body; solo authEnabled. La sesión
        // se establece vía cookie HttpOnly que el navegador guarda y envía.
        const body = (await response.json()) as {
          data: { authEnabled: boolean };
        };
        set({
          authEnabled: body.data.authEnabled,
          authenticated: body.data.authEnabled,
          bootstrapError: null,
        });
      },
    }),
    {
      name: "bolsa-auth",
      partialize: (state) => ({
        authEnabled: state.authEnabled,
      }),
      onRehydrateStorage: () => () => {
        useAuthStore.setState({ isHydrated: true });
      },
    },
  ),
);

export function getApiBaseUrl(): string {
  return API_URL;
}
