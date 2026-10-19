# Evidencia `v2.88.146-beta` — la UI de operativa diaria deja de vender un dry-run como orden, y DÍA-D deja de compartir artefacto entre cuentas

> **Bump:** `2.11.145-beta` → **`2.11.146-beta`** (`package.json` + `meta.bump` de los **13** CLIs; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**). Tag **unsigned**.
>
> **Naturaleza:** presentación, trazabilidad y aislamiento de artefactos — **no** toca el motor de decisión, ni umbrales, ni pesos A/B: **`Δ motor = 0`** · **`Δ decisión = 0`** · contrato **ADITIVO** (`topId`, `topVersion`, `signalId`, `universeCount`; `openapi.json`/`schema.d.ts` **sin diff**) · **SIN migración** (head `056_auto_ops_jobs`).
>
> **Base:** `v2.88.145-beta` (`2fb3e18a`). **Documento de auditoría:** [`auditoria-ui-auto-dia-d-v2.88.145-2026-10-19.md`](../../auditoria-ui-auto-dia-d-v2.88.145-2026-10-19.md).

## 1. Qué corrige (hallazgo verificado → cierre)

| Hallazgo | Antes (verificado en código) | Cierre |
| --- | --- | --- |
| **Premisa SIM implícita** | `LIVE_EXECUTION_UNLOCKED`/`PAPER_D_EXECUTE` off y §6.2, pero **sin invariante de producto** | §7 en [`PROJECT_PREMISES.md`](../../../PROJECT_PREMISES.md:291), enlazado en §0 y anunciado en `README.md`/`HELP.md` |
| **D1 — artefacto DÍA-D por día** | `dia-d-auto-<D>.json` plano ⇒ dos cuentas el mismo día competían por el fichero | [`dia_d_artifacts.py`](../../../../packages/py/application/src/bolsa_application/dia_d_artifacts.py:56): `<segmento-cuenta>/dia-d-auto-<D>.json` + `.../progress/<job>.jsonl`; usado por worker ([`auto_ops_dia_d.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py:70)), CLI (`--out`) y ruta ([`auto_dia_d.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py:56)) |
| **H1 — «Plan disparado» era un `execute=False`** | etiqueta de orden sobre un dry-run | `ok` → **«Plan propuesto»** ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:41)) |
| **H2 — atribución por ticker** | ciclos históricos bajo la señal del día | ventana del audit + «Histórico del valor; no atribuido a esta señal»; solo `planId`/`signalId` atribuyen ([`use-estudio-daily-ops.ts`](../../../../apps/web/src/features/auto-monitor/use-estudio-daily-ops.ts:196)) |
| **H3 — estrategia = constante `estudio_auto`** | `presetKey` pintado como estrategia; `topId`/`topVersion` descartados | `strategyDefinitionId`/`planId`/`signalId` visibles; `presetKey` = «preset de origen»; TOP real y «Indicador ganador: no declarado por el motor» ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:315)) |
| **H4 — vela afirmada sin verificar** | no se distinguía vela de hueco | «vela `<asOfBarDate>`» o «vela no verificada» ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:255)) |
| **H5 — cobertura invisible** | `truncated`/`countsConsistent`/`notes` calculados y no pintados | `universeCount` aditivo; esperados/procesados/recortados/fallidos, aviso de recorte y `notes` ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:692)) |
| **H6 — fallo de audit = «sin dato»** | error convertido en «no aparece en la ventana» | `role="alert"` + **Reintentar** ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:632)) |
| **D3 — job solo en memoria** | recargar ocultaba la corrida | rehidratación por `(cuenta, día)` en [`use-estudio-daily-ops.ts`](../../../../apps/web/src/features/auto-monitor/use-estudio-daily-ops.ts:55) y [`use-dia-d-replay-job.ts`](../../../../apps/web/src/features/auto-monitor/use-dia-d-replay-job.ts:27); reset al cambiar de contexto |
| **D4 — «Actualizar» refrescaba lo oculto** | solo el monitor desactivado | refresco propio por panel (`estudio-daily-refresh`, `dia-d-auto-refresh`, `dia-d-auto-feedback-refresh`) |
| **D2 — artefacto vs ejecución** | `artifactModifiedAt` sin mostrar | «Última ejecución solicitada» vs «Último artefacto válido» ([`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx:328)) |
| **D5 — DÍA-D sin nivel 1** | tabla técnica como primera lectura | resumen con pasos/divergencias/cobertura/muestra y **«Evidencia insuficiente»** ([`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx:246)) |
| **D6 — sin contexto desde la ficha** | salto sin declarar alcance | `?mode=dia-d&day=&symbol=` ([`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:202)) y aviso de comprobación **global** ([`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx:476)) |

