# RELEVO — V1.33.1 Wire Estudio→hit (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — productor Estudio→hit AUTO, **sin tag**.  
> **Padre:** [`traspaso-relevo-v1-33-auto-a-beta-2026-08-30.md`](./traspaso-relevo-v1-33-auto-a-beta-2026-08-30.md) · [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §3.  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33.1 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.33.1

**Wire Estudio→hit** — dictamen/alarma Estudio produce hits con `autoSource` (`estudio_dictamen` \| `estudio_alarma`) + TradePlan TRIGGERED (propose SEMI). Execute opcional detrás de `PAPER_D_EXECUTE` (sigue **off**).

| Pieza                                                               | Estado         |
| ------------------------------------------------------------------- | -------------- |
| `resolve_estudio_auto_source` / `select_estudio_opening_candidates` | CÓDIGO + tests |
| `build_estudio_auto_hit` + `ProposeEstudioAutoOpenings`             | CÓDIGO + tests |
| `POST /instrument-daily-opinions/auto-propose`                      | CÓDIGO         |
| Router A-β/A-δ + EdgeReport + env gate                              | Intactos       |

**Archivos clave:** `estudio_auto_hits.py` · `instrument_daily_opinions.py` (route) · `test_estudio_auto_hits.py`.

**No** se tocó: Radar/Hoy AUTO · drag · thaw · A-γ · flip `PAPER_D_EXECUTE` · hook automático en eod-batch · Confirm SEMI · nav L1.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic           | Qué                               | Fuera           |
| -------------- | --------------------------------- | --------------- |
| Telemetría A6  | **Hecho** (V1.33.2)               | thaw estricto   |
| V1.31 residual | Tema claro · layouts · flash tick | Drag            |
| Frente B       | Drag B-γ                          | N4 + §8 ACUERDO |

## 3. Arranque siguiente chat

1. Este relevo + V1.33 + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) + estudio §3.
2. `python -m pytest application/tests/test_estudio_auto_hits.py application/tests/test_execution_router.py` (cwd `packages/py`).
3. Smoke: `POST …/auto-propose` dry-run → hits con `estudio_alarma`/`estudio_dictamen` + plan TRIGGERED; `execute=true` sin env → `blocked_env`; Paper D sigue `auto_source_not_estudio`.
4. No abrir drag / thaw / A-γ / Radar-Hoy AUTO.
5. Deuda tag: `v1.27`…`v1.33.1` aún no publicados.
