# Evidencia cruda — `v2.88.31-beta` (OPS: el runner de la ventana PAPER deja de poder contaminar la medición)

> **Objeto:** package **`2.11.31-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-02**.
> **Clase:** sello **de operación** sobre el runner de la ventana PAPER `≥4 días`. Cierra los **3 hallazgos** de la auditoría de `v2.88.30-beta` (lock diario, config de freeze inmutable, provenance del gate). **`Δ decisión motor = 0`**: no se toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B, UI ni migraciones; **sin cambios de producto Python**.
> **Padre:** [`evidence/v2.88.30/README.md`](../v2.88.30/README.md) (runner PAPER + fix del Monitor AUTO).
> **Nomenclatura:** `AUTO engineering release = v2.88.31-beta` · `application package = 2.11.31-beta`.

---

## 0. Qué corrige este sello

| # | Grieta (auditoría de `v2.88.30`) | Corrección |
|---|---|---|
| **P0 🔴 · lock** | `run-day` sólo miraba `existsSync(manifest.json) && !--force`: dos ejecuciones del mismo día podían hacer `preflight→…→audit` a la vez y escribir el mismo material. | `acquireDayLock`: `mkdir` de `operability_runs/window-runs/<DIA>/.run.lock/` (indivisible) **antes** de la idempotencia y del freeze; liberación en `try/finally`; `RUN_ALREADY_IN_PROGRESS` si ya corre; `--force` **no** salta un lock vivo; `window:unlock` como escape hatch; aviso en `status`. |
| **P1 🟠 · freeze** | `windowConfig(env)` dejaba que `WINDOW_APPS_HASH`/`WINDOW_PACKAGES_HASH`/`WINDOW_ACCOUNT`/`WINDOW_VERSION_A`/`WINDOW_VERSION_B`/`WINDOW_WATCH_SIZE` sustituyeran la config certificada ⇒ el `TREE_MOVED` dejaba de ser un freeze. | `windowConfig(env, { unsafeOverride })` **ignora** esas variables por defecto; el override exige `--unsafe-override-window-config` (o `WINDOW_UNSAFE_CONFIG_OVERRIDE=1`) y sella `configMode`/`configOverrides` en `manifest.json`, en el ledger y con aviso; un run `UNSAFE` invalida su gate. |
| **P2 🟠 · provenance** | `status` combinaba `ledger.jsonl` con el `operability-window.json` **canónico** sin ligarlos ⇒ podía pintar un `4/2/32` de otra ejecución (material stale) con el ledger vacío. | Al copiar el `window.json` al run se sella `windowProvenance` (incl. `sha256`); `window:status` **deriva** el gate del `window.json` del run y lo valida (`verifyWindowProvenance`): si no liga ⇒ `STALE`/`NO_MEDIDO`, **nunca** un gate heredado. |
| 🟢 · veto | *(no regresión)* `exit 2` sin payload sigue siendo `HARD_ERROR`. | Cubierto por test (`classifyPreflight`, `isPreflightPayload`, `resolveDayStatus`). |
| 🟡 · ventana | **No se cierra la ventana PAPER.** | `status` sigue declarando `NO_MEDIDO` (ledger vacío). Este sello endurece el instrumento, no fabrica días. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Un segundo `run-day` del mismo día **no** arranca (`RUN_ALREADY_IN_PROGRESS`), y `--force` **no** salta un lock vivo. | Volver a `existsSync(manifest)` sin lock ⇒ dos corridas conviven. | `node scripts/window-forward-runner.mjs run-day` con `.run.lock` de PID vivo ⇒ exit `1` (probado con y sin `--force`) |
| **C2** | Un lock con PID muerto en el mismo host se **reclama**; el lock se libera siempre al terminar. | No liberar en `finally` ⇒ el día queda bloqueado para siempre. | `run-day` con lock huérfano ⇒ `lock huerfano (pid_muerto)`, corre y el `.run.lock` queda **ausente** |
| **C3** | `windowConfig` **ignora** los overrides de freeze sin flag; con `--unsafe-override-window-config` los aplica y sella `UNSAFE`. | Aceptar `WINDOW_APPS_HASH` sin flag ⇒ `TREE_MOVED` evitable. | `window-forward.test.mjs` (3 tests de config) + `--dry-run` (hash ajeno sin flag ⇒ sigue `FROZEN`/`freeze OK`) |
| **C4** | `window:status` **no** pinta un gate sin provenance válida. | Leer `operability-window.json` a pelo ⇒ pinta un gate stale con ledger vacío. | Fixture con `MEDIDO` sin provenance ⇒ `gate: STALE`; `window.json` corrompido ⇒ `STALE (sha256_no_coincide)`; provenance válida ⇒ `gate READY (run …)` |
| **C5** | Un `exit 2` sin payload de preflight sigue siendo `HARD_ERROR`, nunca veto. | Tratar cualquier `exit 2` como veto ⇒ el fallo desaparece. | `window-forward.test.mjs` (`isPreflightPayload`, `classifyPreflight`, `resolveDayStatus`) |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `node --test scripts/lib/window-forward.test.mjs` (`pnpm window:test`) | **`19` tests, `19` pass, `0` fail** |
| `node scripts/window-forward-runner.mjs --dry-run run-day` | `config FROZEN` · `freeze OK · apps 2237f069… · packages ce0a38b7…` |
| `WINDOW_UNSAFE_CONFIG_OVERRIDE=1 WINDOW_APPS_HASH=… node … --dry-run run-day` | `CONFIG_OVERRIDE = UNSAFE` · `freeze NO OK` (hashes del freeze respetados, no reescritos) |
| `node … run-day` con `.run.lock` de PID vivo (con y sin `--force`) | `RUN_ALREADY_IN_PROGRESS (pid_vivo)` · exit `1` |
| `node … run-day` con lock huérfano (PID muerto) | `lock huerfano (pid_muerto)` · día terminal omitido · `.run.lock` **ausente** al terminar |
| `node … status` (fixtures de ledger/`window.json`) | sin provenance ⇒ `STALE`; sha corrupto ⇒ `STALE (sha256_no_coincide)`; provenance válida ⇒ `gate READY (run 20261002)`; ledger vacío ⇒ `NO_MEDIDO` |
| `node … status` con `.run.lock` vivo | `RUN EN CURSO: dia … (pid …) — no lances otro run-day` |
| `pnpm --filter @bolsa/web test` / `typecheck` | *(no se toca UI; se re-ejecuta para descartar regresión)* |
| **CI de tag** — `Release tag CI` run [`37049811028`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37049811028) (`ref=refs/tags/v2.88.31-beta`, HEAD `1f870100`, `2026-10-02T18:47:24Z → 18:55:33Z`) | **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. El job `shared` estrena el step **Window runner guards** (`pnpm window:test`) → `# tests 19 · # pass 19 · # fail 0`; `shared` además **96 ficheros / 798 tests `passed` (+1 todo)**. `python`: **`4324 passed, 45 skipped`** (**idéntico a `v2.88.30`** ⇒ sin cambios de producto Python). `frontend`: **`235` ficheros / `1355` tests `passed`** · `passed=true · critical=0 · warn=0`. `lifecycle-pg`: Golden Day 2.0 `2 passed` · Crash/Recovery `2 passed` · Concurrent AUTO `3 passed` · crash injection matrix `2 passed` · multiprocess AUTO `1 passed` (gates *fail-if-skipped*). `replay-repro`: `REPRODUCIDO` (`1E3ADAC2…`, 2ª corrida IDÉNTICA) ⇒ el árbol no mueve el artefacto OOS |

