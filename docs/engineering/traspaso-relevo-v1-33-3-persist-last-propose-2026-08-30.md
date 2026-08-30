# RELEVO — V1.33.3 Persist `lastPropose` A6 (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — JSONL histórico A6, **sin tag**.  
> **Padre:** [`traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md`](./traspaso-relevo-v1-33-2-telemetria-a6-2026-08-30.md) · [`plan-v1333-persist-last-propose-2026-08-30.md`](./plan-v1333-persist-last-propose-2026-08-30.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33.3 + V1.31.1 + V1.31.2 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.33.3

**Persist `lastPropose`** — JSONL append-only + `recentProposes` en GET auto-telemetry. Rojo ≠ Alembic · ≠ ampliar Radar/Hoy · ≠ flip execute.

| Pieza                                                                         | Estado          |
| ----------------------------------------------------------------------------- | --------------- |
| `BOLSA_ESTUDIO_AUTO_PROPOSE_PATH` + default `logs/estudio_auto_propose.jsonl` | CÓDIGO + tests  |
| `remember` / hydrate / `recent_estudio_auto_proposes`                         | CÓDIGO + tests  |
| GET `recentProposes` + `durability=jsonl`                                     | CÓDIGO          |
| Consola label «persistido JSONL» + N histórico                                | CÓDIGO + vitest |

**Archivos clave:** `estudio_auto_telemetry.py` · `test_estudio_auto_telemetry.py` · `api.ts` · `operational-console-sections.tsx`.

**No** se tocó: Alembic · Redis · Confirm · drag · thaw · Radar/Hoy AUTO · `PAPER_D_EXECUTE`.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 · LLM no ejecuta · H2 kill asimétrico.

## 2. Next (un epic)

| Epic              | Qué                                       | Fuera            |
| ----------------- | ----------------------------------------- | ---------------- |
| Frente B          | Drag B-γ                                  | N4 + §8 ACUERDO  |
| Tag deuda         | `v1.27`…`v1.33.3` + `v1.31.1` + `v1.31.2` | —                |
| UI histórico rico | Tabla de proposes                         | Solo strip N hoy |

## 3. Arranque siguiente chat

1. Este relevo + [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
2. `python -m pytest application/tests/test_estudio_auto_telemetry.py application/tests/test_estudio_auto_hits.py` (cwd `packages/py`).
3. Smoke: POST auto-propose dry-run → reiniciar API → GET `lastPropose` + `durability=jsonl` + `recentProposes` crece. `BOLSA_ESTUDIO_AUTO_PROPOSE_PATH=off` → memoria.
4. No abrir drag / thaw / A-γ / Radar-Hoy AUTO / flip execute.
5. Deuda tag: `v1.27`…`v1.33.3` + `v1.31.1` + `v1.31.2` aún no publicados.
