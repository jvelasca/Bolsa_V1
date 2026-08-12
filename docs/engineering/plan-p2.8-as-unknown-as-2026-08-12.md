# Plan — P2.8 residue: sopa de «as unknown as» → fidelidad de contratos en capa FE · 2026-08-12

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada
> P2.8 de la Auditoría consolidada, tras P2.1).
> **Fuentes de verdad:** [traspaso-f5a-contratos-fe-be-2026-08-11.md](./traspaso-f5a-contratos-fe-be-2026-08-11.md)
> (§6 deuda: fidelidad campo-a-campo DTOs manuales vs contrato) ·
> [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md)
> (fila P2.8: «`as unknown as` sistemático») ·
> [plan-p2.1-god-components-2026-08-12.md](./plan-p2.1-god-components-2026-08-12.md) (§8 residuo) ·
> protocolo 3 fases M5.
> **Rama de ejecución:** `stage/p2.8-as-unknown-as-2026-08-12` (desde base `30a0804` = tip P2.1).
> **Regla del hilo:** NO tocar código fuera del alcance P2.8. Batería por paso.
> **Estado:** COMPLETADO 2026-08-12 (7 bridges serialización eliminados; 2 casts residuales confinados en
> helpers nombrados; batería verde salvo `contract:check` por drift F5b heredado). Cierre + traspaso en §8.

---

## 0. Alcance pactado (decisión del usuario, este hilo)

El usuario eligió **"Opción A → sub-enfoque A1 (recomendado)"**: **fidelidad en la capa FE DTO 1:1 con el
wire actual**. Sustituir los bridges `as unknown as Record<string, unknown>` de serialización por **DTOs
concretos** (formas locales reales) en `packages/shared` y en el cliente `apps/web/src/lib/api.ts`, de modo
que la serialización quede **tipada sin cast**. **NO se toca el BE ni el OpenAPI**:
los payloads siguen siendo, en el wire, exactamente lo que el contrato FastAPI define
(`{[key:string]:unknown}[]` / `Record<string, unknown>`); solo que el FE los produce/consume a través de
tipos concretos estructuralmente validados.

**Objetivo (D5, cero features):** eliminar los **7 bridges de serialización** TS↔Py que son deuda P2.8.

---

## 1. Hechos de diagnóstico FASE 1 (confirmados en código)

### 1.1 El BE trata estos payloads como **blobs opacos versionados** (evidencia)

- `core_r.py:19-21`: `queue: list[dict[str, Any]]`, `reports: dict[str, Any]`, `scheduler: dict[str, Any]`;
  `SupervisedF3BundleDto.items: list[dict[str, Any]]`; `DiaDSessionEvidencePersistRequestDto.evidence: dict[str, Any]`.
- Repos: `core_r_repository.py` / `supervised_f3_repository.py` guardan en columnas `*_json` y solo filtran
  a `isinstance(x, dict)` — **round-trip opaco, verionado, sin bind de campos**.
- Contrato OpenAPI (`schema.d.ts`): `SyncCoreRBundleDto`/`CoreRBundleDto`/`SyncSupervisedF3BundleDto` =
  `{[key:string]:unknown}[]` / `{[key:string]:unknown}`.

**Consecuencia:** hacer "bind total" en Pydantic (Opción A2) rompería el versionado de blob y arrastraría
casi todo P2.6. **A1 evita eso**: el wire no cambia; la fidelidad se logra **solo del lado FE**.

### 1.2 Por qué existe el cast (raíz estructural)

Una forma concreta (`CoreRReviewQueueItem`) **no es asignable** a `Record<string, unknown>` sin cast en TS.
Los 7 bridges saltan porque `api.ts` (y las DTOs bundle de `packages/shared`) declaran esos parámetros como
`Record`/`Array<Record>` mientras el caller posee la forma concreta.

### 1.3 Inventario de los `as unknown as` (7 de serialización + 2 ajenos)

