# Evidencia `v2.88.120-beta` — `A1-trace-por-valor`: los ciclos del valor dentro del informe de ESTUDIO (con enlace a la operación)

> **Sello:** `v2.88.120-beta` (base `v2.88.119-beta`).
> **Bump:** `2.11.119-beta` → **`2.11.120-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
> **Naturaleza:** sello **aditivo** · **`Δ motor = 0`** (dominio puro de informe + DTO read-only + UI; no toca decisión/ejecución, umbrales, reparto, `TOP_N`, régimen ni protección) · **`Δ decisión = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP ampliado** (campo `cycles` aditivo en `EstudioAuditValueDto`; endpoint read-only, sin ruta nueva).
> **Cierra:** la rebanada mínima `A1` de la prioridad funcional AUTO/DÍA-D (entradas/salidas **trazables por valor** + trazabilidad exacta de la estrategia y sus señales).
> **Fecha:** 2026-10-13.

---

## 1. Qué cambia (aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Ciclos por valor (fuente única)** | [`estudio_audit.py`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) | Nuevo `_cycles_for_symbol(cycles)` (puro y determinista): lista ordenada por `cycleId` con `entryDay`/`exitDay`/`strategyPresetKey`/`strategyVersion`/`realizedR`. Un ciclo **sin `cycleId` legible** se **cuenta** (`unlinked`) y se declara el hueco; nunca se inventa una clave para forzar el enlace. Cada entrada del informe gana `cycles[]`. |
| **DTO read-only** | [`auto_estudio_audit.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_audit.py) | Nuevo `EstudioAuditCycleDto`; `EstudioAuditValueDto` gana `cycles` (`default_factory=list`, aditivo). Endpoint sigue `readOnly` y `PRECOMPUTED_ARTIFACT`. |
| **Contrato FE/BE** | [`schema.d.ts`](../../../../apps/web/src/api/schema.d.ts) · [`openapi.json`](../../../../apps/web/api/openapi.json) | Regenerados con `contract:gen` (diff **acotado** al `EstudioAuditCycleDto` + `cycles`). |
| **UI** | [`estudio-audit-view.ts`](../../../../apps/web/src/features/auto-monitor/estudio-audit-view.ts) · [`estudio-audit-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-audit-panel.tsx) | Helpers puros `describeCycle`/`formatDay`; cada valor pinta sus ciclos con ventana y R, y un **deep-link** a la operación canónica (`autoOperacionHref(cycleId)` → `/auto/operar/operacion/<cycleId>`). Un valor sin ciclos enlazables declara «Señal sin ciclos enlazables (Sin dato todavía)» y **no** pinta enlace. |
| **Pruebas** | [`test_estudio_audit.py`](../../../../packages/py/application/tests/test_estudio_audit.py) · [`test_auto_estudio_audit_route.py`](../../../../apps/api-python/tests/test_auto_estudio_audit_route.py) · `estudio-audit-{view,panel}.test.*` | Orden por `cycleId` y determinismo; ciclo sin `cycleId` declarado (no silenciado); valor sin ciclos ⇒ `[]`; `realizedR` ilegible ⇒ `None` (nunca `0`); contrato HTTP; deep-link en la UI + hueco declarado. |

---

## 2. El hueco — la señal no enlazaba con la operación

**Antes (`v2.88.119`):** el informe por valor de ESTUDIO declaraba la **señal** como un recuento
(`signal.cycles`/`measuredCycles`/`daysCovered`), pero **no** exponía **qué ciclos** la componen.
El `cycleId` es la clave canónica que el ciclo sella y que el resto del espacio AUTO usa para abrir
la operación (`autoOperacionHref`); sin él, el informe **no** permitía navegar del valor a su
operación, y el «entrada/salida por valor» quedaba inaccesible.

**Ahora:** cada valor expone `cycles[]` con los campos que el ciclo ya sella, y la UI enlaza. Ejemplo
del contrato (entrada por valor):

```json
{
  "symbol": "ACS",
  "strategy": { "presetKey": "sma_crossover", "version": "ver-1" },
  "signal": { "cycles": 3, "measuredCycles": 3, "daysCovered": 2 },
  "cycles": [
    {
      "cycleId": "cyc-1",
      "entryDay": "2026-04-01",
      "exitDay": "2026-04-02",
      "strategyPresetKey": "sma_crossover",
      "strategyVersion": "ver-1",
      "realizedR": 0.5
    }
  ]
}
```

Reglas de honestidad (doctrina «Sin dato todavía», `UNKNOWN ≠ 0`):

1. **Orden determinista** por `cycleId` (mismo estado ⇒ mismo payload).
2. **Ciclo sin `cycleId` no se silencia:** se cuenta y se declara `señal: N ciclo(s) sin cycleId (no enlazables a la operación)`.
3. **Campo ausente ⇒ `None`** (`exitDay` sin dato, `realizedR` ilegible…), nunca `""`/`0`.
4. **Valor sin ciclos ⇒ `cycles == []`** y la UI declara el hueco; no se fabrica un enlace.

---

## 3. Delta de contrato (aditivo)

