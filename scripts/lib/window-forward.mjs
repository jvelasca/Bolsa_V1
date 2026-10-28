/**
 * Helpers del runner de la ventana PAPER forward (>=4 dias) sobre `v2.88.29-beta`.
 *
 * Modulo PURO (sin I/O de red, sin procesos, sin reloj de pared salvo el `Date`
 * inyectable): calculo de rutas por dia, clasificacion de codigos de salida,
 * parseo de freeze/gate e idempotencia. Se ejercita con `--dry-run`.
 *
 * Ops-only: no toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B
 * ni migraciones. Ver `docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md`.
 */
import { join } from 'node:path';

/** Directorio no versionado que acumula el material del forward (`.gitignore`). */
export const OPERABILITY_DIR = 'operability_runs';
/** Subdirectorio del runner: un folder por dia + ledger + manifests. */
export const RUNS_DIR = `${OPERABILITY_DIR}/window-runs`;
/** Ruta del ledger acumulado (una fila JSON por corrida). */
export const LEDGER_PATH = `${RUNS_DIR}/ledger.jsonl`;
/** Ruta canonica del forward del dia (el glob del runbook la reutiliza). */
export const FORWARD_GLOB = `${OPERABILITY_DIR}/forward-market-*.json`;
/** Serie/ventana que produce `v2_80` (material durable, read-only). */
export const WINDOW_JSON = `${OPERABILITY_DIR}/operability-window.json`;
export const WINDOW_HTML = `${OPERABILITY_DIR}/operability-window.html`;
/** Auditoria read-only que produce `v2_83`. */
export const AUDIT_JSON = `${OPERABILITY_DIR}/operability-audit.json`;
export const AUDIT_TXT = `${RUNS_DIR}/window-audit.txt`;
/** Journal JSONL que acumula `v2_77` / `v2_80` (no versionado). */
export const JOURNAL_JSONL = `${OPERABILITY_DIR}/journal.jsonl`;
export const WINDOW_JOURNAL_JSONL = `${OPERABILITY_DIR}/window.jsonl`;

/** Umbrales duros del gate (`window_gate`), no negociables durante la ventana. */
export const WINDOW_MIN_DAYS = 4;
export const WINDOW_MIN_EPISODES = 2;
export const WINDOW_MIN_CYCLES = 32;

/** Nombre del directorio-lock atomico de un dia. */
export const LOCK_DIR_NAME = '.run.lock';
/** TTL de un lock de host desconocido antes de poder reclamarlo con `--force` (12 h). */
export const LOCK_TTL_MS = 12 * 60 * 60 * 1000;

