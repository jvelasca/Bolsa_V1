# Plan — P3 Una cadena de salida (ExitPlan → ExitPermission → SEMI)

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §4 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2.3 · relevo [`traspaso-relevo-p2-riesgo-al-firmar-2026-08-25.md`](./traspaso-relevo-p2-riesgo-al-firmar-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO.** D1–D8 OK · Confirm `exit_permission` · persist reduce · Operaciones advisory · HELP · spine **257**.
> **Método:** un puerto de producto. Lab `EvaluatePositionExits` intacto. Cero auto-exit CTA. Cero Consola. Cero `stopPrice` / OCO. Cero P4. Cero campos extra F1–F4.

---

## 0. Objetivo

Tras un fill P1, la mesa responde «si ocurre Y, ¿podemos salir / reducir ahora?» con **una** cadena: Position persistida → ExitPlan (propone) → ExitPermission (valida) → humano firma en SEMI → fill actualiza Position + ledger → Journal plan vs resultado.

```text
evento (mark / firma humana)
  → ExitPlan propone hold | protect | reduce | full_exit
  → ExitPermission ALLOW/DENY
  → SEMI Confirm execute (exit_hint / reduce)
  → applyReduce en position_states + ledger
  → Journal
```

### Qué entra vs qué queda fuera

| Incluye (P3)                                                                          | Excluye                                           |
| ------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Confirm execute `exit_hint`/`reduce` con Position OPEN → gate `exit_permission`       | Auto-exit CTA · `PAPER_D_EXECUTE` on              |
| Firma humana SEMI = señal `manual` (desriesgo; H2 kill switch intacto)                | Fusionar Lab `evaluate-exits` con ExitPlan        |
| Persist `applyReduce` tras fill de cierre; remaining deja de ser solo as-of apertura  | Consola de Mesa · P4                              |
| Operaciones: advisory `suggestedAction` (mark = lastPrice). **Sin** botón que ejecute | `stopPrice` · OCO · OrderIntent-dios              |
| Journal: plan vs resultado (`exitPlanId` / verdict / action)                          | Thin Hoy «Salida» rewire · mappers 5.x/8.x        |
| Tests familia D + HELP                                                                | Protect/BE persist (no hay acción SEMI protect)   |
| Delta mínimo openapi + schema.d.ts (no `regen_full`)                                  | `POST /portfolio/trade` sell como puerto producto |

---

## 1. Decisiones (D1–D8)

| Id     | Decisión                                                                                                                                                                                                 |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Un puerto = Confirm SEMI `exit_hint`/`reduce` **execute**. Lab `/position-policies/evaluate-exits` **intacto**. Thin Hoy «Salida» **sigue** thin (≠ ExitPlan). **No** nuevo endpoint de salida.          |
| **D2** | Evento de mesa: (a) GET cartera — `markPrice=lastPrice`, **sin** `manual` (advisory). (b) Confirm cierre — `manual=True` (humano firma desriesgo). Factory F3 **sin** campos extra.                      |
| **D3** | Gate solo si hay Position persistida abierta **y** `execute=True`. Sin fila → camino legado (holding plano; no se inventa plan). Aperturas: `check_opening` + `risk_signature` intactos.                 |
| **D4** | Rechazo `exit_permission` ≠ `risk_veto` ≠ `risk_signature`. `execute=False` no aplica. Kill switch: desriesgo humano SEMI **ALLOW** (H2). AUTO/`autoExecute` **fuera**.                                  |
| **D5** | Tras fill de cierre: `apply_position_reduce` + update fila. Idempotencia por `_lastExitTransactionId` en el JSONB (bookkeeping; **no** campo F2). Protect/BE **no** se graban (sin acción SEMI protect). |
| **D6** | Operaciones lee `exitPlan` advisory (`status`, `suggestedAction`, `primaryReason`). **No** CTA auto-exit. Venta directa `/portfolio/trade` **no** es este puerto (solo ledger).                          |
| **D7** | HELP: una cadena = ExitPlan → ExitPermission → SEMI. Lab Señales ≠ mesa. Thin «Salida» ≠ ExitPlan. Auto-exit no es CTA. Tras cierre firmado, el plan se reduce/cierra.                                   |
| **D8** | Tests D · HELP · stamp CURRENT_SYSTEM / CHANGELOG / ADR-033 / roadmap P3 · relevo. **E1:** P4 Consola **o** operar SEMI. **No** P4 en este chat.                                                         |

Si P3 fusiona Lab con ExitPlan, añade auto-exit CTA, Consola, `stopPrice`, o reabre F1–F4 con campos extra: **parar y replanificar**.

---

## 2. Ficheros

- `position_state.py` hydrate `position_state_from_dict` (inverso de `to_dict`; sin campos nuevos)
- `persist_position_from_exit.py` · `evaluate_exit_plan.py`
- `position_state_repository.py` `update_state`
- `confirm_recommendation.py` (gate + persist reduce) · `dependencies.py`
- `OperationalPositionDto.exitPlan` · extra_mappers · operations-panel
- Tests application Confirm/persist · HELP · stamp

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · `check_opening` · H1 pending honesty · H2 factories **sin campos extra** · P1 nacimiento · P2 firma · Dedup Hoy por símbolo · broker **no** · **no** OrderIntent-dios · **no** Consola.
