# Risk Engine (OR-RE v0) — 2026-08-04

> Fachada única pre-execute automático. **No** es el OMS completo ni el portfolio engine.

## Qué

`packages/py/application/.../risk_engine.py` → `check_opening(...) → RiskDecision(ALLOW|DENY, reasons)`.

Internamente:

1. `RISK_KILL_SWITCH` / `kill_switch=True` → DENY inmediato.  
2. `book_max_open_positions` (Libro DEMO) si se pasa → DENY en buy.  
3. `enforce_cognitive_policy_for_opening` (Gate + long-only + policy maxOpen + DD + eventos).

## Quién llama

- `ExecutionRouter` (paper_auto + live_dry_run) — **obligatorio**.  
- Futuro Camino D / Estudio AUTO — **solo** vía esta fachada.  
- SEMI Confirm humano: **no** sustituye Confirm (sigue Camino C).

## Flags

```
RISK_KILL_SWITCH=false   # true = ninguna apertura automática
```

## Fuera de v0

Mandato pre-trade hard · correlaciones portfolio · Decimal money · broker adapter · shadow mode.

@see [triage §9.2](./audit-ext-institutional-pre-auto-triage-2026-08-04.md) · [thaw OR-RE](./camino-d-auto-thaw-checklist-2026-08-04.md)
