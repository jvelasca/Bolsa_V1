# Plan de fase — `v2.67` / `AUTO-20F` · cierre de las 2 P3 de la auditoría de `v2.66`

> **AsOf:** 2026-09-25 · **Versión:** `1.91.0-beta` → **`1.92.0-beta`** · **Base:** tag `v2.66-beta` (`6fe7faa8`)
> **Alcance:** cerrar las **2 P3** no bloqueantes de la auditoría de `v2.66-beta`, registradas en
> [`deuda-p3-post-auditoria-v2.66-2026-09-25.md`](./deuda-p3-post-auditoria-v2.66-2026-09-25.md).
> **Naturaleza:** fase corta de **precisión** (no de producto). **SIN migración** (head `046_fill_reference_mid`).
> **El freeze no se toca.**

## Motivación

La auditoría de `v2.66-beta` fue **APROBADA CON OBSERVACIONES** (0 bloqueantes). Levantó dos P3:

1. **P3-1 (documental)** — El `plan`/`audit-pack` de `v2.66` afirmaban que la matriz de mutaciones «formaliza
   como **M180**» el contrato **TS-vs-Python**. **No se sostiene**: M180 mutila el **render**
   (`auto_evidence_report.py`), no el instrumento (`auto_adaptive_calibration.py`); ese contrato es **vitest** y
   **no** entra en la matriz pytest. Es la **misma clase** de sobre-afirmación que la fase anterior decía
   corregir.
2. **P3-2 (borde)** — Ante un valor **escalar** donde se espera una lista (p. ej. `"requestedStrategyVersions":
   "orb-a"`), el frontend daba `NO MEDIDO` pero el render Python **iteraba la cadena** (`"o, r, b, -, a"`).
   Asimetría **nueva** introducida por `v2.66` (antes ambos colapsaban a `(ninguna)`).

## Diseño

### P3-1 — Corregir la redacción (documental)

- Sustituir en `audit-pack §1 #2` y `§4` la atribución a **M180** por la realidad: el contrato TS-vs-Python se
  cubre por **vitest** (sonda manual reproducida por el auditor); **M180** cubre el atado
  `_CALIBRATION_ROWS`↔`_CALIBRATION_QUESTIONS` **dentro del render Python**.
- Misma nota en el `plan`.
- No se re-sella `v2.66` (tag inmutable): los documentos del tag conservan el texto original; la corrección vive
  en `main` y se documenta en la deuda.

### P3-2 — Espejo exacto en el perímetro (código)

- **Python** — `_version_list`: si el valor **no es lista/tupla**, se trata como **ausente** (`NO MEDIDO`) en
  lugar de iterarlo.
- **TS** — `listLabel` pasa a aceptar `unknown` y devuelve `NO MEDIDO` si no es array; `isMeasuredList` marca
  `inconclusive`. (`asStringArrayOrNull` ya normalizaba en el parser, pero `buildEvidenceView` es pura y debe
  ser robusta ante artefactos construidos a mano.)
- Tests en **ambos** lados + mutación **M181**.

## Superficie

| Fichero | Cambio |
|---|---|
| `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py` | `_version_list` no-lista ⇒ `NO MEDIDO` |
| `packages/py/analytics/tests/test_auto_evidence_report.py` | test no-lista |
| `apps/web/src/features/operational-console/auto-evidence-report.ts` | `listLabel`/`isMeasuredList` robustos |
| `apps/web/src/features/operational-console/auto-evidence-report.test.ts` | test no-lista |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | **M181** |
| `docs/engineering/plan|audit-pack-v2-66-*.md` | corrección de la sobre-afirmación (P3-1) |
| `apps/api-python/scripts/...` (mutaciones) | — |
| `package.json` / `CHANGELOG.md` | bump `1.91.0-beta` → `1.92.0-beta` |

## Verificación prevista

- Frontend: `test`, `typecheck`, `lint`, `build`, `contract:check`.
- Python: `pytest packages/py/analytics`, `ruff`, `import-linter`.
- Mutaciones **M179/M180/M181** muerden; matriz completa sin huecos.

## Fuera de alcance

- La **corrida PAPER real** (paso operativo del propietario; bloqueo por material).
- **`AUTO-21`**. Sin producto nuevo, sin migración, sin tocar el freeze.
