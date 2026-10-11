# Plan — `v2.88.112-beta` / **`P2` — DÍA-D enlazado al ciclo AUTO**: registro durable de la verificación D→hoy

> **Estado:** **EJECUTADO** (2026-10-11) — sello 1 de `P2` implementado y verificado en local; tag `v2.88.112-beta` **por publicar**.
> **Base funcional:** `v2.88.111-beta` (tag anotado `v2.88.111-beta`, objeto `ab02f934` → commit `a530dc93`).
> **Naturaleza:** `Δ motor ≠ 0` **aditivo** · **`Δ decisión = 0`** · **CON migración** (`053_dia_d_cycle_verifications`) · contrato HTTP **ampliado** (`contract:gen`).
> **Origen:** hueco **`P2`** de la [auditoría profundizada](./auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md) (DÍA-D enlazado al ciclo + auditoría por valor). Se entrega **en dos sellos**: este (`v2.88.112-beta`) es el **enlace durable**; el **audit por valor de ESTUDIO** es `v2.88.113-beta`.

---

## 0. Objetivo y criterio de aceptación (falsable)

**Hueco:** la verificación manual D→hoy se lanza hoy **desde** una operación AUTO, pero el vínculo **no sobrevive**: el lanzamiento no transporta el `cycleId` ni la identidad exacta de estrategia, y la persistencia (`research_evidence.summary`) **no tiene columna de ciclo**. El veredicto DÍA-D queda **fragmentado** (declarado ↔ ejecutado · OOS · PAPER).

Cerrar `P2` (sello 1) exige un **registro durable** que enlace, de forma idempotente y auditable, **cada verificación DÍA-D con su ciclo AUTO**, transportando la **identidad exacta** de estrategia (`presetKey`/`version`/`definitionId`), y que ese enlace sea **visible** en el panel de feedback.

**Criterio de aceptación falsable.**
1. `POST /api/auto/dia-d-verifications` registra el enlace; repetir la misma `(cycleId, diaD, endDate, mode)` **actualiza** (no duplica) la fila.
2. `GET /api/auto/dia-d-verifications?cycleId=` devuelve **solo** lo del principal (fail-closed por cuenta: sin cuenta ⇒ `no_account_scope`, nunca datos globales).
3. Un ciclo que no declara estrategia se persiste con la identidad en **`NULL`** («Sin dato todavía»), **jamás** `""`/`0`; un payload sin lo indispensable (`cycleId`/`instrumentId`/`symbol`/`diaD`/`endDate`/`mode`) **no** fabrica enlace.
4. El lanzamiento `useDiaDVerifyLaunch` transporta `cycleId`+`strategyPresetKey`+`strategyVersion`; la sesión y el `archive store` los conservan.
5. El panel DÍA-D pinta `cycles[]` (hoy ignorado) con tri-estado honesto: **«Verificación vinculada»** (registro durable) ≠ **«Sin verificación»** (sin registro) ≠ **«Sin dato todavía»** (ciclo sin `cycleId`).
6. E2E S5: lanzar desde la operación, guardar y **asertar el registro durable enlazado al `cycleId`** (no basta con abrir el laboratorio).
7. El artefacto congelado de `replay-repro` **no** se toca ⇒ `Δ decisión = 0`.

---

## 1. Precedente y reutilización (no duplicar)

- **Identidad exacta H1:** el ciclo sella `cycle.strategyPresetKey` (misma clave que el TOP) — [`auto-operation-strategy.ts`](../../apps/web/src/features/auto/auto-operation-strategy.ts) y evidencia [`v2.88.107`](./evidence/v2.88.107/README.md)/[`v2.88.108`](./evidence/v2.88.108/README.md).
- **Índice por ciclo ya existente:** el artefacto DÍA-D trae `cycles[]` (`cycleId`/`symbol`/`entryDay`/`exitDay`/`strategyVersion`/`realizedR`) en [`dia_d_auto_feedback.py`](../../packages/py/application/src/bolsa_application/dia_d_auto_feedback.py), expuesto read-only en [`auto_dia_d_feedback.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_feedback.py). Hoy el panel **no lo pinta**.
- **Patrón de persistencia durable:** `research_evidence` (entidad + modelo + repositorio + caso de uso) se replica para la tabla nueva.
- **Restricciones del acta `v2.88.111-beta`:** `pointCitable = false` (banda K sin medir), costes **modelados**, `UNKNOWN ≠ 0` (hueco declarado, nunca `0`).

---

## 2. Diseño por fases

### Fase A — Migración y persistencia durable

- Migración [`053_dia_d_cycle_verifications.py`](../../packages/py/infrastructure/alembic/versions/053_dia_d_cycle_verifications.py) `down_revision = "052_top3_opportunities"` (el `053` anterior se retiró en `v2.88.107`; la cadena sigue **lineal**).
- Tabla `dia_d_cycle_verifications`: `id` PK, `cycle_id` (indexado), `account_id`, `instrument_id`, `symbol`, `strategy_preset_key`, `strategy_version`, `strategy_definition_id`, `dia_d`, `end_date`, `mode`, `band`, `result` (JSONB), `research_evidence_id`, `created_at`. Claves de estrategia **nullable** a propósito (ciclos históricos ⇒ «Sin dato todavía», jamás fabricadas); índice único idempotente `(cycle_id, dia_d, end_date, mode)`.
- Entidad [`DiaDCycleVerification`](../../packages/py/domain/src/bolsa_domain/entities/dia_d_cycle_verification.py), modelo [`DiaDCycleVerificationRow`](../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py), repositorio [`SqlAlchemyDiaDCycleVerificationRepository`](../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/dia_d_cycle_verification_repository.py) y casos de uso [`PersistDiaDCycleVerification`/`ListDiaDCycleVerifications`](../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py).
- **Actualizar las 3 constantes `_ALEMBIC_HEAD`** que fijaban `052_top3_opportunities`: `test_discovery_evidence_snapshot_pg.py`, `test_auto_v57_auto16_applied_cost_pg.py`, `test_auto_v88_27_durable_facts_idempotent_pg.py`.

### Fase B — API y contrato

- Rutas nuevas en [`auto_dia_d_verification.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_verification.py): `POST /api/auto/dia-d-verifications` (registra el enlace, idempotente) y `GET /api/auto/dia-d-verifications?cycleId=` (fail-closed por cuenta, como el resto del router).
- DTOs con política de huecos (`None`, nunca `""`/`0`). `contract:gen` regenera `openapi.json`/`schema.d.ts`; `contract:check` verde.

