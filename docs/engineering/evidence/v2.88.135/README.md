# Evidencia `v2.88.135-beta` — alineación de la ventana al universo ESTUDIO, bundle de evidencia P1-P4 (`v2_100`) y helper de re-anclaje del pin

> **Bump:** `2.11.134-beta` → **`2.11.135-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y del NUEVO `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **de producto acotado + tooling de operación** — **no** toca motor de decisión, umbrales, contrato HTTP ni esquema. · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **SIN migración** (head `053_dia_d_cycle_verifications`). **`Δ motor` acotado al ORIGEN del watch** (se cambia de dónde sale la lista, no la decisión). Tag **unsigned**.
>
> **Base:** `v2.88.134-beta`.

---

## 0. Qué cierra (y qué NO)

**Cierra** tres frentes de **instrumentación** para poder operar los pendientes `P1`-`P4`:

1. **`P1`/`P2` alineados:** la lane operada de la ventana mide el universo **ESTUDIO** (no el catálogo), de modo que un mismo conjunto de días sirve a la ventana (días/regímenes/ciclos) y a la evidencia por instrumento del ESTUDIO.
2. **Bundle diario de evidencia `P1`-`P4`:** CLI `v2_100` + `pnpm window:evidence` (read-only) que agrega los cuatro pendientes en un paquete por día.
3. **Helper de re-anclaje del pin:** `scripts/window-pin.mjs` + `pnpm window:freeze` / `pnpm window:pin`.

**NO cierra** (se declara): la **ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) — lo que falta es **OPERACIÓN**, no software —, la evidencia por valor de ESTUDIO `>0/35`, el enlace DÍA-D al ciclo real ni la rentabilidad/magnitud del P&L (**NO MEDIDA**).

---

## 1. `P1`/`P2` — la ventana mide el universo ESTUDIO (fail-closed)

**Hallazgo que motiva el cambio:** la ventana derivaba su watch del **catálogo** (activos con sector + historia, orden por id), mientras que `P2` exige cadenas por instrumento del universo **ESTUDIO** (~35 valores). Operar la ventana **no** cerraba `P2` porque medían universos distintos.

**Cambio:**

- [`v2_76_forward_market_material.py`](../../../../apps/api-python/scripts/v2_76_forward_market_material.py): nuevo flag `--watch-from-estudio`. Con el flag activo, el watch sale de `resolve_daily_watch` (la MISMA composición de la lane diaria AUTO, [`estudio_watch.py`](../../../../apps/api-python/src/bolsa_api/background/estudio_watch.py)) ∩ allowlist de `--watch`.
  - **Fail-closed:** sin ESTUDIO `ok` el watch queda **vacío** y se DECLARA (`RuntimeError` ⇒ exit 2); **nunca** cae al catálogo.
  - **Default byte-idéntico:** sin el flag, el comportamiento es el histórico (watch del CLI o del catálogo).
  - La selección se extrae a `_resolve_forward_watch(...)` (testeable) y el payload declara `watchSource` (`cli`/`estudio`/`catalog`).
- [`window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs): `preflightArgs`/`forwardArgs` añaden `--watch-from-estudio`.
- [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs): `WINDOW_CONFIG.watchFromEstudio = true` (identidad **no-freeze**: no entra en `FREEZE_ENV_KEYS`, así que no altera la semántica del freeze).

---

## 2. `P1`-`P4` — bundle diario de evidencia (`v2_100` / `window:evidence`)

NUEVO [`v2_100_operational_certification_evidence.py`](../../../../apps/api-python/scripts/v2_100_operational_certification_evidence.py), read-only, agrega:

| Pendiente | Fuente reutilizada (sin reimplementar) | Cierre falsable |
| --- | --- | --- |
| **`P1`** ventana PAPER | `v2_98` (`collect_window_rows` + `certify_paper_window`) | `verdict==READY` **y** `missingCriterionIds` vacío |
| **`P2`** cadena por valor de ESTUDIO | `v2_99` / [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) | `measured>0` (de `values`) **y** `completeChains>0` |
| **`P3`** enlace DÍA-D ↔ ciclo | mismo artefacto de cadena (`executedVsDiaD`) | `matches != null` en ≥1 ciclo (True **o** False) |
| **`P4`** aislamiento XTB | envs + `execution_events` ([`tables.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py)) | `BROKER_VENUE==paper`, envs LIVE ausentes **y** trazas venue LIVE `== 0` |