| #   | Fichero:línea                        | Puente (origen → destino)                                  | Familia                                               |
| --- | ------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------------- |
| 1   | `supervised-f3-sync.ts:35`           | `items: SupervisedQueueItem[]` → `Array<Record>`           | SEMI Confirm F3                                       |
| 2   | `core-r-sync.ts:86`                  | `items: CoreRReviewQueueItem[]` → `Array<Record>`          | CORE-R                                                |
| 3   | `core-r-sync.ts:89`                  | `reports: Record<string, CoreRReport>` → `Record`          | CORE-R                                                |
| 4   | `core-r-sync.ts:90`                  | `scheduler: CoreRSchedulerPrefs` → `Record`                | CORE-R                                                |
| 5   | `trading-dia-d-replay-panel.tsx:636` | `evidence: DiaDSessionEvidenceV1` → `Record`               | DÍA D evidence                                        |
| 6   | `backtest-explore-panel.tsx:511`     | `noteFacts: CoachFactsV1` → `Record` (spread en baseFacts) | Coach                                                 |
| 7   | `backtest-explore-panel.tsx:810`     | `coachFacts` → `Record` (a `analyzeBacktestCoach`)         | Coach                                                 |
| 8   | `packages/database/src/index.ts:3`   | `globalThis as unknown as { prisma }`                      | **AJENO** (idioma Prisma singleton, no serialización) |
| 9   | `backtest-hub-nav.test.ts:17`        | `undefined as unknown as string \| null` (param de test)   | **AJENO** (helper de test, no TS↔Py)                  |

**Decisión:** los #1–#7 son el alcance P2.8. El #8 (Prisma singleton) y el #9 (cast de `undefined`
en un test) **quedan fuera de alcance**: no son bridges de serialización TS↔Py ni a `Record`.

---

## 2. Diseño (A1: fidelidad FE 1:1 con el wire)

Principio rector: **el shape del wire no cambia**; el FE declara DTOs concretos cuyos valores serializan
byte-idénticos a lo que hoy produce el cast. Eliminar el cast = **que el tipo del parámetro del cliente sea
el DTO concreto**, de modo que el objeto local (que ya tiene esa forma) sea asignable directamente.

### 2.1 DTOs concretos en `packages/shared` (fuente única de la forma de wire)

- **CORE-R**: en `core-r-api.ts`, sustituir `queue: Array<Record>` / `reports: Record` / `scheduler: Record`
  por tipos concretos:
  `type CoreRQueueItemDto` (shape de `CoreRReviewQueueItem`), `type CoreRReportDto` (shape de `CoreRReport`),
  `type CoreRSchedulerPrefsDto` (shape de `CoreRSchedulerPrefs`), y `type CoreRReportsMapDto = Record<string, CoreRReportDto>`.
- **SEMI F3**: en `supervised-f3-api.ts`, sustituir `items: Array<Record>` por `type SupervisedF3QueueItemDto`
  (shape de `SupervisedQueueItem`).
- **DÍA D evidence**: nuevo DTO `EvidenceDto` (o en un módulo `dia-d-evidence-api.ts`) con shape de
  `DiaDSessionEvidenceV1`.
- **Coach**: DTO `CoachFactsV1Dto` (shape de `CoachFactsV1`) usado como componente del `facts` del payload
  coach y de `baseFacts` extendido.

**Nota de portabilidad:** las formas concretas **no se mueven** desde web; los DTOs de `packages/shared` son
**re-declaraciones** de la shape de wire. Si en el futuro P2.6 decide un hogar único, se consolidan. Con
esto evitamos arrastrar los grafos web-only (`RecommendationV1`, `CoreRVerdict`, etc.) a `packages/shared`.

### 2.2 Cliente `api.ts` — parámetros concretos

- `syncAccountCoreR` body → `{ queue: CoreRQueueItemDto[]; reports: CoreRReportsMapDto; scheduler: CoreRSchedulerPrefsDto }`.
- `syncAccountSupervisedF3` body → `{ items: SupervisedF3QueueItemDto[]; activeId?: string | null }`.
- `persistDiaDSessionEvidence` `evidence` → `DiaDSessionEvidenceV1Dto`.
- `analyzeBacktestCoach` `facts` → `CoachFactsV1Dto | null` (con `baseFacts` tipado como `CoachFactsV1Dto & {...}` donde aplique).

### 2.3 Eliminar los 7 casts

- **#1–#4:** los `localBundle()` de `supervised-f3-sync.ts`/`core-r-sync.ts` devuelven directamente el
  objeto; al ser el body del cliente el DTO concreto (misma shape), **se borra el `as unknown as`**. Donde el
  tipo local no sea idéntico al DTO (p.ej. `CoreRReport` tiene campos propios), se mapea explícitamente o se
  declara el DTO con esa misma shape → asignación directa.
