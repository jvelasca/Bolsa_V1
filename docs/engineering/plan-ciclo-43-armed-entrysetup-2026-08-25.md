# Plan — Ciclo 4.3 `ARMED` (refina ladder post-EntrySetup)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`ARMED` / Wyckoff formal = 4.3+) · relevo [`traspaso-relevo-ciclo-42-entrysetup-2026-08-25.md`](./traspaso-relevo-ciclo-42-entrysetup-2026-08-25.md) · ancla en [`plan-ciclo-42-entrysetup-2026-08-25.md`](./plan-ciclo-42-entrysetup-2026-08-25.md) (D4 difería `ARMED`).
> **AsOf:** 2026-08-25 · HEAD **`4fc864b`** = `origin/main`; feat **`4eb99a2`**.
> **Estado:** **CERRADO en origin** (`4eb99a2` vía `4fc864b`). D1–D7 OK · batería **84**.
> **Método:** rebanada fina; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Insertar **`ARMED`** en la ladder de readiness del `TradePlan` **después** de Ciclo 4.2 (`EntrySetup` + `entry_ready` = TA bias **y** setup≠none).

Hoy el mapper salta `WATCH` → `TRIGGERED` aunque el tipo ya admite `ARMED` (`TradePlanStatus` Python + `@bolsa/shared`). 4.3 hace visible el peldaño intermedio: **stop válido + setup clasificado**, aún sin fuego (`entry_ready` falso).

**No** es Position Manager / thesis health / trailing (Ciclo 5). **No** abre Wyckoff fases formales salvo D3 explícito (default = stub 4.2 intacto).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                     | Propuesta por defecto                                                                                                                                                                                                                                                                                                                             |
| --- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?               | Solo cablear `ARMED` en `build_trade_plan` (+ tests spine). Símbolos ya existen. **Sin** Wyckoff formal · **sin** cambiar prioridad breakout>pullback>wyckoff · **sin** tocar stop/size 4.0 ni régimen 4.1.                                                                                                                                       |
| D2  | ¿Significado `ARMED` vs `WATCH`/`TRIGGERED`? | **WATCH** `no_stop`: sin stop. **WATCH** `entry`: action wait/reduce/`none`, **o** stop OK pero `setup=="none"`. **ARMED**: stop válido **y** `entry_setup ≠ "none"` **y** `entry_ready == False` (p.ej. bias ausente / exhaustion). **TRIGGERED**: `entry_ready` + stop + size (igual que 4.2). `executionAllowed=false` en ARMED; `quantity=0`. |
| D3  | ¿Wyckoff formal en 4.3?                      | **No.** Mantener stub reclaim 4.2 (`_is_wyckoff_reclaim`, `WYCKOFF_SPRING`/`PRIOR`). Fases SOS/LPS/spring state machine → **4.4+** si hace falta.                                                                                                                                                                                                 |
| D4  | ¿Reglas de transición?                       | Orden mapper: `EXPIRED` → `BLOCKED` (régimen/fit/…) → wait/`none` → `WATCH` → `!stop` → `WATCH`/`no_stop` → _(nuevo)_ setup≠none ∧ !ready → **`ARMED`** → ready → **`TRIGGERED`**. No estados nuevos en Why codes.                                                                                                                                |
| D5  | ¿Confirm sin barras?                         | Sin barras → `classify_entry_setup` = `none` → **no** inventar `ARMED` (mismo patrón conservador 4.0–4.2). Típico `WATCH`/`no_stop` o `entry`.                                                                                                                                                                                                    |
| D6  | ¿`contract:gen` / Board HTTP?                | **No.** Solo dict TradePlan en propose/confirm/Hoy (como hoy). Decision Board sin campo nuevo.                                                                                                                                                                                                                                                    |
| D7  | ¿UX Why surface nueva?                       | **No.** Chip `ARMED` ya tipado en Hoy strip. `whyNot` puede seguir con `entry` bajo ARMED (bias/exhaustion). Sin panel Why dedicado ni copy nueva obligatoria.                                                                                                                                                                                    |

