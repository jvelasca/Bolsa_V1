# Arranque auditor externo — V2.13 (Execution Core Honesty) (2026-09-07)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.13** (delta `v2.12-beta` → **`main = 6e279e2d`**, tag **`v2.13-beta`** peeled → `6e279e2d` · package **`1.42.0-beta`** · Release-tag CI V2.13 **GREEN real** [run 34124260037](https://github.com/jvelasca/Bolsa_V1/actions/runs/34124260037), certify `success`, artefacto `"status": "GREEN"`).

**Regla:** NINGÚN estado ambiguo → NO COMPRAR. Dry-run honesto. Compara **línea por línea** `main` (V2.12, `b9b35ec2`) → `main` actual (`6e279e2d`). No inventes PASS.

**Alcance = delta `main:v2.12(b9b35ec2) → 6e279e2d`** (10 commits, 26 ficheros), más los tres pilares **fuera** del delta ya en el tronco (marco el alcance exacto):

- **Core V2.13 (delta):** Concurrency/locking (leases/claims, `SELECT … FOR UPDATE … SKIP LOCKED`, upsert atómico `ON CONFLICT` sin TOCTOU), financial invariants `NUMERIC(18,6)` + CHECKs (migración `021_live_orders_fin`), cancel honesta (CANCEL*REQUESTED→CANCELLED solo confirm broker, `cancel*\*`docs), UNKNOWN recovery del`LiveOrderRecoveryWorker`(nunca re-POST),`live_order_machine_reconcile`(H7, read-only fail-closed) y`Xt_broker-query H6`.
- **Kill switch backend/policy (tronco):** `effective_kill_switch` = env + runtime memory + Redis; enforcement en `check_opening` y en el adapter XTB antes del bridge; no bloquea query/recovery de órdenes existentes.
- **OperationalIncident (tronco, DEX-3/ADR-035):** workflow `open→in_review→resolved→cleared`, persistencia (migración 014 + índice UNIQUE parcial que fuerza clear antes de reabrir), clear solo con recon `clean`.
- **Reconciliation OR-4 / LR-1 (tronco):** detect/report sin auto-heal, veto fail-closed de LIVE ante drift / unavailable / lifecycle lag/blocked.

Leo (fuentes reales, no solo docs):
`packages/py/application/src/bolsa_application/live_order_store.py` · `live_order_machine_reconcile.py` · `broker_adapter.py` · `reconcile_live_ledger.py` · `operational_incident.py` · `operational_incident_store.py` · `reconciliation_opening_gate.py` · `risk_engine.py` · `risk_runtime.py` · `opening_permission.py` · `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py` · migraciones `021_live_orders_fin.py` y `014_operational_incidents.py` · `packages/py/application/tests/test_live_order_store_pg.py` · `test_live_order_machine_reconcile.py` · tests de broker/confirm/crash-restart/recon/incident. Registrar P0/P1/P2/P3.

**Foco (deuda previa):**

1. ¿Concurrency/locking real inter-PID: dos workers no resuelven dos veces la misma UNKNOWN ni compiten corrupt? ¿lease stale OK post-crash? ¿upsert no pierde última escritura?
2. ¿Financial integrity: las cantidades `NUMERIC` + CHECKs no se rompen con fills PARCIAL fraccionales del broker (adapter float)? ¿ledger atómico?
3. ¿Cancel: ninguna ruta fabrica CANCELLED sin confirm del broker? ¿siempre se está `CANCEL_REQUESTED` mientras in-flight? ¿guard anti-confirmación fantasma (exigir `cancel_requested_at` previa)?
4. ¿UNKNOWN: la recuperación jamás re-POSTea, solo query? ¿con kill switch activo el recovery sigue consultando (no fabrica falso CANCELLED ni se queda colgado)?
5. ¿Reconcile: H7 y OR-4/LR-1 son fail-closed y **nunca** auto-heal? ¿vetan LIVE cuando recon no está disponible?
6. ¿OperationalIncident: open→review→resolve→clear persistido; la reapertura exige clear previo del mismo `(account,kind)`; clear solo si recon `clean`; double-worker OPEN no rompe?
7. ¿Decision Spine: ninguna ruta LIVE puede saltar Decision→Proposal→Risk(SPINE)→Authorization→Execution pasando por alto estos gates?
8. ¿Kill switch: ¿es policy de backend efectiva (env/runtime/redis), no solo UI? ¿veta nuevas aperturas pero no bloquea cierre/reduce de posiciones existentes? (P2-1 notado: `check_opening` `if kill_switch` sin exclusión `_EXIT_SIGNAL_KINDS`; no toca cierres hoy).

**Deuda anotada por el sistema antes de pasar (ver [deuda-anotada-audit-v2-13-ampliado-2026-09-07.md](./deuda-anotada-audit-v2-13-ampliado-2026-09-07.md)):** P2-1 (asimetría kill_switch/exit), P2-2 (put incidente doble-worker IntegrityError no idempotente), P3-1 (float→NUMERIC sin rounding), P3-2 (`pg_constraint` global). **No** son fijadas; valida si hay más.

**No pedir:** LIVE · bump · unificar ledger/mesa · re-diseñar ADR · V2.14 por inercia. Cero features fuera del alcance.

**Respuesta esperada:** (pendiente — no inventar PASS). Informe en `[severity]` y veredicto por cada foco, con evidencia archivo:línea y delta real V2.12→V2.13.

---
