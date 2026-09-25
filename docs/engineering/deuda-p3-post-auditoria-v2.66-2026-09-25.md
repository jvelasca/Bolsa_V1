# Deuda P3 post-auditoría `v2.66-beta` (`AUTO-20E`)

> **AsOf:** 2026-09-25 · **Fase auditada:** `v2.66-beta` / `AUTO-20E` (`1.91.0-beta`) · **Tag:** `v2.66-beta` → `6fe7faa8` · **Base:** `v2.65-beta` → `a077c1c6`
> **Veredicto del auditor:** `APROBADO CON OBSERVACIONES` — **0 bloqueantes**; las 9 tesis **sostenidas** y las compuertas re-medidas en verde.
> **Estado:** v2.66 queda **certificada**. Este documento registra **solo** deuda no bloqueante (P3) para la fase siguiente. **No modifica el sello**: el tag `v2.66-beta` permanece en `6fe7faa8`.
> Nace del mismo principio que la fase aplica: **una afirmación solo vale si se puede medir**; si un documento atribuye cobertura de más a una prueba, se corrige en vez de dejarlo pasar.

---

## P3-1 — Sobre-afirmación documental: M180 **no** cubre el contrato TS-vs-Python

**Lo que dicen los documentos.** El `audit-pack §1 #2` afirma que el contrato «puede fallar… prueba manual documentada + mutación **M180**», y el `§4` concluye que *«la matriz lo formaliza como M180»*. El `plan` (§P3-1) dice algo equivalente: *«La misma propiedad se cubre con la mutación M180 (Python)»*.

**Por qué no se sostiene.** **M180** mutila `("shrinkage_calibration", "Shrinkage")` en
`packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py:88` —el **render**—, un fichero que
el test del **frontend** **no lee**. La salida de la matriz lo confirma: M180 enrojece **solo tests Python**
(`test_the_render_labels_every_calibration_question`, `test_the_render_rows_use_the_canonical_calibration_keys`).

**Consecuencia.** La propiedad **TS-vs-Python** (que el test del frontend lea `auto_adaptive_calibration.py` y
caiga si se renombra una clave) **no está en la matriz pytest** —es **vitest**— y su única prueba es la sonda
manual del `§4` (reproducida e **independientemente confirmada** por el auditor). M180 cubre otra cosa:
el atado `_CALIBRATION_ROWS` ↔ `_CALIBRATION_QUESTIONS` **dentro del render Python**.

**Impacto.** **Nulo de código** (la propiedad está cubierta por vitest). Es un **defecto de exactitud
documental** —la misma clase de sobre-afirmación que esta fase dice corregir—.

**Remediación propuesta.** Redactar: *«M180 formaliza el atado `_CALIBRATION_ROWS`↔`_CALIBRATION_QUESTIONS`; el
contrato TS-vs-Python se cubre por **vitest**»*. Corregir la redacción en `plan` y `audit-pack` (fase siguiente),
no re-sellar `v2.66` solo por prosa.

---

## P3-2 — Divergencia TS/Python ante lista no-array (borde malformado)

**Descripción.** Para un valor **escalar** malformado (p. ej. `"requestedStrategyVersions": "orb-a"`):

- **TS** — `asStringArrayOrNull` devuelve `null` si no es array ⇒ `NO MEDIDO`
  (`apps/web/src/features/operational-console/auto-evidence-report.ts:114-117`).
- **Python** — `_version_list` itera el valor ⇒ `"o, r, b, -, a"`
  (`packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py:139-149`).

**Alcance.** Solo alcanzable con un **artefacto importado a mano malformado**: la cadena real siempre emite
**listas** (`auto_material_manifest.py:189-192`). En `v2.65` ambos colapsaban a `(ninguna)`, así que la
**asimetría es nueva** de esta fase (consecuencia de distinguir ausente de vacío).

**Impacto.** **Bajo**, de borde, no bloqueante.

**Remediación propuesta.** En `_version_list`, tratar un valor que **no** sea lista/tupla como ausente
(`NO MEDIDO`), espejo exacto de `asStringArrayOrNull`; añadir test en ambos lados.

---

## Estado del árbol

Comprobado al cierre de la auditoría: **árbol limpio**; el auditor reprodujo la rotura del contrato renombrando
una clave en `auto_adaptive_calibration.py` y la **restauró** (`git diff` **vacío**), y la matriz de mutaciones
dejó los ficheros **byte a byte**. `v2.66-beta` (**`6fe7faa8`**) permanece intacta.

---

## Lo que NO es deuda (para no confundir el cierre)

- **Las 3 P3 de `v2.65` quedan cerradas** (contrato real + filtro de CI, procedencia contradictoria ⇒
  desconocida, ausente ≠ vacío).
- **Freeze, reparto y migración intactos**: ningún fichero congelado en el diff; `auto18-v1`/`auto15-v1` sin
  tocar; Alembic head `046_fill_reference_mid`.
- **La corrida PAPER real** no se ejecuta (bloqueo por **material**, no por código): paso operativo del
  propietario.

---

## Checklist para la fase siguiente

1. [x] P3-1 — corregir la redacción de `plan`/`audit-pack` sobre el alcance de M180 (hecho en `v2.67`).
2. [x] P3-2 — `_version_list` (Python): no-array ⇒ `NO MEDIDO` (espejo de TS) + tests en ambos lados (hecho en `v2.67`, mutación **M181**).

> **RESUELTA en `v2.67-beta` (`AUTO-20F`).** Ver
> [`plan`](./plan-v2-67-auto-20f-cierre-p3-v2.66-2026-09-25.md) · [`audit-pack`](./audit-pack-v2-67-auto-20f-cierre-p3-v2.66-2026-09-25.md).
> Este documento se conserva como **registro histórico**.