### Fase C — UI: transportar y mostrar el enlace

- [`use-dia-d-verify-launch.ts`](../../apps/web/src/features/trading/use-dia-d-verify-launch.ts): `DiaDVerifyLaunchArgs` gana `cycleId?`, `strategyPresetKey?`, `strategyVersion?` y los pasa a `enterSession`.
- [`dia-d-trading-session-store.ts`](../../apps/web/src/stores/dia-d-trading-session-store.ts): la sesión persiste `cycleId`/`strategyPresetKey`/`strategyVersion`.
- [`auto-operation-story-panel.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx): `startDiaDVerification` pasa `selected.cycleId` + `selected.strategyPresetKey` + `selected.strategyVersion`.
- [`trading-dia-d-replay-panel.tsx`](../../apps/web/src/features/trading/trading-dia-d-replay-panel.tsx): el flujo de guardado incluye `cycleId`+identidad y llama a la nueva API; [`dia-d-evidence-archive-store.ts`](../../apps/web/src/stores/dia-d-evidence-archive-store.ts) guarda `cycleId` en el ítem.
- [`dia-d-auto-feedback-cycles.tsx`](../../apps/web/src/features/auto-monitor/dia-d-auto-feedback-cycles.tsx) + [`dia-d-cycle-verification-status.ts`](../../apps/web/src/features/auto-monitor/dia-d-cycle-verification-status.ts): **pintar `cycles[]`** con tri-estado honesto por ciclo.

### Fase D — Pruebas

- Python: migración up/down; round-trip del repositorio (PG); caso de uso; ruta POST/GET con y sin `cycleId` (sin `cycleId` ⇒ no se fabrica enlace).
- Vitest: el launch transporta `cycleId`; el store lo persiste; el panel pinta `cycles[]` con los 3 estados.
- E2E: ampliar [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) — lanzar desde la operación, guardar y **asertar el registro durable enlazado al `cycleId`**.

---

## 3. Restricción DURA — el sello `replay-repro` NO se puede mover

`replay-repro` regenera `replay-oos-durable-v2.88.7.json` desde el fixture y **asserta su `SHA-256` byte a byte**. El registro durable es una **tabla nueva** y una **costura UI/HTTP**; **no** entra en el payload del replay ⇒ el artefacto congelado **no** puede moverse (`Δ decisión = 0`).

---

## 4. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Migración rompe la cadena lineal | `down_revision = "052_top3_opportunities"`; roundtrip verificado; 3 `_ALEMBIC_HEAD` actualizadas |
| Fabricar identidad en ciclos históricos | Claves **nullable**; `UNKNOWN ≠ 0`; hueco declarado («Sin dato todavía») |
| Falsa confirmación / doble contabilización | El registro es de **enlace y resultado declarado**; **no** emite `CONFIRMED` ni afirma rentabilidad |
| Fuga entre cuentas | Escritura/lectura acotadas a la cuenta del principal; sin cuenta ⇒ `no_account_scope`/`400` |
| Regresión del sello congelado | El sello 1 **no** entra en el payload del replay |

---

## 5. Entrega, gates y sello

- `docs/engineering/evidence/v2.88.112/README.md` (formato del de `v2.88.111`).
- **Bump** `package.json` → `2.11.112-beta` y `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97` (guardián [`test_dia_d_bump_guard.py`](../../apps/api-python/tests/test_dia_d_bump_guard.py)).
- CI verde en [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml): `python`, `lifecycle-pg` (Alembic + golden, con `DIA_D_CYCLE_VERIFICATION_PG_REQUIRED=1`), `frontend` (`contract:check`), `playwright-integrated-auto-s5`, `replay-repro` = `REPRODUCIDO`, `certify`.
- Tag anotado **`v2.88.112-beta`** (unsigned, limitación de certificación) + cita POST-TAG.