**Salida:** `operability_runs/daily-evidence/<YYYYMMDD>/evidence.json` + `evidence.md` (matriz `P1`-`P4`, veredictos, `missing`). **Regla `UNKNOWN ≠ 0`:** un dato ausente viaja `null` (hueco) y **no** cierra el pendiente; un conteo sólo es `>= 0` si se MIDIÓ. Exit `0` al declarar hueco, `2` si el material no se pudo leer, `1` uso incorrecto.

**`package.json`:** nuevo script `window:evidence` (delega en el comando `evidence` del runner, que inyecta la cuenta/versiones del pin).

---

## 3. Helper de re-anclaje del pin (`window:pin`)

NUEVO [`scripts/window-pin.mjs`](../../../../scripts/window-pin.mjs):

- `--check` (`pnpm window:freeze`): compara `git rev-parse HEAD:apps HEAD:packages` con `WINDOW_CONFIG`; imprime `freeze OK` (exit 0) o `TREE_MOVED` con los hashes a fijar (exit 1). El **freeze real son los dos tree hashes**; `commit` es solo la etiqueta del sello.
- `--write` (`pnpm window:pin`): actualiza **solo** `commit`/`appsHash`/`packagesHash` y antepone un bloque de comentario `RE-ANCLAJE <fecha>` con el motivo. **Idempotente**. NO toca la identidad (cuenta/versiones/watchSize). No sustituye a `window:unlock` (ese gestiona el lock diario huérfano).
- Tests puros (parseo/freeze/idempotencia, sin I/O git) en [`window-forward.test.mjs`](../../../../scripts/lib/window-forward.test.mjs).

---

## 4. Estado medido de la ventana (al sellar, 2026-10-15)

- **Freeze:** `pnpm window:freeze` → **`freeze OK`** (`HEAD:apps` / `HEAD:packages` == pin; `commit` del pin = etiqueta del sello; el re-anclaje del árbol `apps` que mueve este sello se aplica en el commit **POST-TAG**, ver §9).
- **Alineación ESTUDIO verificada en vivo:** `window:preflight` de hoy devuelve `watchSize: 35` y **`watchSource: "estudio"`** ⇒ el watch ya sale del universo ESTUDIO (no del catálogo). Régimen `BEAR_TREND`, `entriesAllowedLong = false` ⇒ **LONG VETADAS** (exit 2 declarado).
- **Ledger de la ventana:** `medidos=0 veto=2 declarados=0 duros=0` (días `20261014` y `20261015`, ambos `NO_MEDIDO_REGIMEN` por `BEAR_TREND`). Gate `NO_MEDIDO`.
- **Bundle `window:evidence` de hoy:** `cerrados 1/4 (P4)` — `P1 INCONCLUSIVE` (`días 0`) · `P2 0/35 medidos` · `P3 0 ciclos con DÍA-D` · **`P4 CERRADO`** (`venue paper`, envs LIVE ausentes, `0` trazas LIVE).
- **`v2_99`:** 35 valores ESTUDIO, **todos «sin ciclos»** ⇒ `0/35` medidos (declarado, sin fabricar).

> **Consecuencia:** `P1` sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** mientras el mercado vete LONG. El sello habilita el instrumento y **alinea el universo**; la medición es **OPERACIÓN**.

---

## 5. Evidencia de verificación (local)

```
node --test scripts/lib/window-forward.test.mjs ......... 28 passed   (incluye pin: parseo/freeze/idempotencia)
pytest test_v2_76_watch_from_estudio.py ................. 6 passed    (--watch-from-estudio fail-closed)
pytest test_operational_certification_evidence.py ....... 12 passed   (v2_100 unitario; UNKNOWN != 0)
pytest test_operational_certification_evidence_pg.py .... 1 passed    (PG-gated; read-only, invariantes)
pytest test_dia_d_bump_guard.py ......................... 1 passed    (2.11.135-beta)
pytest test_live_order_recovery_isolation.py + test_a8_m0_auto_live_invariant.py ... 92 passed  (P4 aislamiento)
playwright gp-v288-s5 (integrado, stack real) ........... 4 passed   (S5-04 en 4.6 s, SIN reintento)
ruff check (scripts + tests) ............................ OK
typecheck / lint (web) .................................. OK / 0 errores (23 warnings preexistentes)
```

