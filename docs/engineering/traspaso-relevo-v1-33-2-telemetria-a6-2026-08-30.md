# RELEVO — V1.33.2 Telemetría A6 (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — scorecard A6 Estudio AUTO, **sin tag**.  
> **Padre:** [`traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md`](./traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md) · [`plan-v1332-telemetria-a6-2026-08-30.md`](./plan-v1332-telemetria-a6-2026-08-30.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33.2 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.33.2

**Telemetría A6** — embudo Estudio→hit + veredicto `expandSourcesReady` (P1–P5 PASS + EdgeReport paridad SEMI). Rojo ≠ thaw · ≠ ampliar Radar/Hoy.

| Pieza                                                                            | Estado          |
| -------------------------------------------------------------------------------- | --------------- |
| `count_estudio_auto_funnel` / `derive_a6_gates` / `build_estudio_auto_telemetry` | CÓDIGO + tests  |
| Snapshot `lastPropose` (memoria de proceso)                                      | CÓDIGO + tests  |
| `GET /instrument-daily-opinions/auto-telemetry`                                  | CÓDIGO          |
| Consola card + strip Asesor                                                      | CÓDIGO + vitest |
| Router A-β/A-δ + execute env off                                                 | Intactos        |

**Archivos clave:** `estudio_auto_telemetry.py` · `instrument_daily_opinions.py` (GET) · `operational-console-sections.tsx`.

**No** se tocó: Radar/Hoy AUTO · drag · thaw · A-γ · flip `PAPER_D_EXECUTE` · Alembic · nav L1.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic                  | Qué                                                   | Fuera                 |
| --------------------- | ----------------------------------------------------- | --------------------- |
| V1.31 residual        | Tema claro **Hecho** (V1.31.1) · layouts · flash tick | Drag                  |
| Persist `lastPropose` | Tabla/eventos si hace falta histórico                 | Alembic sin necesidad |
| Frente B              | Drag B-γ                                              | N4 + §8 ACUERDO       |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + estudio §3 A6.
2. `python -m pytest application/tests/test_estudio_auto_telemetry.py application/tests/test_estudio_auto_hits.py application/tests/test_execution_router.py` (cwd `packages/py`).
3. Smoke: `GET …/auto-telemetry` → `funnel.allowedSources` Estudio · `gates.expandSourcesReady=false` · `paperDExecuteEnv=false`. POST auto-propose dry-run → `lastPropose.executeStatus=dry_run`.
4. No abrir drag / thaw / A-γ / Radar-Hoy AUTO / flip execute.
5. Deuda tag: `v1.27`…`v1.33.2` aún no publicados.
6. API local sin `--reload`: reiniciar `pnpm dev` para ver el GET nuevo.
