# Evidencia `v2.88.165-beta` — la auditoría de detección cierra sus 21 criterios

## 1. Qué publica este sello

Sello de **cierre** posterior y acotado a `v2.88.164-beta`. Aplica los **cinco** criterios que la
[`auditoría de detección`](../../auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md)
dejó como *criterio escrito sin prueba ejecutada* —`S-4`, `S-5`, `O-3`, `O-4` y `T-3`— y los
documenta en su **§9.12**. Con ellos, la trazabilidad pasa de **16/21** a **21/21** criterios con
prueba ejecutada.

- **`Δ motor = 0`** salvo el **journal** de `S-5` (`position_unmanaged`): declara una consecuencia,
  no opera.
- **`Δ decisión = 0`**: no se toca el decisor, el reloj de barras ni la cadencia del AUTO.
- **`Δ contrato HTTP` aditivo**: `AutoMonitorHeaderDto.venue` pasa a `string | null` (sin default
  `"paper"`) y entra `venueMeasurement` (default `"UNKNOWN"`); `openapi.json`/`schema.d.ts`
  regenerados y `contract:check` en verde.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.164-beta` → `2.11.165-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard` ⇒ **2 passed**).

## 2. Los cinco frentes

| Criterio | Qué estaba mal | Qué se publicó | Prueba |
| --- | --- | --- | --- |
| **S-4** | Se afirmaba que `THESIS_EXIT` era *estructuralmente* inalcanzable: con `invalidation_price` congelado en el stop, la precedencia convertía todo en `STRUCTURAL_STOP` | La rama es alcanzable **por contrato** cuando el plan declara un nivel por encima del stop: mark `96` con nivel `96.5` y stop `95` ⇒ `THESIS_INVALIDATION` **sin** `STRUCTURAL_STOP`; con mark `94` sigue ganando el stop (la precedencia no se rompe). La brecha que queda es de **producto**: hoy ningún productor emite ese nivel | `test_thesis_exit_reachable_with_declared_invalidation_price` (`packages/py/analytics/tests/test_exit_plan.py`) |
| **S-5** | Una posición sin `PositionState` y sin adopción posible dejaba `_v2_position_package` en `None`: abierta, sin gestión V2 y **sin una sola fila** | `POSITION_UNMANAGED` (`POSITION_LIFECYCLE_REASONS`) + `_v2_declare_unmanaged_position`: una fila por barra y símbolo con `held`, precio, `reason: "no_position_state"`, `management: "none"` y `attention: "high"`; no abre ni vende | `test_unadopted_position_is_declared_in_journal` (`apps/api-python/tests/test_auto_v2_audit_regressions.py`) |
| **O-3** | `closedCount ?? 0`, `openCount ?? 0`, `lastSignalPrice ?? 0` y el default `"paper"` del `venue` | DÍA-D pinta lo ausente (`formatDiaDValue()`; `closed === null` ⇒ `insufficient`), alertas rotulan el hueco y el monitor operativo viaja `venue = None` + `venueMeasurement = "UNKNOWN"` cuando el snapshot no lo declara | `test_absent_measurement_is_not_rendered_as_zero` · `signal-alerts-section.test.tsx` · `auto-monitor-header.test.tsx` |
| **O-4** | Dos componentes afirmaban `INCONCLUSIVE` sin consultarlo: el texto no podía cambiar cuando la ventana cambiara | `window-verdict.ts` **lee** el veredicto del gate por valor: un veredicto ⇒ ese; varios ⇒ «SIN VEREDICTO ÚNICO» con recuento; ninguno medido ⇒ **NO MEDIDO**. El bloque de cadena publica el veredicto **del valor** y declara que no se generaliza; la leyenda deja de escribir el veredicto | `test_window_verdict_is_read_from_gate` · `window-verdict.test.ts` |
| **T-3** | La cadencia (decisión diaria, ejecución de 60 s) sólo estaba en el diseño | Varios ticks de 60 s sobre la barra cerrada ⇒ **una** decisión fresca (`bar_tick`) y un **único** `logical_order_id` para los trozos de fill, sin segunda ejecución | `test_auto_loop_decides_once_per_closed_bar_and_settles_intrabar` (`apps/api-python/tests/test_auto_v2_bar_short_circuit.py`) |

## 3. Ficheros

| Capa | Ficheros |
| --- | --- |
| Python · aplicación/API | `auto_reason_codes.py`, `auto_simulation_worker.py`, `auto_operational_monitor.py` (caso de uso y ruta) |
| Python · pruebas | `test_exit_plan.py`, `test_auto_v2_audit_regressions.py`, `test_auto_v2_bar_short_circuit.py` |
| Web · UI | `dia-d-auto-panel.tsx`, `signal-alerts-section.tsx`, `auto-monitor-header.tsx`, `estudio-daily-ops-panel.tsx`, `estudio-chain-evidence.tsx`, `window-verdict.ts` (nuevo) |
| Web · pruebas | `dia-d-auto-panel.test.tsx`, `signal-alerts-section.test.tsx`, `auto-monitor-header.test.tsx`, `estudio-daily-ops-panel.test.tsx`, `window-verdict.test.ts` (nuevo) |
| Compartido | `packages/shared/src/cognitive/auto-operational-monitor.ts` (`venue: string | null`) |
| Contrato | `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts` (regenerados) |
| Docs | `auditoria-deteccion-compras-ventas-entorno-diario-2026-10-26.md` (§5.6, §5.7, §6 T-3, §7.4, §7.5, §9.12, trazabilidad y backlog) |

## 4. Trazabilidad de la auditoría

| Estado | Criterios |
| --- | --- |
| **Implementados (21/21)** | `B-1`…`B-6`, `O-1`…`O-6`, `S-1`…`S-6`, `T-1`, `T-2`, `T-3` |
| **Criterio escrito sin prueba ejecutada** | — (ninguno) |

Ningún hallazgo llega a **E3**. La evidencia es **E1** (hermética), con **E2** parcial donde ya lo
era (`S-6`, `T-1`, `T-3`). La ventana PAPER sigue **`INCONCLUSIVE`** por sus propios números
(`episodios 0/2`, `ciclos 0/32`): este sello **no la mueve**.

## 5. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest` (domain + market + application + analytics + api-python) | **5930 passed** (11:04) |
| Suites tocadas (`test_exit_plan`, `test_auto_v2_audit_regressions`, `test_auto_v2_bar_short_circuit`, `test_auto_estudio_audit_route`) | **65 passed** |
| `apps/web` (`vitest`) | **2383 passed / 319 ficheros** |
| `packages/shared` (`vitest`) | **855 passed / 99 ficheros** (+1 todo) |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm --filter @bolsa/web lint` | **0 errores**, 23 avisos preexistentes |
| `contract:gen` / `contract:check` | **OK** (aditivo: `venue` nullable + `venueMeasurement`) |
| `ruff` | **All checks passed** |
| `mypy` (gate de CI) | **573 ficheros sin issues** |
| Guardián de bump | **2 passed** |

## 5-bis. Cierre POST-TAG — CI público del sello (medido)

`Release tag CI` del tag `v2.88.165-beta` sobre `00f321bb6e05332b677e7c880ba23442af9486cf`:
[run **40541828291**](https://github.com/jvelasca/Bolsa_V1/actions/runs/40541828291) — **`success`**,
25m08s (2026-10-27T16:31:57Z → 16:57:05Z), `run_attempt 1`, artefacto `release-tag-ci-summary`
(id `12753290915`) con `status: GREEN` y los **12** jobs obligatorios verdes.

| Job | Medido |
| --- | --- |
| `shared` | **`freeze OK (00f321bb)`** · `window:test` **50 passed** · **99 ficheros** |
| `frontend` | `contract:check` verde · **319 ficheros** |
| `python` | **`5570 passed, 62 skipped`** (113 s) · `mypy` **573** · `Contracts: 4 kept, 0 broken` |
| `lifecycle-pg` | **176** + **225** + **45** + **3** + **7** + **23** + **2** + **3** + **2** + **2** + **1** |
| `playwright (mock E2E)` | **139 passed (13.7m)** — incluye `gp-e2e-v290` leyendo el veredicto del gate |
| `playwright (live AUTO daily)` / `integrated AUTO S5` / `integrated axe` | **2** / **8** / **32** passed — el primero **no** está en `certify.needs`, así que no es obligatorio |
| `replay-repro` | **`REPRODUCIDO`** `sha256 E9B7376B…F5625` ⇒ **`Δ decisión = 0`** |
| `a7-gate` / `decision-spine` / `security` / `dr-verify` | **7 passed** / **622 passed** / gitleaks limpio / DB_DR·TCP |
| `certify (aggregate + artifact)` | `success` (GREEN) |
| `playwright (integrated E2E, opt-in)` | `skipped` por diseño — **no certifica** |

**Intento previo, rojo y retirado:** el tag se creó primero sobre `068b3fae` (objeto de tag
`e62b2b7b31ef4fe54921fe51d3dcb71042ae7c65`); el run
[**40516676602**](https://github.com/jvelasca/Bolsa_V1/actions/runs/40516676602) terminó en
`failure` con **12 `success`, 2 `failure` y 1 `skipped`** sobre 15 entradas: rojo en
`playwright (mock E2E)` porque `gp-e2e-v290` afirmaba el literal `INCONCLUSIVE` que `O-4` retira, y
rojo también en `certify` por agregación (`11/12` obligatorios verdes; el pack no debe decir «12 de
13»). Se corrigió la prueba (`fb18d729`), se re-ancló el pin (`00f321bb`, `freeze OK`) y el tag se
movió. El intento se documenta; no se cita como verde. El objeto de tag anterior ya no está en la
ref pero sigue siendo recuperable por su SHA: es el antecedente auditable de la publicación.

## 5-ter. Verificación independiente (2026-10-27)

Comprobaciones ejecutadas contra el remoto y contra el árbol local, con la salida literal. No
dependen de leer un sha escrito en un documento.

```text
$ git rev-parse 'v2.88.165-beta^{commit}'
00f321bb6e05332b677e7c880ba23442af9486cf