## 2. Compatibilidad legacy (declarada, no silenciosa)

[`_resolve_artifact`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py:77) sirve el fichero plano histórico **solo** si `meta.account == scope`; en ese caso la respuesta lleva `notes: ["legacy_artifact"]`. Nunca se sirve a otra cuenta.

## 3. Prueba integrada (obligatoria, sin `skip`)

[`test_auto_daily_dia_d_chain_integration.py`](../../../../apps/api-python/tests/test_auto_daily_dia_d_chain_integration.py): dos cuentas + barras sembradas → `RunEstudioDailyOps` (identidad `signalId`/`planId`/`topId`) → dos jobs `dia_d_replay` **concurrentes** el mismo día → **dos** artefactos distintos y **ninguna** ruta plana compartida → ruta HTTP real sirviendo a cada cuenta **solo** lo suyo, con `artifactModifiedAt`, `notes: []` y lectura estable al repetir (recarga) → tercera cuenta **sin acceso**. Si falta una precondición, **falla**; no se marca `skipped`. El subproceso del CLI se sustituye por el caso de uso real (exige PostgreSQL y ~90 días de barras): **doble declarado**.

## 4. Verificación medida (local, comandos de casa)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Web (suite completa) | `pnpm --filter @bolsa/web test` | **312 ficheros / 2299 passed** |
| Web typecheck | `pnpm --filter @bolsa/web typecheck` | **OK** |
| Web lint | `pnpm --filter @bolsa/web lint` | **0 errores** (23 avisos preexistentes) |
| Python focalizado | `pytest` worker + ruta + servicio + integrada | **25 passed** |
| Python completo | `python -m pytest -q` | **5797 passed / 1 skipped** (ver límites) |
| Ruff (CI parity) | `pnpm lint:py` | **`All checks passed!`** |
| Import-linter | `pnpm imports:py` | **`4 kept, 0 broken`** |
| Mypy | `pnpm types:py` | **`Success: no issues found in 566 source files`** |
| Contrato | `pnpm --filter @bolsa/web contract:gen` + `contract:check` | **OK** (aditivo, sin diff) |
| Bump guard | `pytest test_dia_d_bump_guard.py` | **2 passed** |
| Freeze PAPER | `pnpm window:freeze` | **OK** tras re-anclaje (ver §6) |

### Límites del entorno (declarados, no ocultados)

- El **control de aplicaciones de Windows** bloquea el spawn de `mypy.exe`/`lint-imports.exe` (`os error 4551`) y la carga de `llvmlite.dll`: mypy e import-linter se ejecutaron por `python -m`; `packages/py/analytics/tests/test_vectorbt_optuna.py` quedó **ignorado** en la corrida completa. El CI Linux los corre completos.
- `scripts/ci/test_selection.py` colecciona el helper `test_files_under(directory)` como test y falla por fixture ausente: **preexistente** y fuera de las rutas que ejecuta el CI.

## 5. Invariantes que NO cambian

- La operativa sigue **100 % SIM** (§7): ninguna orden real a XTB ni a otro broker.
- `CONFIRMED` **no se emite**; `OOS_SUPPORTED` no se promociona.
- La ventana PAPER real sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** ⇒ este sello **no demuestra rentabilidad**.
- `Δ motor = 0` · `Δ decisión = 0`; sin migración; contrato solo aditivo.

## 6. Publicación

- El gate `window:freeze` es fail-closed contra los **tree hashes** de `HEAD:apps`/`HEAD:packages` ⇒ tras el commit funcional se re-ancla el pin (`pnpm window:pin --write`) y el tag apunta al commit **cuyo pin casa con su árbol**.
- Tag `v2.88.146-beta` (**anotado, unsigned**) y `Release tag CI` — **resultado pendiente en el momento de escribir esta sección**; se cita abajo en el POST-TAG, con `freeze OK` y `replay-repro` como medidas del CI.
