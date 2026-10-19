# Auditoría — UI de Operativa diaria AUTO y DÍA-D (`v2.88.145-beta`)

> **Fecha:** 2026-10-19 · **Base auditada:** tag `v2.88.145-beta` → commit **`2fb3e18a`** ·
> **Sellado en:** `v2.88.146-beta` (`2.11.146-beta`), commit del sello en la
> [evidencia](../engineering/evidence/v2.88.146/README.md).
> **Alcance:** superficie de UI de `mode=daily` (operativa diaria por valor) y `mode=dia-d`
> (sandbox + feedback), y el camino que las alimenta (worker `dia_d_replay`, ruta read-only
> `/api/auto/dia-d-replay`, contrato `EstudioDaily*`).
> **Naturaleza del cambio:** presentación + trazabilidad + aislamiento de artefactos.
> **`Δ motor = 0` · `Δ decisión = 0`. Contrato solo aditivo. Sin migración de BD.**
> No se promociona `CONFIRMED` ni se declara rentabilidad.

## 0. Premisa que gobierna esta auditoría

Toda la operativa —manual, AUTO, en tiempo real y con cualquier cuenta/broker— es
**SIMULADA** contra un ledger virtual/PAPER. **No se envían órdenes reales a XTB ni a ningún
broker.** Queda formulado como invariante de producto en
[`PROJECT_PREMISES.md` §7](../PROJECT_PREMISES.md:291), enlazado en su índice §0 y anunciado
en `README.md` y `docs/HELP.md`.

Consecuencia para esta auditoría: un `ok` del parte diario es un **plan propuesto en dry-run**
(`"execute": False` en `estudio_daily_ops.py`), nunca una orden. Las etiquetas de UI
«Orden enviada» / «Operación ejecutada» se reservan para hechos durables de orden/fill.

## 1. Hallazgos verificados y cierre

### H1 — «Plan disparado» describía un dry-run

| Antes | Ahora |
| --- | --- |
| `ok` se rotulaba **«Plan disparado»** ([panel](../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:41) en la versión auditada). El parte se genera con `"execute": False`. | `ok` → **«Plan propuesto»** (`estudio-daily-ops-panel.tsx:41`); leyenda «decisión propuesta: plan en dry-run (no es una orden)». Test: `estudio-daily-ops-panel.test.tsx` asserta «Plan propuesto» y la **ausencia** de «Plan disparado». |

### H2 — Atribución por ticker sin vínculo causal

| Antes | Ahora |
| --- | --- |
| La auditoría se unía solo por `symbol`; los ciclos históricos se presentaban bajo la señal del día sin declarar la ventana. | Bajo «3 · Operación ejecutada» se declara **la ventana** (`audit.window`) y la frase **«Histórico del valor; no atribuido a esta señal»**. Solo un `planId`/`signalId` iguales atribuyen (`auditCycleAttribution` / `auditAttributionForValue` en [`use-estudio-daily-ops.ts`](../../apps/web/src/features/auto-monitor/use-estudio-daily-ops.ts:169)). El contrato actual de ciclos **no** trae esos campos ⇒ el resultado normal es «no atribuido»; no se simula el vínculo. |

### H3 — «Identidad de estrategia» era una constante

| Antes | Ahora |
| --- | --- |
| Se mostraba `presetKey`, que en este camino es la constante `estudio_auto`; `strategyDefinitionId`/`planId` existían en el contrato pero no se pintaban; `topId`/`topVersion` se descartaban en `to_dict()`. | Se muestran `strategyDefinitionId`, `planId` y **`signalId`** (aditivo desde `signal.id`, [`estudio_daily_ops.py`](../../packages/py/application/src/bolsa_application/estudio_daily_ops.py:613)); `presetKey` se rotula **«preset de origen»**. Se expone el TOP real (`topId`/`topVersion`, `estudio_daily_ops.py:151`) y se declara **«Indicador ganador: no declarado por el motor»** en vez de fabricar un ganador. |