**Operación ejercida en vivo (read-only / declarada):** `window:preflight` → `watchSource=estudio`, `watchSize=35`, `BEAR_TREND` (veto); `window:run-day` → `NO_MEDIDO_REGIMEN` (`regime_invalid`); `window:evidence` → bundle `20261015` (`P4 CERRADO`, `P1`-`P3` ABIERTOS con evidencia medida); `v2_99` → `0/35` (todos «sin ciclos»); SQL de venue LIVE → `0`.

**No ejecutado en local (declarado):** `replay-repro` no es ejecutable en Windows (CRLF/entorno); los E2E integrados se cubren en CI.

---

## 6. Sello / bump

- Bump `2.11.134-beta` → **`2.11.135-beta`**: `package.json` + `meta.bump` de los 13 CLIs; `v2_100` añadido a `_SCRIPTS` del guardián. Guardián → **1 passed**.
- **`Δ decisión = 0` · `Δ contrato HTTP = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`).
- **Re-anclaje del pin:** `window-pin.mjs` vive en `scripts/` (no participa del freeze), así que re-anclar **no** mueve a su vez el árbol. Al commitear el sello (cambia `apps/`), `HEAD:apps` se mueve ⇒ el pin se **re-ancla en el commit POST-TAG** (`pnpm window:pin --write --note "sello v2.88.135"`, `freeze OK`).

---

## 7. Ficheros del sello