$ git rev-parse v2.88.165-beta            # objeto de tag, no el commit
2f3cb37665dc0bb06cef2812882237bac70436c8

$ git cat-file -p 2f3cb37665dc0bb06cef2812882237bac70436c8 | head -2
object 00f321bb6e05332b677e7c880ba23442af9486cf
type commit

$ git cat-file -p e62b2b7b31ef4fe54921fe51d3dcb71042ae7c65 | head -2
object 068b3faeb5da06821c80030eab0772aeb2d6d4ff
type commit

$ git ls-remote --tags origin v2.88.165-beta
2f3cb37665dc0bb06cef2812882237bac70436c8        refs/tags/v2.88.165-beta

$ node scripts/window-pin.mjs --check
[window-pin] freeze OK (ae44f78c)
  appsHash     927c22988d27ff63512f3c3bf6cb150ba0dd5551
  packagesHash 41e0afa8c5937c10dd3eaa2c8f3f66e2bc10f925

$ git rev-parse 00f321bb:apps 00f321bb:packages
927c22988d27ff63512f3c3bf6cb150ba0dd5551
41e0afa8c5937c10dd3eaa2c8f3f66e2bc10f925
```

> **Cómo leerlo.** `git rev-parse v2.88.165-beta` devuelve el **objeto de tag** (`2f3cb376…`);
> `git rev-parse 'v2.88.165-beta^{commit}'` devuelve el **commit** (`00f321bb`). El objeto retirado
> `e62b2b7b…` ya no está en `refs/tags`, pero se recupera por SHA y apunta a `068b3fae`, el árbol que
> produjo el run rojo. Nota de higiene: el pin declara `commit: fb18d729` mientras `HEAD` es
> `ae44f78c`; el checker lo rotula como etiqueta desactualizada y el freeze real son los dos tree
> hashes, que coinciden.

| Comprobación | Resultado medido |
| --- | --- |
| `git rev-parse 'v2.88.165-beta^{commit}'` | `00f321bb6e05332b677e7c880ba23442af9486cf` |
| `git ls-remote --tags origin v2.88.165-beta` | objeto `2f3cb37665dc0bb06cef2812882237bac70436c8` → `00f321bb` |
| Objeto retirado (antecedente) | `e62b2b7b31ef4fe54921fe51d3dcb71042ae7c65` → `068b3fae` |
| Run del sello | `40541828291`: `head_sha=00f321bb…`, `run_attempt=1`, `success`, 25m08s |
| `certify` (log del job) | `"status": "GREEN"`, `"sha": "00f321bb…"`, `"asOf": "2026-10-27T16:57:02Z"`, 12/12 `success` |
| Run previo | `40516676602`: `head_sha=068b3fae…`, `failure` (2 `failure`, 1 `skipped`) |
| `node scripts/window-pin.mjs --check` | `freeze OK` · `apps 927c2298…` / `packages 41e0afa8…` |
| `git diff --shortstat 13362515 00f321bb` | 44 ficheros, +1 484/−66 |
| `git diff --stat 00f321bb ae44f78c` | 3 ficheros, todos `docs/` + `CHANGELOG.md` (no mueve el freeze) |
| `playwright (live AUTO daily chain)` | `success`, pero **fuera** de `certify.needs`: no es obligatorio |

Comandos para reproducirlo:

```bash
git fetch origin --tags
git rev-parse 'v2.88.165-beta^{commit}'
git rev-parse 'ae44f78c^{commit}'
git cat-file -p v2.88.165-beta
git ls-remote --tags origin v2.88.165-beta
node scripts/window-pin.mjs --check
gh api repos/jvelasca/Bolsa_V1/actions/runs/40541828291 \
  --jq '{head_sha,conclusion,run_attempt,created_at,updated_at}'
