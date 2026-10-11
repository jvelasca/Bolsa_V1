# Evidencia — `v2.88.112-beta` / **`P2` — DÍA-D enlazado al ciclo AUTO**: el registro durable que une la verificación D→hoy con su ciclo

> **Base funcional:** `v2.88.111-beta` (commit `a530dc93`). Abre el hueco **`P2`** (DÍA-D enlazado al ciclo + auditoría por valor) de la [auditoría profundizada](../../auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md).
> **Naturaleza:** sello **aditivo**. `Δ motor ≠ 0` (tabla nueva, repositorio, caso de uso, rutas y costura UI) pero **`Δ decisión = 0`**: sin motor de decisión, sin umbrales, sin reparto ni `TOP_N`/régimen/selección/protección. **CON migración** (`053_dia_d_cycle_verifications`) y **contrato ampliado** (`contract:gen`).
> **Alcance:** **sello 1 de `P2`** — el **enlace durable**. La **composición por valor de ESTUDIO** (estrategia + porqué + señal + resultado) es el **sello 2** (`v2.88.113-beta`).
> **Plan:** [`plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md`](../../plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md).

---

## 1. Qué cierra (el hueco de `P2`)

La verificación manual D→hoy se lanza **desde** una operación AUTO, pero hasta ahora el vínculo **no sobrevivía** a la sesión: el lanzamiento ([`use-dia-d-verify-launch.ts`](../../../../apps/web/src/features/trading/use-dia-d-verify-launch.ts)) **no** transportaba el `cycleId` ni la identidad exacta de estrategia, y la persistencia (`POST /research/dia-d-session-evidence` → `research_evidence.summary`) **no** tenía columna de ciclo. El veredicto DÍA-D quedaba **fragmentado** (declarado ↔ ejecutado · OOS · PAPER) y el índice por ciclo `cycles[]` del artefacto de feedback (`cycleId`/`symbol`/`entryDay`/`exitDay`/`strategyVersion`/`realizedR`) **no se pintaba**. Este sello incorpora el **registro durable** que enlaza cada verificación con su ciclo y lo hace **visible**.

## 2. Fase A — Migración `053` y persistencia durable

[`053_dia_d_cycle_verifications.py`](../../../../packages/py/infrastructure/alembic/versions/053_dia_d_cycle_verifications.py) (`down_revision = "052_top3_opportunities"`, cadena **lineal**) crea la tabla `dia_d_cycle_verifications`:

- Columnas: `id` PK, `cycle_id` (**indexado**), `account_id`, `instrument_id`, `symbol`, `strategy_preset_key`, `strategy_version`, `strategy_definition_id`, `dia_d`, `end_date`, `mode`, `band`, `result` (JSONB), `research_evidence_id`, `created_at`.
- **Unique idempotente** `(cycle_id, dia_d, end_date, mode)` (`dia_d_cycle_verifications_cycle_key`) + índice `dia_d_cycle_verifications_cycle_id_idx`.
- Claves de estrategia **nullable** a propósito: un ciclo histórico que no declara su estrategia se persiste **en el hueco** («Sin dato todavía»), sin backfill forzado.

Entidad de dominio [`DiaDCycleVerification`](../../../../packages/py/domain/src/bolsa_domain/entities/dia_d_cycle_verification.py), modelo [`DiaDCycleVerificationRow`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py), repositorio [`SqlAlchemyDiaDCycleVerificationRepository`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/dia_d_cycle_verification_repository.py) (`upsert` idempotente + `list_verifications` acotado por cuenta/ciclo + `get_by_id`) y casos de uso [`PersistDiaDCycleVerification`/`ListDiaDCycleVerifications`](../../../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py) + helper PURO [`build_dia_d_cycle_verification_draft`](../../../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py) (sin lo indispensable ⇒ draft `None`: **no** se fabrica enlace).

