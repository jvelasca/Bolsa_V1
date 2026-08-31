# Plan — V1.33.4 Estudio AUTO dry-run ops (2026-08-31)

> **AsOf:** 2026-08-31 · **Estado:** **CÓDIGO** (este slice).  
> **Padre:** [`traspaso-relevo-v1-33-3-persist-last-propose-2026-08-30.md`](./traspaso-relevo-v1-33-3-persist-last-propose-2026-08-30.md) · [ADR-023](../adr/023-camino-d-thaw.md) · [ADR-042](../adr/042-operating-excellence.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Tip certificado producto:** `v1.41.3-beta` → `a8101ab7`.

---

## 0. Decisión de owner

Adelantar **F8a** (dry-run operativo Estudio AUTO) respecto al orden V1.42 F1–F7.  
**No** flip `PAPER_D_EXECUTE`. **No** thaw estricto. **No** Radar/Hoy como fuentes. Measure ≠ Accept.

```text
SEMI: IA propone → Risk → Policy → Humano confirma → Execution
AUTO: IA propone → Risk → Policy → Execution   (mismo risk; Confirm omitido)
```

Arm UI (`ACTIVAR AUTO`) ≠ permiso de execute. Dry-run ≠ execute.

## 1. Entregables

| ID  | Qué                                                                                    |
| --- | -------------------------------------------------------------------------------------- |
| A1  | CTA Consola: **Correr auto-propose (dry-run)** → `POST …/auto-propose` `execute=false` |
| A2  | Tabla `recentProposes` (A6 JSONL) en Consola                                           |
| A3  | Copy: dry-run ≠ execute · arm ≠ env                                                    |
| A4  | vitest consola                                                                         |

## 2. Freeze intacto

Confirm = firma SEMI · Ranking ≠ BUY · `check_opening` = autoridad · Estudio membership · TradePlan TRIGGERED + risk_signature (A-β) · `PAPER_D_EXECUTE` default off · LLM no ejecuta · H2 kill asimétrico.

## 3. Fuera

Flip env · thaw P1–P5 · Radar/Hoy AUTO · broker live · eod auto-execute · A-γ · ExecutionState/TradeStory (V1.42 F2–F4).

## 4. Después (hoja)

Smoke local documentado: `PAPER_D_EXECUTE=1` + `PAPER_D_ACCOUNT_ID` + arm UI (DEMO). F8b = execute paper como modalidad de producto.
