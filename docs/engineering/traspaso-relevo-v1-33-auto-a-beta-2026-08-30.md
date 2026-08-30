# RELEVO — V1.33 AUTO A-β + gobernanza (2026-08-30)

> **AsOf:** 2026-08-30 · **Estado:** **CÓDIGO** — producto V1.33-beta, **sin tag todavía**.  
> **Padre:** [`traspaso-relevo-v1-32-semi-paper-maduro-2026-08-30.md`](./traspaso-relevo-v1-32-semi-paper-maduro-2026-08-30.md) · [`roadmap-v127-path-to-10-2026-08-28.md`](./roadmap-v127-path-to-10-2026-08-28.md) · [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md).  
> **Tag certificado:** `v1.26-beta` → `96c0d5d7`. Tip incluye V1.27–V1.33 (código; sin commit/tag aún).

---

## 0. Qué cierra V1.33

**AUTO A-β + gobernanza (arranque A-δ)** — aperturas `paper_auto` con **paridad SEMI**: TradePlan TRIGGERED + `risk_signature` (solo salta Confirm). Sizing libro/% caja **no** es autoridad (A-γ rechazada). Fuente aperturas: solo Estudio (`estudio_dictamen` | `estudio_alarma`). EdgeReport en paper_auto **sigue** exigido (V1.17.1). `PAPER_D_EXECUTE` **off**. Copy producto «Libro AUTO».

| Pieza                                                         | Estado         |
| ------------------------------------------------------------- | -------------- |
| `resolve_supervised_opening_quantity` (PY twin de TS)         | CÓDIGO + tests |
| Router: qty = plan TRIGGERED · `evaluate_risk_signature`      | CÓDIGO + tests |
| A-δ: skip `auto_source_not_estudio` (Paper D marca `paper_d`) | CÓDIGO + tests |
| EdgeReport / env gate / ExitPermission H2                     | Intactos       |
| Copy `demo-book-auto-copy` → «Libro AUTO»                     | CÓDIGO + tests |

**Archivos clave:** `supervised_opening_sizing.py` · `execution_router.py` · `paper_d_propose.py` · `demo-book-auto-copy.ts`.

**No** se tocó: drag · thaw estricto · A-γ · flip `PAPER_D_EXECUTE` · Radar/Hoy AUTO · broker live · Confirm SEMI bypass · nav L1.

## 1. Freeze intacto

Confirm = firma · gráfico G0 · sin drag · AUTO execute env off · nav L1 congelada · LLM no ejecuta · H2 kill asimétrico intacto.

## 2. Next (un epic)

| Epic                 | Qué                                         | Fuera           |
| -------------------- | ------------------------------------------- | --------------- |
| **Wire Estudio→hit** | **Hecho** (V1.33.1) — `POST …/auto-propose` | Radar/Hoy       |
| V1.31 residual       | Tema claro · layouts · flash tick           | Drag            |
| Frente B             | Drag B-γ                                    | N4 + §8 ACUERDO |
| Telemetría A6        | Antes de ampliar fuentes / thaw             | thaw estricto   |

## 3. Arranque siguiente chat

1. Relevo hijo [`traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md`](./traspaso-relevo-v1-33-1-wire-estudio-hit-2026-08-30.md) (Wire Estudio→hit **Hecho**).
2. Deuda tag: `v1.27`…`v1.33.1` aún no publicados.