- **#5:** `evidencePayload` es ya `DiaDSessionEvidenceV1`; al ser `evidence: DiaDSessionEvidenceV1Dto`, se
  borra el cast.
- **#6:** `baseFacts` se tipa como `CoachFactsV1Dto & { policy..., dualAudit..., coachPass... }` (forma real
  completa), se borra el `as unknown as` sobre `noteFacts`.
- **#7:** `coachFacts` ya es `CoachFactsV1`; al ser `facts: CoachFactsV1Dto`, se borra el cast.

### 2.4 Contract drift

El contrato OpenAPI **no cambia** (Blob opaco sigue). A1 **aumenta** lo que el FE conoce del shape interno
de esos campos; esto es exactamente la dirección que F5a §6 dejó como deuda medida (la fidelidad tipo-vs-
wire). Para blindarlo opcionalmente se pueden añadir `CoreRBundleDto`/`SupervisedF3BundleDto` como
**sentinels** del `contract-check.ts` (claves FE ⊆ contrato sigue verde porque `queue`/`reports`/`scheduler`
existen en el contrato; la shape interna del elemento no se comprueba, igual que ya pasa hoy con el FE en
modo `Record`). **Se decide en tabla de decisiones** si se añaden (ver §5).

---

## 3. Estados del mapa (FASE 1/2 completada)

- **`as unknown as` de serialización:** 7 bridges inventariados (barrido `rg "as unknown as"` en `*.ts*`,
  verificado). Tipos origen/destino mapeados.
- **`packages/shared`:** `core-r-api.ts` (`CoreRBundleDto`), `supervised-f3-api.ts` (`SupervisedF3BundleDto`)
  son las únicas DTOs bundle implicadas; el barrel `index.ts` ya las exporta.
- **Cliente:** `api.ts:1100-1133` (core-r y supervised-f3), `api.ts:1499` (persistDiaDSessionEvidence),
  `api.ts:158` (analyzeBacktestCoach).
- **Dependencias de tipos:** formas concretas residen en web (`core-r-review-queue-store.ts`,
  `core-r-judgment.ts`, `core-r-scheduler.ts`, `supervised-f3-queue-store.ts`, `dia-d-session-evidence.ts`,
  `backtest-deep-coach.ts`). **No se mueven** en esta fase (deuda P2.6).

---

## 4. Validación / batería por paso

Cada commit de la fase debe pasar (en `apps/web`), como en F5c/P2.1:

- `pnpm --filter @bolsa/web typecheck` → exit 0. **✓**
- `pnpm --filter @bolsa/web lint` → 0 errores. **✓** (2 warnings pre-existentes en un effect no tocado de `backtests-page.tsx`, ya anotados en P2.1).
- `pnpm --filter @bolsa/web test` → **714 passed (141 f)** — sin regresiones. **✓**
- `pnpm --filter @bolsa/web build` → 0. **✓**
- `pnpm --filter @bolsa/shared typecheck` + `build` + `test` → 10✓. **✓**
- `pnpm --filter @bolsa/web contract:check` → **ROJO por drift heredado de F5b** (ver §6; no introducido por P2.8).

### Nota sobre `contract:check` (drift F5b heredado)

`apps/web/api/openapi.json` commitado está **desfasado** respecto al FastAPI vivo: el cambio F5b/P2.7
`DepositCashDto.amount`/`WithdrawCashDto.amount → gt=0` añade `exclusiveMinimum: 0.0` al dump real, y el
contrato no se regeneró tras el merge de F5b (P2.1 tampoco lo hizo; su batería no incluyó `contract:check`).
Por tanto, desde el merge de F5b, `contract:check` es rojo **en cualquier rama**, con o sin P2.8. Decisión
del usuario: **excluir** ese regen de P2.8 (fuera de alcance) y registrarlo como deuda.

---

## 5. Decisiones a confirmar (no bloqueantes para el plan)

