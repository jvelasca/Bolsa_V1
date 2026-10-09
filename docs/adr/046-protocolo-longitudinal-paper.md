# ADR-046 — Protocolo longitudinal PAPER (serie de evidencia + promoción humana)

**Estado:** Accepted
**Fecha:** 2026-10-09
**Contexto:** el contrato PAPER ([`contrato-evidencia-paper-confirmacion-2026-10-09.md`](../engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md)) evalúa **siete criterios** sobre el material durable. Hasta `v2.88.102`, esa evidencia se recalculaba **on-demand** con topes declarados (`500` ciclos / `5000` fills) en `read_paper_evidence` y **no se acumulaba**: era imposible observar la *evolución* de la evidencia (¿los criterios se van cumpliendo según crece el historial?). El `verdict` es el literal reservado `NO_CONFIRMED`: no existe rama que emita `CONFIRMED`.

**Depende de:** [ADR-029](./029-order-proposal-decision-journal.md) (spine append-only) · `PAPER-2`/`PAPER-2.1` (`v2.88.99`/`v2.88.100`) · evidencia `v2.88.102`.

---

## 1. Decisión

Se añade un **protocolo longitudinal** que materializa una **serie de fotos durables** de la evidencia PAPER, sin cambiar el contrato de veredicto:

- **Snapshot durable append-only.** Cada foto es una fila del spine `decision_journal_entries` con `event_type = auto_paper_evidence_snapshot`, construida por `build_paper_evidence_snapshot_entry` (pura). La identidad natural es `(cuenta, día)` vía `dedupe_key`: **una foto por cuenta y día**; un reintento no duplica y **no pisa** la primera (ON CONFLICT DO NOTHING).
- **Serie de lectura pura.** `paper_evidence_series` reconstruye la serie ordenada (más antigua → más nueva) desde las filas durables; no agrega ni interpreta.
- **Superficies:** `GET /api/auto/paper-evidence/history` (read-only, acotado por cuenta) sirve la serie; `POST /api/auto/paper-evidence/snapshot` **escribe** la foto del día (driver del protocolo).
- **Sin migración.** La serie vive en el spine JSONB (ADR-029): no hay tabla nueva. Si a escala hace falta un índice de expresión, esa será una decisión medida, no un cambio de identidad.

## 2. La regla dura: `CONFIRMED` es humano

- El `verdict` de TODO snapshot es **siempre** el literal `NO_CONFIRMED`. Ningún camino del protocolo lo promueve.
- `GET /api/auto/paper-evidence` sigue declarando `readOnly = true` y **no escribe**. La escritura vive solo en el `POST` explícito: mezclar lectura y escritura rompería el contrato.
- La promoción a `CONFIRMED` es una **decisión humana** con evidencia firmada (fuera de alcance aquí). Este protocolo **observa**; no promueve.

## 3. Invariantes (`UNKNOWN ≠ 0`)

- Un snapshot sin cuenta atribuible devuelve `None` (no se finge). La ruta `GET .../history` sin cuenta visible devuelve serie vacía con `no_account_scope`.
- Un campo no medido viaja `null`; jamás un `0` de relleno. `fillsTotalForAccount` puede ser `None`.
- La ventana truncada se declara (`fillsWindowFull = false`) en cada foto: una foto sobre material parcial **no** se presenta como el universo completo.

## 4. Alternativas consideradas

- **Tabla dedicada + migración Alembic.** Rechazada: el spine append-only ya es el sustrato durable canónico (ADR-029) y una tabla paralela duplicaría autoridad. Si el volumen lo exigiera, se reconsideraría con medición.
- **Recalcular la serie on-demand sin persistir.** Rechazada: sin acumulación no hay serie; el punto del protocolo es conservar la evolución a lo largo del tiempo.
- **Escribir el snapshot dentro del GET read-only.** Rechazada: contradice `readOnly = true` y convierte una lectura en una escritura.

## 5. Consecuencias

- La evidencia PAPER deja de ser una foto efímera: pasa a tener **historial** durable por cuenta y día.
- Coste acotado: una fila por cuenta y día (idempotente).
- El veredicto sigue siendo `NO_CONFIRMED` en todas las superficies; la separación observación/promoción queda explícita.

## 6. Verificación

- Tests puros (`packages/py/application/tests/test_paper_evidence_protocol.py`): identidad determinista, `NO_CONFIRMED` literal, serie ordenada, ausencia de cuenta ⇒ `None`, truncación declarada.
- Tests de ruta (`apps/api-python/tests/test_auto_paper_evidence_route.py`): `GET .../history` ordena y aísla por cuenta, `POST .../snapshot` escribe una fila por día (idempotente) y sin cuenta no escribe.
- `contract:check` en verde tras regenerar `schema.d.ts` con las rutas nuevas.
- El `verdict` reservado se comprueba por test: ninguna foto emite `CONFIRMED`.

## 7. Auditoría durable como política (ventana PAPER)

El protocolo **acumula** hechos durables: sin escritura de auditoría no hay serie. Por eso la política
operativa de la ventana PAPER enciende `AUTO_OPERATIONAL_AUDIT=1` en el **entorno del proceso** forward
(ya declarado en `scripts/lib/window-forward.mjs` y en el runbook de la ventana), de modo que
`auto_entry_order`, `auto_protection_event`, `auto_cycle_settlement`, `auto_position_materialized` y —con
este ADR— `auto_paper_evidence_snapshot` se sellan de forma continua.

El **default del código sigue OFF**: encenderlo por defecto cambiaría el comportamiento de todos los
procesos y rompería la garantía `Δ motor = 0` que los sellos anteriores certifican. La política vive en la
**inyección de entorno de la ventana**, no en una constante de módulo. La captura del snapshot es
idempotente por `(cuenta, día)`, así que la frecuencia del driver no altera la serie.

## 8. Drivers de la captura (manual + periódico)

La serie necesita que **alguien** escriba la foto del día. Hay dos drivers, ambos explícitos:

- **Manual:** `POST /api/auto/paper-evidence/snapshot` (§1). Útil para forzar una foto puntual.
- **Periódico:** `paper_evidence_snapshot_worker` (`apps/api-python/src/bolsa_api/background/`), registrado
  en el proceso de crons (`workers/scheduler_worker.py`). Enumera las cuentas del owner y captura **una**
  foto por cuenta por tick. Es **off-by-default** (`PAPER_EVIDENCE_SNAPSHOT_ENABLED=false`): con el flag
  apagado no se construye tarea ⇒ no-op, `Δ motor = 0`. Se enciende como **política de la ventana PAPER**
  (`PAPER_EVIDENCE_SNAPSHOT=1`), junto a `AUTO_OPERATIONAL_AUDIT=1`.

Reglas del worker, alineadas con §2/§3:

- **Aditivo.** Compone la evidencia con `read_paper_evidence` (solo `SELECT`) y **solo** escribe la traza
  del protocolo; nunca toca `sim_auto_positions`, reservas, órdenes ni la decisión.
- **Fail-closed por cuenta.** Una cuenta sin identidad no se finge; el fallo de una cuenta **no** tumba el
  tick de las demás (transacción por cuenta).
- **Sin promoción.** El `verdict` sigue siendo el literal `NO_CONFIRMED` (lo impone `build_paper_evidence_snapshot_entry`).
