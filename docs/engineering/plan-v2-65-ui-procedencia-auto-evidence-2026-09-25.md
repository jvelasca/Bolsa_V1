# Plan de fase — AUTO-20D · UI de procedencia del AUTO EVIDENCE REPORT (`V2.65` / `1.90.0-beta`)

**Versión:** `1.89.0-beta` → **`1.90.0-beta`** · **Rótulo:** `AUTO-20D` / `V2.65` · **Fecha:** 2026-09-25 ·
**Migración: NO** (Alembic head sigue en `046_fill_reference_mid`).
**Origen:** auditoría de `v2.64-beta` (punto 14: el badge de procedencia es la prioridad nº 1 de UI) ·
**Base:** [traspaso post-v2.64](./traspaso-relevo-post-v2.64-auto-20c-paper-virtual-2026-09-25.md).

## 1. Objetivo e invariantes

    10|La cadena de evidencia está sellada en `v2.64` (`paper_cycles_export.py` →
`auto_replay_battery.py --walk-forward --out/--render`) pero **no tiene ninguna superficie de cabina**: el
JSON, el render y `stderr` son las únicas salidas. Esta fase añade la **UI de procedencia** que lee el
artefacto `auto20c_evidence_artifact_v1` y hace **imposible** confundir una corrida PAPER real con el
fixture sintético (y declara el caso "sin material").

Invariantes que NO se mueven:

- **La UI lee y presenta; no recalcula.** R, WFE, coverage, shrinkage y veredictos viajan **verbatim** del
  `report`. Ninguna métrica se re-deriva en TypeScript.
- **Nunca se inventa un cero.** Un conteo ausente (`null`) se muestra `NO MEDIDO`; `0` significa
  "hemos medido y no hay". Es la regla `None → INCONCLUSIVE` trasladada a la cabina.
    20|- **Nunca se asume PAPER real.** Un `materialOrigin` desconocido —o un artefacto sin material— **no** se
  degrada a `paper_real`.
- `ADAPTIVE_POLICY_VERSION = "auto18-v1"` y `DATA_GATE_POLICY_VERSION = "auto15-v1"` intactos; sin
  migración; **ningún** fichero Python ni del freeze se toca (`auto_adaptive.py`,
  `auto_adaptive_data_gate.py`, `auto_simulation_worker.py`, `auto_adaptive_journal.py`,
  `auto_adaptive_replay.py`, `v2_43_governor_evidence.py`, `governor.json`).

```mermaid
flowchart TD
  cli["auto_replay_battery.py --out"] --> json["AUTO20C_REAL_PAPER_REPORT.json"]
  json --> imp["Import manual (subir o pegar JSON)"]
  imp --> parse["parse + validacion de esquema (puro)"]
    30|  parse --> cls["clasificacion de procedencia"]
  cls --> badge["Badge SOURCE + bloques verbatim"]
  badge --> store["store local persistido"]
```

## 2. Comportamiento de la UI (punto 14)

El **badge de procedencia** va arriba, en banda propia (no dentro de un `<details>` ni de un JSON):

| Caso | Condición | Etiqueta | `tone` | Base de decisión |
|---|---|---|---|---|
    40|| A | `materialOrigin = paper_real` y `material` presente | `PAPER REAL` | ok | **sí** |
| B | `materialOrigin = synthetic_fixture` | `FIXTURE SINTÉTICO` + `NO UTILIZAR PARA DECISIONES` | warn | no |
| C | sin artefacto o `material === null` | `SIN MATERIAL · NO MEDIDO` | neutral | no |
| D | `materialOrigin` no reconocido | `PROCEDENCIA DESCONOCIDA` | danger | no |

Se separan los **tres ejes** (punto 11), sin renombrar la clave `materialOrigin` (compatibilidad):
`Origen: PAPER real` · `Ejecución: virtual / sin dinero real` · `Dinero real en riesgo: no`.

## 3. Piezas

- **`auto-evidence-report.ts` (puro, determinista)**: constantes espejo del esquema; `parseAutoEvidenceArtifact`
  (rechaza esquema ajeno con motivo); `classifyEvidenceSource`; `buildEvidenceView` (Material / Calibration /
  Declared / perímetro, con `INCONCLUSIVE` ante hueco); `integrityWarnings` (dinero real, ejecución no virtual,
    50|  venue no paper, lectura saturada).
- **`auto-evidence-archive-store.ts`**: zustand `persist`, clave `bolsa-auto-evidence-archive-v1`, cap 10,
  dedupe por `schema|materialOrigin|fingerprint`.
- **`OpsAutoEvidenceSection`**: sección de primer nivel en la Consola operacional; import por fichero y por
  pegado; error de import **sin** persistir; limpiar archivo; aviso declarado (procedencia autodeclarada, la
  huella no es prueba criptográfica).
- **Tests**: `auto-evidence-report.test.ts` (parser, 4 estados, `None → INCONCLUSIVE`, contrato de claves),
  `auto-evidence-section.test.tsx` (badge, no-invención de 0, import inválido, aviso de dinero real),
  `auto-evidence-archive-store.test.ts` (save/dedupe/cap/remove/clear).

## 4. Compuertas

   60|- `pnpm --filter @bolsa/web test` · `typecheck` · `lint`.
- Se re-verifica que `packages/py` y el freeze siguen **intactos** (el diff no los toca).
- Equivalente a mutación: la matriz TS cubre los 4 estados de procedencia + `realMoneyAtRisk=true` + esquema
  ajeno; el test de contrato de claves cae si Python cambia la forma del esquema.

## 5. Hallazgo declarado — la corrida AUTO-20D real NO se ejecuta

Comprobación read-only sobre el PostgreSQL local: `sim_fill_finance_context` tiene **628 fills y
`cycle_id` NULL en todos** ⇒ `paper_cycles_export.py` bloquearía con `exit 2` ("no hay ciclos cerrados") y
    70|el estado real es **Caso C — SIN MATERIAL / NO MEDIDO**. La corrida real queda **bloqueada por material, no
por código**, y sigue siendo paso operativo del propietario (≥32 ciclos medidos por estrategia):

```powershell
uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py --account-id <uuid> --strategy-version <v> > ciclos.json
uv run --no-sync python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json --out AUTO20C_REAL_PAPER_REPORT.json --render AUTO20C_REAL_PAPER_REPORT.txt
```

## 6. Docs, sello y paso operativo

   80|
- Nuevos: plan, audit-pack, traspaso/relevo, arranque-auditor, arranque-agente de v2.65; `CHANGELOG`,
  `PROJECT_STATE`, `engineering-index`; `package.json` → `1.90.0-beta`; tag `v2.65-beta`.
- Se conserva la **regla de oro**: `INCONCLUSIVE` por muestra insuficiente **no** se arregla bajando
  `min_is`/`min_oos`/`folds`.

## 7. Límites declarados

- Sin material PAPER real, la UI muestra `SIN MATERIAL · NO MEDIDO`; no se fabrica ningún resultado.
- El **artefacto** se importa a mano: no hay endpoint ni migración en esta fase.
- `P(R>0)`, correlación entre estrategias y current-regime gating siguen fuera (AUTO-21).
