# Spec — V1.98 Trail + T2 Coexistence (2026-09-04)

> **AsOf:** 2026-09-04 · **Estado:** **IN** (implementación) · partida tip [`v1.97-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.97-beta) → [`2e9d4675`](https://github.com/jvelasca/Bolsa_V1/commit/2e9d4675).  
> **Padre:** auditoría V1.97 (hallazgo trail|T2 exclusivo vs ExitPolicy) · [`spec-v197`](./spec-v197-t2-transactional-atomicity-2026-09-03.md).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
t1_executed
  ├─ TRAIL_APPLIED → trailing ⇄ TRAIL_APPLIED (N ratchets)
  │                    ├─ T2_TRIGGERED → t2_ready → T2_EXECUTED
  │                    └─ EXIT_REQUIRED | POSITION_CLOSED
  └─ T2_TRIGGERED → t2_ready → T2_EXECUTED
                       ├─ TRAIL_APPLIED → trailing
                       └─ POSITION_CLOSED
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** Alembic nuevo (sigue `019_outbox_position_fifo`).  
**No** auto-heal · **no** E2E integrado obligatorio · **no** cablear SEMI protect → `TRAIL_APPLIED`.

## 1. Problema

El FSM de lifecycle (mock V1.84) trataba trail y T2 como **linajes excluyentes**.  
ExitPolicy (V1.27) lleva T1 + T2 + `trail_width` en las tres plantillas.  
`decide_position_policy` emite `TARGET_2` sin mirar trailing → AUTO puede ejecutar T2 en caja mientras el sidecar recibe `illegal_transition` y el outbox FIFO se envenena (`dead_head`).

Además: geometría de trail usaba mark mock 106/110 (rechazaría stops PAPER reales) y el helper e2e TS validaba trail **solo LONG**.

## 2. Entregas

| ID    | Entrega                                                                               | Pri |
| ----- | ------------------------------------------------------------------------------------- | --- |
| P1-01 | Tabla FSM: trailing self-loop + trailing→T2 + t2_executed→trail/EXIT + t2_ready→CLOSE | P1  |
| P1-02 | `last_fill_price(log)` para geometría TRAIL (snapshots mock intactos)                 | P1  |
| P1-03 | `needs_atomic_t2_pair` también desde `trailing`                                       | P1  |
| P1-04 | Sync TS mock + SHORT `trail_relaxation`                                               | P1  |
| P2-01 | `stop_worsens` canónico en dominio; analytics/DEX-5 delegan                           | P2  |
| P2-02 | Tests domain + bridge + vitest FSM                                                    | P2  |

## 3. OUT

- LIVE · bump · `PAPER_D_EXECUTE` on · unificar ledger · auto-heal · Playwright integrated obligatorio
- SEMI protect → `TRAIL_APPLIED` (residual documentado)
- `open` → T2 / `open` → TRAIL (protect antes de T1)
- Rediseñar `LineagePath` a flags `has_trail`+`has_t2`

## 4. Criterio de cierre

P0=0 · P1 FSM/trail/T2 cerrados con tests.  
Ruff + Typecheck + domain/application tests GREEN.  
Freeze intacto. **No** declarar E2E browser certificado. **No** LIVE.
