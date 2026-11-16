# ADR-053 — Disparador gobernado del embudo AUTO

**Estado:** **Accepted — implementado en el árbol.** El embudo (ESTUDIO → LAB → TOP3 → COACH →
FINALISTA) pasa a ser alcanzable a demanda por HTTP, con `dryRun` por defecto, idempotencia
durable, ámbito ESTUDIO y auditoría por ejecución. **Techo FINALISTA: esta ruta no puede escribir
ACTIVE.** **`Δ motor = 0`** · **`Δ ledger = 0`** · **`Δ contrato ≠ 0`** (ruta aditiva: exige
`contract:gen`, ver §6).
**Fecha:** 2026-11-16
**Contexto:** [auditoría LAB 2026-11-16](../engineering/plan-remediacion-laboratorio-2026-11-16.md) ·
[ADR-052](./052-p1-gate-beneficio-neto.md) (el gate que el embudo aplica).
**Depende de:** [ADR-016](./016-research-persistence-model.md) (persistencia del dominio
Scientific) · [ADR-029](./029-order-proposal-decision-journal.md) (journal append-only) ·
[RFC-008](./rfc/008-cognitive-decision-architecture.md) (Evidence / MKL / Gate).

**Afecta a:**
[`orchestrator_trigger.py`](../../packages/py/application/src/bolsa_application/orchestrator_trigger.py) ·
[`orchestrator_cycle.py`](../../packages/py/application/src/bolsa_application/orchestrator_cycle.py) ·
[`auto_orchestrator.py`](../../packages/py/application/src/bolsa_application/auto_orchestrator.py) ·
[`auto_orchestrator.py` (ruta)](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_orchestrator.py) ·
[`orchestrator_trigger_ledger.py`](../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/orchestrator_trigger_ledger.py) ·
[`auto_orchestrator_worker.py`](../../apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py) ·
[`backtest-orchestrator-trigger.tsx`](../../apps/web/src/features/backtests/backtest-orchestrator-trigger.tsx).

---

## 1. El problema

El embudo completo existía, pero solo era alcanzable **de noche** y con
`AUTO_ORCHESTRATOR_ENABLED=1`. Desde producto eso significa que un usuario no podía pedir «evalúa
este valor ahora» sin esperar al reloj del worker o encender un flag global. La tentación evidente
—una ruta que llame al orquestador— tiene tres formas de salir mal:

1. **Reimplementar el embudo** en la ruta: dos implementaciones divergen en semanas, y la de la
   ruta no pasa por los gates que la de fondo sí aplica.
2. **Aceptar evidencia del cliente** para «ahorrar» el LAB: el cliente decide qué es evidencia, y
   la procedencia deja de ser verificable.
3. **Abrir un camino a ACTIVE** que no pase por `decide_promotion`: se salta la promoción
   gobernada por evidencia.

## 2. Decisión

### 2.1 Contrato

```
POST /api/auto/orchestrator/run
body: { instrumentId, accountId?, dryRun?: true, toPhase?: "finalista", dataSnapshotId? }
→ 200 recibo | 400 petición fuera de contrato | 409 ámbito | 422 cuerpo con campos extra
```

### 2.2 Reglas, todas obligatorias

| Regla | Implementación | Por qué |
|-------|----------------|---------|
| **`dryRun` por defecto `true`** | `Field(default=True)` en el DTO; el servidor lo aplica si se omite | Un `POST` sin cuerpo no escribe nada del lifecycle |
| **Nunca escribe ACTIVE** | `max_phase=PHASE_FINALISTA` en el orquestador + rechazo de `toPhase='active'` (400) + defensa en profundidad en el recibo | El salto a ACTIVE sigue siendo `decide_promotion` |
| **Idempotencia** | Clave `(instrumentId, accountId, snapshot, cycle, dryRun)` → `runId = trigger:<sha256[:20]>`; el recibo se busca por correlación **antes** de ejecutar | Repetir no duplica ni re-ejecuta |
| **Ámbito ESTUDIO** | El `instrumentId` debe estar en el universo resuelto; si no, `409` | El disparador no sustituye el universo canónico |
| **Auditoría** | Un evento `auto.orchestrator.run` por ejecución (actor, `dryRun`, fase, gates, resultado) | Sin eso, el disparador es una puerta trasera |
| **Fail-closed** | Ciclo que no llega a FINALISTA ⇒ `status=INCOMPLETE` con motivos y gates | Nunca un `200` optimista |
| **Sin evidencia del cliente** | `extra='forbid'` en el DTO; no hay campo de gates/metrics/runId | La evidencia se mide, no se declara |