Si D3 = Wyckoff formal ahora, **parar y replanificar** (contrato fases + tests + posible UI). Si D2 = otro semántica (p.ej. ARMED = TRIGGERED con `executionAllowed=false`), replanificar tests Golden A/B.

---

## 2. Alcance 4.3 (sí / no)

### Sí

| Pieza        | Regla                                                                                                                                                            |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mapper       | En `build_trade_plan` (`packages/py/analytics/.../trade_plan.py`): tras `stop_valid`, si `entry_setup != "none"` y `not entry_ready` → `status="ARMED"`.         |
| Why / qty    | `why_not` incluye `entry` (conservador); `quantity=0`; `execution_allowed=False`; `actionability` intermedia (p.ej. `0.7`, entre WATCH entry `0.4` y TRIGGERED). |
| Propose path | Sin cambio de inputs: `build_v0_trade_plan_dict` ya calcula `setup` + `entry_ready_from_ta`; el mapper absorbe ARMED.                                            |
| Tests        | ≥2–3 casos: (1) stop+breakout sin bias → `ARMED`; (2) stop+breakout+bias → sigue `TRIGGERED` (Golden A); (3) confirm/rebuild sin barras → no ARMED inventado.    |
| Docs cierre  | Tras implement: nota ADR-031 §6 Ciclo 4.3; stamp SoT + relevo (fuera de este BORRADOR).                                                                          |

### No

- Wyckoff fases formales / motor paralelo Lab
- Cambiar prioridad `breakout > pullback > wyckoff` ni umbrales 4.2
- `check_opening`, broker, F9-B, purge MONITOR, `PAPER_D_EXECUTE`, thesis health / MFE, qty Confirm
- `contract:gen` / Board HTTP
- Pisar `suggestedQuantity` del ticket F3
- Cambiar reglas 4.0 stop/size ni 4.1 `NO_NEW_LONGS`
- UI nueva más allá del chip ya existente

---

## 3. Diseño mapper (borrador)

```text
expired? → EXPIRED
regime blocks long? → BLOCKED (+ regime)          # 4.1
!fit / !freshness / !mandate → BLOCKED
wait/reduce/none → WATCH entry
!stop → WATCH no_stop
setup ≠ none AND !entry_ready → ARMED (+ entry)   # 4.3
!entry_ready (setup == none) → WATCH entry        # 4.2 sin patrón
else → TRIGGERED + size                           # ready + stop
# entrySetup siempre rellenado (puede ser "none"); ARMED exige setup ≠ none
```

**Confirm:** rebuild sin barras/ATR/bias → setup `none`, sin stop → `WATCH`/`no_stop` (D5). Nunca `ARMED` por omisión.

**Invariant:** Ranking ≠ BUY. `ARMED` ≠ permiso de fill. `TRIGGERED` sigue siendo el único status Plan candidato a BUY operativo (junto a `check_opening` ALLOW + firma humana).

---

## 4. Batería pactada

- ruff touched Python (`trade_plan.py` + tests application)
- `pnpm test:decision-spine` (hoy **81**; +casos ARMED ≥2–3 → esperado **83–84**)
- vitest `@bolsa/shared` solo si tocamos el tipo (no esperado: `ARMED` ya está en `TradePlanStatusV1`)

---

## 5. Criterio de cierre 4.3

1. Stop + `entrySetup=breakout` + bias ausente/exhaustion → `ARMED`, qty 0, `executionAllowed=false`.
2. Golden A (breakout + bias + stop) → sigue `TRIGGERED` + size > 0.
3. Confirm/rebuild sin barras → no `ARMED` inventado.
4. Diff `check_opening` vacío; stop/size/régimen/EntrySetup priority intactos.
5. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D7)

```text
Implementar Ciclo 4.3 ARMED según plan-ciclo-43-armed-entrysetup-2026-08-25.md.
D1=solo ARMED en mapper · D2=ARMED=stop+setup≠none+!ready · D3=wyckoff stub 4.2 · D4=transición tras no_stop · D5=confirm sin barras no arma · D6=sin contract:gen · D7=sin UX Why nueva.
No check_opening · no Wyckoff formal · no thesis health · no F9-B/purge/broker.
```