- **Nuevos:** [`apps/api-python/scripts/v2_100_operational_certification_evidence.py`](../../../../apps/api-python/scripts/v2_100_operational_certification_evidence.py); [`scripts/window-pin.mjs`](../../../../scripts/window-pin.mjs); [`apps/api-python/tests/test_v2_76_watch_from_estudio.py`](../../../../apps/api-python/tests/test_v2_76_watch_from_estudio.py); [`apps/api-python/tests/test_operational_certification_evidence.py`](../../../../apps/api-python/tests/test_operational_certification_evidence.py); [`apps/api-python/tests/test_operational_certification_evidence_pg.py`](../../../../apps/api-python/tests/test_operational_certification_evidence_pg.py); [`runbook-cierre-p1-p4-2026-10-15.md`](../../runbook-cierre-p1-p4-2026-10-15.md); esta evidencia.
- **Modificados:** [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) (fix CI: idempotencia ante reintentos del test `S5-04`); [`v2_76_forward_market_material.py`](../../../../apps/api-python/scripts/v2_76_forward_market_material.py); [`window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs); [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs); [`window-forward.test.mjs`](../../../../scripts/lib/window-forward.test.mjs); `meta.bump` de 12 CLIs; [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py); `package.json`; [`CHANGELOG.md`](../../../../CHANGELOG.md); [`PROJECT_STATE.md`](../../PROJECT_STATE.md).

---

## 8. Límites declarados (sin fabricar) + falsabilidad

- **Ventana PAPER real (ADR-046):** sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. Lo que falta es **OPERACIÓN** (≥4 días operables, ≥2 regímenes, ≥32 ciclos con `cycle_id`), no software.
- **`P2`/`P3` dependen de `P1`:** sin días operables no hay ciclos ni enlace DÍA-D que medir.
- **`P4` es un invariante de MANTENIMIENTO:** su cierre no acredita la operación PAPER.
- **Este sello no demuestra rentabilidad.**

**Falsabilidad.**
- Si `--watch-from-estudio` cayera al catálogo con ESTUDIO no `ok`, `test_v2_76_watch_from_estudio.py` **rompe**.
- Si `v2_100` cerrara un pendiente sin evidencia medida, `test_operational_certification_evidence.py` **rompe**.
- Si `meta.bump` de cualquier CLI difiere de `package.json`, el guardián **rompe**.
- Si el pin no coincide con `HEAD:apps`/`HEAD:packages`, `pnpm window:freeze` lo declara `TREE_MOVED`.

---

## 9. `Release tag CI` del sello

**Tag** `v2.88.135-beta` (**lightweight**, unsigned) ⇒ apunta **directamente** al commit del sello (la cita del run va en el commit **POST-TAG**). **Base:** `v2.88.134-beta`.

**Incidente de CI (declarado y cerrado).** El **primer** `Release tag CI` del sello (run [`38715413962`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38715413962)) salió **ROJO** en `certify` por **un solo job**: `playwright (integrated AUTO S5)` (test `GP-V288-S5-04`). **No** era un defecto del código sellado: `apps/web` y `packages` eran **byte-idénticos** al sello verde `v2.88.134` (`git diff --stat 7cef7fcc <sello-pre-fix> -- apps/web packages` **vacío**), y en los sellos verdes `v2.88.133`/`v2.88.134` ese test **ya fallaba su primer intento** y solo pasaba por `retries: 1`. Aquí el **reintento** también falló: su precondición «no-residuo» exigía `total == 0` en `GET /api/auto/dia-d-verifications?cycleId=`, pero el `POST` del panel es **idempotente** por `(cycleId, diaD, endDate, mode)` ⇒ el reintento encontraba el enlace durable que el **propio intento anterior** había dejado (`total = 1`). **Defecto de idempotencia del test ante reintentos, no del producto.**

**Cierre:** endurecido el test ([`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts)) para medir el **RESULTADO durable** (fila con el `cycleId` **y** el `instrumentId` del ciclo) sin exigir estado limpio previo; verificado local **4/4** (`S5-04` en `4.6 s`, **sin reintento**). El tag se **movió** de `1c60b58e` a **`73317a9e`** y el CI se relanzó: `Release tag CI` [run **`38720406853`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38720406853) **VERDE** (~12m55s, `2026-10-15T10:27:35Z` → `10:40:30Z`; **todos los jobs `success`**, incluido `certify`; `playwright (integrated AUTO S5)` **`success`** con `S5-04` verde en el **retry #1** ~5.5s). El primer intento de `S5-04` en CI sigue siendo **flaky** (lentitud del primer run > 60 s), pero el retry ahora **no** choca con el residuo ⇒ job verde. El pin se re-ancla en el commit **POST-TAG** (`pnpm window:pin --write` → `freeze OK`, `apps c49d561f…` / `packages d48ac37b…`). **Falsable:** con el `assert total == 0` restaurado, el reintento vuelve a fallar.

**El resto del run rojo estaba VERDE** (`python` ruff/imports/mypy/pytest, `frontend` typecheck/lint/test/build + `contract:check`, `decision-spine`, `shared`, `lifecycle-pg`, `a7-gate`, `dr-verify`, `security (gitleaks)`, `playwright (integrated axe)`, `playwright (mock E2E)`; `replay-repro` **REPRODUCIDO**).

---

## 10. Seguimiento POST-TAG (2026-10-15) — precisión P4 y medición de `S5-04`

> Lo de arriba (§1-§9) es la evidencia **del sello**; esto documenta el trabajo **posterior al
> tag**, para no reescribir la verificación histórica. Naturaleza: **tooling y tests**, `Δ motor = 0`,
> `Δ decisión = 0`, `Δ contrato HTTP = 0`, **sin migración**.

### 10.1 `P4` — precisión del certificador (fail-closed estricto)

**Hallazgo.** El contrato de `P4` (README §2, `limits` del bundle, runbook §2) exige
`BROKER_VENUE == "paper"`, pero `_p4_pending` cerraba con `venue != "live"`: un venue **vacío,
`xtb` o desconocido** podía cerrar `P4` si las envs LIVE estaban ausentes y el conteo era `0`. Es
una debilidad del **certificador de evidencia** (no demuestra por sí mismo que AUTO enviara órdenes
reales).

**Cambio.** [`v2_100_operational_certification_evidence.py`](../../../../apps/api-python/scripts/v2_100_operational_certification_evidence.py):
`_p4_pending` exige ahora `venue == "paper"` explícito (`_REQUIRED_VENUE`). `UNKNOWN ≠ 0`: con
`liveVenueEvents is None` (BD ilegible) `P4` queda **ABIERTO**. La lista `_LIVE_VENUES` y el conteo
SQL no cambian.

**Pruebas (falsables).**
- [`test_operational_certification_evidence.py`](../../../../apps/api-python/tests/test_operational_certification_evidence.py):
  `16 passed` (antes 12). Nuevas negativas: venue `None`/vacío/espacios/`xtb`/`binance`/`unknown`/`PAPERX`
  ⇒ **no** cierra; venue vacío se declara hueco (`None`); `paper` con espacios/mayúsculas se
  canoniza y **sí** cierra; `paper` con `liveVenueEvents > 0` **no** cierra.
- [`test_operational_certification_evidence_pg.py`](../../../../apps/api-python/tests/test_operational_certification_evidence_pg.py):
  el assert débil `brokerVenue != "live"` pasa a `brokerVenue == "paper"` (PG-gated).
- `ruff check ... --config pyproject.toml`: **OK**.

**Falsable:** restaurado `venue != "live"`, `test_p4_requires_explicit_paper_venue` **rompe**.

### 10.2 `S5-04` — medición del primer intento vs retry (sin tocar `timeouts`)

**Hallazgo (§9).** El primer intento de `S5-04` supera los 60 s; el retry pasa. Es **lentitud del
primer arranque**, no un defecto del producto.

**Instrumentación read-only (NO cambia `timeout`, `retries` ni aserciones).**
- Job `playwright (integrated AUTO S5)` de [`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml):
  segundo reporter **JSON** a fichero (`PLAYWRIGHT_JSON_OUTPUT_NAME=/tmp/s5-integrated-report.json`)
  junto al `list` que alimenta el guard anti-skip (intacto). Paso de medición + artefacto
  `playwright-integrated-auto-s5-timings` (incluso en rojo).
- NUEVO [`scripts/ci/playwright-attempt-timings.mjs`](../../../../scripts/ci/playwright-attempt-timings.mjs):
  parser **puro** que resume, por test, el tiempo de cada intento (primero vs retry, delta) y los
  pasos más lentos. Declara un **hueco** (y no falla) si el informe no existe. Test:
  [`scripts/ci/playwright-attempt-timings.test.mjs`](../../../../scripts/ci/playwright-attempt-timings.test.mjs)
  (`node --test` → `8 passed`).
- [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts):
  `test.step` nombra los tramos lentos (abrir operación, lanzar D→hoy, esperar evidencia LAB,
  guardar/verificar enlace). Solo instrumenta; el primer intento sigue mandando.

**Regla:** medir en varias ejecuciones **antes** de optimizar; nunca ampliar `timeout`/`retries` para
«pasar ni ocultar el fallo.

**Comparación con CI (`38735478442`).** El run de CI
[`38735478442`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38735478442) dejó la evidencia cruda
de la instrumentación, conservada **verbatim** en
[`s5-ci-run-38735478442/`](./s5-ci-run-38735478442/) (`s5-timings.txt`, `s5-network.txt`,
`s5-network-timings.json.attempt0.json`, `…attempt1.json`, `s5-integrated-report.json`). Es la
comparación directa con el **N=3 local en frío** (§6.1 del runbook) y **no** se reproduce localmente:

- **`S5-04` intento 1: `failed` 64.59 s** — timeout **exacto** en el tramo
  `esperar la evidencia de la sesión LAB` (**60.00 s**); `abrir la operación AUTO` 4.34 s; `lanzar la
  verificación D→hoy` 0.17 s. **Retry: `passed` 7.39 s** (esperar LAB **1.35 s**). **Delta 57.21 s.**
- **Red:** en el intento 0, `api:other` = 52 peticiones / suma 11.97 s / **máx 8.89 s**, y esa máxima
  es **`POST /api/instruments/<id>/sync`** (`status 200`, `durationMs 8892`, `offsetMs 13803`). En el
  retry `api:other` baja a máx 0.23 s y **desaparece** la petición `/sync`. `module:src` = 739
  peticiones en ambos intentos (máx 0.56 / 0.65 s) y `api:run` = 2 en ambos (sin waterfall/re-run).

**Lectura acotada.** El fallo apunta a la **readiness asíncrona de la cadena LAB/scan** (el botón
`Guardar Evidence` aparece cuando la evidencia de sesión está lista), **no** al motor de backtesting
ni al cálculo de indicadores (fases Python <65 ms, sin pico en la 1ª llamada). El
`POST /instruments/<id>/sync` de **8.89 s** es un **coste observable** del arranque en frío, pero
**no demuestra por sí solo** ser la causa de los ~60 s de espera.

**Alcance.** Esto **cierra la incidencia de DIAGNÓSTICO**; **no** demuestra que la intermitencia del
runner de CI haya desaparecido (estabilidad local **≠** ausencia de flakiness en el runner). `timeout`
y `retries` siguen en **1** y los umbrales `ADR-046` **sin cambios**.

### 10.3 Estado de la ventana (sin cambios de honestidad)

`P1` sigue **`INCONCLUSIVE`** (`0/4 días`, `0/2 regímenes`, `0/32 ciclos`) por veto `BEAR_TREND`;
`P2`/`P3` dependen de `P1`. No se declara AUTO certificado, no se relajan umbrales ni `ADR-046`, no se
fuerza el régimen. El runner distingue «no hay entradas permitidas» (veto declarado con payload de
preflight **válido**) de «no se pudo ejecutar/medir» (fallo duro) — ver runbook §1 y
[`window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs).
