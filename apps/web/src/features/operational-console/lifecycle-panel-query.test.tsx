/**
 * Tests — causa real de error en los paneles de lifecycle de la Consola.
 *
 * Regresión (2026-10-01, local): los tres endpoints `/api/lifecycle/*` exigen JWT
 * (`require_jwt_principal`, que no cae al principal de settings) mientras que el resto
 * de la consola sí; con `authEnabled:false` devuelven 401 permanente.
 *
 * Antes: `retry:1` reintentaba en vano y `refetchInterval:30s` re-disparaba la llamada
 * cada 30 s para siempre (consola llena de 401), y el panel decía «No se pudo cargar»,
 * que el operador lee como avería de datos. Ahora: se dice que requiere sesión y se
 * deja de sondear.
 */

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ApiError } from "@/lib/api";
import {
  isAuthError,
  lifecyclePanelQueryOptions,
} from "@/features/operational-console/lifecycle-panel-query";
import {
  OpsFinancialIntegritySection,
  OpsLifecycleOutboxSection,
} from "@/features/operational-console/operational-console-sections";

afterEach(() => cleanup());

describe("isAuthError", () => {
  it("reconoce 401 y 403 como causa de sesión", () => {
    expect(
      isAuthError(new ApiError("Sesión expirada o no autorizada", 401)),
    ).toBe(true);
    expect(isAuthError(new ApiError("Forbidden", 403))).toBe(true);
  });

  it("no confunde averías reales con falta de sesión", () => {
    expect(isAuthError(new ApiError("boom", 500))).toBe(false);
    expect(isAuthError(new ApiError("no contactada", 0))).toBe(false);
    expect(isAuthError(new Error("cualquiera"))).toBe(false);
    expect(isAuthError(undefined)).toBe(false);
  });
});

describe("lifecyclePanelQueryOptions", () => {
  it("no reintenta: un 401 permanente no se arregla reintentando", () => {
    expect(lifecyclePanelQueryOptions().retry).toBe(false);
  });

  it("deja de sondear en 401 y sigue sondeando si el error no es de sesión", () => {
    const { refetchInterval } = lifecyclePanelQueryOptions();
    expect(
      refetchInterval({
        state: { error: new ApiError("Sesión expirada o no autorizada", 401) },
      }),
    ).toBe(false);
    expect(
      refetchInterval({ state: { error: new ApiError("boom", 500) } }),
    ).toBe(30_000);
    expect(refetchInterval({ state: { error: null } })).toBe(30_000);
  });
});

describe("paneles de lifecycle — mensaje honesto", () => {
  it("outbox: un 401 se explica como 'requiere sesión', no como avería", () => {
    render(
      <OpsLifecycleOutboxSection
        stats={undefined}
        isError
        error={new ApiError("Sesión expirada o no autorizada", 401)}
      />,
    );
    expect(screen.getByTestId("ops-section-auth-error")).toBeTruthy();
    expect(screen.getByText(/Requiere sesión/)).toBeTruthy();
    expect(screen.queryByText(/No se pudo cargar outbox stats\./)).toBeNull();
  });

  it("integrity: un error que NO es de sesión mantiene el mensaje genérico", () => {
    render(
      <OpsFinancialIntegritySection
        report={undefined}
        isError
        error={new ApiError("boom", 500)}
      />,
    );
    expect(screen.queryByTestId("ops-section-auth-error")).toBeNull();
    expect(
      screen.getByText(/No se pudo cargar financial integrity\./),
    ).toBeTruthy();
  });
});
