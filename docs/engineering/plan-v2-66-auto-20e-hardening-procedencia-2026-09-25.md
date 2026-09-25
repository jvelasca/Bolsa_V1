# Plan de fase — `v2.66` / `AUTO-20E` · hardening de procedencia del AUTO EVIDENCE REPORT

> **AsOf:** 2026-09-25 · **Versión:** `1.90.0-beta` → **`1.91.0-beta`** · **Base:** tag `v2.65-beta` (`a077c1c6`)
> **Alcance:** cerrar las **3 observaciones P3** no bloqueantes de la auditoría de `v2.65-beta`, registradas en
> [`deuda-p3-post-auditoria-v2.65-2026-09-25.md`](./deuda-p3-post-auditoria-v2.65-2026-09-25.md).
> **Naturaleza:** fase de endurecimiento (no añade funcionalidad nueva de producto). Superficie: **frontend**
> + **un fichero Python de render** (`auto_evidence_report.py`) + **CI** (filtro de ruta) + **matriz de mutaciones**.
> **SIN migración** (Alembic head sigue en `046_fill_reference_mid`). **El freeze no se toca.**

## Motivación

`v2.65-beta` (AUTO-20D) fue **aprobada con observaciones**: la UI de procedencia se sostiene, pero el auditor
levantó tres P3 que no bloqueaban el sello y que conviene cerrar antes de que se conviertan en deuda gris:

1. **P3-1** — El «contrato de claves de calibración» era **TS-vs-TS**: el test comparaba la constante TS
   contra un literal escrito en el propio test. Además, `frontend-ci.yml` **no** incluía `packages/py/**`, así
   que un cambio solo en Python no habría disparado el workflow. La afirmación del plan/audit-pack del `v2.65`
   («el test cae si Python cambia») estaba **sobredimensionada**.
2. **P3-2** — `materialOrigin` de la raíz tenía **precedencia** sobre `material.materialOrigin` sin avisar de
   una contradicción entre ambos.
3. **P3-3** — Las listas de perímetro **ausentes** se mostraban `(ninguna)`, igual que las **vacías medidas**:
   una asimetría frente a la regla de conteos (`null` ≠ `0`).

## Diseño

### P3-1 — Contrato cruzado real

- El test del frontend **lee el instrumento Python** (`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py`),
  extrae las seis constantes `CALIBRATION_QUESTION_*` por regex y compara el conjunto con
  `AUTO_EVIDENCE_CALIBRATION_KEYS`. **Falla ruidosamente** si el fichero no existe o no encaja el patrón.
- `frontend-ci.yml` incorpora ese fichero a sus `paths` de `push` y `pull_request`: sin esto, un cambio solo
  de Python no ejecutaría la compuerta y el «contrato» seguiría siendo decorativo.
- El render Python gana un test que ata sus filas (`_CALIBRATION_ROWS`) a las **claves canónicas** que emite
  el instrumento (`_CALIBRATION_QUESTIONS`), de modo que el render no puede desalinearse.

**Prueba de que el contrato puede fallar (no se afirma, se mide):** renombrando temporalmente
`CALIBRATION_QUESTION_INTERVAL_COVERAGE` en Python, el test `matches the calibration keys the Python instrument
actually emits` pasa a **ROJO**; restaurado el fichero, vuelve a verde. Es un contrato **vitest**: **no** lo
cubre la matriz de mutaciones (pytest) — esa cubre el atado del render Python (**M180**), que es **otra**
propiedad. *(Precisión corregida en `v2.67`: la redacción original decía «la misma propiedad se cubre con
M180», que era una sobre-afirmación.)*

### P3-2 — Procedencia sin contradicción silenciosa

- `classifyEvidenceSource`: si **raíz** y **material** declaran un `materialOrigin` no nulo y **distinto**, la
  clasificación es **`PROCEDENCIA DESCONOCIDA`** (jamás `PAPER REAL`) con un *caveat* que explica la
  contradicción.
- `integrityWarnings`: emite un aviso (`materialOrigin incoherente: raíz=… vs material=…`).

### P3-3 — Ausente ≠ vacío en el perímetro

- **TS:** se preserva la **ausencia** (`asStringArrayOrNull` → `string[] | null`) en lugar de colapsarla a `[]`;
  `listLabel` devuelve `NO MEDIDO` si la lista es `null`/`undefined` y `(ninguna)` si es `[]`, con
  `inconclusive` marcado solo en el primer caso.
- **Python:** `_version_list` aplica el mismo criterio en `_perimeter_lines`
  (`ausente ⇒ NO MEDIDO`, `vacía ⇒ (ninguna)`).
- **Impacto:** solo cambia la salida para listas **ausentes**. Los artefactos reales declaran siempre esas
  listas ⇒ su render es **byte-idéntico**.

## Superficie

| Fichero | Cambio |
|---|---|
| `apps/web/src/features/operational-console/auto-evidence-report.ts` | P3-2 + P3-3 (clasificación, aviso, `listLabel`, `asStringArrayOrNull`) |
| `apps/web/src/features/operational-console/auto-evidence-report.test.ts` | P3-1 (lee Python) + P3-2 + P3-3 |
| `apps/web/src/features/operational-console/auto-evidence-section.test.tsx` | fixtures coherentes (P3-2) |
| `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py` | P3-3 (`_version_list`) |
| `packages/py/analytics/tests/test_auto_evidence_report.py` | P3-3 + ata las filas del render a las claves canónicas |
| `.github/workflows/frontend-ci.yml` | filtro de ruta del instrumento Python |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | **M179** (perímetro colapsado), **M180** (claves del render desalineadas) |
| `package.json` / `CHANGELOG.md` | bump `1.90.0-beta` → `1.91.0-beta` |

## Verificación prevista

- Frontend: `test` (1323), `typecheck`, `lint` (0 errores), `build`, `contract:check`.
- Python: `pytest packages/py/analytics` (1208), `ruff`, `import-linter`.
- Matriz de mutaciones **M1–M180** (el tramo nuevo, M179/M180, muerde).

## Explícitamente FUERA de alcance

- **La corrida PAPER real** sigue siendo paso operativo del propietario (≥32 ciclos medidos por estrategia);
  el bloqueo por material (`cycle_id` NULL en los fills locales) **no** es un defecto de esta fase.
- **`AUTO-21`**: `P(R>0)`, correlación y current-regime gating siguen fuera.
- **No se añade superficie de producto**: no hay endpoint, ni migración, ni cambios en el freeze.
