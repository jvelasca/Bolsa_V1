# Roadmap — v1.9 Operational Core

> **Padre:** [`audit-ext-v181-triage-2026-08-25.md`](./audit-ext-v181-triage-2026-08-25.md) · ADR-032 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **FASE CERRADA (modelo).** F1–F4 + ExitPermission + INFRA cerrados. Tag **`v1.9-beta` → `7d90d965`**. Broker adapter **no**. Siguiente fase: [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **Método:** operación **realmente modelada**, no otro módulo thin. No thaw. No broker. No LLM.

---

## 0. Por qué esta fase

v1.8.1 dejó la base limpia. El siguiente salto no es un panel ni un score: es autoridad de **posición abierta**.

```text
TRADEPLAN
    │
    ▼
POSITION STATE
    │
    ├──────────┬──────────┐
    ▼          ▼
THESIS HEALTH  PROTECTION
    │          │
    └────┬─────┘
         ▼
     EXIT PLAN
         │
         ▼
  EXECUTION PLAN
         │
         ▼
      PAPER → SEMI → BETA AUTO / LIVE
```

Autoridad normativa:

```text
CURRENT_SYSTEM → ADR-032 → código → tests → HELP
```

---

## 1. Secuencia (no se salta)

| Slice     | Nombre                    | Qué                                                              | Estado ahora     |
| --------- | ------------------------- | ---------------------------------------------------------------- | ---------------- |
| **D0**    | Diseño / ADR-032 audit    | Congelar campos (gap doc) · **no código**                        | **CERRADO docs** |
| **INFRA** | CI reproducible por tag   | `on: push tags v*` sin path-filter · gates spine+shared+security | **CERRADO**      |
| **F1**    | TradePlan v1              | Campos gap §1 **dentro** de TradePlan · sin mapper hermano       | **CERRADO**      |
| **F2**    | PositionState             | Autoridad post-entrada · no promover thin 5.x/8.x                | **CERRADO**      |
| **F2.1**  | PositionState transitions | Mark / reduce / stop BE · `PARTIAL`/`PROTECTED`/`CLOSED`         | **CERRADO**      |
| **F3**    | ExitPlan                  | Razones canónicas · **≠** execution                              | **CERRADO**      |
| **F4**    | ExecutionPlan → PAPER     | Journal / Replay / Validation · **después** broker adapter       | **CERRADO**      |
| **EP**    | ExitPermission            | Veto salida / stop · **≠** check_opening · **≠** auto-exit       | **CERRADO**      |

**Fuera de v1.9 (siguen parked):** broker live · OCO · thaw estricto · ActionabilityScore predictivo · Daily Operating Console plena · `ActionIdentity` (salvo si F2 lo exige para no perder EXIT+ENTRY del mismo símbolo) · Expectancy histórica plena.

Cada slice: plan D1–D8 que cite ADR-032 + tests de invariante + HELP si el concepto es de usuario + stamp CURRENT_SYSTEM.

---

## 2. Freeze de fase

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 intactos · `PAPER_D_EXECUTE` **off** · broker **no** · **no** `contract:gen` hasta shape F1 estable · **no** optimizar con DEMO · **no** inflar tests por conteo.

Hoy / ActionQueue / C1 honesty **intactos** hasta que F2+ActionIdentity lo justifiquen.

---

## 3. Siguiente rebanada

**Cerrado.** No wire ExitPermission ni Consola de Mesa desde este roadmap. Fase viva = v1.10 Operational Authority (H1 honesty pending). Relevo: [`traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md`](./traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md).