**Cadena Alembic.** Se actualizan las **3 constantes `_ALEMBIC_HEAD`** que fijaban `052_top3_opportunities` → `053_dia_d_cycle_verifications`: [`test_discovery_evidence_snapshot_pg.py`](../../../../apps/api-python/tests/test_discovery_evidence_snapshot_pg.py), [`test_auto_v57_auto16_applied_cost_pg.py`](../../../../apps/api-python/tests/test_auto_v57_auto16_applied_cost_pg.py) y [`test_auto_v88_27_durable_facts_idempotent_pg.py`](../../../../apps/api-python/tests/test_auto_v88_27_durable_facts_idempotent_pg.py).

## 3. Fase B — API y contrato (`POST`/`GET` fail-closed por cuenta)

[`auto_dia_d_verification.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_verification.py) registra el router en [`router.py`](../../../../apps/api-python/src/bolsa_api/api/v1/router.py):

- **`POST /api/auto/dia-d-verifications`** — registra (idempotente) el enlace: `cycleId`/`instrumentId`/`symbol`/`diaD`/`endDate`/`mode` obligatorios + identidad exacta (`strategyPresetKey`/`strategyVersion`/`strategyDefinitionId`, `band`, `result`, `researchEvidenceId`) **opcional**. Sin cuenta del principal ⇒ **`400`** (fail-closed); payload sin lo indispensable ⇒ **`400`** (no se fabrica).
- **`GET /api/auto/dia-d-verifications?cycleId=`** — lista lo del principal, acotado a un ciclo si se pide. Sin cuenta ⇒ `data: []`, `notes: ["no_account_scope"]` (nunca datos globales).
- DTOs con **política de huecos** (`None`, nunca `""`/`0`); dependencia [`get_dia_d_cycle_verification_repository`](../../../../apps/api-python/src/bolsa_api/api/dependencies.py).
- `contract:gen` regenera [`openapi.json`](../../../../apps/web/api/openapi.json)/[`schema.d.ts`](../../../../apps/web/src/api/schema.d.ts); `contract:check` **OK**. Tipos compartidos en [`dia-d-verification-api.ts`](../../../../packages/shared/src/dia-d-verification-api.ts); cliente en [`api.ts`](../../../../apps/web/src/lib/api.ts) (`persistDiaDCycleVerification`/`listDiaDCycleVerifications`).

## 4. Fase C — Transporte y superficie UI

**Transporte (el `cycleId` y la identidad viajan con la sesión):**

- [`use-dia-d-verify-launch.ts`](../../../../apps/web/src/features/trading/use-dia-d-verify-launch.ts): `DiaDVerifyLaunchArgs` gana `cycleId?`/`strategyPresetKey?`/`strategyVersion?` y los pasa a `enterSession`.
- [`dia-d-trading-session-store.ts`](../../../../apps/web/src/stores/dia-d-trading-session-store.ts): la sesión persiste `cycleId`/`strategyPresetKey`/`strategyVersion`.
- [`auto-operation-story-panel.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx): `startDiaDVerification` pasa `selected.cycleId` + `selected.strategyPresetKey` + `selected.strategyVersion`.
- [`trading-dia-d-replay-panel.tsx`](../../../../apps/web/src/features/trading/trading-dia-d-replay-panel.tsx): al guardar la evidencia se llama a la API nueva (si hay `session.cycleId`); el [`dia-d-evidence-archive-store.ts`](../../../../apps/web/src/stores/dia-d-evidence-archive-store.ts) guarda `cycleId` en el ítem.

**Superficie (el panel pinta `cycles[]` con tri-estado honesto):**