### H4 — Vela diaria afirmada sin verificar

| Antes | Ahora |
| --- | --- |
| La UI no distinguía una vela verificada de un hueco. | Cada ficha muestra **«vela `<asOfBarDate>`»** o **«vela no verificada»** (`data-bar-verified`) y la hora de cálculo o «hora de cálculo sin dato». No se infiere `has_eod_bar=true` del hecho de que exista opinión. |

### H5 — Universo y cobertura invisibles

| Antes | Ahora |
| --- | --- |
| `truncated`, `countsConsistent` y `report.notes` se calculaban pero no se pintaban. | `universeCount` viaja **aditivo** (`estudio_daily_ops.py:174/195`). La cabecera declara «Cobertura: N de M valores ESTUDIO procesados», avisa si el universo está **recortado** o el parte es **parcial**, y publica las `notes` y `generatedAt`. Tests: `estudio-daily-coverage`, `estudio-daily-coverage-warning`, `estudio-daily-report-notes`. |

### H6 — Un fallo de auditoría se pintaba como «sin dato»

| Antes | Ahora |
| --- | --- |
| `useAutoEstudioAudit().isError` se convertía en «este valor no aparece en la ventana». | `auditQuery.isError` produce un `role="alert"` con el mensaje y **Reintentar** (`estudio-daily-audit-error`), y por valor «no se pudo leer la auditoría… **no** significa que no exista» (`estudio-daily-value-validation-error`). |

### D1 — El artefacto DÍA-D dependía solo del día (colisión entre cuentas)

