# ADR-035: Operational Reliability — validar el sistema (contrato v1.12)

**Estado:** Accepted — **D0 docs CERRADO.** **OR-1…OR-6 CERRADOS** (código). Fase v1.12 **cerrada en pack + tag** (`v1.12-beta`).  
**Fecha:** 2026-08-26  
**Contexto:** Auditoría externa post-`v1.11-beta` (`76d0f951`). Operational Integrity (ADR-034) **cerrada**. El modelo sobrevive al fill; falta demostrar que sobrevive a timeout, retry, crash, drift y estado de broker desconocido.

**Depende de:** [ADR-034](./034-operational-integrity-continuity.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · triage [`audit-ext-v111-operational-reliability-triage-2026-08-26.md`](../engineering/audit-ext-v111-operational-reliability-triage-2026-08-26.md) · roadmap [`roadmap-v112-operational-reliability-2026-08-26.md`](../engineering/roadmap-v112-operational-reliability-2026-08-26.md).

---

## 1. Decisión

**Validar, no expandir.** v1.12 no añade indicadores, IA, páginas, rankings, modelos ML ni brokers. Convierte el Operational Integrity Layer en un sistema **operacionalmente determinista** bajo fallos.

```text
v1.11  MODELO  🟢 fuerte
v1.12  REALIDAD  🟠 validar  ← esta fase
```

Este documento **acepta el contrato de fiabilidad**. OR-1…OR-6 son los únicos objetivos. El código empieza en OR-1 (chat siguiente), no en este ADR.

Nombre de tag: **`v1.12-beta`**. No confundir con notas históricas CORE-R que decían «v1.12».

---

## 2. Dos gates de riesgo (no es omisión)

El camino HTTP manual **no** pasa por `risk_signature`. Eso es política, no un bug.

| Camino           | Origen                 | Gate                                                                 |
| ---------------- | ---------------------- | -------------------------------------------------------------------- |
| **AI_SEMI**      | TradePlan `TRIGGERED`  | `RiskSignature` (`require_triggered_plan` → `no_tradeplan`)          |
| **HUMAN_MANUAL** | `origin: HUMAN_MANUAL` | **ManualTradeRiskGate** = `check_opening` en buy; sell skip apertura |

Ambos terminan en `PositionState` (OI-1). `ManualTradeRiskGate` nombra la política I1 existente. **No** un segundo motor. **No** forzar TradePlan de IA a la operativa manual.

---

## 3. Seis objetivos (OR-1…OR-6)

| ID   | Contrato                                                                              | Fuera de este ID                    |
| ---- | ------------------------------------------------------------------------------------- | ----------------------------------- |
| OR-1 | Retry Confirm paper = 1 fill / 1 posición / misma identidad · **CERRADO**             | Alembic · live e2e                  |
| OR-2 | Crash tras submit → `UNKNOWN` reconstruible; mapeo intent ↔ venue order · **CERRADO** | Heal · Alembic · Redis multi-worker |
| OR-3 | State machine de orden más allá de `CREATED`/`FILLED` · **CERRADO**                   | Broker producción · OCO             |
| OR-4 | Recon `drift` / live `unavailable` = veto **global de apertura** · **CERRADO**        | Auto-heal · UI de resolución        |
| OR-5 | Suite de escenarios A–L + retry + crash en el Decision Spine · **CERRADO**            | Simulación masiva post-v1.12        |
| OR-6 | Readiness 4 estados + CTA `EJECUTAR EN PAPER\|LIVE` · **CERRADO**                     | Thaw estricto · AUTO on             |

**OR-4 (veto):** `DRIFT` → no new entries · Allow protective / manual de-risk · Require human resolution. Detect → Explain → Require resolution. **Nunca** auto-heal.

**OR-6 (readiness):** `PAPER_READY` · `PAPER_DEGRADED` · `LIVE_EXPERIMENTAL` · `LIVE_BLOCKED`. Un FAIL crítico (p.ej. recon = 0) **no** se promedia a «50 % listo». OE-1 sigue **measure ≠ Accept**.

---

## 4. LIVE experimental · AUTO no es modalidad

- `XtbBrokerAdapter` + `POST /orders` = **puerto de experimento**, no de capital.
- `submitted ≠ fill`. Producto **BETA / no producción**.
- Clasificación: LIVE ADAPTER WIRED · LIVE TRADING **NOT ACCEPTED**.
- AUTO **no** significa IA → BUY. Significa Opportunity → TradePlan → Risk → Portfolio permission → Execution policy → Order, y cada paso puede bloquear. Confirm sigue siendo la **única** firma transaccional. `PAPER_D_EXECUTE` default **OFF**.

---

## 5. Parked (deuda deliberada)

- Tabla `position_revisions` (hoy JSON en snapshot).
- JSONB `position_state` como SoT → columnas (JP-1 dual-write se conserva).
- ExecutionRecord como entidad fuerte (OR-1 no la crea; OR-2 si la identidad durable lo exige).
- Más brokers (IBKR, etc.).
- AUTO on · thaw estricto · Accept P1–P5.
- Simulación 1.000–10.000 sesiones (después de cerrar OR-1…OR-6).

---

## 6. Freeze

ADR-034 intacto · Confirm = única firma · Lab ≠ mesa · thin 5.x/8.x congelados · I1–I3 + RX1 · `PAPER_D_EXECUTE` off · mesa default paper · no `contract:gen` en OR-1…OR-3 · no Alembic en OR-1…OR-3.

---

## 7. Consecuencias

- Docs: triage v111 reliability · roadmap v1.12 · plan OR-1 · plan OR-2 · plan OR-3 · plan OR-4 · plan OR-5 · plan OR-6 · relevo OR-6.
- Código: **OR-1 CERRADO** — short-circuit Confirm · ids estables · fail-closed sin `decision_id`. **OR-2 CERRADO** — `DurableSubmitIntent` pre-submit · recovery `UNKNOWN` sin re-POST · mapeo `venue_order_id`. **OR-3 CERRADO** — `PaperOrder` Literal + grafo · PaperBroker `SUBMITTED`→`FILLED`/`UNKNOWN` · crash recovery `paperOrder.status=UNKNOWN`. **OR-4 CERRADO** — recon → opening veto (`drift` / live `unavailable`); exits ALLOW; OE-1 OI-6 honesto; sin auto-heal. **OR-5 CERRADO** — suite A–L + retry + crash anclada a spine (15 tests certificación). **OR-6 CERRADO** — 4 estados de readiness (sin promedio) + CTA `Ejecutar en PAPER|LIVE` + UI preferencia cuenta.
- Spine: `pnpm test:decision-spine` **433** (partida v1.11 = 367 · post-OR-1 = 372 · post-OR-2 = 382 · post-OR-3 = 387 · post-OR-4 = 403 · post-OR-5 = 418 · post-OR-6 = 433).
- Siguiente: thaw estricto (deuda) · operar SEMI. Pack [`audit-pack-estado-global-2026-08-26-v112.md`](../engineering/audit-pack-estado-global-2026-08-26-v112.md) · relevo tag [`traspaso-relevo-tag-v1-12-beta-2026-08-26.md`](../engineering/traspaso-relevo-tag-v1-12-beta-2026-08-26.md).
