# Traspaso / relevo — A7 Iter-1 · C3 (crash-injection real-PG) — V2.18-beta

Fecha: 2026-09-09 · Ámbito: LIVE Certification / A7 — Iter-1, gated a **C3**.

## Resumen del ciclo

La Iter-0 (V2.17) dejó mapeado con 🔴 el gap **C3 — crash-injection sobre
`scheduler_worker`/recovery** y un home + gate _sugeridos_ para la Iter-1. Esta Iter-1 materializa ese primer
escenario A7 real: una batería **real-PG** de **crash de proceso real** sobre el worker de recovery/scheduler,
con comprobación de invariantes **order-state/FSM** (≈ resolución exacta, sin doble transición ni doble
materialización) y un **gate CI dedicado** (`a7-gate`) que hace fail-hard si el escenario se salta.

Núcleo financiero congelado **intacto**. Alembic head `023_ohlcv_bars_unique_reconcile` (sin migración).

## Alcance cerrado (ruta:línea)

- Batería: [`apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py`](../../apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py)
  - C3-A → `test_c3a_crash_after_recovery_claim_then_second_is_exact_once`: subproceso A reclama UNKNOWN
    (claim `FOR UPDATE` en vivo) → **SIGKILL** → subproceso B reapropia y resuelve **exactamente una vez**
    (`resolved=1`, final `FILLED`, `financial_apply_count == 0`, sin UNKNOWN huérfana).
  - C3-B → `test_c3b_crash_after_resolve_put_no_double_on_relaunch`: tras un resolve durable real (proceso),
    relanzar la recuperación no re-procesa (`drained=0`) → idempotencia del `put`/terminal-not-UNKNOWN.
- Harness de proceso: [`apps/api-python/tests/chaos/live_a7/_crash_recovery_probe.py`](../../apps/api-python/tests/chaos/live_a7/_crash_recovery_probe.py)
  (`_probe_crash_hold` parquea SIN commit sobre el claim real; `_probe_reader` resuelve con `resolve_one_unknown`).
  No toca el núcleo (`apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py`, `scheduler_worker.py`,
  FSM `live_order.py`, reconcilers, DR). Se une solo por **ruta de fichero** (subprocess), no por import.
- CI: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) → job **`a7-gate`**
  (Postgres service + BD dedicada `bolsa_v1_a7` drop+create; esquema a head por `ensure_migrated` idempotente en
  la batería; pytest `apps/api-python/tests/chaos/live_a7` con `LIVE_A7_PG_REQUIRED=1`) + `a7-gate` en `needs` de
  `certify` y en el artefacto de resumen.
- Offline herméticos: `--ignore=apps/api-python/tests/chaos/live_a7` añadido al pytest offline del tag y
  `python-ci.yml` (A7 corre en `a7-gate`).

## Decisiones registradas

- **Modo `fsm_only` (dec. V2.18):** el recovery del UNKNOWN hoy NO materializa dinero (veto XL-3 / apply
  PARKED; ver `live_order_recovery_worker.py`). Por tanto C3 no comprueba `cash`/`position`; sí valida que la
  orden no se resuelva dos veces ni se invente un apply financiero. La vertiente financiera del crash queda a
  Iter-2.
- **Home efectivo:** `apps/api-python/tests/chaos/live_a7/` (no `packages/py/infrastructure/tests/chaos/live_a7/`
  como apuntaba la Iter-0). Motivo: la realización real-PG cruza la costura app (`bolsa_api.background`) +
  `bolsa_application` (store/lease), por lo que el hogar en la app reusa el mismo camino que
  `test_live_order_recovery_concurrency_pg.py` sin acoplar infra a la app.
- **Esquema a head:** la batería lleva la BD dedicada a `023` vía `ensure_migrated` (idempotente, respeta
  `DATABASE_URL` de settings); no depende de la migración CLI de `alembic.ini` (que apunta a la DB principal).

## Estado de A7 tras la Iter-1

- C3: 🔴 → 🟡 **cubierto(parcial)** — crash real-PID + reclaim exacto-una-vez + no-doble (fsm_only).
- Pendientes Iter-1+: la **vertiente financiera** del crash (C3 extendido a ledger cuando XL-3 habilite el
  apply), A3 (timeout/network real), B2 (partial fill) y P2-01 (ExecutionEvent durable) son los puentes a esa
  vertiente (ver backlog §5 del gap-map).

## Verificación

- Live (PG real dedicado, primera y repetición): `chaos/live_a7` **2 passed**.
- Ruff `apps/api-python packages/py` limpio; `test_live_order_recovery_worker.py` + `test_scheduler_worker.py`
  → **12 passed**.
- Elevación completada en GitHub: **Release-tag CI `#34341628713` GREEN** sobre el tag remoto `v2.18-beta`
  (`conclusion: success`; `origin/main` en `bd2bd163`, sin ahead/behind). El nuevo job **`a7-gate`**
  (Postgres service + BD dedicada `bolsa_v1_a7` drop+create + pytest `chaos/live_a7` con
  `LIVE_A7_PG_REQUIRED=1`) pasó en verde y `certify` lo agregó; `playwright (integrated)` skipped (opt-in,
  correcto).

FIN DEL RELEVO — A7 Iter-1 · C3 (V2.18-beta) elevado en GitHub: `origin/main` `bd2bd163` + tag remoto
`v2.18-beta` y **Release-tag CI `#34341628713` GREEN** (`conclusion: success`, `certify` ✓ con `a7-gate`);
C3 queda 🔴 → 🟡 cubierto(parcial) certificado por el pipeline, repo dispuesto para Iter-2 / auditoría.
