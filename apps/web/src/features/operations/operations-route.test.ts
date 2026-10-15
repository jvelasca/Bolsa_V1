/**
 * v111 — guarda falsable de la ruta `/operations`.
 *
 * La auditoría v111 detectó que `/operations` había quedado como un `<Navigate>` a Mesa,
 * dejando la página de Posiciones sin entrada real. Esta guarda fija que la ruta vuelve a
 * montar `<OperationsPage />` y que deja de redirigir.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const APP = readFileSync(resolve(process.cwd(), "src/app.tsx"), "utf8");

describe("v111 · ruta /operations restaurada", () => {
  it("importa OperationsPage", () => {
    expect(APP).toContain(
      'import { OperationsPage } from "@/features/operations/operations-page"',
    );
  });

  it("monta OperationsPage en /operations (no un Navigate a Mesa)", () => {
    const routeBlock = APP.match(/path:\s*"operations",[\s\S]*?\},/)?.[0];
    expect(routeBlock).toBeTruthy();
    expect(routeBlock).toContain("<OperationsPage />");
    expect(routeBlock).not.toContain("<Navigate");
  });
});
