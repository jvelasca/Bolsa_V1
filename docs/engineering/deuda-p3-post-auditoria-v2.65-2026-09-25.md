# Deuda P3 post-auditoría `v2.65-beta` (AUTO-20D)

> **AsOf:** 2026-09-25 · **Fase auditada:** `v2.65-beta` / `AUTO-20D` (`1.90.0-beta`) · **Tag:** `v2.65-beta` → `a077c1c6` · **Base:** `v2.64-beta` → `e605f475`
> **Veredicto del auditor:** `APROBADO CON OBSERVACIONES` — **0 bloqueantes**.
> **Estado:** v2.65 queda **certificada**. Este documento registra **solo** deuda no bloqueante (P3) para que entre en la fase siguiente (`v2.66`). **No modifica el sello**: el tag `v2.65-beta` permanece en `a077c1c6`.
>
> **Actualización 2026-09-25 — RESUELTA en `v2.66-beta` (`AUTO-20E`).** Las 3 P3 y los dos puntos de higiene
> quedan cerrados en la fase siguiente: ver [`plan`](./plan-v2-66-auto-20e-hardening-procedencia-2026-09-25.md) ·
> [`audit-pack`](./audit-pack-v2-66-auto-20e-hardening-procedencia-2026-09-25.md). Este documento se conserva
> como **registro histórico** de la deuda tal y como se levantó.

## Por qué existe este documento

La auditoría externa de `v2.65-beta` verificó las 6 tesis de la fase contra el código sellado y las declaró **sostenidas**; re-midió las compuertas en verde (**1320 passed**, `typecheck` OK, `lint` **0 errores / 23 warnings** — ninguno en ficheros de la fase) y confirmó el freeze y la ausencia de migración. Levantó además **3 observaciones P3 no bloqueantes**. Una de ellas (P3-1) implica que **una afirmación del plan y del audit-pack estaba sobredimensionada**, por lo que conviene dejarla por escrito en lugar de perderla en el chat.

---

## P3-1 — El «contrato de claves» es TS-vs-TS, no TS-vs-Python

**Afirmación sobredimensionada.** El plan §4 y el audit-pack §1 #13 sostienen que *«el test de contrato de claves cae si Python cambia una clave»*. **No se sostiene tal cual.**

**Evidencia.**
- El test `pins the calibration keys emitted by the Python instrument` compara la constante TS contra un **array literal escrito en el propio test**: `apps/web/src/features/operational-console/auto-evidence-report.test.ts:252-263`.
- El test **no lee Python** ni cruza con `auto_adaptive_calibration.py`; `contract:check` solo valida OpenAPI / `schema.d.ts`, no estas claves.
- Las claves **sí coinciden hoy**: Python las emite en `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py:116-121` y el TS las espeja en `apps/web/src/features/operational-console/auto-evidence-report.ts:37-44`.
- El mapeo etiqueta→clave es idéntico al del render Python (`auto_evidence_report.py:85-95`); solo cambia el **orden** de las filas (el TS refleja el orden del render, no el de emisión), lo cual es inocuo porque la búsqueda es por clave.

**Impacto real.** **Nulo en seguridad del veredicto**: una clave ausente cae a `INCONCLUSIVE`, que es fail-safe. El defecto es de **exactitud documental** (una prueba que no prueba lo que dice), no de código. Riesgo futuro: si Python renombrara/eliminara una clave, el test seguiría verde y la UI mostraría `INCONCLUSIVE` sin que ninguna compuerta avisara del desajuste.

**Remediación propuesta para `v2.66`.** Que el test lea de verdad las claves del instrumento Python (parseo del módulo o un export JSON intermedio) de modo que un renombrado en `auto_adaptive_calibration.py` **rompa** la compuerta del frontend. Mientras no exista, **corregir la redacción** del plan/audit-pack: llamarlo *espejo pinneado de TS contra TS*, no «contrato con Python».

**Nota de sello.** La corrección de redacción afecta a documentos ya sellados en el tag `v2.65-beta`; se asume como deuda documental y se reescribe al abrir `v2.66` (no se re-sella `v2.65` solo por prosa).

---

## P3-2 — Precedencia de `materialOrigin` sin chequeo de coherencia