/**
 * Configuracion pinneada de la ventana (arbol congelado).
 * Los hashes son de `git rev-parse "HEAD:apps" "HEAD:packages"`; si el arbol de
 * codigo se mueve, el runner declara `TREE_MOVED` y aborta (fail-closed).
 * `commit` nombra el commit cuyo arbol queda pinneado.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.50-beta`): el cierre PIT/UI de `v2.88.50` (universo
 * point-in-time POR DÍA en los arneses multianuales `v2_91`/`v2_92`/`v2_93` —`candidate_ids` +
 * `eligible_days_by_symbol` + poda in-window de barras—, proyección de las 5 banderas
 * `*Measurement` de reservas hasta la UI, dos fixes de UI —`enabled: mode === "current"` y
 * tooltip `sin dato`—, el arreglo del rojo de `main` en `dia-d-auto-feedback-panel.test.tsx`
 * y el PILOTO AUTO UI 1.0 `buildAutoOperationStory`) tocó `src`/tests bajo `packages/` y
 * `apps/`. `Δ motor = 0`: CERO ficheros de motor; el replay congelado se reproduce byte a byte.
 * El arbol pinneado es el del commit funcional `6915ef66`. Editar el pin NO mueve a su vez el
 * arbol porque este modulo vive en `scripts/`. Pin anterior (sello `v2.88.49-beta`, commit
 * `e70b23fa`): `apps` `cc0fdda6…` / `packages` `a706e357…`.
 *
 * RE-ANCLAJE 2026-10-05 (2º, DENTRO del mismo sello `v2.88.50-beta`): el arnes de certificacion
 * `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` pasa a exigir el VIAJE
 * COMPLETO en la barrida determinista (`_filling_instrument_id(..., round_trip=True)`) porque el
 * venue SIM sortea su ruido POR LADO (`draw_queue_noise(seed, side, instrument_id)`): la barrida
 * de la entrada sola dejaba el cierre del dia a una moneda al aire por barra. El primer
 * `Release tag CI` del sello (run `37277722008`, attempt 1) cayo por ese flake
 * determinista-por-fecha (diagnostico + tabla en la evidencia `v2.88.50` §7); `replay-repro` fue
 * VERDE. Es un fichero de TEST bajo `apps/` (Δ motor = 0 intacto): el arbol pinneado pasa a
 * `356aaf2a` y `packages` NO cambia.
 *
 * RE-ANCLAJE 2026-10-05 (3º, DENTRO del mismo sello `v2.88.50-beta`): el SEGUNDO `Release tag CI`
 * del sello (run `37282852860`) cayo en el paso Golden Day 2.0 por el test CON PRECIO REAL
 * (`PermanentRejectionError: No tienes suficientes acciones. En cartera: 4e-06`, dia sin cerrar;
 * reproducido en local el mismo dia). Defecto latente del ledger de posicion: cuantizaba las
 * CANTIDADES de los fills aplicados a 4 dp (quantum de la CASA) cuando viven como `Numeric(18, 6)`
 * (quantum del DINERO): el libro publicaba `490.0001` sobre una cartera de `490.000024` y la salida
 * pedia mas de lo que habia. Fix `round6` en
 * `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py` (cantidades; precio/P&L
 * siguen en `round4`) y notional por fill al quantum del dinero en
 * `apps/api-python/tests/applied_fill_equity.py`. Ablacion declarada: la variante que tocaba
 * `position_state.py` DESCARTADA por romper el motor; `replay-repro` sigue `REPRODUCIDO` byte a
 * byte (`Δ motor = 0`). Evidencia `v2.88.50` §8. El arbol pinneado pasa a `40876dac` (`apps` y
 * `packages` cambian; `scripts/` no participa del pin).
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.51-beta`): fix del PnL `PARTIAL` en el read-model
 * `bolsa_application.auto_operational_monitor` (`result` sigue la medicion del cierre) + la UI
 * `auto-cycle-timeline` (rotula la medicion) + el documento `AUTO UI SEMANTIC MODEL 1.0` +
 * el bump de `package.json`/`meta.bump`. Tocan `apps/` (scripts + web) y `packages/`;
 * `scripts/` no participa del pin. `Δ motor = 0`: CERO ficheros de motor. El arbol pinneado es
 * el del commit funcional `b05de1b5`. Pin anterior (sello `v2.88.50-beta`, 2º re-anclaje):
 * `apps` `e683160a…` / `packages` `7633be63…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.52-beta`): AUTO UI Refactor 1.0 — view-model semantico de
 * 14 etapas con `kind`/`group` (`SELECTION` ← `TOP_N` y `DECISION` `NOT_MEASURED` separadas;
 * `EXIT` `DERIVED` de `SETTLEMENT`; `OPPORTUNITY` movida al bloque `context`), `MeasurementValue`
 * unificado en los 4 paneles AUTO, modo `operation` por defecto con seleccion en la URL
 * (`mode`/`cycle`/`day`/`window`/`symbol`) y enlace `EXPLANATION` → DÍA-D, mas el bump de
 * `package.json`/`meta.bump`. Tocan `apps/` y `packages/`; `scripts/` no participa del pin.
 * `Δ motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `cdedd3e2`. Pin anterior (sello `v2.88.51-beta`, commit `b05de1b5`):
 * `apps` `f931a357…` / `packages` `28d2faf4…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.53-beta`): AUTO UI Refactor 1.1 — `EXIT` plegado en
 * `SETTLEMENT` (`foldedInto` falsable; una sola fila `REACHED` por hecho), identidad de la
 * explicacion (`cycleId`/estrategia/`entryDay`; `timeframe`/`regimen` declarados NO MEDIDO) y
 * operacion unica consolidada (sin doble montaje de reservas/concurrencia; boton «Detalle
 * tecnico» → `mode=current`), mas el bump de `package.json`/`meta.bump`. Tocan `apps/` y
 * `packages/`; `scripts/` no participa del pin. `Δ motor = 0`: CERO ficheros de motor. El arbol
 * pinneado es el del commit funcional `2b7f1940`. Pin anterior (sello `v2.88.52-beta`, commit
 * `cdedd3e2`): `apps` `41fb4a97…` / `packages` `2dc97daf…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.54-beta`): auditoria UI de las 15 rutas de nivel 1 con
 * navegador real + `axe-core` 4.10.2 — criticos a 0 (nombres accesibles de 2 botones icon-only y
 * de 1 `select`), serious a 0 (`nested-interactive` 506 nodos —`role="button"` envolviendo
 * `<button>`/`<a>` en `/instruments` y en las pestanas de `/trading`—, `color-contrast` 25 nodos y
 * `link-in-text-block` 7 nodos), `landmark-one-main`+`region` a 0 en `/trading` (`<main>` +
 * `<h1 class="sr-only">`, y el rail de dibujo pasa de `<aside>` a `<div>`) y
 * `page-has-heading-one` a 0 en 10 rutas (`h2` -> `h1`). Queda declarado un unico hallazgo
 * best-practice `heading-order` (1 nodo) en 11 rutas. Toca `apps/` (web) y `packages/`
 * (`auto-operation-story` + tests); `scripts/` no participa del pin. `Δ motor = 0`: CERO ficheros
 * de motor. El arbol pinneado es el del commit funcional `425292fd`. Pin anterior (sello
 * `v2.88.53-beta`, commit `2b7f1940`): `apps` `9fcd4452…` / `packages` `371105fc…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.55-beta`): AUTO UI REFACTOR 2.0 — espacio AUTO con
 * sub-navegacion propia (`Operar`/`Cartera`/`Riesgo`/`Analisis`/`Sistema`) en `/auto/*`, shell
 * `auto-workspace-layout.tsx` (sin anidar `<main>`; un `h1` por ruta y jerarquia `h1`/`h2`/`h3`),
 * OPERAR canonico `/auto/operar/operacion/:cycleId`, secciones que componen superficies existentes
 * y entry point `AdminRail` -> `/auto` + command palette. ADR-044 + spec `AUTO UI REFACTOR 2.0`.
 * Toca `apps/` (web) y `packages/` (`@bolsa/shared` sin cambios de motor); `scripts/` no participa
 * del pin. `Delta motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `714863c9`. Pin anterior (sello `v2.88.54-beta`, commit `425292fd`):
 * `apps` `b5babdb2…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.56-beta`): AUTO UI REFACTOR 2.1 — navegacion canonica del
 * `AutoOperationStoryPanel` (helpers puros `autoTechnicalDetailHref`/`autoDiaDHref` -> `/auto-monitor`
 * y `/auto/analisis`), `?cycle=` no inerte en el monitor, OPERAR sin doble seleccion, tabs WAI-ARIA
 * de ANALISIS y wording de CARTERA; + E2E mock `gp-e2e-v28856`. UI/read-model puro: toca `apps/`
 * (web/e2e); `packages/` NO cambia (mismo arbol que `v2.88.55`); `scripts/` no participa del pin.
 * `Delta motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `f6286e6e`. Pin anterior (sello `v2.88.55-beta`, commit `714863c9`):
 * `apps` `451fa1c9…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.57-beta`): AUTO UI REFACTOR 2.1.1 — integridad del deep-link
 * de la operacion: el `AutoOperationStoryPanel` resuelve la seleccion explicita (ruta o `?cycle=`)
 * con `resolveAutoOperationSelection`; un id inexistente declara "Operacion no encontrada" y NO cae
 * a `cycles[0]`; + E2E mock `gp-e2e-v28857`. UI/read-model puro: toca `apps/` (web/e2e);
 * `packages/` NO cambia (mismo arbol que `v2.88.56`); `scripts/` no participa del pin.
 * `Delta motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `287a15b5`. Pin anterior (sello `v2.88.56-beta`, commit `f6286e6e`):
 * `apps` `13d5bdc4…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-05 (sello `v2.88.58-beta`): AUTO COCKPIT 1.0 (usuario basico) — F1 semaforo de
 * realidad monetaria fail-closed (`auto-reality.ts` + `auto-reality-strip.tsx` sobre el `<Outlet />`),
 * F2 identidad legible de operacion (`auto-operation-identity.ts`), F3 cockpit OPERAR con estados
 * error/vacio distinguibles, F4 lenguaje plano (`auto-copy.ts`/`auto-story-plain-labels.ts`),
 * reconciliacion no duplicada y tablist WAI-ARIA de DIA-D. UI/read-model puro: toca `apps/` (web);
 * `packages/` NO cambia (mismo arbol que `v2.88.57`); `scripts/` no participa del pin.
 * `Delta motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `dd3af96d`. Pin anterior (sello `v2.88.57-beta`, commit `287a15b5`):
 * `apps` `0556be2f…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.59-beta`): AUTO COCKPIT 1.0.1 — telemetria honesta del semaforo
 * de realidad monetaria: tercer tono `unknown` (ambar) cuando el tipo de cuenta no se conoce
 * (`auto-reality.ts`), `isVirtual` tri-estado, y `PAPER_D_EXECUTE` no medido declarado `NO MEDIDO`
 * (`auto-reality-strip.tsx`, `?? null`). UI/read-model puro: toca `apps/` (web); `packages/` NO
 * cambia (mismo arbol que `v2.88.58`); `scripts/` no participa del pin.
 * `Delta motor = 0`: CERO ficheros de motor. El arbol pinneado es el del commit funcional
 * `c8c23cef`. Pin anterior (sello `v2.88.58-beta`, commit `dd3af96d`):
 * `apps` `6f24ce28…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.60-beta`): fase backend F5 — resolucion DIA-D por `cycleId`.
 * El artefacto `dia-d-feedback-v2` expone un indice `cycles[]` (`cycleId` -> identidad del ciclo) y
 * la ruta `/auto/dia-d-feedback` lo proyecta (`DiaDFeedbackCycleDto`); el panel `resolveExplanation`
 * usa `cycleId` si esta en el indice y, si no, cae al instrumento declarando la resolucion PARCIAL.
 * **A diferencia de `v2.88.59` (solo `apps`), este sello mueve `apps/` Y `packages/`** (application
 * `dia_d_auto_feedback.py` + shared `auto-operation-story.ts`) y su contrato HTTP (openapi/schema.d.ts
 * viven en `apps/`). `scripts/` no participa del pin.
 * `Delta motor = 0`: CERO ficheros de motor; NO se toca `replay_oos.RoundTrip.to_dict` (la huella
 * `sha256 1E3ADAC2…` del `replay-repro` no se mueve). El arbol pinneado es el del commit funcional
 * `71ab00df`. Pin anterior (sello `v2.88.59-beta`, commit `c8c23cef`):
 * `apps` `a909995b…` / `packages` `95cb0d69…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.61-beta`): version bump a `2.11.61-beta` (package + `meta.bump`
 * de los 9 CLI DIA-D) + fix de arranque de la venv bajo Windows Smart App Control
 * (`scripts/lib/python.mjs`, `scripts/fix-venv-python.mjs`; **`scripts/` no participa del pin**).
 * Cambia `apps/` SOLO por el `meta.bump` de `v2_89`..`v2_97`; `packages/` NO cambia (mismo arbol que
 * `v2.88.60`). `Delta motor = 0`: CERO ficheros de motor; NO se toca `replay_oos.RoundTrip.to_dict`.
 * Este sello **absorbe la F5 de `v2.88.60`** (su arbol de `apps`/`packages` viaja dentro, sin tag
 * propio). El arbol pinneado es el del commit `52a697e1`. Pin anterior (sello `v2.88.60-beta`,
 * commit `71ab00df`): `apps` `d7e6da64…` / `packages` `b482a276…`.
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.62-beta`): **AUTO UI REFACTOR 3.0 (user-first cockpit)** en
 * `apps/web/**` (HOME `/auto`, Operacion 3.0, dos niveles de densidad, spec `axe`) y
 * `packages/shared/src/cognitive/auto-operation-story.ts` (grupo `EXPLANATION` propio) + bump a
 * `2.11.62-beta` (package + `meta.bump` de los 9 CLI DIA-D; `scripts/` no participa del pin).
 * `Delta motor = 0`: CERO ficheros de motor; NO se toca `replay_oos.RoundTrip.to_dict`. El arbol
 * pinneado es el del commit `42085822`. Pin anterior (sello `v2.88.61-beta`, commit `52a697e1`):
 * `apps` `286cf716…` / `packages` `b482a276…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.63-beta`): el test M0 pasa a vigilar
 * `auto_simulation_worker.py`. Cambia `packages/` por el test y `apps/` por el
 * `meta.bump` de los CLI DÍA-D. `Delta motor = 0`. El árbol pinneado es el del
 * commit `427ee270`. Pin anterior (sello `v2.88.62-beta`, commit `42085822`):
 * `apps` `8ad1efc2…` / `packages` `bdcb1d34…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.64-beta`): test de cantidad de posición
 * contra el ledger. `Delta motor = 0`. El árbol pinneado es el del commit
 * `5b0c1a54`. Pin anterior (`v2.88.63-beta`, `427ee270`): `apps` `fd4ff254…` /
 * `packages` `19df876c…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.65-beta`): admisión de venta en Decimal.
 * `Delta motor = 0` en el camino de 6 decimales. Árbol pinneado: `23abc3ee`.
 * Pin anterior (`v2.88.64-beta`, `5b0c1a54`): `apps` `54aefdee…` / `packages` `8d2fdf90…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.66-beta`): IdempotencyKeyReused → FAILED.
 * Árbol pinneado: `c47f7882`. Pin anterior (`23abc3ee`): `apps` `f49b2222…` /
 * `packages` `757c2883…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.67-beta`): cash suelto deja de ser puerta pública.
 * Árbol pinneado: `c6a4be15`. Pin anterior (`c47f7882`): `apps` `ca763e61…` /
 * `packages` `677b2e17…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.68-beta`): CHECK cash y cantidad.
 * Árbol pinneado: `c3ca7a93`. Pin anterior (`c6a4be15`): `apps` `8b35fa7a…` /
 * `packages` `5db6d7e0…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.69-beta`): idempotency_key NOT NULL.
 * Árbol pinneado: `1cc6eff7`. Pin anterior (`c3ca7a93`): `apps` `5cbd5fc0…` /
 * `packages` `907726db…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.70-beta`): equity del libro en el turno.
 * Δ motor ≠ 0. Árbol pinneado: `5e264556`. Pin anterior (`1cc6eff7`):
 * `apps` `e92ff504…` / `packages` `737ba3bf…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.71-beta`): dividendo con retención.
 * Δ motor = 0. Árbol pinneado: `332c9eea`. Pin anterior (`5e264556`):
 * `apps` `a84a14bd…` / `packages` `737ba3bf…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.72-beta`): certificación del libro AUTO.
 * Δ motor = 0. Árbol pinneado: `969136d8`. Pin anterior (`332c9eea`):
 * `apps` `01d36cf8…` / `packages` `8b10b611…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.73-beta`): el id de Alembic 050 cabe
 * en varchar(32). Δ motor = 0. Árbol pinneado: `69966996`. Pin anterior
 * (`969136d8`): `apps` `56aca8b7…` / `packages` `bd993b5d…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.74-beta`): el primer nivel no afirma
 * posición ni dinero. Δ motor = 0. Árbol pinneado: `68335c5c`. Pin anterior
 * (`69966996`): `apps` `ff9a3623…` / `packages` `30169088…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.76-beta`): la tarjeta muestra las seis
 * ranuras. Incluye el corte local v2.88.75. Δ motor = 0. Árbol pinneado:
 * `13d5bff6`. Pin anterior (`68335c5c`): `apps` `34172e7f…` / `packages` `f80b2285…`.
 *
 * RE-ANCLAJE 2026-10-06 (sello `v2.88.77-beta`): en curso no es abierta.
 * Δ motor = 0. Árbol pinneado: `9b8e4904`. Pin anterior (`13d5bff6`):
 * `apps` `5b0d50e7…` / `packages` `f80b2285…`.
 *
 * RE-ANCLAJE 2026-10-14 (sello `v2.88.132-beta`): re-anclaje del pin DESFASADO para ABRIR la
 * ventana PAPER (ADR-046; plan `plan-ventana-paper-arranque-operativo-2026-10-14.md` §C/§G.1). El
 * pin anterior (sello `v2.88.77-beta`, commit `9b8e4904`) llevaba `apps` `79fb2685…` / `packages`
 * `f80b2285…`; el arbol de `HEAD` ya habia avanzado y `run-day` abortaba fail-closed con
 * `TREE_MOVED` antes de medir nada. Nuevo arbol pinneado: commit `1ec67416` (`apps` `04226aba…` /
 * `packages` `d48ac37b…`, medidos con `git rev-parse "HEAD:apps" "HEAD:packages"`). Editar el pin NO
 * mueve a su vez el arbol porque este modulo vive en `scripts/`, que NO participa del pin.
 * **Honestidad:** este re-anclaje salta muchos sellos (`9b8e4904..1ec67416`) y NO se reclama
 * `Δ motor = 0` aqui (los RE-ANCLAJE previos sí lo exigian porque ya habia dias `MEDIDO` que
 * quedarian `STALE`). La legitimidad descansa en la regla de §G.1: **el pin anterior AUN NO HABIA
 * MEDIDO NINGUN DIA** (ledger vacio, `v2_98` = `INCONCLUSIVE`) ⇒ mover el pin NO invalida nada.
 *
 * RE-ANCLAJE 2026-10-14 (2º, tras la ejecucion (a)(b)(c); sello `v2.88.132-beta`): el primer
 * re-anclaje del dia pinneo `1ec67416` (`apps` `04226aba…`); despues se COMMITEARON los cambios
 * funcionales del dia — `(b)` test hermetico del sellado `executionId -> cycle_id`
 * (`apps/api-python/tests/test_auto_fill_cycle_seal_pg.py`) y `(c)` cierre de huecos de operativa
 * diaria del AUTO en `apps/web/**` (P1-P5) — mas la nota de evidencia en `docs/`. Eso movio el
 * arbol de `apps` y dejo el pin otra vez desfasado. Nuevo arbol pinneado: commit `05dc2d5b`
 * (`apps` `5696698e…` / `packages` `d48ac37b…` — `packages` NO cambio). El dia ya registrado bajo
 * `1ec67416` fue `NO_MEDIDO_REGIMEN` (no `MEDIDO`) ⇒ re-anclar NO invalida ningun dia medido.
 * Regla operativa: los dias que CERTIFICAN la ventana deben correrse DESPUES de landear los
 * cambios de codigo y de este re-anclaje final. `scripts/` NO participa del pin, asi que commitear
 * este re-anclaje NO mueve a su vez el arbol.
 *
 * RE-ANCLAJE 2026-10-15 (sello `v2.88.133-beta`): sello del cierre de `G6` a nivel de HANDLER (la
 * redaccion de credenciales alcanza de verdad a `root`/`uvicorn`/workers), del panel FA robusto ante
 * un payload que VIOLA `FundamentalCardDto` (guarda `isFundamentalCardDto` + normalizacion en
 * `useEnsureInstrumentFundamentals` y en el segundo camino del panel: deja de blanquear `/backtests`
 * y de tumbar el verificador DIA-D), del refresco de los goldens win32 del certificado visual (drift
 * +20px de alto PREEXISTENTE, contenido identico; el spec se salta en CI) y del helper del sello de
 * ciclo `test_auto_fill_cycle_seal_pg.py` (exige fill COMPLETO), mas el bump de
 * `package.json`/`meta.bump` de 12 CLIs. Tocan `apps/` (logging src + web + tests + scripts + e2e) y
 * `packages/` NO cambia (mismo arbol que `v2.88.132`). `Delta motor = 0`: CERO ficheros de motor. El
 * arbol pinneado es el del commit funcional `530fa674` (`apps` `07fa362c…` / `packages` `d48ac37b…`,
 * medidos con `git rev-parse "HEAD:apps" "HEAD:packages"`). Editar el pin NO mueve a su vez el arbol
 * porque este modulo vive en `scripts/`, que NO participa del pin. Pin anterior (sello
 * `v2.88.132-beta`, 2º re-anclaje, commit `05dc2d5b`): `apps` `5696698e…` / `packages` `d48ac37b…`.
 * **Honestidad:** la ventana PAPER real sigue `INCONCLUSIVE` (`0/4 dias`, `0/2 regimenes`,
 * `0/32 ciclos`); lo que falta es OPERACION, no software. Los dias que CERTIFICAN la ventana deben
 * correrse DESPUES de este re-anclaje.
 *
 * RE-ANCLAJE 2026-10-15 (sello `v2.88.134-beta`, DOCS-ONLY): sello de la `respuesta a la auditoria
 * externa del sello v2.88.133` — documento de respuesta, verificacion propia del sello (6/7
 * afirmaciones sostenidas; el PIN se re-anclo en commit POST-TAG, no en el commit sellado) y
 * trazado de los pendientes operativos `P1`-`P4` con criterio falsable — mas el bump de
 * `package.json`/`meta.bump` de 12 CLIs. NO hay cambio de producto (`Delta motor = 0`,
 * `Delta decision = 0`, `Delta contrato HTTP = 0`, sin migracion): `packages/` NO cambia (mismo
 * arbol que `v2.88.132`/`v2.88.133`) y `apps/` cambia SOLO por el `meta.bump` de los 12 CLIs del
 * sello. El arbol pinneado es el del commit del sello `7cef7fcc` (`apps` `86052343…` / `packages`
 * `d48ac37b…`, medidos con `git rev-parse "HEAD:apps" "HEAD:packages"`). Editar el pin NO mueve a
 * su vez el arbol porque este modulo vive en `scripts/`, que NO participa del pin. Pin anterior
 * (sello `v2.88.133-beta`, commit `530fa674`): `apps` `07fa362c…` / `packages` `d48ac37b…`.
 * **Honestidad:** la ventana PAPER real sigue `INCONCLUSIVE` (`0/4 dias`, `0/2 regimenes`,
 * `0/32 ciclos`); el preflight de hoy (2026-10-15) declara `BEAR_TREND` con LONG vetadas ⇒
 * `run-day` NO produce dia medible (bloqueo de MERCADO, no de software). Los dias que CERTIFICAN
 * la ventana deben correrse DESPUES de este re-anclaje.
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `1c60b58e`
 * (`apps` `a7fe0730391ce18f02a8100016d0b1fd2d1cb74c` / `packages` `d48ac37bbf44b229b5c05da2949aa310d06fcd86`).
 * Motivo: sello v2.88.135
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `73317a9e`
 * (`apps` `c49d561fc722c0f60f9d5a0a2cc38616e9ffd55a` / `packages` `d48ac37bbf44b229b5c05da2949aa310d06fcd86`).
 * Motivo: sello v2.88.135 (fix CI S5-04, tag movido a 73317a9e)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `f23032c6`
 * (`apps` `9e81f1cbc8211295e13654408ea498e691154fa2` / `packages` `d48ac37bbf44b229b5c05da2949aa310d06fcd86`).
 * Motivo: POST-TAG v2.88.135: medicion read-only S5-04 (parser de tiempos + artefacto) y certificador P4 estricto (venue==paper); apps 9e81f1cb / packages d48ac37b
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `1ee09a48`
 * (`apps` `37340d14b9cdf265845b4e191d8b02a402f1c9dd` / `packages` `b6de90f3204352565eb1e7b7aaf00c40c7e65432`).
 * Motivo: diagnostico READ-ONLY del arranque en frio de S5-04 (fases del servidor env-gated + red por intento + repro en frio); sin tocar timeout/retries/umbrales ADR-046
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `5624789c`
 * (`apps` `c26315b0b69e3aa271218e4f2e071c729f1642b3` / `packages` `fea248f25609a49cd173d7466b895830a99a7731`).
 * Motivo: A16 gobernanza de la gramatica + cierre S5-04 POST-TAG
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-15 — pin del arbol re-anclado a `c3bccf88`
 * (`apps` `6df2725fef9cda9e3fbad43d7bd074b96fea1dbb` / `packages` `471af9f08ddf64c94b05725ce7601abe60518676`).
 * Motivo: sello v2.88.136-beta: reanclaje POST-TAG (correccion de identidad DIA-D)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `fc0808aa`
 * (`apps` `934dc7625895a988e3642726a3e3d1e9422a623d` / `packages` `c1fde00965eb337201768cbc10f83dbca97999bb`).
 * Motivo: remediacion AUDITORIA2: SSRF por DNS rebinding (conexion fijada a la IP validada) + huecos DIA-D instrument_id/symbol nullable (migracion 055) — commit fc0808aa; el ledger PAPER sigue en 0 dias MEDIDO (re-anclar no deja ningun dia STALE)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `c6c2d677`
 * (`apps` `958e0b5350cfd5d7294e1eb9c74e35a8c6f5b715` / `packages` `1909964634b0f7eec3b56ac76c4848cf107e33dd`).
 * Motivo: v2.88.137-beta (AUDITORIA3): worker del OUTBOX + observabilidad /health + gate window:freeze; bump 2.11.137-beta
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `7ac1d999`
 * (`apps` `d706f132375acd54ae4839bb1ade979568a07dfd` / `packages` `1909964634b0f7eec3b56ac76c4848cf107e33dd`).
 * Motivo: sello v2.88.137 - fix del fixture del sello BY_FILL: el seed del test exige llenado TOTAL (el parcial deja la reserva viva en OPEN); re-anclaje del arbol del fix para portar el tag
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `bf606d69`
 * (`apps` `4a36b7b19cac37b36b04639416700d3c1570a7c3` / `packages` `6d006d6c50dc3cddda8731add272db0ee8833e0e`).
 * Motivo: sello v2.88.138 (explicacion P3->P4 + fix auditoria identidad LAB / lectura verificacion)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `723048e4`
 * (`apps` `0b2df883c20130e13468839d9d1af30897b7f2f7` / `packages` `6d006d6c50dc3cddda8731add272db0ee8833e0e`).
 * Motivo: verificacion v2.88.138: instrumentos de ventana + guardian de bump v2_87 (test-only)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `b03f09e6`
 * (`apps` `5e33b63701b7b69b2f1ad28671fbbb24aad40151` / `packages` `6d006d6c50dc3cddda8731add272db0ee8833e0e`).
 * Motivo: cierre de la CAUSA RAIZ del bloqueador de entorno de la ventana PAPER — la purga de
 * residuos de los tests (`apps/api-python/tests/conftest.py`, fixture autouse de sesion) borraba
 * toda cuenta con `id <> 'default-account-seed'`, incluida la cuenta operativa de la ventana; como
 * ADR-046 exige que sobreviva >=4 dias de CALENDARIO, cualquier `pytest` local devolvia la ventana
 * a 0/4. Se protege la cuenta con el id de la FUENTE UNICA + tripwire. Toca `apps/` (conftest +
 * test nuevo) y `scripts/` (ops); `packages/` NO cambia.
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`, que NO participa del
 * freeze. La ventana sigue con 0 dias MEDIDO => re-anclar NO invalida ningun dia medido.
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `6f04f5b2`
 * (`apps` `795eb763820203b7397e06c42961288bc95ef4f7` / `packages` `6d006d6c50dc3cddda8731add272db0ee8833e0e`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `fddd7a85`
 * (`apps` `552e1ddd7466c703325413544358223dcf8db4a7` / `packages` `6d006d6c50dc3cddda8731add272db0ee8833e0e`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `e3a5f864`
 * (`apps` `d38dc7ae804a766231b6b2173082210dfc3904bd` / `packages` `e96a12b80a1606523f422750493274894ff07ef4`).
 * Motivo: sello v2.88.140-beta: vigia diario de la ventana PAPER (window_day_watch, alerta de dia perdido) + instalador de la cadencia diaria arreglado (wrapper .cmd); 0 dias MEDIDO, re-anclar no deja dias STALE
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `af5aa08e`
 * (`apps` `e151cd4329591c24835256082882dfe478107e63` / `packages` `e96a12b80a1606523f422750493274894ff07ef4`).
 * Motivo: sello v2.88.141-beta: sello corrector del Ruff del CI del .140 (paridad local<->CI: lint:py/imports:py/types:py); 0 dias MEDIDO, re-anclar no invalida nada
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `68d8b594`
 * (`apps` `e151cd4329591c24835256082882dfe478107e63` / `packages` `e96a12b80a1606523f422750493274894ff07ef4`).
 * Motivo: sello v2.88.141-beta (docs): pin re-anclado al arbol del sello corrector; apps e151cd43 (incluye apps/api-python/tests) / packages e96a12b8; 0 dias MEDIDO
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-16 — pin del arbol re-anclado a `3be17ebb`
 * (`apps` `e151cd4329591c24835256082882dfe478107e63` / `packages` `e96a12b80a1606523f422750493274894ff07ef4`).
 * Motivo: sello v2.88.141-beta (final): pin re-anclado al arbol del sello corrector; 0 dias MEDIDO
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-17 — pin del arbol re-anclado a `3485493f`
 * (`apps` `e151cd4329591c24835256082882dfe478107e63` / `packages` `e96a12b80a1606523f422750493274894ff07ef4`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-17 — pin del arbol re-anclado a `b02c90b2`
 * (`apps` `446f198b99d4bca36df0ca55560102627bfd0a84` / `packages` `6377a7a24d6c279c84c3b36096c44d8afae82285`).
 * Motivo: re-anclaje del sello v2.88.142-beta (vigia 2.0: latido durable + arrastre + CLI/tarea window:watch); 0 dias MEDIDO
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-17 — pin del arbol re-anclado a `dad93f99`
 * (`apps` `fe9798e31683e349c853b836f44e56009e0cc261` / `packages` `6377a7a24d6c279c84c3b36096c44d8afae82285`).
 * Motivo: v2.88.143: bump 2.11.143-beta de los 13 CLIs (apps/api-python/scripts) -- 0 dias MEDIDO, el cambio de fondo vive en scripts/ (freeze-neutral)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-18 — pin del arbol re-anclado a `ac9f1ccd`
 * (`apps` `e1c5e8250e31db2d88138f3826b3deb5eb8e983a` / `packages` `6377a7a24d6c279c84c3b36096c44d8afae82285`).
 * Motivo: v2.88.144: bump 2.11.144-beta de los 13 CLIs (apps/api-python/scripts) -- 0 dias MEDIDO, el cambio de fondo vive en scripts/ (freeze-neutral)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-18 — pin del arbol re-anclado a `396bd205`
 * (`apps` `e1c5e8250e31db2d88138f3826b3deb5eb8e983a` / `packages` `6377a7a24d6c279c84c3b36096c44d8afae82285`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-18 — pin del arbol re-anclado a `fc78565d`
 * (`apps` `0a49a43b76d0b346401d8c7c13ef15b84f69e0f7` / `packages` `5bc5c3eb5b10958e086a6029f88e1f01e2ac2817`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `ce42fa96`
 * (`apps` `efac219ec84402e9d58375b47675eded4fa1cf06` / `packages` `5bc5c3eb5b10958e086a6029f88e1f01e2ac2817`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `8f3a78e8`
 * (`apps` `1e1744bc4b1096a9d05d8d12d0cc4e39edfb54bd` / `packages` `a37f7f759526463db13501d93da5b5b9bde5aff2`).
 * Motivo: arbol del sello v2.88.146-beta (auditoria UI AUTO diaria y DIA-D)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `ce6d817d`
 * (`apps` `2e70dd8051769ce077e9bb850f4b781d58161596` / `packages` `a37f7f759526463db13501d93da5b5b9bde5aff2`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `a94c60fa`
 * (`apps` `d5464cbb021bf590de91eebeb0c651a7adf6e8c7` / `packages` `a37f7f759526463db13501d93da5b5b9bde5aff2`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `bb417791`
 * (`apps` `e451c6a5acc757868b821de90b02973c930f6fb9` / `packages` `a37f7f759526463db13501d93da5b5b9bde5aff2`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `16624d29`
 * (`apps` `e451c6a5acc757868b821de90b02973c930f6fb9` / `packages` `a37f7f759526463db13501d93da5b5b9bde5aff2`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `c6bcbacc`
 * (`apps` `a4b495a9204369b3996b21d9cdaa3ddecd16ddc7` / `packages` `963c7575168d2265ea83fa53d842696a07cd9a65`).
 * Motivo: re-ancla al arbol del sello .148 (artefacto DIA-D escritor=lector)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `1cf7fb75`
 * (`apps` `e637ad27f3c0cc0fe05cca4c86c2ba6ed9d26e0a` / `packages` `963c7575168d2265ea83fa53d842696a07cd9a65`).
 * Motivo: auditoria read-only .149 (docs + bump meta de 13 CLIs); el codigo de decision no cambia
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `dc8eb5bd`
 * (`apps` `c596721859ca40ecd833a13848c6828d51753b1a` / `packages` `4bf6673a3eb59f121f669cdba4c28ec844924be9`).
 * Motivo: v2.88.150-beta: ADR-047 gate direccional por simbolo (delta decision != 0) + baseline de replay segmentado
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `fae6d0d2`
 * (`apps` `4ab620feb1de3f71d286b72afb676b7b04345269` / `packages` `4bf6673a3eb59f121f669cdba4c28ec844924be9`).
 * Motivo: sello .151 (Ayuda DIA D): apps solo suma la guia de Ayuda, packages sin cambio; delta motor 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `b883f6ef`
 * (`apps` `d5038efc0398fb235ccba47c8adbb74d873b4018` / `packages` `5596a42f50ec131a356f784ef5ab603057c3eea0`).
 * Motivo: sello v2.88.152 (evidencia por valor ESTUDIO + DIA-D del valor); delta motor 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-19 — pin del arbol re-anclado a `5803ac03`
 * (`apps` `f4646c1f76907e2f1c4ba44c8bf3c9e3b5e45b79` / `packages` `5596a42f50ec131a356f784ef5ab603057c3eea0`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `0b2417bf`
 * (`apps` `eb380c14a39e43ead1e22e99c6ac1d1bf28530d0` / `packages` `c6a6d9d912517da14f4ba1d667fa5325d7a6d849`).
 * Motivo: sello v2.88.153-beta - identidad del indicador ganador (057) y S5-04 observable
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `172aacf6`
 * (`apps` `feed7590d042102b3999ae9110d63f3f83b63fd5` / `packages` `c6a6d9d912517da14f4ba1d667fa5325d7a6d849`).
 * Motivo: sello v2.88.153-beta - correccion del sweep a9 (lifecycle-pg)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `b0d0f7b2`
 * (`apps` `438e9bef25e6cc090d6539d53417a8c27123abb7` / `packages` `b27921813bae331a7ef8d3a4a87178a5650ef1de`).
 * Motivo: endurecimiento P2 .153 (guarda fail-closed de la 057 + tri-estado de la identidad; Delta motor 0)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `1ac2dd72`
 * (`apps` `ef0ca05ad416106a7053c5e114662122ecba1637` / `packages` `4a7a456b84bb358bc763c2f477e98da593df2894`).
 * Motivo: bateria integrada por valor (2026-10-20): tests PG nuevos en apps/ + lector de identidad del ciclo en packages/
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `31a7f43f`
 * (`apps` `e162746abd48af34acfb277009e712db0a2994f2` / `packages` `be243531e663830f0ffa2abb7316c045d917c389`).
 * Motivo: sello v2.88.154-beta: bateria integrada por valor (tests PG en apps/) + lector de identidad del ciclo y tri-estado (packages/) + meta.bump de los 13 CLIs en apps/api-python/scripts
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `9062a2d0`
 * (`apps` `1171f4572628383a5525d5253da4b6908af67c55` / `packages` `be243531e663830f0ffa2abb7316c045d917c389`).
 * Motivo: Correccion P2 (versionLabel en la estrategia ejecutada) mueve apps/web; Delta motor = 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-20 — pin del arbol re-anclado a `79131c07`
 * (`apps` `5fccc568215d0aa4b645d2c4f62573cb11f6b3da` / `packages` `be243531e663830f0ffa2abb7316c045d917c389`).
 * Motivo: Sello .155 (bump 2.11.155-beta de los 13 CLIs); Delta motor = 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-21 — pin del arbol re-anclado a `bf13d62b`
 * (`apps` `6767a3b502572037582ec0b294a15581fc404da3` / `packages` `3fa61137184d8639cab2628b3eed4b19d7a3eb57`).
 * Motivo: Sello .156 (bump 2.11.156-beta de los 13 CLIs + read-models N-155/H-145 + gap 2); Delta motor = 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-21 — pin del arbol re-anclado a `2064fbd7`
 * (`apps` `162ad6dfc63c5aa5462d4153cc0da920b08a2fd3` / `packages` `3fa61137184d8639cab2628b3eed4b19d7a3eb57`).
 * Motivo: Sello .156 - correccion de test de la ruta de auditoria (CI del primer objeto de tag rojo); Delta motor = 0
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-21 — pin del arbol re-anclado a `9f632315`
 * (`apps` `5e5c508649b88cb06a5cbea334416f75ec3dc5ec` / `packages` `55571608ca700d82752a7b2b8d274d2d7c39c170`).
 * Motivo: Sello .157 (bump 2.11.157-beta de los 13 CLIs + integridad del parte ESTUDIO + atribucion DIA-D); Delta motor = 0 con cartera medida
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-21 — pin del arbol re-anclado a `9c485c64`
 * (`apps` `4c9d5cc3de6307dc210866291ddd032de483d00e` / `packages` `55571608ca700d82752a7b2b8d274d2d7c39c170`).
 * Motivo: W-157-1: identidad de motor estable (AUTO_ENGINE_SIM_ENGINE_ID) para que la cadencia diaria opere un solo libro y los ciclos puedan cerrarse
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-21 — pin del arbol re-anclado a `41860d4c`
 * (`apps` `f37b6da083f18e3b9f604ded4d680b0a53646814` / `packages` `b33bf1e0a8876602b933da8d82b0fdc11298100d`).
 * Motivo: 2.11.159-beta: dato de barra cargado en cada tick y adopcion con base de coste
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-22 — pin del arbol re-anclado a `4a76d477`
 * (`apps` `4be4a32f87b4f2c8feaace4d09842fbcf020bf5c` / `packages` `0824c030a43bb057ef782dad22a1bc76614b10fa`).
 * Motivo: w160: cierre de los huecos A-E (adopcion, atribucion, ranking) tras el dia 20261021 MEDIDO/BLOCKED; sin migracion
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-23 — pin del arbol re-anclado a `64e23eaf`
 * (`apps` `d06695aba31c3e9c1db821b304a3a5a8089fccd0` / `packages` `243cd09cfe16752e4e18ad47eedad858a1389192`).
 * Motivo: post-tag v2.88.161-beta: bump de 13 CLIs en apps (seal 64e23eaf); el tag debe apuntar a un commit con freeze OK
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-26 — pin del arbol re-anclado a `1523cfe7`
 * (`apps` `807f67a090b181cb2444128ba17782a055d90efe` / `packages` `b2fae3bf7983762f8d17e1f95c8679730da17d54`).
 * Motivo: post seal v2.88.162-beta (1523cfe7): bump de 13 CLIs y fix de feature OHLCV en apps/packages; el tag debe apuntar a un commit con freeze OK; la ventana sigue INCONCLUSIVE (0/2 episodios, 0/32 ciclos)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-26 — pin del arbol re-anclado a `9b91f472`
 * (`apps` `d7e698cfafa21262ee9b9bca3409ee0c0ed127c3` / `packages` `26ec8a8ed5514a88053ddd764877e6e00c1d957e`).
 * Motivo: post seal v2.88.163-beta (9b91f472): fix de logging del bootstrap en proceso (env.py + migrations.py) en packages; el tag debe apuntar a un commit con freeze OK; la ventana sigue INCONCLUSIVE y el dia 20261026 se perdio por API_NOT_READY
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-27 — pin del arbol re-anclado a `3e9ab2cc`
 * (`apps` `381aa48095090c93c1b1c3daea39d6e9878b9cf7` / `packages` `54a96c1ba696946abc01dc3e2cf3740ec964e6da`).
 * Motivo: sello 2.11.164-beta: bump de los 13 meta.bump en apps/api-python/scripts y contrato regenerado
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-27 — pin del arbol re-anclado a `803613db`
 * (`apps` `3a9d1228fb6b4151360550acd6df956e282e8964` / `packages` `41e0afa8c5937c10dd3eaa2c8f3f66e2bc10f925`).
 * Motivo: sello 2.11.165-beta: cierre S-4/S-5/O-3/O-4/T-3 (journal, UI honrada, contrato venue)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-27 — pin del arbol re-anclado a `fb18d729`
 * (`apps` `927c22988d27ff63512f3c3bf6cb150ba0dd5551` / `packages` `41e0afa8c5937c10dd3eaa2c8f3f66e2bc10f925`).
 * Motivo: (no declarado).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-28 — pin del arbol re-anclado a `0b6f68f3`
 * (`apps` `dcea57014f3d59bbac78dcf0ad74c877587c7747` / `packages` `ca2b288f9a3038590baa010cabc83adb8f468da0`).
 * Motivo: sello v2.88.169 (bump de los 13 meta.bump y prueba de abril)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-28 — pin del arbol re-anclado a `1f084f18`
 * (`apps` `6bdf5f25c095f3abbecf35e09fa7eb7ca541e98d` / `packages` `ca2b288f9a3038590baa010cabc83adb8f468da0`).
 * Motivo: sello v2.88.169 (correccion del teardown del S5 tras el rojo del primer tag)
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
/**
 * RE-ANCLAJE 2026-10-28 — pin del arbol re-anclado a `cc00b735`
 * (`apps` `becfc7562883ec8c2f6ab6d5457fe1bccc15805b` / `packages` `7dafa4009de1995a7f25b191122b27d626edf5a6`).
 * Motivo: sello v2.88.170 (cierre de los seis P1 de representacion de UI y del comodin P2-04; el bump mueve apps).
 * Editar este pin NO mueve a su vez el arbol: este modulo vive en `scripts/`,
 * que NO participa del freeze. Los dias que CERTIFICAN la ventana deben correrse
 * DESPUES de este re-anclaje (o quedarian `STALE`).
 */
