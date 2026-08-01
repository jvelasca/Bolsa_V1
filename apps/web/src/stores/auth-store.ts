import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { resolveApiBaseUrl } from '@/lib/api-base-url';
import { clearVisualizationSession } from '@/stores/visualization-store';

const API_URL = resolveApiBaseUrl();
const AUTH_STATUS_TIMEOUT_MS = 8_000;

interface AuthState {
  token: string | null;
  authEnabled: boolean;
  isHydrated: boolean;
  bootstrapError: string | null;
  setSession: (token: string, authEnabled: boolean) => void;
  clearSession: () => void;
  setHydrated: () => void;
  clearBootstrapError: () => void;
  checkAuthRequired: () => Promise<boolean>;
  login: (password: string) => Promise<void>;
}

async function fetchAuthStatus(): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), AUTH_STATUS_TIMEOUT_MS);
  try {
    return await fetch(`${API_URL}/api/auth/status`, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      authEnabled: false,
      isHydrated: false,
      bootstrapError: null,
      setSession: (token, authEnabled) => set({ token, authEnabled, bootstrapError: null }),
      clearSession: () => {
        clearVisualizationSession();
        set({ token: null });
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

          const body = (await response.json()) as { data: { authEnabled: boolean } };
          set({ authEnabled: body.data.authEnabled, bootstrapError: null });
          return body.data.authEnabled;
        } catch (error) {
          const timedOut = error instanceof DOMException && error.name === 'AbortError';
          set({
            authEnabled: false,
            bootstrapError: timedOut
              ? `La API en ${API_URL} no responde (timeout ${AUTH_STATUS_TIMEOUT_MS / 1000}s). Arranca con pnpm dev desde la raíz del monorepo.`
              : `No se pudo conectar con ${API_URL}. Comprueba que la API Python esté en marcha (puerto 8000) y que VITE_API_URL apunte al backend correcto.`,
          });
          return false;
        }
      },
      login: async (password: string) => {
        const response = await fetch(`${API_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(body?.detail ?? 'Contraseña incorrecta');
        }
        const body = (await response.json()) as {
          data: { token: string; authEnabled: boolean };
        };
        set({ token: body.data.token, authEnabled: body.data.authEnabled, bootstrapError: null });
      },
    }),
    {
      name: 'bolsa-auth',
      partialize: (state) => ({ token: state.token, authEnabled: state.authEnabled }),
      onRehydrateStorage: () => () => {
        useAuthStore.setState({ isHydrated: true });
      },
    },
  ),
);

export function getAuthToken(): string | null {
  return useAuthStore.getState().token;
}

export function getApiBaseUrl(): string {
  return API_URL;
}
