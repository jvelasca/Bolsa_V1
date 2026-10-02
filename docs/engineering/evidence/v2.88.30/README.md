# Evidencia cruda — `v2.88.30-beta` (OPS: runner de la ventana PAPER ≥4 días · AUTO: el Monitor vuelve a pintarse)

> **Objeto:** package **`2.11.30-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-02**.
> **Clase:** sello **híbrido** — una pieza de **operación** (automatizar el pipeline de la ventana PAPER `≥4 días`, que era el salto siguiente declarado por `v2.88.29`) y un **fix de producto de UI** (el Monitor AUTO no pintaba contra la API real). **Sin tocar motor**: ni umbrales, ni `TOP_N`, ni régimen, ni allocation, ni la lógica de entrada/salida.
> **Padre:** [`evidence/v2.88.29/README.md`](../v2.88.29/README.md) (Golden Day 2.0 v2 · hechos durables + precio real en PG real) · [`evidence/v2.88.28/README.md`](../v2.88.28/README.md) (`PROTECTION` exactly-once).
> **Nomenclatura:** `AUTO engineering release = v2.88.30-beta` · `application package = 2.11.30-beta` (el tag de ingeniería **no** es el semver del paquete).

---

## 0. Qué produce este sello

| # | Hueco (hasta `v2.88.29`) | Hecho que se produce / se mide ahora |
|---|---|---|
| **H1 🟠 · ops** | La ventana PAPER `≥4 días` estaba **declarada** como siguiente salto pero sólo existía como protocolo manual del runbook (`§3.1`): el operador encadenaba a mano `v2_76`→`v2_77`→`v2_80`→`v2_83`, riesgo de pasos olvidados y de contaminar el árbol congelado. | `scripts/window-forward-runner.mjs` (+ `scripts/lib/window-forward.mjs`) encadena el pipeline con **arte factual por día** (`operability_runs/window-runs/<DIA>/`), **ledger acumulado** (`ledger.jsonl`) y `manifest.json` con el gate. Scripts `window:*` en `package.json`. |
| **H2 🟠 · ops** | Un `exit 2` del preflight se confundía con un veto de régimen (y un fallo real con un veto). | `exit 2` **sólo** es `NO_MEDIDO_REGIMEN` si el preflight devuelve **JSON válido** (`mode: 'preflight'`); si no, `HARD_ERROR`. Un día vetado se registra **sin** exigir la API web viva. |
| **H3 🟠 · ops** | Nada impedía correr la ventana sobre un árbol ya movido (la ventana dejaría de ser de un solo árbol). | `freezeCheck`: compara `git rev-parse "HEAD:apps" "HEAD:packages"` con los hashes pinneados; si el código se mueve ⇒ `TREE_MOVED` y **aborta** (`fail-closed`). |
| **H4 🔴 · producto** | El **Monitor AUTO** (`/auto-monitor`) quedaba **en blanco**: `view = null`, sin `Cargando` y sin error. | El endpoint `GET /api/auto/operational-monitor` responde el `AutoOperationalMonitorDto` **directo**, no un envoltorio `{ data }`; se corrige el tipo del cliente y el consumo del hook ⇒ la UI monta header, notas, timeline, reservas y concurrencia. |
| **H5 🟡 · producto** | La suite del monitor **mockeaba el hook**, así que el bug de forma de respuesta era invisible. | Nuevo `auto-monitor-page.test.tsx` monta la **página real** (sólo mockea API + cuenta activa) contra el DTO directo; **muerde** (rojo) si vuelve el acceso con envoltorio. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | El runner encadena los 5 pasos con los flags de operación **sólo** en el `env` del hijo. | Exportar los flags en el shell contaminante ⇒ las suites PG de proceso dan falso rojo (`precio AUSENTE ⇒ HOLD`). | `node scripts/window-forward-runner.mjs --dry-run run-day` (imprime el env del hijo) |
| **C2** | Un `exit 2` sin payload de preflight es `HARD_ERROR`, **nunca** `NO_MEDIDO_REGIMEN`. | Tratar cualquier `exit 2` como veto ⇒ un fallo real se registra como "no computable" y desaparece. | clasificación en `scripts/lib/window-forward.mjs` (`isPreflightPayload`) |
| **C3** | La ventana **aborta** si el árbol de código se movió (`TREE_MOVED`). | Editar `apps`/`packages` sin re-anclar ⇒ el runner declara `TREE_MOVED`. | `freezeCheck` vs `git rev-parse "HEAD:apps" "HEAD:packages"` → `freeze OK` (`apps 2237f069…` · `packages ce0a38b7…`) |
| **C4** | **Producto:** el Monitor AUTO pinta la cadena contra el DTO **directo** del endpoint. | Volver a `query.data.data` ⇒ `view = null`, página en blanco sin `Cargando` ni error. | `apps/web/src/features/auto-monitor/auto-monitor-page.test.tsx` |
| **C5** | El contrato no drifta: **sin migración** (head `048`) y `openapi.json`/`schema.d.ts`/shared sin cambios. | Tocar el DTO / la cadena ⇒ `contract:check`/`alembic heads` rojo. | `uv run alembic heads` → `048_journal_entry_dedupe_key (head)` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `pnpm --filter @bolsa/web exec vitest run` | **`Test Files 235 passed (235)`** · **`Tests 1355 passed (1355)`** (incluye el nuevo `auto-monitor-page.test.tsx`) |
| `pnpm --filter @bolsa/web typecheck` (`tsc -b --noEmit`) | **limpio** (exit `0`) |
| Morder la regresión: reintroducir `query.data.data` en el hook | `auto-monitor-page.test.tsx` **rojo** (`waitFor` de `auto-monitor-header` nunca resuelve); restaurado ⇒ **verde** |
| App en vivo (`pnpm dev` → API `:8000` + web `:5173`) | `/auto-monitor` monta `auto-monitor-header`, notas, timeline (`Sin ciclos durables en la ventana`, correcto: aún sin días de forward), reservas y `auto-monitor-concurrency`; **0** errores de consola |
| Terminal dev observado ~7 min (3 pasadas) | **0** respuestas `HTTP 500`; sin `Traceback`/`Exception`/`ECONNREFUSED`/`EADDRINUSE`; puertos `8000`/`5173`/`3002` a la escucha; único ruido: `DeprecationWarning [DEP0190]` de Node (inofensivo) |
| `node scripts/window-forward-runner.mjs status` | `estado de la ventana · 4 dias / 2 episodios / 32 ciclos`; `ledger vacio: aun no hay ningun dia registrado (NO MEDIDO, nunca 0)` |
| `node scripts/window-forward-runner.mjs --dry-run run-day` | `freeze OK · apps 2237f069… · packages ce0a38b7…`; imprime la cadena de 5 pasos y los flags de operación del hijo |
| `uv run alembic heads` (en `packages/py/infrastructure`) | `048_journal_entry_dedupe_key (head)` (**sin migración**) |
| **CI de tag** — `Release tag CI` run [`37042907416`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37042907416) (`ref=refs/tags/v2.88.30-beta`, HEAD `52a07e19`, `2026-10-02T17:45:44Z → 17:53:19Z`) | **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. `python`: **`4324 passed, 45 skipped`** (**idéntico a `v2.88.29`** ⇒ sin cambios de producto Python). `frontend`: **`235` ficheros / `1355` tests `passed`** · `passed=true · critical=0 · warn=0`. `lifecycle-pg`: Golden Day 2.0 `2 passed` · Crash/Recovery `2 passed` · Concurrent AUTO `3 passed` · crash injection matrix `2 passed` · multiprocess AUTO `1 passed` (gates *fail-if-skipped*). `replay-repro`: `REPRODUCIDO` (`1E3ADAC2…`, 2ª corrida IDÉNTICA) |

> Nota de honestidad: no hay cambios de **producto Python**, así que este sello **no** re-cita `ruff`/`mypy`/`pytest` (los certificó `v2.88.29`). El runner es **Node** (sólo-lanzador) y el fix es **UI**. La certificación del árbol completo la hace el job `python`/`lifecycle-pg`/`frontend` del `Release tag CI`.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No cierra la ventana PAPER.** Automatiza el **pipeline**; la ventana `≥4 días` / `≥2 regímenes` sigue **abierta** (necesita días reales distintos; hoy el preflight declara `BEAR_TREND` ⇒ día no computable).
2. **La cuenta fija (`1484e253…`) sigue ausente de la BD alcanzable** (bloqueante declarado en `v2.88.29` §0.1): el runner no la crea ni la siembra.
3. **No re-mide `Δ motor = 0` con PG real**: no hay cambio de motor que re-medir.
4. **Sin migración / sin backfill** (head `048`).
5. **`PROJECT_STATE.md`/engineering-index no se tocan** (mismo criterio que `v2.88.25`–`v2.88.29`).

---

## 4. Comandos (reproducir)

```bash
pnpm --filter @bolsa/web exec vitest run
pnpm --filter @bolsa/web typecheck
node scripts/window-forward-runner.mjs status
node scripts/window-forward-runner.mjs --dry-run run-day
node scripts/window-forward-runner.mjs preflight          # requiere la API/py operativa
uv run alembic heads                                       # en packages/py/infrastructure
```

---

## 5. Sello

- **Versión:** `2.11.30-beta` (base `2.11.29-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros de operación:** `scripts/window-forward-runner.mjs`, `scripts/lib/window-forward.mjs`, `package.json` (`window:*`), `scripts/lib/window-forward.mjs` (re-anclaje `v2.88.30-beta`), docs de runbook/arranque.
- **Ficheros de producto:** `apps/web/src/lib/api.ts` (tipo del endpoint), `apps/web/src/features/auto-monitor/use-auto-operational-monitor.ts` (consumo del DTO directo) + `apps/web/src/features/auto-monitor/auto-monitor-page.test.tsx` (regresión que muerde).
- **RELEASE (GitHub, auditabilidad externa):** `v2.88.30-beta` — *pre-release* sobre el tag anotado, con estas notas.
- **CI:** el push del tag dispara `release-tag-ci.yml` (security, shared, decision-spine, python, lifecycle-pg, replay-repro, dr-verify, a7-gate, frontend, playwright mock, certify).
- **CITA REAL DEL CI (POST-TAG, 2026-10-02):** `Release tag CI` run [`37042907416`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37042907416) (`ref=refs/tags/v2.88.30-beta`, HEAD `52a07e19`) → **`SUCCESS`**: 11 jobs `success` + `playwright (integrated E2E, opt-in)` `skipped` por diseño, `certify` `success`. `python` **`4324 passed, 45 skipped`** (idéntico a `v2.88.29`); `frontend` **`235` ficheros / `1355` tests `passed`**; `lifecycle-pg` **VERDE** (Golden Day 2.0 `2 passed`, Crash/Recovery `2 passed`, Concurrent AUTO `3 passed`, gates *fail-if-skipped*); `replay-repro` **REPRODUCIDO** (`1E3ADAC2…`, 2ª corrida IDÉNTICA) ⇒ el árbol no mueve el artefacto OOS.
