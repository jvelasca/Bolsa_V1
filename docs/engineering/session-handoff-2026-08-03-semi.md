# Handoff — SEMI libro DEMO (2026-08-03)

> **Retomar aquí.** Padres: [demo-operating-modes-brief](./demo-operating-modes-brief-2026-08-03.md) · [semi-demo-book-impl-slice1](./semi-demo-book-impl-slice1-2026-08-03.md).

## Hecho

### Slice 1 (PR #23 · main)
- Libro DEMO MANUAL/SEMI · sizing · F3 lote · Radar/Finalistas gates.

### Slice 1.1 geo (PR #24 · main)
- Ranker óptimo → país→EU→mundo · control en Libro DEMO.

### Slice 1.2 — cola F3 BD + country en propose (esta rama)
- Tabla `supervised_f3_account_state` · GET/PUT `/api/accounts/{id}/supervised-f3-queue`.
- Hydrate/push (patrón CORE-R) · `SupervisedF3QueueHost` en PlatformShell.
- `Recommendation.country` desde instrumento en propose.
- Smoke automatizado: vitest prefs/geo/finalists/queue (16 tests OK 2026-08-03).

## Verificación

```bash
pnpm test:semi
pnpm test:semi:smoke   # API :8000 + migración
```

## Pendiente

1. Smoke UI manual (checklist en impl brief).  
2. AUTO / Belief pesos — **no** hasta descongelar.

## Ops

```bash
python packages/py/infrastructure/scripts/apply_supervised_f3_account_state_migration.py
```

## Rama

`stage/semi-f3-queue-bd-2026-08-03` (PR #25)