| Id     | Decisión                                                                                          | Opciones                             |
| ------ | ------------------------------------------------------------------------------------------------- | ------------------------------------ |
| D-CTRL | ¿Añadir `CoreRBundleDto`/`SupervisedF3BundleDto` como sentinels de `contract-check.ts`?           | **Sí (blindaje)** · No (mínimo)      |
| D-DTO  | ¿Los DTOs concretos viven en `packages/shared` (re-declaración) o cabe re-exportar los tipos web? | Shared (recomendado) · Re-export web |

---

## 6. Fuera de alcance

- **No** tocar Pydantic/Python ni regenerar OpenAPI (`contract:gen` no debe producir diff).
- **Drift F5b heredado (`exclusiveMinimum` en DepositCashDto/WithdrawCashDto)**: NO incluido en P2.8
  (decisión `cd_exclude`). Registrado como deuda → fase de contrato/fidelidad (regen + commit del contrato).
- **No** mover tipos web-only a `packages/shared` (grafos `RecommendationV1`/`CoreRVerdict` etc.) — deuda P2.6.
- **No** el `as unknown as` de `packages/database/src/index.ts:3` (Prisma singleton, ajeno).
- **No** el `as unknown as` de `backtest-hub-nav.test.ts:17` (cast de `undefined` en un test, no TS↔Py).
- No adoptar `openapi-fetch` completo ni reescribir `api.ts` entero (deuda F5a, no esta fase).
- No otros `Record<string, unknown>` que no tengan `as unknown as` (p.ej. `coachFacts` en
  `instrument-strategy-top.ts` que ya es `Record` y no es un bridge de cast).

### Casts residuales (confinados, intencionales)

Tras P2.8 quedan **2 `as unknown as` de serialización**, confinados cada uno a un único helper nombrado
(documenta explícitamente la frontera TS↔wire de un blob abierto):

- `supervised-f3-sync.ts` → `toF3ItemDto` (el `payload` del item es una propuesta Supervised con grafos
  web-only; se serializa a opaco en ese único punto).
- `backtest-explore-panel.tsx` → `toCoachFactsRecord` (el blob-abierto `coachFacts` se serializa a opaco
  en ese único punto).