| Antes | Ahora |
| --- | --- |
| Ruta plana `operability_runs/dia-d-auto/dia-d-auto-<D>.json`: dos cuentas el mismo día competían por el mismo fichero. | **Un artefacto por `(cuenta, día)`**: `operability_runs/dia-d-auto/<segmento-cuenta>/dia-d-auto-<D>.json` y progreso en `.../<cuenta>/progress/<job>.jsonl`. Esquema único en [`dia_d_artifacts.py`](../../packages/py/application/src/bolsa_application/dia_d_artifacts.py:56), usado por worker ([`auto_ops_dia_d.py`](../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d.py:69)), CLI (`--out`) y ruta ([`auto_dia_d.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py:77)). Sanitización: cuenta no segura ⇒ `acct-<sha256>` (no puede escapar del árbol). |

**Compatibilidad legacy declarada:** si no existe la ruta canónica, se acepta la plana
histórica **solo** cuando su `meta.account` coincide con la cuenta del principal; en ese caso
la respuesta incluye `notes: ["legacy_artifact"]`. Nunca se sirve a otra cuenta.

### D2/D4 — Ejecución solicitada vs artefacto válido

| Antes | Ahora |
| --- | --- |
| `artifactModifiedAt` existía y no se mostraba; el estado del job vivía solo en memoria. | Bloque de procedencia (`dia-d-auto-provenance`) con **«Última ejecución solicitada»** (job, estado, día, `createdAt`/`finishedAt`; o «sin job observado») y **«Último artefacto válido»** (`artifactModifiedAt`, cuenta, `versionA`, horizonte). |

### D3 — Continuidad de jobs y refresco

| Antes | Ahora |
| --- | --- |
| `jobId` solo en estado local; recargar parecía no haber lanzado nada. «Actualizar» refrescaba el monitor oculto. | `useEstudioDailyJob` ([`use-estudio-daily-ops.ts`](../../apps/web/src/features/auto-monitor/use-estudio-daily-ops.ts:55)) y `useDiaDReplayJob` ([`use-dia-d-replay-job.ts`](../../apps/web/src/features/auto-monitor/use-dia-d-replay-job.ts:27)) **rehidratan** el job más reciente de `(cuenta, día)` desde la cola durable y **limpian** al cambiar de contexto. La invalidación usa el **día del job**, no el día en pantalla. Cada panel trae su propio «Actualizar» (parte + auditoría; días + artefacto; feedback), y el botón global deja de pintarse en `daily`/`dia-d`. |

### D5 — DÍA-D sin lectura de primer nivel

| Antes | Ahora |
| --- | --- |
| Se entraba directamente a la tabla técnica; un veredicto podía leerse como aprobación. | **Nivel 1** antes de la tabla ([`dia-d-auto-panel.tsx`](../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx:246)): pasos medidos/total, divergencias, cobertura del universo (`watchSize`, fuente, excluidos sin barras, sesgo declarado), muestra OOS y límites. Si no hay pasos medidos o ciclos cerrados, el titular es **«Evidencia insuficiente»** (ámbar), no un color de aprobación. |

### D6 — Sin enlace contextual desde la ficha diaria

Ahora cada ficha enlaza a `?mode=dia-d&day=<vela>&symbol=<valor>`
([`diaDContextHref`](../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx:202)).
El sandbox **lee** `symbol` y declara que es una comprobación **global del día**, no una
validación individual de esa señal (`dia-d-auto-symbol-context`).

### D7 — Estado vacío con acción imposible

Sin cuenta activa ya no se muestra «no hay parte… Pulsa Calcular»: solo se declara «Sin
cuenta activa».

## 2. Verificación medida

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tests web AUTO | `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor` | **20 ficheros / 154 passed** |
| Tests web (suite completa) | `pnpm --filter @bolsa/web test` | **312 ficheros / 2299 passed** |
| Typecheck web | `pnpm --filter @bolsa/web typecheck` | **OK** |
| Lint web | `pnpm --filter @bolsa/web lint` | **0 errores** (23 avisos preexistentes) |
| Tests Python (worker, ruta, servicio, integrada) | `uv run python -m pytest apps/api-python/tests/test_auto_ops_dia_d.py apps/api-python/tests/test_auto_dia_d_route.py packages/py/application/tests/test_estudio_daily_ops.py apps/api-python/tests/test_auto_daily_dia_d_chain_integration.py -q` | **25 passed** |
| Tests Python (suite completa) | `uv run python -m pytest -q` | **5797 passed / 1 skipped** (ver límites) |
| Lint Python (paridad CI) | `pnpm lint:py` | **`All checks passed!`** |
| Import-linter | `pnpm imports:py` | **`4 kept, 0 broken`** |
| Mypy | `pnpm types:py` | **`Success: no issues found in 566 source files`** |
| Contrato | `pnpm --filter @bolsa/web contract:gen` + `contract:check` | **OK** (solo campos aditivos; `openapi.json`/`schema.d.ts` sin diff) |
| Freeze PAPER | `pnpm window:freeze` | **OK** tras re-anclar el pin al commit del sello |

**Límites del entorno (declarados):** el control de aplicaciones de Windows bloquea el spawn de
`mypy.exe`/`lint-imports.exe` y la carga de `llvmlite.dll`; mypy e import-linter se ejecutaron por
`python -m` y `test_vectorbt_optuna` quedó ignorado en la corrida completa (el CI Linux los corre
completos). `scripts/ci/test_selection.py` colecciona un helper `test_files_under(directory)` como
test y falla por fixture ausente: **preexistente** y fuera de las rutas del CI.

**CI del sello publicado (`v2.88.146-beta`):** `Release tag CI`
[run `39211944171`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39211944171) **VERDE**
(~13m57s; **13 jobs `success` + `certify` `success`**; opt-in `skipped`, declarado), con
`[window-pin] freeze OK (cbdf7b22)` en `shared` y `replay-repro` ⇒ **`REPRODUCIDO`**
(`sha256 1E3ADAC2…929A37E7`, idéntico a `.136`…`.145` ⇒ **`Δ decisión = 0` medido por el CI**).

### 2.1 Prueba integrada (obligatoria, sin `skip`)

[`test_auto_daily_dia_d_chain_integration.py`](../../apps/api-python/tests/test_auto_daily_dia_d_chain_integration.py)
recorre, con código de producción:

1. `RunEstudioDailyOps` compone el parte de **dos cuentas** y expone `signalId`/`planId`/`topId`.
2. Dos jobs `dia_d_replay` **concurrentes** (mismo día, cuentas distintas) escriben en rutas
   distintas; se verifica que **no** existe la ruta plana compartida.
3. La ruta HTTP real sirve a cada cuenta **solo** su artefacto, con la identidad del parte en
   `executedDetail`, `artifactModifiedAt` no nulo, `notes: []` (canónico) y lectura estable al
   repetir la petición (recarga). Una tercera cuenta **no** ve nada.

**Doble declarado:** el subproceso del CLI (necesita PostgreSQL y ~90 días de barras). Todo lo
demás —servicio diario, worker, rutas, contrato— es el código real. Si una precondición falta,
el test **falla**; no se marca `skipped`.

## 3. Límites declarados (sin fabricar)

- **La operativa sigue siendo 100 % SIM** (§7 de premisas). Este cambio no acerca dinero real:
  `LIVE_EXECUTION_UNLOCKED`/`PAPER_D_EXECUTE` siguen off y `venue=paper` por defecto.
- La evidencia histórica del valor **no** se atribuye a la señal salvo identidad estable; el
  contrato actual de ciclos no la trae, así que la UI dice «no atribuido». No es un bug: es la
  lectura honesta.
- El indicador ganador **no existe** como campo del motor en este camino; se muestra el TOP
  usado y se declara el hueco.
- `OOS_SUPPORTED` **no** se promociona a `CONFIRMED`; la ventana PAPER no cambia.
- La rehidratación depende de la cola durable (`auto_ops_jobs`); sin worker los jobs quedan
  `queued`, y la UI lo declara (no lo esconde).
- Un artefacto legacy se acepta solo con `meta.account == cuenta`; el fallback se declara en
  `notes`.

## 4. Reproducción

```powershell
pnpm --filter @bolsa/web contract:gen
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor

pnpm lint:py
pnpm imports:py
pnpm types:py

uv run python -m pytest `
  apps/api-python/tests/test_auto_ops_dia_d.py `
  apps/api-python/tests/test_auto_dia_d_route.py `
  packages/py/application/tests/test_estudio_daily_ops.py `
  apps/api-python/tests/test_auto_daily_dia_d_chain_integration.py -q

pnpm window:freeze
```

## 5. Addendum 2026-10-19 — hallazgo P1 al ejecutar el E2E integrado (`v2.88.147-beta`)

Al ejecutar por primera vez el journey integrado (`gp-v288-s5`) con el **worker real** se midió un
defecto **no cubierto** por esta auditoría (afecta a la operación, no a la UI):

- **Síntoma:** todo job `dia_d_replay` terminaba `failed` con `error: "NotImplementedError: "`.
- **Causa:** en Windows `scheduler_worker` fuerza `SelectorEventLoop` (psycopg async) y ese bucle
  **no implementa** `asyncio.create_subprocess_*`; el handler lo usaba para lanzar `v2_89`.
- **Arreglo (`v2.88.147-beta`):** `Popen` en hilo + `poll`/`kill` + ficheros temporales, con la misma
  validación estricta del artefacto; regresión falsable en
  [`test_auto_ops_dia_d.py`](../../apps/api-python/tests/test_auto_ops_dia_d.py).
- **Pruebas nuevas en este journey:** `S5-06` (UI diaria real: semántica, job durable único,
  «Actualizar» por panel, enlace contextual a DÍA-D) y `S5-07` (aislamiento por cuenta con control
  negativo), **7/7 passed** en local. Evidencia:
  [`evidence/v2.88.147/README.md`](./evidence/v2.88.147/README.md).

Lo declarado en §2 (huecos) **no cambia**; lo que cambia es que el replay manual **ya puede**
completar en Windows. La ventana PAPER sigue `NO MEDIDO` por operación/mercado.
