# A2–A5 prep Camino D (2026-08-04)

> Código listo detrás de flags. **No** hay thaw: `PAPER_D_EXECUTE` default off. Padres: [checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md).

| Fase | Entrega | Estado |
|------|---------|--------|
| **A2** | Execute Paper D → Risk Engine + book maxOpen + DecisionSession DENY/fill + idempotencia | Hecho (flag off) |
| **A3** | Kill switch runtime API/UI + doble confirm armado local | Hecho |
| **A4** | ADR-023 Proposed + freeze nota + HELP | Hecho (sin evidencia P1–P5) |
| **A5** | `PAPER_D_ACCOUNT_ID` opt-in 1 cuenta | Hecho (doc + gate) |

## Flags

```bash
# PAPER_D_EXECUTE=0          # default: no execute
# PAPER_D_ACCOUNT_ID=        # opcional: solo esa cuenta DEMO
# RISK_KILL_SWITCH=false     # env duro; UI también vía POST /api/risk/kill-switch
```

## API

- `GET/POST /api/risk/kill-switch` — runtime (memoria + Redis)
- Health `components.risk` — kill switch + `paperDExecuteEnv`

## UI (Operativa → Configuración)

- Kill switch toggle
- «Armar AUTO (doble confirm)» → frase `ACTIVAR AUTO` (localStorage; no habilita pill)
- Pill Auto · prep sigue disabled (`DEMO_BOOK_AUTO_UI_ENABLED=false`)