export const WINDOW_CONFIG = Object.freeze({
  commit: 'cc00b735',
  appsHash: 'becfc7562883ec8c2f6ab6d5457fe1bccc15805b',
  packagesHash: '7dafa4009de1995a7f25b191122b27d626edf5a6',
  account: '1484e253d2d54645945a6b1d7',
  versionA: 'v283-window-a',
  versionB: 'v283-window-b',
  watchSize: 20,
  /**
   * V2.88.135 — la lane operada de la ventana mide el universo **ESTUDIO** (no el
   * catálogo) para que los mismos días sirvan a P1 (ventana 4/2/32) y a P2 (cadena
   * durable por instrumento del ESTUDIO). Fail-closed: sin ESTUDIO `ok` el watch
   * queda vacío y el día se declara, sin caer al catálogo. NO es clave de freeze
   * (no es identidad del árbol); con `false` el comportamiento es el histórico.
   */
  watchFromEstudio: true,
  days: WINDOW_MIN_DAYS,
  /** Flags de operacion: se inyectan SOLO en el `env` del proceso hijo. */
  operatorEnv: Object.freeze({
    AUTO_ENGINE_SIM_REAL_PRICE: '1',
    AUTO_OPERATIONAL_AUDIT: '1',
    BROKER_VENUE: 'paper',
    /**
     * V2.88.158 — IDENTIDAD DE MOTOR ESTABLE de la ventana (una sola, para toda la
     * cadencia). Sin ella cada corrida acuñaba `auto-v76-<aleatorio>`; como la
     * readopción de posición va scoped por `(account_id, engine_id)`, el día N no
     * adoptaba la posición del día N-1 y el ciclo no podía cerrarse NUNCA ⇒ 0 ciclos
     * medibles y ventana incapaz de certificar (medido 2026-10-21: 2 motores con el
     * mismo símbolo vivo y 0 ciclos en los días con fills). Con la identidad fijada
     * la cadencia diaria opera UN libro persistente y los ciclos se cierran.
     * No es clave de freeze (no es identidad del árbol): vive en `scripts/`.
     */
    AUTO_ENGINE_SIM_ENGINE_ID: 'auto-window-1484e253',
  }),
});

