# Audit-pack — `v2.65-beta` (`AUTO-20D` · UI de procedencia del AUTO EVIDENCE REPORT)

**Versión:** `1.90.0-beta` · **Rótulo:** `AUTO-20D` / `V2.65` · **Fecha:** 2026-09-25 · **Base de
auditoría:** cierre de `v2.64-beta`.

**Plan:** [plan-v2-65](./plan-v2-65-ui-procedencia-auto-evidence-2026-09-25.md) ·
**Relevo:** [traspaso post-v2.65](./traspaso-relevo-post-v2.65-ui-procedencia-auto-evidence-2026-09-25.md) ·
    10|**Origen:** auditoría de `v2.64-beta` (punto 14) · **Pack previo:**
[audit-pack v2.64](./audit-pack-v2-64-auto-20c-paper-virtual-2026-09-25.md).

## §1 — Qué se construyó (afirmación → código → test)

| # | Afirmación | Código | Test que la sostiene |
|---|---|---|---|
| 1 | Un esquema ajeno se **rechaza con motivo** y no se persiste | `parseAutoEvidenceArtifact` | `rejects a foreign schema with a declared reason`, `rejects a foreign schema without persisting` |
| 2 | El informe viaja **verbatim** (no se reinterpreta) | `parseAutoEvidenceArtifact` | `keeps the report verbatim (no reinterpretation)` |
| 3 | `paper_real` es la **única** procedencia base de decisión | `classifyEvidenceSource` | `paper_real is decision-safe` |
| 4 | Un **fixture** no puede leerse como real | idem + `OpsAutoEvidenceSection` | `synthetic fixture is NOT decision-safe`, `makes a synthetic fixture impossible to misread` |
    20|| 5 | Sin artefacto / sin material ⇒ `SIN MATERIAL · NO MEDIDO` | idem | `no artifact is sin_material`, `artifact with null material is sin_material`, `starts as SIN MATERIAL · NO MEDIDO` |
| 6 | Una procedencia **desconocida** no se degrada a `paper_real` | idem | `unknown origin never degrades to paper_real` |
| 7 | Un conteo ausente es `NO MEDIDO`, **no** `0` | `buildEvidenceView` | `distinguishes NO MEDIDO from a legitimate 0` |
| 8 | Un veredicto ausente ⇒ `INCONCLUSIVE` (nunca inventado) | idem | `maps missing verdicts to INCONCLUSIVE, never invents one` |
| 9 | Los veredictos y el WFE se muestran **tal cual** | idem | `maps supported/not_supported and formats the WFE` |
| 10 | El render declara `AUTO-21` fuera de alcance y el reparto congelado | idem | `declares AUTO-21 out of scope and the allocation freeze` |
    30|| 11 | El perímetro se expone **sin** tocar el universo medido | idem | `exposes the perimeter without touching the measured universe` |
| 12 | La procedencia incoherente (dinero real / venue no paper / lectura saturada) **avisa** | `integrityWarnings` | `flags real money and non-virtual execution`, `flags a non-paper venue and saturated risk read`, `flags a real-money artifact with an integrity warning` |
| 13 | El contrato de claves con Python está **pinneado** | `AUTO_EVIDENCE_CALIBRATION_KEYS` | `pins the calibration keys emitted by the Python instrument` |
| 14 | El archivo local dedupe por huella y respeta el cap | `auto-evidence-archive-store` | `saves and exposes the latest artifact`, `dedupes by schema+origin+fingerprint and keeps the newest`, `caps the archive`, `removes by id and clears` |
| 15 | La sección se monta en la cabina y es visible en primer nivel | `operational-console-page.tsx` | `surfaces exceptions first; technical sections in details` |

## §2 — Superficie medida (compuertas)
    40|
| Compuerta | Comando | Resultado |
|---|---|---|
| Tests web | `pnpm --filter @bolsa/web test` | **1320 passed** (232 ficheros); **30 nuevos** (report 19 + sección 7 + store 4) |
| Tipos | `pnpm --filter @bolsa/web typecheck` | **OK** (`tsc -b --noEmit`) |
| Lint | `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes, ninguno en ficheros de la fase) |

**Freeze / Python intactos:** el diff de la fase **no toca** `packages/py` ni ningún fichero congelado
(`auto_adaptive.py`, `auto_adaptive_data_gate.py`, `auto_simulation_worker.py`, `auto_adaptive_journal.py`,
    50|`auto_adaptive_replay.py`, `v2_43_governor_evidence.py`, `governor.json`). **Sin migración** (head
`046_fill_reference_mid`).

## §3 — Superficie de cambio

Solo frontend (`apps/web`), **+3 ficheros** de producción y **+3** de test:

- `apps/web/src/features/operational-console/auto-evidence-report.ts` (**nuevo**, puro) — parser,
  clasificación de procedencia, vista verbatim, avisos de integridad.
- `apps/web/src/stores/auto-evidence-archive-store.ts` (**nuevo**) — archivo local persistido.
- `apps/web/src/features/operational-console/auto-evidence-section.tsx` (**nuevo**) — badge + bloques +
    60|  import manual.
- `auto-evidence-report.test.ts`, `auto-evidence-section.test.tsx`, `auto-evidence-archive-store.test.ts`
  (**nuevos**).
- `operational-console-page.tsx` y `operational-console-page.test.tsx` (**modificados**, +1 sección).

## §4 — Equivalente a mutación (matriz TS)

No hay productor Python nuevo que mutar; la cobertura equivalente vive en los tests:

| Escenario | Rojo en |
|---|---|
| Un fixture mostrado como `PAPER REAL` | `synthetic fixture is NOT decision-safe` (+1) |
| Un `null` impreso como `0` | `distinguishes NO MEDIDO from a legitimate 0` |
| Un veredicto ausente tratado como `SUPPORTED` | `maps missing verdicts to INCONCLUSIVE, never invents one` |
    70|| Un artefacto de otra venue aceptado en silencio | `flags a non-paper venue and saturated risk read` |
| Un esquema ajeno persistido | `rejects a foreign schema without persisting` |
| El schema sin las 6 claves de calibración | `pins the calibration keys emitted by the Python instrument` |

## §5 — Hallazgo y límites declarados

1. **La corrida AUTO-20D real NO se ejecuta** (y no se fabrica): en el PostgreSQL local
   `sim_fill_finance_context` tiene **628 fills con `cycle_id` NULL en todos** (`fills_with_cycle = 0`) ⇒ el
    80|   exportador bloquearía con `exit 2`. El estado real es **SIN MATERIAL · NO MEDIDO**, que la UI muestra
   explícitamente. Bloqueo por **material**, no por código.
2. La procedencia es **autodeclarada**: la huella sella el universo medido, **no** es prueba criptográfica
   de origen (declarado en la propia sección).
3. **Import manual**: sin endpoint ni migración; el artefacto se sube o se pega.
4. `P(R>0)`, correlación entre estrategias y current-regime gating siguen fuera (AUTO-21).

## §6 — Veredicto de la fase

La UI de procedencia cierra el punto 14 de la auditoría de `v2.64`: la procedencia (`PAPER REAL` /
`FIXTURE SINTÉTICO` / `SIN MATERIAL` / `DESCONOCIDA`) es un **badge prominente**, no un campo escondido en un
    90|JSON. Sigue sin moverse el reparto (`auto18-v1`) y sin declararse ningún edge: esta fase **presenta** la
evidencia, no la amplía.