gh api repos/jvelasca/Bolsa_V1/actions/runs/40516676602/jobs --paginate \
  --jq '.jobs[] | [.name,.conclusion] | @tsv'
```

## 6. Falsabilidad — cómo un auditor rompe cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | La tesis dispara antes que el stop cuando el plan declara su nivel | `test_thesis_exit_reachable_with_declared_invalidation_price` falla si `primary_reason` deja de ser `THESIS_INVALIDATION` o si `STRUCTURAL_STOP` viaja como motivo; y falla si la mitad de control (mark `94`) deja de dar el stop |
| 2 | La posición no gestionada se declara una vez por barra | `test_unadopted_position_is_declared_in_journal` falla si no hay fila, si falta el símbolo/`held`, o si el tick siguiente repite el hecho |
| 3 | Un dato ausente no se pinta como `0`/`"paper"` | las tres pruebas de UI fallan si reaparece `0`, `0.00` o `paper` cuando el DTO no trae el dato |
| 4 | El veredicto de la ventana es dato | `test_window_verdict_is_read_from_gate` cambia el veredicto del mock (`INCONCLUSIVE` → `READY`) y falla si la pintura no cambia; `window-verdict.test.ts` falla si `UNKNOWN` se rellena con un veredicto |
| 5 | La cadencia está fijada | `test_auto_loop_decides_once_per_closed_bar_and_settles_intrabar` falla si hay más de una decisión fresca por barra o si los trozos de fill no comparten `logical_order_id` |
| 6 | Bump coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` (`2.11.165-beta`) |
| 7 | Contrato sincronizado | `pnpm contract:check` falla si `openapi.json`/`schema.d.ts` no reflejan el DTO |
| 8 | Sin migración | `alembic heads` da otro head que `058_estudio_daily_proposals` |

## 7. Reproducir la verificación

```bash
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync python -m pytest packages/py/analytics/tests/test_exit_plan.py \
  apps/api-python/tests/test_auto_v2_audit_regressions.py \
  apps/api-python/tests/test_auto_v2_bar_short_circuit.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm contract:check
```

## 8. Límites / huecos declarados

1. **AUTO sigue OFF**; la operativa es **100 % PAPER virtual**, sin LIVE ni XTB real.
2. **La ventana PAPER sigue `INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`). La UI ahora **lee**
   ese veredicto (o declara `NO MEDIDO` si el gate no mide); este sello no lo mueve.
3. **`S-4` no crea el productor.** La rama es alcanzable por contrato; que ningún plan de entrada
   declare un nivel de invalidación distinto del stop sigue siendo deuda de **producto**.
4. **`T-3` no certifica la cadencia en producción**: procesos vivos, latencia del primer tick y
   cobertura de la cola son observación operativa, no contrato.
5. **No demuestra rentabilidad.** Los cambios declaran consecuencias y leen datos; no validan
   señales ni P&L.