/**
 * Variables de entorno que **solo** pueden tocar la identidad/el freeze en modo
 * explicitamente inseguro (`--unsafe-override-window-config`). `WINDOW_PY`,
 * `WINDOW_UV` y `WINDOW_API_READY_URL` NO son freeze y siguen siendo legitimas.
 */
export const FREEZE_ENV_KEYS = Object.freeze({
  appsHash: 'WINDOW_APPS_HASH',
  packagesHash: 'WINDOW_PACKAGES_HASH',
  account: 'WINDOW_ACCOUNT',
  versionA: 'WINDOW_VERSION_A',
  versionB: 'WINDOW_VERSION_B',
  watchSize: 'WINDOW_WATCH_SIZE',
});

/**
 * Config efectiva de la ventana. Por defecto es **inmutable**: el entorno NO
 * puede reescribir `appsHash`/`packagesHash`/`account`/`versionA`/`versionB`/`watchSize`
 * (si lo hiciera, el freeze `TREE_MOVED` dejaria de ser un freeze). El override
 * exige `unsafeOverride: true`; devuelve `configMode` y `configOverrides` para
 * sellarlos en el manifest.
 * @param {NodeJS.ProcessEnv | Record<string,string|undefined>} [env]
 * @param {{unsafeOverride?: boolean}} [options]
 */