### 2.3 Una sola implementación del ciclo

El cuerpo del ciclo se extrajo del bucle del worker a `run_cycle_once`
(`orchestrator_cycle.py`); el worker y la ruta **comparten** esa función. La composición del
orquestador también es compartida (`build_orchestrator`): la ruta no compone un orquestador
distinto. Las únicas diferencias son declarativas:

- `max_phase=FINALISTA` (techo),
- `watch=False` (la vigilancia escribe salud sobre la ACTIVA: fuera del techo),
- `dryRun` envuelve el store en `DryRunLifecycleStore` (solo lectura, escrituras declaradas).

### 2.4 `dryRun` no finge: declara

El dry run envuelve el store del lifecycle en un envoltorio que **delega las lecturas** al store
real y **suprime las escrituras conocidas**, apuntándolas. El recibo devuelve `writes` con la lista
de lo que se habría escrito. Esto preserva una propiedad importante: un dry run lee el estado real
(sus gates son los de verdad), y a la vez es demostrable que no escribió.

El evento de auditoría **sí** se persiste en dry run: es el recibo durable y la clave de
idempotencia. Un dry run que no dejara traza sería indistinguible de un dry run que nunca ocurrió.

### 2.5 `dryRun` forma parte de la clave de idempotencia

Se desvía deliberadamente del enunciado «idempotencia por `(instrumentId, accountId, snapshot,
cycle)`»: un recibo *dry* **no puede** bloquear la ejecución real del mismo ciclo —son resultados
distintos, con escrituras distintas—. Repetir el MISMO cuerpo (mismo `dryRun`) sí devuelve el mismo
recibo con `replayed=true`. La alternativa (clave sin `dryRun`) haría que una simulación «gastara»
la ejecución real del día, que es peor que la desviación.

## 3. Consecuencias

**Buenas.**
- El embudo es alcanzable a demanda con el mismo rigor que de noche.
- La simulación es el default: probar no ensucia la evidencia del LAB.
- Cada ejecución deja un recibo verificable (fase, gates, `runId`, escrituras suprimidas).
- Es imposible llegar a ACTIVE por esta ruta, y el recibo lo demuestra (`promoted=false`).

**Costes aceptados.**
- Superficie nueva de escritura: mitigada por `dryRun` default, techo de fase y auditoría.
- El recibo vive en `platform_events` como evento de plataforma. Es aditivo y no requiere
  migración, pero **no** es una tabla de jobs: no hay progreso incremental ni cancelación. Si el
  embudo crece hasta necesitar progreso, deberá migrar a la cola durable (`auto_ops_jobs`).
- Un ciclo es síncrono en la petición: un LAB grande puede agotar el tiempo del cliente. El recibo
  ya estará persistido, así que repetir el POST recupera el resultado (idempotencia real).

## 4. Lo que este ADR no hace

- **No** escribe ACTIVE, ni promociona, ni toca el TOP directamente.
- **No** sustituye el universo ESTUDIO ni acepta una lista de instrumentos del cliente.
- **No** cambia el reloj del worker: el bucle de fondo sigue igual (`AUTO_ORCHESTRATOR_ENABLED`).
- **No** cancela ejecuciones en vuelo: un POST concurrente con la misma clave devolverá el recibo
  ya persistido si llegó a escribirse, o ejecutará el ciclo si aún no existe. El índice de
  `platform_events` no impone unicidad por correlación.

## 5. Verificación

`test_orchestrator_trigger.py`: `dryRun` no escribe y declara escrituras · el store real se
restaura · con techo FINALISTA no se escribe ACTIVE ni promoción · `toPhase='active'` se rechaza ·
repetir devuelve el mismo `runId` con `replayed=true` y ejecuta una sola vez · fuera de ESTUDIO es
conflicto · universo no resuelto no ejecuta · un fallo del LAB produce `INCOMPLETE` con motivo.
`test_auto_orchestrator_route.py`: default `dryRun` · idempotencia HTTP · `409` fuera de ESTUDIO ·
`409` cuenta cerrada · `400` `toPhase` inválido · `422` con evidencia del cliente · `400` sin
instrumento. `backtest-orchestrator-trigger.test.tsx`: toggle visible, recibo con fase/gates,
`not_evaluated` → «Sin dato todavía», `INCOMPLETE` rotulado, acto de contrato denunciado.

## 6. Contrato FE/BE

La ruta es **aditiva** en `openapi.json`: se regenera con `contract:gen` y `contract:check` queda
en verde. Es una decisión explícita (superficie nueva), no un efecto colateral, y por eso queda
fuera del invariante `Δ contrato = 0` que la auditoría exige al resto de cambios.
