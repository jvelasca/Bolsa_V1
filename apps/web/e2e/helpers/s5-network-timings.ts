/**
 * Integrated E2E — medición READ-ONLY de la red del journey S5 (arranque en frío).
 *
 * Por qué existe (`S5-04`, post-`v2.88.135-beta`): el primer intento del journey integrado
 * supera los 60 s en el tramo «esperar la evidencia de la sesión LAB» y el retry pasa. La
 * infraestructura previa (`playwright-attempt-timings.mjs` + `test.step`) mide DÓNDE espera el
 * test, no QUÉ componente tarda. Este helper añade la dimensión de RED/navegador: registra el
 * tiempo de CADA petición (API, módulos de Vite, assets) para poder atribuir la lentitud a una
 * fase concreta (transformación de Vite en frío, waterfall de API, …) sin tocar `timeout`,
 * `retries` ni aserciones.
 *
 *   - NO cambia `timeout`, `retries`, `test.step` ni la aserción del test.
 *   - NO oculta el fallo: escribe el informe SIEMPRE (intento verde o rojo).
 *   - NO depende de red ni de PostgreSQL para escribirse: es un volcado local.
 *   - Un `S5_TIMINGS_OUT` ausente ⇒ no escribe nada (medición opt-in), no rompe.
 *
 * El volcado por intento se escribe en `<S5_TIMINGS_OUT>.attempt<N>.json`
 * para que el retry no sobrescriba al primer intento. El parser puro
 * [`scripts/ci/s5-network-timings.mjs`](../../../../scripts/ci/s5-network-timings.mjs) los agrupa.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Page, Request, TestInfo } from "@playwright/test";

/** Una petición terminada (o fallida) del navegador, con su tiempo de pared medido. */
export type S5NetworkRecord = {
  /** Índice de aparición (orden de finalización). */
  index: number;
  method: string;
  pathname: string;
  resourceType: string;
  /** Código HTTP observado, o `null` si la respuesta no estaba disponible (hueco). */
  status: number | null;
  /**
   * Duración de pared en ms: desde que el runner ve arrancar la petición (`page:request`)
   * hasta que la ve terminar. Es EXACTAMENTE lo que espera el test (incluye red + server +
   * transform de Vite), por eso es la magnitud de atribución. `null` solo si no se registró
   * el arranque.
   */
  durationMs: number | null;
  /** Duración según `request.timing()` (Resource Timing); cross-check, `null` si no está. */
  timingMs: number | null;
  /** ms desde que se enganchó el helper hasta que la petición terminó. */
  offsetMs: number;
  failed: boolean;
  failure: string | null;
};

export type S5NetworkTimingsController = {
  /** Instantánea inmutable de lo medido hasta ahora (para diagnóstico inline). */
  records(): S5NetworkRecord[];
  /** Vuelca el informe a `<S5_TIMINGS_OUT>.attempt<N>.json` (no-op si no hay env). */
  flush(): void;
};

/** Duración según `request.timing()` (Resource Timing); `null` si no está disponible. */
function timingDuration(request: Request): number | null {
  let timing;
  try {
    timing = request.timing();
  } catch {
    return null;
  }
  const start = timing?.startTime;
  const end = timing?.responseEnd;
  if (
    typeof start === "number" &&
    typeof end === "number" &&
    Number.isFinite(start) &&
    Number.isFinite(end) &&
    start >= 0 &&
    end >= 0 &&
    end >= start
  ) {
    return end - start;
  }
  return null;
}

function pathnameOf(url: string): string {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

/**
 * Engancha los listeners de red sobre `page` y devuelve un controlador para volcar el informe.
 * El `retry` del `testInfo` decide el sufijo del fichero (cada intento, su propio informe).
 */
export function attachS5NetworkTimings(
  page: Page,
  testInfo: Pick<TestInfo, "retry">,
): S5NetworkTimingsController {
  const t0 = Date.now();
  const records: S5NetworkRecord[] = [];
  // Arranque observado por el runner para cada petición: la base de `durationMs`.
  const startedAt = new WeakMap<Request, number>();
  let counter = 0;

  page.on("request", (request) => {
    startedAt.set(request, Date.now());
  });

  const push = (
    request: Request,
    extra: { status: number | null; failed: boolean; failure: string | null },
  ): void => {
    const startedAtMs = startedAt.get(request);
    records.push({
      index: counter++,
      method: request.method(),
      pathname: pathnameOf(request.url()),
      resourceType: request.resourceType(),
      status: extra.status,
      durationMs:
        startedAtMs === undefined
          ? null
          : Math.max(0, Date.now() - startedAtMs),
      timingMs: timingDuration(request),
      offsetMs: Date.now() - t0,
      failed: extra.failed,
      failure: extra.failure,
    });
  };

  page.on("requestfinished", (request) => {
    void request
      .response()
      .then((response) => {
        push(request, {
          status: response ? response.status() : null,
          failed: false,
          failure: null,
        });
      })
      .catch(() => {
        push(request, { status: null, failed: false, failure: null });
      });
  });

  page.on("requestfailed", (request) => {
    push(request, {
      status: null,
      failed: true,
      failure: request.failure()?.errorText ?? "request failed",
    });
  });

  return {
    records: () => [...records],
    flush: () => {
      const base = process.env.S5_TIMINGS_OUT?.trim();
      if (!base) return;
      const target = `${base}.attempt${testInfo.retry}.json`;
      try {
        mkdirSync(path.dirname(target), { recursive: true });
        writeFileSync(
          target,
          JSON.stringify(
            {
              attempt: testInfo.retry,
              generatedAt: new Date().toISOString(),
              records,
            },
            null,
            2,
          ),
          "utf8",
        );
      } catch {
        // La medición es instrumentación: un volcado imposible NO tumba el journey.
      }
    },
  };
}