**Descripción.** `classifyEvidenceSource` toma `artifact.materialOrigin ?? artifact.material?.materialOrigin` (`apps/web/src/features/operational-console/auto-evidence-report.ts:204-205`). Un artefacto importado **a mano** que declare `materialOrigin: "paper_real"` en la raíz y `material.materialOrigin: "synthetic_fixture"` se clasificaría como `PAPER REAL`; `integrityWarnings` (`:431-468`) **no** avisa de esa discrepancia.

**Impacto real.** **Bajo.** En la cadena real ambos valores son el mismo (`auto_replay_battery.py:175-188` + `auto_material_manifest.py:190-195`) y el propio badge declara que la procedencia es **autodeclarada**. Es un endurecimiento menor, no un defecto.

**Remediación propuesta para `v2.66`.** Si raíz y `material.materialOrigin` discrepan, añadir un `integrityWarning` (o forzar `desconocido`). Decidir la política: avisar y mantener, o avisar y degradar.

---

## P3-3 — Listas de perímetro ausentes se muestran `(ninguna)` en vez de `NO MEDIDO`

**Descripción.** `perimeterRows` marca `inconclusive: false` fijo para «Versiones pedidas» / «observadas» (`apps/web/src/features/operational-console/auto-evidence-report.ts:368-378`), así que un campo **ausente** y una lista **vacía** se ven igual (`(ninguna)`).

**Impacto real.** **Muy bajo.** Es **coherente con el render Python** (`auto_evidence_report.py:144-146`), por lo que **no rompe el invariante** de la fase. Se anota como **asimetría de honestidad** respecto a los conteos (donde `null` ≠ `0`): aquí `ausente` ≠ `[]` no se distingue.

**Remediación propuesta para `v2.66`.** Aplicar la misma regla de honestidad que a los conteos: si la lista es `null`/ausente → `NO MEDIDO`; si es `[]` → `(ninguna)`. Cambiarlo **en TS y en el render Python a la vez** para no reintroducir divergencia (y verificar que el render del exportador no queda desincronizado).

---

## Estado del árbol de trabajo (no deuda de la fase)

Comprobado durante el cierre de la auditoría:

- **Los 3 ficheros Python que figuraban como modificados NO tienen cambios de contenido.** `git diff --numstat` sale **vacío**: son artefactos de fin de línea (CRLF en el *working copy* vs LF en el índice, por `core.autocrlf=true` + atributo `eol=lf`). No hay nada que commitear; se normalizan con un `git add --renormalize`.
- **`governor.json` (raíz) es un artefacto generado huérfano.** Nunca ha estado trackeado en ninguna rama (`git log --all -- governor.json` vacío), no está en `.gitignore` y **ningún código Python/TS/script lo referencia** (solo aparece en prosa de docs). Es ruido: **no debe commitearse**; se recomienda añadirlo a `.gitignore` o borrarlo.

---

## Lo que NO es deuda (para no confundir el cierre)

- **Freeze intacto:** `git diff v2.64-beta v2.65-beta -- packages/py apps/api-python` → vacío; los 6 ficheros congelados (`auto_adaptive.py`, `auto_adaptive_data_gate.py`, `auto_simulation_worker.py`, `auto_adaptive_journal.py`, `auto_adaptive_replay.py`, `v2_43_governor_evidence.py`) y `governor.json` del freeze → sin cambios.
- **Sin migración:** Alembic head sigue en `046_fill_reference_mid` (no existe `047_*`).
- **La corrida PAPER real (AUTO-20D) no se ejecuta** y **no** es un defecto de la fase: el PostgreSQL local tiene `sim_fill_finance_context` con `628 fills` y `cycle_id` **NULL en todos** ⇒ el exportador bloquearía con `exit 2`. El estado real es `SIN MATERIAL · NO MEDIDO` y **la UI lo declara correctamente**. El bloqueo es por **material, no por código**.

---

## Checklist para `v2.66` (entrada sugerida)

1. [x] P3-1 — hacer que el test de claves **lea Python** de verdad; corregir la redacción de plan/audit-pack.
2. [x] P3-2 — decidir política ante `materialOrigin` raíz ≠ `material.materialOrigin` y avisar.
3. [x] P3-3 — distinguir `ausente` de `[]` en perímetro, **en TS y en Python a la vez**.
4. [x] Higiene — `git add --renormalize` de los 3 Python y decidir el destino de `governor.json` (`.gitignore`).