- `EstudioAuditValueDto` gana `cycles` (opcional en el esquema OpenAPI; siempre presente en el payload del endpoint).
- Nuevo `EstudioAuditCycleDto` con `cycleId` (requerido) + 5 campos opcionales.
- **No** se añade ninguna ruta; los dos `GET /auto/estudio-audit[/{window}]` mantienen su forma y su modo `PRECOMPUTED_ARTIFACT`.

---

## 4. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy` (lista exacta de CI: `domain`/`market`/`infrastructure`/`application`/`api-python`, `--follow-imports=silent`) | ✅ `Success: no issues found in 552 source files` |
| `lint-imports --config packages/py/.importlinter` | ✅ **4 kept, 0 broken** |
| `pytest packages/py/application/tests -q` | ✅ **2710 passed** (176.44 s) — **+4** sobre los `2706` del sello anterior |
| `pytest apps/api-python/tests -q` | ✅ **1002 passed**, **2 failed** — ver «fallo ambiental declarado» abajo |
| `pnpm --filter @bolsa/web test` | ✅ **2094 passed** (297 ficheros) |
| `pnpm --filter @bolsa/web typecheck` | ✅ sin errores |
| `pnpm --filter @bolsa/web lint` | ✅ **0 errores** (23 warnings **preexistentes**, ajenos al diff) |
| `pnpm --filter @bolsa/web contract:check` | ✅ `openapi.json` y `schema.d.ts` coinciden con el commit |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | ✅ **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |

**Fallo ambiental declarado (no disimulado):** `apps/api-python/tests/test_lists.py::test_lists_crud_flow`
y `::test_delete_list_with_items_does_not_violate_fk` fallan **también en el commit base** (verificado
con `git stash` + re-ejecución sobre `HEAD` sin este diff) ⇒ **preexistente y de entorno** (el `/api/lists`
del app resuelve un alcance/cuenta distinto al de la BD `bolsa_v1` local, que sí tiene 5 listas / 75
instrumentos). **No** lo introduce este sello ni lo toca.

---

## 5. Límites declarados

- **Es un informe, no una decisión.** `Δ motor = 0` y `Δ decisión = 0`: el sello **no** recalcula nada en
  vivo (compone lo ya calculado) ni cambia umbrales, reparto, `TOP_N`, régimen o protección.
- **No** se automatiza la lane diaria ESTUDIO (cron/universo servidor): eso toca scheduling/config y
  reabre el plan PARKED `plan-cierre-operativa-auto-2026-10-08.md`.
- **No** se rellena el «porqué» (`why`): sigue el hueco declarado de la rebanada `C2`, bloqueado por una
  decisión de fuente (artefacto CLI `v2_90` vs BD).
- **No** se añade recompute en vivo del DÍA-D ni se emite `CONFIRMED` (reservado a la ventana PAPER;
  `P3-2`/`P3-3` abiertos).
- El enlace es **por `cycleId`**: un ciclo sin esa clave se declara como hueco, no se enlaza «por símbolo»
  (eso reintroduciría la ambigüedad que H1 cierra).
- **Tag `unsigned`:** el tag anotado **no** está firmado.

---

## 6. Cita POST-TAG

**Tag `v2.88.120-beta` empujado** (anotado, **unsigned**; commit de sello `664ec641`). `Release tag CI`
[**38369913850**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38369913850) — **verde en 10m03s**
(`createdAt` 2026-10-13T08:32:09Z → `updatedAt` 08:42:12Z), **12/12 jobs** (`playwright (integrated E2E,
opt-in)` = `skipped` por diseño). Lo decisivo: el job **`replay-repro (regenera el artefacto del sello desde
el fixture)`** cerró en **success** (08:32:13Z → 08:37:34Z): el artefacto congelado **SE REPRODUCE** —
coherente con **`Δ decisión = 0`** (este sello no toca el payload del replay).

| Job | Conclusión | Ventana |
| --- | --- | --- |
| `decision-spine` | ✅ success | 08:32:12 → 08:32:43 |
| `a7-gate` (chaos real-PG) | ✅ success | 08:32:12 → 08:33:07 |
| **`replay-repro`** (regenera el artefacto) | ✅ **success** | 08:32:13 → 08:37:34 |
| `security` (gitleaks) | ✅ success | 08:32:13 → 08:32:21 |
| `playwright` (integrated AUTO S5) | ✅ success | 08:32:12 → 08:35:33 |
| `shared` (build/typecheck/test) | ✅ success | 08:32:16 → 08:32:53 |
| `playwright` (mock E2E) | ✅ success | 08:32:24 → 08:42:04 |
| `python` (ruff/imports/mypy/pytest offline) | ✅ success | 08:32:13 → 08:35:21 |
| `lifecycle-pg` (Alembic + auth + golden restart) | ✅ success | 08:32:13 → 08:37:50 |
| `frontend` (typecheck/lint/test/build + contract:check) | ✅ success | 08:32:38 → 08:36:35 |
| `dr-verify` (battery DB_DR / TCP CI) | ✅ success | 08:32:29 → 08:33:29 |
| `playwright` (integrated E2E, opt-in) | ⏭️ skipped (diseño) | — |
| `certify` (aggregate + artifact) | ✅ success | 08:42:07 → 08:42:11 |

`lifecycle-pg` cierra con **sin migración** (head `053_dia_d_cycle_verifications`). CI en verde ⇒ **sello CERRADO**.