Los **7 casts dispersos en el caller se eliminaron** (#1–#7). TS exige `unknown` para cualquier conversión
concreto→`Record`, por lo que un blob abierto no puede serializarse sin cast; la fidelidad lograda es que el
cast ya no se dispersa y cada payload de shape fija se tipa exactamente.

---

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                        |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Diagnóstico P2.8 completado: 9 `as unknown as` únicos (7 serialización + 1 Prisma ajeno + 1 test ajeno); evidencia de blobs opacos BE; raíz estructural del cast.                                                                                                                             |
| 2026-08-12 | Decisión usuario: **Opción A → sub-enfoque A1** (fidelidad FE 1:1 con wire; NO BE/OpenAPI). D-DTO=shared · D-CTRL=Sentinelas CoreR/SupervisedF3.                                                                                                                                              |
| 2026-08-12 | **DTOs concretos** en `packages/shared`: `core-r-api.ts` (CoreRQueueItemDto/CoreRReportDto/CoreRReportsMapDto/CoreRSchedulerPrefsDto), `supervised-f3-api.ts` (SupervisedF3QueueItemDto), nuevos `dia-d-evidence-api.ts` (DiaDSessionEvidenceV1Dto) y `coach-facts-api.ts` (CoachFactsV1Dto). |
| 2026-08-12 | **Cliente `api.ts`**: `syncAccountCoreR`/`syncAccountSupervisedF3`/`persistDiaDSessionEvidence`/`analyzeBacktestCoach` tipados con DTOs concretos (se quita `Record`).                                                                                                                        |
| 2026-08-12 | **7 casts eliminados**: core-r-sync (#2#3#4 asignación directa), supervised-f3-sync (#1 vía `toF3ItemDto`), trading-dia-d-replay (#5), backtest-explore (#6 vía `toCoachFactsRecord`, #7 directo). Sentinelas G4/G5 en `contract-check.ts`.                                                   |
| 2026-08-12 | **Batería**: shared typecheck✓ build✓ test 10✓ · web typecheck✓ lint 0 errores test 714✓ (141 f) build✓ · `contract:check` ROJO por drift F5b heredado (decisión `cd_exclude`, registrado como deuda).                                                                                        |

---

## 8. Cierre — resultado alcanzado y traspaso

P2.8 (residuo "as unknown as") **COMPLETADO** con cero cambios de comportamiento (D5) y cero cambios de wire:

- **7 bridges de serialización TS↔Py eliminados.** Los payloads de shape fija (CORE-R queue/reports/scheduler,
  SEMI F3 item, DÍA D evidence, Coach `facts`) pasan por **DTOs concretos** en `packages/shared` y se asignan
  directamente al cliente `api.ts` — sin `as unknown as`.
- **2 casts residuales confinados** en helpers nombrados (`toF3ItemDto`, `toCoachFactsRecord`) que serializan
  blobs abiertos intencionales a `Record<string, unknown>` en un único punto documentado de la frontera
  TS↔wire.
- **`contract-check.ts`** ampliado con sentinelas `CoreRBundleDto`/`SupervisedF3BundleDto` (G4/G5).
- **Contracto OpenAPI NO cambia** (decisión A1); `contract:check` queda rojo por **drift F5b heredado**
  (`exclusiveMinimum` en Deposit/Withdraw), fuera de alcance y registrado como deuda.
- **No** se toca Python/Pydantic, repos, ni los `as unknown as` ajenos (Prisma singleton y cast de `undefined`
  en test).

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: P2.8 residue (sopa de `as unknown as`) **COMPLETADO** en rama
> `stage/p2.8-as-unknown-as-2026-08-12` (desde base `30a0804` = tip P2.1).
>
> - **7 bridges de serialización TS↔Py eliminados** vía DTOs concretos en `packages/shared` (A1, sin tocar
>   BE/OpenAPI): `core-r-api.ts` (CoreRQueueItemDto/CoreRReportDto/CoreRReportsMapDto/CoreRSchedulerPrefsDto),
>   `supervised-f3-api.ts` (SupervisedF3QueueItemDto), nuevos `dia-d-evidence-api.ts` + `coach-facts-api.ts`.
> - **`api.ts`**: syncAccountCoreR / syncAccountSupervisedF3 / persistDiaDSessionEvidence / analyzeBacktestCoach
>   tipados con DTOs concretos (se retiró `Record<string, unknown>` en esos 4).
> - **2 casts residuales confinados** en helpers nombrados: `toF3ItemDto` (supervised-f3-sync) y
>   `toCoachFactsRecord` (backtest-explore) — serializan blobs abiertos a `Record` en un único punto.
> - **`contract-check.ts`**: sentinelas nuevas G4 (CoreRBundleDto) y G5 (SupervisedF3BundleDto).
> - BATERÍA: shared typecheck✓ build✓ test **10✓** · web typecheck✓ lint **0 errores** test **714✓ (141 f)**
>   build✓ · `contract:check` **ROJO por drift F5b heredado** (ver deuda siguiente).
>
> DEUDA REGISTRADA → fases posteriores:
>
> - **Drift contrato F5b**: `openapi.json` desfasado del FastAPI vivo (`Deposit/Withdraw.amount → gt=0`
>   añade `exclusiveMinimum`); `contract:check` rojo en cualquier rama desde el merge de F5b. Fase de fidelidad:
>   `contract:gen` + commit del regen. (`contract:gen/check` requieren `$env:PYTHONIOENCODING="utf-8"` en Windows.)
> - **P2.6 residue**: duplicación TS↔Py restante (ai-indicator-series ↔ technical_rating/data_quality;
>   execution-policies/position-policies/tracker-definitions/tax-report ↔ py) → requiere acuerdo de
>   fuente de verdad. P2.8 re-declaró formas en shared sin consolidar los tipos web-only (grafos
>   RecommendationV1/CoreRVerdict) → consolidarlos ahí.
> - **F5a §6** fidelidad campo-a-campo + openapi-fetch como cliente (deuda previa).
> - Deuda previa: P1.9 API thin (hilo propio), P1.3 auth full (D4), mypy por fases.
>
> Lee PRIMERO: `docs/engineering/plan-p2.8-as-unknown-as-2026-08-12.md` (§4-§8) y sus fuentes
> (`traspaso-f5a-contratos-fe-be-2026-08-11.md` §6, `audit-consolidado-internas-externas-2026-08-11.md`
> fila P2.8, `plan-p2.1-god-components-2026-08-12.md` §8).
> NO toques código fuera del alcance de la fase que se declare.
