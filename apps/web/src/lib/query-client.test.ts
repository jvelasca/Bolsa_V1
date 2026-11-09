import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { createQueryClient, handleUnauthorizedError } from "@/lib/query-client";
import { useAuthStore } from "@/stores/auth-store";

function authenticatedSession(): void {
  useAuthStore.setState({
    authEnabled: true,
    authenticated: true,
    isHydrated: true,
    bootstrapError: null,
  });
}

describe("query-client · 401 global (Fase 3.2)", () => {
  beforeEach(() => {
    authenticatedSession();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    useAuthStore.setState({ authEnabled: false, authenticated: false });
  });

  it("un 401 con sesión activa la cierra y deja authEnabled para ver el login", () => {
    const outcome = handleUnauthorizedError(new ApiError("no autorizado", 401));

    expect(outcome).toBe("session_expired");
    const state = useAuthStore.getState();
    expect(state.authenticated).toBe(false);
    expect(state.authEnabled).toBe(true);
  });

  it("no entra en bucle: un segundo 401 ya en login no cambia nada ni llama a logout", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    expect(handleUnauthorizedError(new ApiError("no autorizado", 401))).toBe(
      "session_expired",
    );
    const afterFirst = useAuthStore.getState();

    expect(handleUnauthorizedError(new ApiError("no autorizado", 401))).toBe(
      "already_unauthenticated",
    );
    const afterSecond = useAuthStore.getState();

    expect(afterSecond.authenticated).toBe(false);
    expect(afterSecond.authEnabled).toBe(true);
    expect(afterSecond).toMatchObject({
      authEnabled: afterFirst.authEnabled,
      authenticated: afterFirst.authenticated,
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("un login fallido (401 sin sesión) no dispara ninguna petición extra", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    useAuthStore.setState({ authEnabled: true, authenticated: false });

    expect(
      handleUnauthorizedError(new ApiError("password incorrecta", 401)),
    ).toBe("already_unauthenticated");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("un 500 no cierra la sesión", () => {
    const outcome = handleUnauthorizedError(new ApiError("error interno", 500));

    expect(outcome).toBe("not_401");
    expect(useAuthStore.getState().authenticated).toBe(true);
  });

  it("sin auth activo un 401 no se interpreta como sesión caducada", () => {
    useAuthStore.setState({ authEnabled: false, authenticated: false });

    expect(handleUnauthorizedError(new ApiError("no autorizado", 401))).toBe(
      "auth_disabled",
    );
    expect(useAuthStore.getState().authEnabled).toBe(false);
  });

  it("errores que no son ApiError no tocan la sesión", () => {
    expect(handleUnauthorizedError(new Error("red"))).toBe("not_401");
    expect(useAuthStore.getState().authenticated).toBe(true);
  });

  it("la QueryCache aplica el 401 y no reintenta", async () => {
    const queryFn = vi.fn(async () => {
      throw new ApiError("no autorizado", 401);
    });
    const client = createQueryClient();

    await expect(
      client.fetchQuery({ queryKey: ["probe"], queryFn }),
    ).rejects.toBeInstanceOf(ApiError);

    expect(queryFn).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().authenticated).toBe(false);
  });

  it("la MutationCache también cierra la sesión ante un 401", async () => {
    const client = createQueryClient();

    await expect(
      client
        .getMutationCache()
        .build(client, {
          mutationFn: async () => {
            throw new ApiError("no autorizado", 401);
          },
        })
        .execute(undefined),
    ).rejects.toBeInstanceOf(ApiError);

    expect(useAuthStore.getState().authenticated).toBe(false);
  });

  it("tras volver a iniciar sesión, un nuevo 401 vuelve a cerrarla", () => {
    handleUnauthorizedError(new ApiError("no autorizado", 401));
    expect(useAuthStore.getState().authenticated).toBe(false);

    useAuthStore.getState().setSession(true, true);
    expect(useAuthStore.getState().authenticated).toBe(true);

    expect(handleUnauthorizedError(new ApiError("no autorizado", 401))).toBe(
      "session_expired",
    );
    expect(useAuthStore.getState().authenticated).toBe(false);
  });
});
