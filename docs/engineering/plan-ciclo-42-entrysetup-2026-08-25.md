# Plan — Ciclo 4.2 `EntrySetup` (refina `entry_ready`)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 · relevo [`traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md`](./traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md) · ancla en [`plan-ciclo-41-…`](./plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md) §5.
> **AsOf:** 2026-08-25 · HEAD **`f646d2a`** = `origin/main` (4.0+4.1 cerrados).
> **Estado:** **CERRADO en origin** (`a7eeaee` vía stamp `4930344`). D1–D6 OK 2026-08-25. Sin ARMED.
> **Método:** rebanada fina; no sustituye stop/size/`check_opening`; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Contrato `EntrySetup` = `breakout | pullback | wyckoff | none` que **refina** `entry_ready` (ADR-031: SETUP ≠ motor paralelo). Ranking sigue ≠ BUY. Golden A exige setup listo + stop + bias.

**No** es Position Manager / thesis health / trailing (Ciclo 5).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                       | Propuesta por defecto                                                                                                                                                                           |
| --- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada? | Contrato + clasificador determinista + cableado propose + campo `entrySetup` en `TradePlan.to_dict`. **Sin** motor Wyckoff completo.                                                            |
| D2  | ¿`wyckoff` en 4.2?             | **Stub:** clasificador puede devolver `wyckoff` solo con regla mínima (reclaim tras low falso en 3–5 barras); si no hay señal clara → `none`. Sin fases SOS/LPS formales (→ 4.3 si hace falta). |
| D3  | ¿Cuándo `entry_ready`?         | `entry_ready_from_ta` **y** `setup != "none"`. Bias/exhaustion siguen.                                                                                                                          |
| D4  | ¿Introducir `ARMED`?           | **No en 4.2.** Sigue `WATCH` (`entry` / `no_stop`) → `TRIGGERED`. `ARMED` = Ciclo 4.3 o 5.                                                                                                      |
| D5  | ¿Confirm sin barras?           | `setup=none` → no inventa ready (mismo patrón conservador 4.0/4.1).                                                                                                                             |
| D6  | ¿`contract:gen` / Board HTTP?  | **No.** Solo dict TradePlan en propose/confirm/Hoy payload (como hoy).                                                                                                                          |

Si D4 = sí ARMED ahora, replanificar (más tests + UX Why).

---

## 2. Alcance 4.2 (sí / no)

### Sí

| Pieza          | Regla                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Tipo           | `EntrySetup = Literal["breakout","pullback","wyckoff","none"]` (Python + mirror shared TS opcional si ya tipamos TradePlan)                      |
| Campo          | `TradePlan.entry_setup` → JSON `entrySetup`                                                                                                      |
| Breakout       | long: `close` > max(`high`) de 20 barras cerradas; short: `close` < min(`low`) 20 (excluye barra actual incompleta: `bars[-21:-1]` + last close) |
| Pullback       | long: bias bullish + `close` dentro de `1.0 × ATR` sobre SMA20 (o low de 5); short simétrico                                                     |
| Wyckoff (mín.) | long: mínimo de 5 barras cerradas < min de prev 10, y last close > ese mínimo (reclaim); short simétrico. Si no → no fuerza wyckoff              |
| Prioridad      | si varios matchean: `breakout` > `pullback` > `wyckoff` > `none`                                                                                 |
| Ready          | `entry_ready_from_ta(...) and setup != "none"`                                                                                                   |
| Propose        | clasificar con `ohlcv_bars` + atr + bias; pasar setup al builder                                                                                 |
| Tests          | A con breakout → TRIGGERED; bias OK sin setup → WATCH/`entry`; confirm sin barras → sin setup inventado                                          |
| Docs           | ADR-031 §6 nota 4.2; stamp + relevo                                                                                                              |

### No

- `ARMED` status machine
- Familias Lab (`donchian_breakout` / `pullback_in_uptrend` strategy types) como motor — solo heurística de barras en analytics
- `check_opening`, broker, F9-B, purge, thesis health, MFE
- `contract:gen`
- Pisar `suggestedQuantity`
- Cambiar reglas 4.0 stop/size ni 4.1 régimen

---

## 3. Diseño mapper (borrador)

```text
expired? → EXPIRED
regime blocks long? → BLOCKED (+ regime)          # 4.1
!fit / !freshness / !mandate → BLOCKED
wait/reduce/none → WATCH entry
!stop → WATCH no_stop
!entry_ready (bias/exhaustion/setup) → WATCH entry
else → TRIGGERED + size
# entrySetup siempre rellenado (puede ser "none")
```

---

## 4. Batería pactada

- ruff touched Python
- `pnpm test:decision-spine` (hoy **79**; +casos setup ≥3)
- vitest shared solo si tocamos `@bolsa/shared` TradePlan type

---

## 5. Criterio de cierre 4.2

1. Golden A con breakout artificial → `TRIGGERED` + `entrySetup=breakout`.
2. Bias OK + sin patrón → `WATCH`/`entry` + `entrySetup=none`.
3. Confirm rebuild sin barras → `none` / no ready inventado.
4. Diff `check_opening` vacío.
5. Relevo + stamp. Commit/push solo con OK.

---

## 6. Texto de arranque (tras OK D1–D6)

```text
Implementar Ciclo 4.2 EntrySetup según plan-ciclo-42-entrysetup-2026-08-25.md.
D1=contrato+clasificador · D2=wyckoff mínimo · D3=ready=ta+setup · D4=sin ARMED · D5=confirm sin barras=none · D6=sin contract:gen.
No check_opening · no thesis health.
```