export function windowConfig(env = {}, { unsafeOverride = false } = {}) {
  const base = { ...WINDOW_CONFIG };
  const configOverrides = [];
  if (unsafeOverride) {
    for (const [field, key] of Object.entries(FREEZE_ENV_KEYS)) {
      const raw = env[key];
      if (raw === undefined || raw === '') continue;
      if (field === 'watchSize') {
        const parsed = Number(raw);
        if (Number.isFinite(parsed) && parsed > 0) {
          base.watchSize = parsed;
          configOverrides.push(key);
        }
      } else if (String(raw) !== String(WINDOW_CONFIG[field])) {
        base[field] = raw;
        configOverrides.push(key);
      }
    }
  }
  return {
    ...base,
    configMode: unsafeOverride ? 'UNSAFE' : 'FROZEN',
    configOverrides,
  };
}

const pad = (value) => String(value).padStart(2, '0');

/** Sello de dia `YYYYMMDD` (nombre de fichero del forward). */
export function dayStamp(date = new Date()) {
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
}

/** Dia `YYYY-MM-DD` (cabecera del ledger). */
export function dayIso(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Carpeta de artefactos de un dia. */
export function runDir(day) {
  return `${RUNS_DIR}/${day}`;
}

/** Fichero dentro de la carpeta de un dia. */
export function runFile(day, name) {
  return join(runDir(day), name);
}

/** Ruta canonica del forward del dia (`operability_runs/forward-market-<DIA>.json`). */
export function forwardPath(day) {
  return `${OPERABILITY_DIR}/forward-market-${day}.json`;
}

/** Directorio-lock (creado con `mkdir`, atomico) que serializa el dia. */
export function runLockDir(day) {
  return `${runDir(day)}/${LOCK_DIR_NAME}`;
}

/**
 * Decide que hacer con un lock existente. Logica PURA (reloj y `isProcessAlive`
 * inyectables) para poder ejercitarla sin tocar el sistema de ficheros:
 *   - sin lock => `acquire`.
 *   - mismo host + PID vivo => `blocked` (un `--force` **no** salta un lock vivo).
 *   - mismo host + PID muerto => `reclaim` (stale inequivoco, sin `--force`).
 *   - otro host / TTL superado => `blocked` salvo `--force` => `reclaim`.
 * @param {{
 *   lock?: Record<string, unknown> | null,
 *   now?: number,
 *   host?: string,
 *   isProcessAlive?: (pid: unknown) => boolean,
 *   ttlMs?: number,
 *   force?: boolean,
 * }} [options]
 */
export function lockDecision({
  lock = null,
  now = Date.now(),
  host = '',
  isProcessAlive = () => false,
  ttlMs = LOCK_TTL_MS,
  force = false,
} = {}) {
  if (!lock || typeof lock !== 'object') {
    return { action: 'acquire', reason: 'sin_lock', stale: false };
  }
  const sameHost = String(lock.host ?? '') !== '' && String(lock.host) === String(host);
  if (sameHost && isProcessAlive(lock.pid)) {
    return { action: 'blocked', reason: 'pid_vivo', stale: false };
  }
  if (sameHost) {
    return { action: 'reclaim', reason: 'pid_muerto', stale: true };
  }
  const startedAt = Date.parse(String(lock.startedAt ?? ''));
  const expired = Number.isFinite(startedAt) && now - startedAt > ttlMs;
  if (force) {
    return { action: 'reclaim', reason: expired ? 'ttl_expirado_force' : 'host_distinto_force', stale: true };
  }
  return { action: 'blocked', reason: expired ? 'ttl_expirado' : 'host_distinto', stale: true };
}

/**
 * Decide que hacer con `window:unlock`. A diferencia de `acquireDayLock`, el
 * unlock es una accion MANUAL del operador: **nunca** debe borrar el lock de un
 * proceso vivo (romper el lock de exclusion mutua permitiria dos `run-day`
 * simultaneos del mismo dia). Logica PURA (reloj y `isProcessAlive` inyectables):
 *   - sin lock => `nothing`.
 *   - lock ilegible (`lock.json` ausente/corrupto: no se puede probar ownership)
 *     => `deny` salvo `--force` => `reclaim` (`lock_ilegible_force`).
 *   - mismo host + PID vivo => `deny` (un `--force` **no** salta un PID vivo: el
 *     operador mata el proceso y el PID pasa a muerto => `reclaim` automatico).
 *   - mismo host + PID muerto => `reclaim` (huerfano inequivoco, sin `--force`).
 *   - otro host + TTL superado (12 h) => `reclaim` (huerfano), sin `--force`.
 *   - otro host + TTL no expirado => `deny` salvo `--force` => `reclaim`.
 * @param {{
 *   lockExists?: boolean,
 *   lock?: Record<string, unknown> | null,
 *   now?: number,
 *   host?: string,
 *   isProcessAlive?: (pid: unknown) => boolean,
 *   ttlMs?: number,
 *   force?: boolean,
 * }} [options]
 */
export function unlockDecision({
  lockExists = false,
  lock = null,
  now = Date.now(),
  host = '',
  isProcessAlive = () => false,
  ttlMs = LOCK_TTL_MS,
  force = false,
} = {}) {
  if (!lockExists) {
    return { action: 'nothing', reason: 'sin_lock', stale: false };
  }
  if (!lock || typeof lock !== 'object') {
    return force
      ? { action: 'reclaim', reason: 'lock_ilegible_force', stale: true }
      : { action: 'deny', reason: 'lock_ilegible', stale: false };
  }
  const base = lockDecision({ lock, now, host, isProcessAlive, ttlMs, force });
  if (base.action === 'acquire') {
    return { action: 'nothing', reason: 'sin_lock', stale: false };
  }
  if (base.action === 'reclaim') {
    return { action: 'reclaim', reason: base.reason, stale: true };
  }
  if (base.reason === 'pid_vivo') {
    return { action: 'deny', reason: 'pid_vivo', stale: false };
  }
  if (base.reason === 'ttl_expirado') {
    return { action: 'reclaim', reason: 'ttl_expirado', stale: true };
  }
  return { action: 'deny', reason: base.reason, stale: false };
}

/**
 * Clasifica el codigo de salida de un script del pipeline.
 * `0` ok · `2` declarado (bloqueo/no material, NO es fallo duro) · `1` uso incorrecto
 * · `null`/otro error duro.
 * @param {number | null | undefined} exitCode
 */
export function classifyExit(exitCode) {
  if (exitCode === 0) return { exit: 0, ok: true, declared: false, hard: false, kind: 'ok' };
  if (exitCode === 2) {
    return { exit: 2, ok: false, declared: true, hard: false, kind: 'declared' };
  }
  if (exitCode === 1) {
    return { exit: 1, ok: false, declared: false, hard: true, kind: 'usage_error' };
  }
  return {
    exit: exitCode ?? null,
    ok: false,
    declared: false,
    hard: true,
    kind: 'error',
  };
}

/**
 * Preflight de `v2_76`: `0` = el universo admite LONG hoy; `2` = veto de regimen
 * legitimo (LONG vetadas; se DECLARA y no se fuerza) ; cualquier otro = error duro.
 * @param {number | null | undefined} exitCode
 */
export function classifyPreflight(exitCode) {
  const base = classifyExit(exitCode);
  if (exitCode === 0) return { ...base, veto: false, status: 'ALLOWED' };
  if (exitCode === 2) return { ...base, veto: true, status: 'NO_MEDIDO_REGIMEN' };
  return { ...base, veto: false, status: 'HARD_ERROR' };
}

/**
 * ¿El payload capturado es el de un preflight REAL? Sirve para no confundir un
 * fallo de arranque del interprete (que puede devolver codigo 2) con un veto de
 * regimen legitimo.
 * @param {unknown} payload
 */
export function isPreflightPayload(payload) {
  return Boolean(
    payload && typeof payload === 'object' && payload.mode === 'preflight' && payload.marketRegime,
  );
}

/**
 * Extrae `marketRegime` del payload de preflight (`v2_76 --preflight-only --json`).
 * @param {unknown} payload
 */
export function parsePreflight(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const regime = payload.marketRegime;
  if (!regime || typeof regime !== 'object') return null;
  return {
    operationalRegime: String(regime.operationalRegime ?? 'UNKNOWN'),
    // ADR-047: la barrera es por símbolo; `entriesAllowedLong` es «algún símbolo pasa».
    entriesAllowedLong: Boolean(regime.entriesAllowedLong),
    entryGateScope:
      typeof regime.entryGateScope === 'string' ? regime.entryGateScope : null,
    symbolsOperable:
      Number.isFinite(Number(regime.symbolsOperable)) ? Number(regime.symbolsOperable) : null,
    // La lectura del agregado conservador, conservada como DECLARACIÓN (no veta).
    entriesAllowedLongGlobal:
      typeof regime.entriesAllowedLongGlobal === 'boolean'
        ? regime.entriesAllowedLongGlobal
        : null,
    aggregate: String(regime.aggregateTrialRegime ?? regime.aggregate ?? ''),
    bySymbol: regime.bySymbol && typeof regime.bySymbol === 'object' ? regime.bySymbol : {},
  };
}

/**
 * Parseo defensivo de un JSON capturado en stdout (devuelve `null` si no lo es).
 * @param {string} text
 */
export function parseJsonLoose(text) {
  const raw = String(text ?? '').trim();
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * Extrae el gate de la ventana (`v2_80 --json` / `--out`). `null` si no lo trae:
 * nunca se fabrica un `0` ni un `READY`.
 * @param {unknown} payload
 */
export function parseGate(payload) {
  if (!payload || typeof payload !== 'object') return null;
  const gate = payload.meta?.gate;
  if (!gate || typeof gate !== 'object') return null;
  const number = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const list = (value) => (Array.isArray(value) ? value.map(String) : []);
  return {
    days: number(gate.days, 0),
    episodes: number(gate.episodes, 0),
    cycles: number(gate.cycles, 0),
    minDays: number(gate.minDays, WINDOW_MIN_DAYS),
    minEpisodes: number(gate.minEpisodes, WINDOW_MIN_EPISODES),
    minCycles: number(gate.minCycles, WINDOW_MIN_CYCLES),
    ready: Boolean(gate.ready),
    measured: Boolean(gate.measured),
    verdict: String(gate.verdict ?? 'INCONCLUSIVE'),
    dayList: list(gate.dayList),
    regimes: list(gate.regimes),
  };
}

/**
 * Parseo de `git rev-parse "HEAD:apps" "HEAD:packages"` (dos lineas, en orden).
 * @param {string} text
 */
export function parseRevParse(text) {
  const lines = String(text ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return { apps: lines[0] ?? '', packages: lines[1] ?? '' };
}

/**
 * Contraste del arbol de codigo contra el sello congelado.
 * @param {{apps: string, packages: string}} revisions
 * @param {ReturnType<typeof windowConfig>} config
 */
export function freezeCheck(revisions, config) {
  const appsOk = revisions.apps === config.appsHash;
  const packagesOk = revisions.packages === config.packagesHash;
  return {
    ok: appsOk && packagesOk,
    apps: revisions.apps,
    packages: revisions.packages,
    expectedApps: config.appsHash,
    expectedPackages: config.packagesHash,
    appsOk,
    packagesOk,
  };
}

/** Estados terminales de un dia (idempotencia: no se re-ejecuta salvo `--force`). */
export const TERMINAL_STATUSES = Object.freeze([
  'NO_MEDIDO_REGIMEN',
  'MEDIDO',
  'DECLARADO',
  'HARD_ERROR',
  // v2.88.143: un fin de semana NO es un dia de ventana. Se registra como terminal
  // para que una re-ejecucion del mismo dia se omita (y para no contarlo como veto).
  'NON_MARKET_DAY',
]);

/**
 * Estado del dia cuando NO hay sesion de mercado (v2.88.143).
 *
 * Motivo: la tarea diaria corre `/sc daily` **tambien sabados y domingos** y el runner
 * escribia una fila de **veto de regimen** en el ledger, de modo que un sabado parecia
 * «un dia de ventana intentado y vetado». Un dia sin sesion no es ninguna de las dos
 * cosas: se registra `NON_MARKET_DAY` y **no se ejecuta el preflight**.
 */
export const NON_MARKET_DAY_STATUS = 'NON_MARKET_DAY';

/**
 * ¿Es dia de mercado? **Puro.** Solo descarta **fin de semana** (sabado/domingo).
 *
 * **Limite declarado:** NO cubre **festivos** de bolsa. Se usa la misma regla que el
 * vigia (`window_day_watch_worker.evaluate_day_watch`, `weekday() >= 5`) para que los dos
 * instrumentos no puedan discrepar sobre si el dia era de mercado.
 *
 * @param {Date} [date] instante en hora local del proceso (Europe/Madrid en el runner)
 * @returns {boolean}
 */
export function isMarketDay(date = new Date()) {
  const value = date instanceof Date ? date : new Date(date);
  const weekday = value.getDay(); // 0 = domingo … 6 = sabado
  return weekday !== 0 && weekday !== 6;
}


/** @param {unknown} status */
export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.includes(String(status ?? ''));
}

/**
 * Decide el estado del dia a partir de las clasificaciones de cada paso.
 * Veto de regimen manda; un fallo duro manda sobre "declarado".
 * @param {{ preflight?: ReturnType<typeof classifyPreflight>, window?: ReturnType<typeof classifyExit>, hard?: boolean }} steps
 */
export function resolveDayStatus(steps) {
  if (steps.hard) return 'HARD_ERROR';
  if (steps.preflight?.veto) return 'NO_MEDIDO_REGIMEN';
  if (steps.preflight?.hard) return 'HARD_ERROR';
  if (steps.window?.ok) return 'MEDIDO';
  return 'DECLARADO';
}

/**
 * Ultima fila por dia (el ledger puede tener re-ejecuciones con `--force`).
 * @param {Array<Record<string, unknown>>} rows
 */
export function latestByDay(rows) {
  const map = new Map();
  for (const row of rows ?? []) {
    const day = String(row?.day ?? '').trim();
    if (!day) continue;
    map.set(day, row);
  }
  return [...map.values()].sort((a, b) => String(a.day).localeCompare(String(b.day)));
}

/**
 * Resumen honesto del ledger: cuenta dias por estado y adjunta el gate de la
 * ventana (o `null` si aun no se puede leer: nunca `0` fabricado).
 * @param {Array<Record<string, unknown>>} rows
 * @param {ReturnType<typeof parseGate>} [gate]
 */
export function summarizeLedger(rows, gate = null) {
  const days = latestByDay(rows);
  const count = (status) => days.filter((row) => row.status === status).length;
  // v2.88.143: los dias SIN sesion (fin de semana) no son dias de ventana. Se cuentan
  // aparte y NO entran en `total`, para que «N dias» siga significando lo que parece.
  const nonMarketDays = days
    .filter((row) => row.status === NON_MARKET_DAY_STATUS)
    .map((row) => row.day);
  const marketDays = days.filter((row) => row.status !== NON_MARKET_DAY_STATUS);
  return {
    days,
    total: marketDays.length,
    rows: days.length,
    nonMarket: nonMarketDays.length,
    nonMarketDays,
    measured: count('MEDIDO'),
    vetoed: count('NO_MEDIDO_REGIMEN'),
    declared: count('DECLARADO'),
    hardErrors: count('HARD_ERROR'),
    measuredDays: days.filter((row) => row.status === 'MEDIDO').map((row) => row.day),
    vetoedDays: days.filter((row) => row.status === 'NO_MEDIDO_REGIMEN').map((row) => row.day),
    gate,
    ready: Boolean(gate?.ready),
  };
}

/**
 * Comprueba que el gate que se va a pintar procede de un run **ligado** al ledger
 * y al arbol congelado: mismo dia/cuenta/versionA, freeze certificado, sha256 del
 * `window.json` del run y cabecera (`meta.header`) coherente. Logica PURA.
 * Cualquier problema => `ok:false` (el runner NO debe mostrar el gate).
 * @param {{
 *   ledgerRow?: Record<string, unknown> | null,
 *   manifest?: Record<string, unknown> | null,
 *   windowGate?: ReturnType<typeof parseGate> | null,
 *   windowJsonSha256?: string | null,
 *   windowHeader?: Record<string, unknown> | null,
 *   frozen?: typeof WINDOW_CONFIG,
 * }} [options]
 */
export function verifyWindowProvenance({
  ledgerRow = null,
  manifest = null,
  windowGate = null,
  windowJsonSha256 = null,
  windowHeader = null,
  frozen = WINDOW_CONFIG,
} = {}) {
  const problems = [];
  if (!manifest || typeof manifest !== 'object') {
    return { ok: false, problems: ['sin_manifest'] };
  }
  const provenance = manifest.windowProvenance;
  if (!provenance || typeof provenance !== 'object') problems.push('sin_provenance');
  if (!windowGate) problems.push('sin_gate');
  if (!manifest.freeze || manifest.freeze.ok !== true) {
    problems.push('freeze_no_certificado');
  } else {
    if (manifest.freeze.apps !== frozen.appsHash) problems.push('apps_hash_no_congelado');
    if (manifest.freeze.packages !== frozen.packagesHash) problems.push('packages_hash_no_congelado');
  }
  if (manifest.configMode === 'UNSAFE') problems.push('config_override_unsafe');
  if (ledgerRow) {
    if (String(ledgerRow.day ?? '') !== String(manifest.day ?? '')) problems.push('dia_no_coincide');
    if (String(ledgerRow.account ?? '') !== String(manifest.account ?? '')) {
      problems.push('cuenta_no_coincide');
    }
    if (String(ledgerRow.versionA ?? '') !== String(manifest.versionA ?? '')) {
      problems.push('version_a_no_coincide');
    }
  }
  if (provenance && provenance.windowJsonSha256) {
    if (!windowJsonSha256 || windowJsonSha256 !== provenance.windowJsonSha256) {
      problems.push('sha256_no_coincide');
    }
  }
  if (windowHeader) {
    if (String(windowHeader.account ?? '') !== String(manifest.account ?? '')) {
      problems.push('window_cuenta_no_coincide');
    }
    const versions = Array.isArray(windowHeader.versions) ? windowHeader.versions.map(String) : [];
    if (versions.length > 0 && !versions.includes(String(manifest.versionA ?? ''))) {
      problems.push('window_version_no_coincide');
    }
  } else {
    problems.push('sin_window_header');
  }
  return { ok: problems.length === 0, problems };
}

// ---------------------------------------------------------------------------
// Wrapper `.cmd` de la tarea programada (v2.88.142)
// ---------------------------------------------------------------------------

/**
 * Contenido del wrapper `.cmd` que ejecuta la tarea diaria de Windows.
 *
 * **Puro** (sin FS ni `process`): se prueba en `window-forward.test.mjs`.
 *
 * Dos defectos REALES cerrados aqui, ambos medidos:
 * 1. `2.11.140` — `/tr "cmd /c \"cd ... && ...\""` con comillas ANIDADAS rompia
 *    `schtasks` («Falta la opcion obligatoria "sc"»): el wrapper usa una ruta SIN
 *    comillas anidadas, de modo que `/tr "<ruta>"` es un unico token.
 * 2. `2.11.142` — el wrapper invocaba `<root>\node_modules\.bin\pnpm.cmd`, que **no
 *    existe** en este repo (pnpm es instalacion GLOBAL, no dependencia del arbol) y que
 *    tampoco esta en el PATH del Programador de tareas => las dos tareas quedaban
 *    `Estado: Listo` y **no ejecutaban nada** («no se reconoce como un comando interno
 *    o externo»). Ahora se invoca **node por ruta absoluta** sobre el runner: cero
 *    dependencia de pnpm/PATH. `exit /b %ERRORLEVEL%` propaga el codigo (3 = hubo aviso).
 *
 * @param {{root: string, node: string, runner: string, command: string}} parts
 *   Rutas absolutas (se normalizan a `\`) y el subcomando del runner (`run-day`/`watch`).
 * @returns {string}
 */
export function cmdWrapperContent({ root, node, runner, command }) {
  const norm = (value) =>
    String(value ?? '')
      .trim()
      .replace(/[\\/]+$/, '')
      .replace(/\//g, '\\');
  const dir = norm(root);
  const exe = norm(node);
  const script = norm(runner);
  const cmd = String(command ?? '').trim();
  if (!dir || !exe || !script || !cmd) {
    throw new Error('cmdWrapperContent: faltan root/node/runner/command');
  }
  if (!/^[A-Za-z]:\\/.test(exe)) {
    throw new Error('cmdWrapperContent: `node` debe ser una ruta absoluta de Windows');
  }
  return (
    '@echo off\r\n' +
    'setlocal\r\n' +
    `cd /d "${dir}"\r\n` +
    'if errorlevel 1 exit /b 1\r\n' +
    `"${exe}" "${script}" ${cmd}\r\n` +
    'exit /b %ERRORLEVEL%\r\n'
  );
}

/** Marca que `task:install` exige leer del XML registrado (verificacion POST-registro). */
export const START_WHEN_AVAILABLE_MARKER =
  '<StartWhenAvailable>true</StartWhenAvailable>';

const TASK_TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Escapa texto para XML (nombre/descripcion/ruta no son de fiar como literales). */
function xmlEscape(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * `2.11.144` — XML de una tarea diaria de Windows. Logica PURA.
 *
 * **Por que XML y no `/tr`:** `schtasks /create` **no** expone «Iniciar la tarea si se
 * omitio el inicio programado» (`StartWhenAvailable`); esa opcion **solo existe en el
 * XML** de la tarea (o via `Set-ScheduledTask`). Defecto medido el `18/10/2026`: el
 * equipo estaba en **modern standby** a las `18:00` y la tarea se ejecuto a las
 * `18:39` (primer despertar de mantenimiento), con `StartWhenAvailable = False`; si el
 * equipo **no** despierta en todo el dia, el dia **se pierde**.
 *
 * **Decisiones declaradas (no se cambian de tapadillo):**
 * - `StartWhenAvailable = true` ⇒ si el equipo estaba dormido/apagado, la corrida se
 *   recupera **en cuanto haya sesion**; el runner sella **el dia del reloj al arrancar**,
 *   asi que una recuperacion dentro del mismo dia sigue siendo ese dia.
 * - `DisallowStartIfOnBatteries` / `StopIfGoingOnBatteries` quedan en **`true`** (el
 *   valor medido antes de este cambio): se preserva el comportamiento, no se amplia el
 *   alcance. Que la ventana no corra con bateria es un **limite declarado**, no un bug.
 * - `WakeToRun = false`: despertar el equipo a diario tiene coste real y depende de
 *   hardware/BIOS ⇒ **no** se activa sin decision explicita del operador.
 * - `LogonType = InteractiveToken` (solo interactivo, igual que antes) y `IgnoreNew`.
 *
 * @param {{name: string, time: string, wrapper: string, description?: string,
 *          date?: Date, startWhenAvailable?: boolean,
 *          disallowStartIfOnBatteries?: boolean,
 *          stopIfGoingOnBatteries?: boolean, wakeToRun?: boolean}} parts
 * @returns {string} XML completo (se persiste como UTF-16 con BOM)
 */
export function taskXml({
  name,
  time,
  wrapper,
  description = '',
  date = new Date(),
  startWhenAvailable = true,
  disallowStartIfOnBatteries = true,
  stopIfGoingOnBatteries = true,
  wakeToRun = false,
}) {
  const taskName = String(name ?? '').trim();
  const stamp = String(time ?? '').trim();
  const command = String(wrapper ?? '').trim();
  if (!taskName) throw new Error('taskXml: falta `name`');
  if (!command) throw new Error('taskXml: falta `wrapper`');
  if (!TASK_TIME_RE.test(stamp)) {
    throw new Error('taskXml: `time` debe ser HH:MM (00:00–23:59)');
  }
  const day = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(day.getTime())) throw new Error('taskXml: `date` no es una fecha');
  const yyyy = String(day.getFullYear()).padStart(4, '0');
  const mm = String(day.getMonth() + 1).padStart(2, '0');
  const dd = String(day.getDate()).padStart(2, '0');
  const bool = (value) => (value ? 'true' : 'false');
  const note = String(description ?? '').trim() || `Bolsa V1 · ${taskName}`;
  return (
    '<?xml version="1.0" encoding="UTF-16"?>\r\n' +
    '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\r\n' +
    '  <RegistrationInfo>\r\n' +
    `    <Description>${xmlEscape(note)}</Description>\r\n` +
    `    <URI>\\${xmlEscape(taskName)}</URI>\r\n` +
    '  </RegistrationInfo>\r\n' +
    '  <Triggers>\r\n' +
    '    <CalendarTrigger>\r\n' +
    `      <StartBoundary>${yyyy}-${mm}-${dd}T${stamp}:00</StartBoundary>\r\n` +
    '      <Enabled>true</Enabled>\r\n' +
    '      <ScheduleByDay>\r\n' +
    '        <DaysInterval>1</DaysInterval>\r\n' +
    '      </ScheduleByDay>\r\n' +
    '    </CalendarTrigger>\r\n' +
    '  </Triggers>\r\n' +
    '  <Principals>\r\n' +
    '    <Principal id="Author">\r\n' +
    '      <LogonType>InteractiveToken</LogonType>\r\n' +
    '      <RunLevel>LeastPrivilege</RunLevel>\r\n' +
    '    </Principal>\r\n' +
    '  </Principals>\r\n' +
    '  <Settings>\r\n' +
    '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\r\n' +
    `    <DisallowStartIfOnBatteries>${bool(disallowStartIfOnBatteries)}</DisallowStartIfOnBatteries>\r\n` +
    `    <StopIfGoingOnBatteries>${bool(stopIfGoingOnBatteries)}</StopIfGoingOnBatteries>\r\n` +
    '    <AllowHardTerminate>true</AllowHardTerminate>\r\n' +
    `    <StartWhenAvailable>${bool(startWhenAvailable)}</StartWhenAvailable>\r\n` +
    '    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>\r\n' +
    '    <IdleSettings>\r\n' +
    '      <StopOnIdleEnd>true</StopOnIdleEnd>\r\n' +
    '      <RestartOnIdle>false</RestartOnIdle>\r\n' +
    '    </IdleSettings>\r\n' +
    '    <AllowStartOnDemand>true</AllowStartOnDemand>\r\n' +
    '    <Enabled>true</Enabled>\r\n' +
    '    <Hidden>false</Hidden>\r\n' +
    '    <RunOnlyIfIdle>false</RunOnlyIfIdle>\r\n' +
    `    <WakeToRun>${bool(wakeToRun)}</WakeToRun>\r\n` +
    // PT72H = el limite por defecto de `schtasks /create`: se preserva tal cual.
    '    <ExecutionTimeLimit>PT72H</ExecutionTimeLimit>\r\n' +
    '    <Priority>7</Priority>\r\n' +
    '  </Settings>\r\n' +
    '  <Actions Context="Author">\r\n' +
    '    <Exec>\r\n' +
    `      <Command>${xmlEscape(command)}</Command>\r\n` +
    '    </Exec>\r\n' +
    '  </Actions>\r\n' +
    '</Task>\r\n'
  );
}

