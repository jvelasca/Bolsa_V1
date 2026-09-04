# Spec — V1.99 Position Management Certification (2026-09-04)

> **AsOf:** 2026-09-04 · **Estado:** **IN** (certificación implementada; tip/tag pendiente Release-tag GREEN) · partida tip [`v1.98-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.98-beta) → [`7b5b1052`](https://github.com/jvelasca/Bolsa_V1/commit/7b5b1052).  
> **Padre:** auditoría post-V1.98 (P2 lineagePath + golden de gestión completa) · [`spec-v198`](./spec-v198-trail-t2-coexistence-2026-09-04.md).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.  
> **No features:** no cambia `TRANSITIONS`, outbox, ExitPolicy ni schema de riesgo.

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** Alembic nuevo (sigue `019_outbox_position_fifo`).  
**No** `open` → TRAIL / `open` → T2 · **no** LineagePath flags · **no** cuarteto de riesgo persistido · **no** UI MERCADO / AUTO Desk (V2.0).

## 1. Problema

V1.98 alinea FSM con ExitPolicy (trail ⇄ T2). Falta **certificar** combinaciones de gestión de posición y documentar dos reglas P2:

1. `lineagePath` es clasificación last-wins, **no** historia.
2. Trail / T1 / T2 **no** reescriben `initialRisk` / `initialStop`.

Trail solo **después de T1** (FSM actual). El golden agresivo del auditor se mapea a Golden 5 con fills reales (T1 @ 120, no trail antes de T1).

## 2. Modelo de verdad

```text
event log  = verdad histórica
stage      = estado derivado (FSM)
lineagePath = clasificación last-wins (NO historia)
```

Tras `T2_EXECUTED → TRAIL_APPLIED`: `stage = trailing`, `lineagePath = "trail"`, y el log **sigue** conteniendo `T2_EXECUTED`.

Riesgo histórico (regla, no schema nuevo):

- `initialRisk` / `initialStop` = nacimiento; **inmutables** tras trail / reduce
- `currentStop` = protección vigente (puede ratchet)
- Realized / remaining = fills + `remainingQuantity`

## 3. Goldens (8)

| ID  | Secuencia                                     | Capa                   |
| --- | --------------------------------------------- | ---------------------- |
| G1  | OPEN (+ stop 95) → EXIT                       | domain                 |
| G2  | OPEN → T1 → EXIT                              | domain + HTTP V1.95    |
| G3  | OPEN → T1 → T2 → EXIT                         | domain + HTTP V1.96    |
| G4  | OPEN → T1 → TRAIL → TRAIL → EXIT              | domain + vitest        |
| G5  | OPEN → T1 → TRAIL → TRAIL → T2 → TRAIL → EXIT | domain master + vitest |
| G6  | OPEN → T1 → T2 → TRAIL → TRAIL → EXIT         | domain + vitest        |
| G7  | T2_TRIGGERED → CRASH → RETRY → T2_EXECUTED ×1 | ancla V1.97 + PG       |
| G8  | stop worsen LONG/SHORT (ratchet OK / DENY)    | domain + vitest        |

### Fixture Golden 5 (legal en FSM)

```text
OPEN  qty=10 @ 100   stop=95   initialRisk=50
T1    qty=5  @ 120   remaining=5   lastFill=120
TRAIL 95 → 100
TRAIL 100 → 105
T2    qty=3  @ 125   remaining=2   lastFill=125
TRAIL 105 → 110      stage=trailing  lineagePath=trail  (log ⊃ T2_EXECUTED)
EXIT  qty=2
```

## 4. Entregas

| ID  | Entrega                                                               | Pri |
| --- | --------------------------------------------------------------------- | --- |
| C1  | Domain goldens G1–G6, G8 + lineage ≠ log                              | P1  |
| C2  | PositionState: `initial_risk`/`initial_stop` inmutables tras trail/T1 | P1  |
| C3  | G7 anclado en V1.97 crash/retry (sin reimplementar)                   | P1  |
| C4  | Vitest mirror G1/G4/G5/G6/G8                                          | P2  |
| D0  | spec/plan/relevo/arranque + CURRENT_SYSTEM + index §68                | P2  |

## 5. OUT

- LIVE · bump · `PAPER_D_EXECUTE` on · unificar ledger · Alembic · auto-heal
- Cambiar `TRANSITIONS` · `open` → TRAIL/T2 · LineagePath flags
- Persistir Initial/Current/Realized/Remaining Risk
- UI MERCADO / desk AUTO (fase V2.0 post-freeze)
- HTTP golden nuevo de 8 caminos (Confirm no expresa ratchets)

## 6. Criterio de cierre

P0=0 · 8 goldens GREEN · lineage + initialRisk GREEN.  
Ruff + mypy + domain/application + vitest FSM GREEN.  
Release-tag CI GREEN (python + lifecycle-pg + frontend + playwright-mock).  
Freeze intacto. **No** declarar BETA final congelada hasta PASS auditor.  
Siguiente fase documentada: **ENGINE FREEZE** → V2.0 Operational UX / AUTO Desk.