> El step nuevo `Window runner guards` (`pnpm window:test`) ya corre en el job `shared` del `Release tag CI`.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No cierra la ventana PAPER.** `≥4 días` / `≥2 episodios` / `≥32 ciclos` sigue **abierta**; el `status`
   honesto es `NO_MEDIDO` (ledger vacío, `BEAR_TREND` posible veto de régimen).
2. **Cuenta fija supeditada a la BD alcanzable** (bloqueante declarado en `v2.88.29` §0.1): el runner no la
   crea ni la siembra.
3. **No re-mide `Δ motor = 0` con PG real**: no hay cambio de motor que re-medir.
4. **Sin migración / sin backfill** (head `048`).
5. **Provenance sólo en el runner (Node):** no se modifica `v2_80_market_window.py` ni se añade provenance al
   `meta` del capturador Python (decisión del propietario); el `window.json` del run se contrasta por
   `sha256` + cabecera (`meta.header`).
6. **`PROJECT_STATE.md`/engineering-index no se tocan** (mismo criterio que `v2.88.25`–`v2.88.30`).

---

## 4. Comandos (reproducir)

```bash
pnpm window:test
node scripts/window-forward-runner.mjs --dry-run run-day
node scripts/window-forward-runner.mjs status
node scripts/window-forward-runner.mjs unlock
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
```

---

## 5. Sello

- **Versión:** `2.11.31-beta` (base `2.11.30-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros de operación:** `scripts/lib/window-forward.mjs` (config inmutable, `lockDecision`, `verifyWindowProvenance`), `scripts/window-forward-runner.mjs` (lock, `--unsafe-override-window-config`, `unlock`, provenance + `sha256`), `scripts/lib/window-forward.test.mjs` (nuevo), `package.json` (`window:unlock`/`window:test`, bump), `.github/workflows/release-tag-ci.yml` (step `pnpm window:test` en `shared`), docs de runbook/arranque.
- **RELEASE (GitHub):** `v2.88.31-beta` — *pre-release* sobre el tag anotado.
- **CITA REAL DEL CI (POST-TAG, 2026-10-02):** `Release tag CI` run [`37049811028`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37049811028) (`ref=refs/tags/v2.88.31-beta`, HEAD `1f870100`) → **`SUCCESS`**: 11 jobs `success` + `playwright (integrated E2E, opt-in)` `skipped` por diseño, `certify` `success`. Step nuevo en `shared` **Window runner guards** (`pnpm window:test`) **`19/19`**; `python` **`4324 passed, 45 skipped`** (idéntico a `v2.88.30`); `frontend` **`235` ficheros / `1355` tests `passed`**; `lifecycle-pg` **VERDE** (Golden Day 2.0 `2 passed`, Crash/Recovery `2 passed`, Concurrent AUTO `3 passed`, gates *fail-if-skipped*); `replay-repro` **REPRODUCIDO** (`1E3ADAC2…`, 2ª corrida IDÉNTICA) ⇒ el árbol no mueve el artefacto OOS.
- **`Δ motor = 0`:** ningún fichero de motor/producto Python tocado; sin cambios de contrato.