- [`dia-d-cycle-verification-status.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-cycle-verification-status.ts): helper PURO `resolveDiaDCycleVerificationState` → `linked` | `not-verified` | `unknown`.
- [`dia-d-auto-feedback-cycles.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-feedback-cycles.tsx): tabla de los ciclos de la ventana con las columnas `Ciclo`/`Valor`/`Días`/`Estrategia`/`R`/`Verificación DÍA-D`, integrada en [`dia-d-auto-feedback-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.tsx) (hook [`use-auto-dia-d-feedback.ts`](../../../../apps/web/src/features/auto-monitor/use-auto-dia-d-feedback.ts)).

**Tri-estado (nunca se finge):** **«Verificación vinculada»** solo si existe el registro durable que enlaza el ciclo; **«Sin verificación»** si no lo hay; **«Sin dato todavía»** si el ciclo no declara `cycleId` (o falló la lectura ⇒ «No disponible»; en carga ⇒ «Comprobando…»).

## 5. Fase D — Pruebas

- **PG (gated)** [`test_dia_d_cycle_verification_pg.py`](../../../../apps/api-python/tests/test_dia_d_cycle_verification_pg.py): tabla/índices en head `053`; `upsert` **idempotente** por `(cycle_id, dia_d, end_date, mode)` (misma fila, última gana); huecos persistidos como **`NULL`** (nunca `""`); `list_verifications` acota por **cuenta y ciclo**; roundtrip `downgrade→upgrade` de la 053.
- **Ruta (hermética)** [`test_auto_dia_d_verification_route.py`](../../../../apps/api-python/tests/test_auto_dia_d_verification_route.py): persiste con identidad exacta; declara huecos sin fabricar; sin cuenta ⇒ `POST 400` / `GET` vacío con `no_account_scope`; payload incompleto ⇒ `400`; listado por ciclo y del principal.
- **Aplicación** [`test_dia_d_cycle_verification.py`](../../../../packages/py/application/tests/test_dia_d_cycle_verification.py): draft (completo / huecos / falta lo indispensable / `result` no-dict) + casos de uso.
- **Vitest:** [`dia-d-cycle-verification-status.test.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-cycle-verification-status.test.ts) (tri-estado) · [`dia-d-auto-feedback-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-feedback-panel.test.tsx) (los 3 estados pintados) · [`dia-d-trading-session-store.test.ts`](../../../../apps/web/src/stores/dia-d-trading-session-store.test.ts) (el store conserva `cycleId`+identidad).
- **E2E ampliado** [`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`](../../../../apps/web/e2e/gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts) → nuevo **`GP-V288-S5-04`**: parte del **no-residuo** (`total == 0`), lanza desde la operación, guarda y **aserta el registro durable enlazado al `cycleId`** (no basta con abrir el laboratorio); un hueco de precondición es **FALLO** si `E2E_S5_REQUIRED=1`.

## 6. Bump, migración y contrato

`2.11.111-beta` → **`2.11.112-beta`**: `package.json` + `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97`, guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**. **CON migración** (head `053_dia_d_cycle_verifications`); **contrato ampliado** (`contract:gen`/`contract:check` verde). CI: el job `lifecycle-pg` gana `DIA_D_CYCLE_VERIFICATION_PG_REQUIRED: '1'` y registra el fichero PG nuevo.

## 7. Verificación (local)

- `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed**.
- `lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken**.
- `mypy` (las 5 raíces `src`, `--follow-imports=silent`) → **549 source files, no issues**.
- `pytest packages/py/application/tests -q` → **2668 passed**.
- `pnpm --filter @bolsa/shared build` + web: `typecheck` **OK** · `vitest` → **295 files / 2087 passed**.
- Guardianes + rutas DÍA-D + PG (`test_dia_d_bump_guard` + `test_ci_test_selection_census` + `test_auto_dia_d_verification_route` + `test_auto_dia_d_feedback_route` + `test_auto_dia_d_route` + `test_dia_d_cycle_verification_pg`) → **34 passed**.
- `contract:gen` (223 paths / 478 schemas) + `contract:check` → **OK**.

## 8. Límites (declarados, no disfrazados)

- **Enlace y resultado DECLARADO, no confirmación.** El registro une la verificación con su ciclo; **no** emite `CONFIRMED` ni afirma rentabilidad.
- **Huecos declarados.** Un ciclo histórico sin identidad de estrategia se persiste en **`NULL`** («Sin dato todavía»), nunca `""`/`0`; sin `cycleId` la UI no finge ausencia.
- **`Δ decisión = 0`.** El sello **no** entra en el payload del replay; el artefacto de `replay-repro` **no** se toca.
- **Cita POST-TAG pendiente:** el objeto del tag, el commit y el run de `Release tag CI` se añaden en §9 tras publicar.

## 9. Cita POST-TAG

Pendiente de publicar el tag anotado **`v2.88.112-beta`** (unsigned, limitación de certificación).
