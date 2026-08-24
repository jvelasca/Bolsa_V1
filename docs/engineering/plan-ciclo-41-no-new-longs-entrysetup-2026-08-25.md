# Plan — Ciclo 4.1 `NO_NEW_LONGS` (+ EntrySetup diferido 4.2)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §5 Golden G · §6 · relevo [`traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md`](./traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md).
> **AsOf:** 2026-08-25 · HEAD **`f02ff1a`** = `origin/main` (Ciclo 4.0 cerrado).
> **Estado:** **CERRADO en origin `97f4862`.** D1–D6 aprobados 2026-08-25. EntrySetup = 4.2.
> **Método:** rebanada fina; `check_opening` intacto; sin `contract:gen`; sin LLM en SL/size.

---

## 0. Objetivo

Cerrar **Golden G** (régimen adverso → no nuevos longs) en la capa **Plan** (`TradePlan`), reutilizando `whyNot: regime` ya tipado en shared/Python.

**No** es Entry Engine completo. Familias `EntrySetup` (Breakout / Pullback / Wyckoff) quedan en **Ciclo 4.2** (fase propia).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                 | Propuesta por defecto                                                                      |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------------ |
| D1  | ¿Alcance de **esta** rebanada?           | **Solo 4.1 `NO_NEW_LONGS`**. EntrySetup = 4.2.                                             |
| D2  | ¿Qué regímenes activan el veto de longs? | `risk_off` **y** `crisis` (macro ya clasificado). `uncertain` / `neutral` **no**.          |
| D3  | ¿Shorts en `risk_off`/`crisis`?          | **Permitidos** por plan (Golden G = `NO_NEW_LONGS` solo). Fit/gates siguen.                |
| D4  | ¿Dónde vive el veto?                     | Solo `build_trade_plan` → `BLOCKED` + `whyNot: regime`. **No** tocar `check_opening`.      |
| D5  | ¿Fuente de régimen en propose?           | Ya existe: `macro_assess.regime` en `propose_recommendation.py` (~375). Pasarlo al mapper. |
| D6  | Confirm rebuild sin macro                | Sin régimen → **no** inventar veto (mismo patrón conservador que sin barras → `WATCH`).    |

Si D1 = “4.1 + stub EntrySetup”, parar y replanificar (contrato + tests + UI).

---

## 2. Alcance 4.1 (sí / no)

### Sí

| Pieza   | Regla                                                                                                                                                                                               |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input   | `market_regime: str \| None` en `build_trade_plan` / `build_v0_trade_plan_dict`                                                                                                                     |
| Regla   | `direction == long` **y** `regime in {risk_off, crisis}` → `BLOCKED`, `whyNot` incluye `regime`, `quantity=0`, `executionAllowed=false`                                                             |
| Orden   | Tras `expired`; **antes o junto** a fit/freshness/mandate (veto de régimen no espera stop). Preferencia: mismo bloque `BLOCKED` que fit (acumular why si ambos fallan, o régimen primero — ver §3). |
| Propose | Pasar `regime` ya calculado al builder.                                                                                                                                                             |
| Tests   | Golden G: long + `risk_off` → `BLOCKED`/`regime`; long + `risk_on`/`neutral` sin cambio; short + `risk_off` puede seguir a stop/ready.                                                              |
| Docs    | ADR-031 §5 G → “Ciclo 4.1”; §6 nota 4.1; stamp SoT + relevo.                                                                                                                                        |

### No

- Familias `EntrySetup` / cambio de semántica de `entry_ready` por setup
- `check_opening`, broker, `PAPER_D_EXECUTE`, F9-B, purge, thesis health / MFE
- `contract:gen` / campo nuevo en Decision Board HTTP
- Pisar `suggestedQuantity` del ticket F3
- Veto de shorts por régimen
- UI nueva (Hoy ya lee `whyNot`; chips existentes bastan)

---

## 3. Diseño mapper (borrador)

```text
expired? → EXPIRED
regime blocks long? → BLOCKED (+ why regime)   # 4.1
!fit / !freshness / !mandate → BLOCKED
wait/reduce/none → WATCH entry
!stop → WATCH no_stop
!entry_ready → WATCH entry
else → TRIGGERED + size
```

**Acumulación:** si régimen y fit fallan a la vez, devolver `whyNot: [regime, fit]` en un solo `BLOCKED` (mejor para Why/Why not). Implementación: evaluar régimen + fit/freshness/mandate en el mismo tramo BLOCKED.

**Confirm:** rebuild sin `regime` → `None` → no bloquea por régimen (fail-open conservador en ausencia de dato; el fill sigue bajo `check_opening`).

---

## 4. Batería pactada

- ruff touched Python
- `pnpm test:decision-spine` (hoy **75**; +Golden G ≥1–3 casos)
- sin mypy amplio salvo fallo local del fichero

---

## 5. Ciclo 4.2 (fuera de este plan — solo ancla)

Contrato `EntrySetup` = `breakout | pullback | wyckoff | none` que **refina** `entry_ready` (no sustituye stop/size). Requiere plan E1 propio + tests A/B. **Prohibido** abrir en el mismo PR que 4.1.

---

## 6. Criterio de cierre 4.1

1. Golden G verde en spine.
2. Propose cablea régimen macro → TradePlan.
3. Confirm sin régimen no inventa `BLOCKED` por régimen.
4. `check_opening` diff vacío.
5. Relevo + stamp SoT. Commit solo con OK; push solo si el propietario lo pide.

---

## 7. Texto de arranque (tras OK D1–D6)

```text
Implementar Ciclo 4.1 NO_NEW_LONGS según plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md.
D1=solo 4.1 · D2=risk_off+crisis · D3=shorts OK · D4=TradePlan only · D5=macro_assess.regime · D6=confirm sin régimen no veta.
No EntrySetup · no check_opening · no contract:gen.
```
