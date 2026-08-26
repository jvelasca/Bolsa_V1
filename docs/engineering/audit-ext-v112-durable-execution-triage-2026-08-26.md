# Triage — Auditoría externa Durable Execution (post v1.12)

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) §5 · pack interno [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md).
> **Entrada:** informe externo post-tag **`v1.12-beta` → `369b5d1`** (cierre funcional `164e2ad`; CI Ruff `369b5d1`). Contraste contra ADR-035 OR-1…OR-6 y código real.
> **AsOf:** 2026-08-26. **Estado:** **RATIFICADO.** Operational Reliability v1.12 **CERRADA como release**; **OR-2 = PARTIAL** (lógico cerrado · físico InMemory). Siguiente = **V1.13 Durable Execution** (DEX-1…DEX-5).
> **Hijos:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · plan [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md) · relevo [`traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md`](./traspaso-relevo-audit-ext-v112-apertura-v113-2026-08-26.md).

---

## 0. Veredicto producto (ratificado)

El auditor acierta la **paradoja**: v1.12 implementó correctamente el _concepto_ `DurableSubmitIntent`, pero la durabilidad _física_ cross-PID sigue parked (InMemory de proceso). Tag `v1.12-beta` **no se invalida**; la certificación crash/restart baja a **PARTIAL (~70 %)**.

```text
v1.11   operación INTEGRADA     (ADR-034)
v1.12   operación VALIDADA      (lógica OR-1…OR-6)  ← tag OK; OR-2 físico incompleto
v1.13   operación DURABLE       (cross-PID)          ← esta auditoría
```

| Área                                                       | Auditor | Arbitraje Bolsa                                                                                         |
| ---------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------- |
| Arquitectura / Decision Spine                              | 🟢 9+   | **Aceptado.** Congelar dirección; no más módulos thin.                                                  |
| OR-1 idempotencia E2E                                      | 🟢      | **CERRADO.** `decision_id` → `intent_id` → `order_id` estables · short-circuit.                         |
| OR-3 order state machine                                   | 🟢      | **CERRADO.** CREATED…FILLED + ramas; UNKNOWN no terminal.                                               |
| OR-4 opening veto                                          | 🟢      | **CERRADO.** Drift / live unavailable → DENY aperturas; exits ALLOW; sin auto-heal.                     |
| OR-5 scenario suite                                        | 🟢      | **CERRADO.** A–L + retry + crash en spine.                                                              |
| OR-6 SEMI readiness                                        | 🟢      | **CERRADO.** 4 estados sin promedio; CTA venue.                                                         |
| OR-2 crash/restart                                         | 🟠 70 % | **PARTIAL.** Concepto + recovery OK; store InMemory **no sobrevive al PID**; tests = fake restart.      |
| LIVE real / AUTO                                           | 🔴      | **Correctamente NO.** Experimental / off.                                                               |
| Confirm God Use Case                                       | 🟠      | **Deuda controlada.** ~1516 líneas → DEX-4 (tras DEX-1/2).                                              |
| Solape OrderIntent/PaperOrder/SubmitIntent/ExecutionRecord | 🟠      | **Deuda controlada.** No refactor ahora.                                                                |
| `require=False` recon gate                                 | 🟡      | Producción inyecta lookups → `require=True`. Fail-open solo tests/legado. OperationalPolicy = post-DEX. |
| Human resolution / Incident                                | 🟠      | **Pendiente.** OR-4 = detect→veto; workflow = **DEX-3**.                                                |
| Property / invariant suite                                 | 🟡      | Unit/integration excelente; stochastic = **DEX-5**.                                                     |
| Prioridad = cerrar OR-2 físico                             | 🟢      | **Aceptado.** V1.13 = Durable Execution; primer código = **DEX-1**.                                     |

---

## 1. Hallazgo P0 — OR-2 no es durabilidad real

Evidencia en código:

| Pieza                                                                                                  | Hecho                                              |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| [`submit_intent_store.py`](../../packages/py/application/src/bolsa_application/submit_intent_store.py) | _«no sobrevive al PID»_ · _«Tabla PG = parked»_    |
| Alembic                                                                                                | Sin `submit_intents` (001–012)                     |
| Tests OR-2                                                                                             | Store compartido entre «procesos»; **no** kill PID |
| `send_attempted_durable`                                                                               | `intent is not None` = ya se intentó enviar        |

```text
Confirm → INSERT intent (memoria) → adapter.submit → APP CRASH
→ restart → InMemory vacío → no hay reconstrucción solo desde ese store
```

Recon puede detectar drift después; la **idempotencia de reintento** aún no está garantizada por identidad durable cross-PID.

**Arbitraje:** OR-2 = **PARTIAL / CONDITIONALLY CLOSED**.

| Cerrado (lógico)                          | Falta (físico)                    |
| ----------------------------------------- | --------------------------------- |
| UNKNOWN model · intent identity           | Persistencia PostgreSQL           |
| venue_order_id mapping · no blind re-POST | Tests crash/restart cross-proceso |
| Reconstruction logic en mismo worker      | `send_attempted` ≠ `recorded`     |

---

## 2. Scorecard P0 / P1 / P2 (post-v1.12 audit)

### P0 — V1.13

| #   | Claim del auditor                                           | Veredicto   | Dónde              |
| --- | ----------------------------------------------------------- | ----------- | ------------------ |
| 1   | PG `submit_intents` + persist before submit                 | **ABIERTO** | **DEX-1**          |
| 2   | Crash/restart real (proceso A → kill → proceso B)           | **ABIERTO** | **DEX-2**          |
| 3   | Fases `recorded` ≠ `send_attempted` (+ `send_attempted_at`) | **ABIERTO** | **DEX-1** (mínimo) |

### P1 — V1.13 después de DEX-1/2

| #   | Claim                                   | Veredicto     | Dónde                 |
| --- | --------------------------------------- | ------------- | --------------------- |
| 4   | OperationalIncident + resolución humana | **ABIERTO**   | **DEX-3**             |
| 5   | Confirm → orquestador + coordinators    | **ABIERTO**   | **DEX-4**             |
| 6   | Invariantes / property-based            | **ABIERTO**   | **DEX-5**             |
| 7   | Banner LIVE_BLOCKED + motivos en Mesa   | **PARKED UI** | Tras DEX-3 o slice UI |

### P2 — no ahora

| #   | Claim                                    | Veredicto  | Dónde                  |
| --- | ---------------------------------------- | ---------- | ---------------------- |
| 8   | LIVE trading accepted                    | **NO**     | Experimental           |
| 9   | AUTO on                                  | **NO**     | Off                    |
| 10  | position_revisions tabla / SoT columnas  | **PARKED** | JP-1 dual-write        |
| 11  | ExecutionRecord entidad DB fuerte        | **PARKED** | Tras identidad durable |
| 12  | OperationalPolicy (TEST/PAPER/SEMI/LIVE) | **PARKED** | Post-DEX o con DEX-5   |
| 13  | Simulación 1k–10k sesiones               | **PARKED** | Post-v1.13             |

---

## 3. Cerrado de verdad (v1.12 — no reabrir OR-1/3/4/5/6)

| Slice       | Qué es                                       | Qué no es         |
| ----------- | -------------------------------------------- | ----------------- |
| OR-1        | Idempotencia E2E paper en escenario modelado | Durabilidad PG    |
| OR-3        | State machine PaperOrder                     | Broker OMS        |
| OR-4        | Opening veto                                 | Incident workflow |
| OR-5        | Suite A–L + retry + crash (fake restart OK)  | Mass sim          |
| OR-6        | 4 estados + CTA venue                        | Thaw / AUTO       |
| OR-2 lógico | UNKNOWN + no re-POST mismo worker            | Cross-PID         |

Tag **`v1.12-beta` → `369b5d1`** permanece. Thin 5.x/8.x congelados. Confirm = única firma. `PAPER_D_EXECUTE` off. BETA.

---

## 4. Secuencia V1.13 (adoptada del auditor)

| Slice     | Nombre                    | Cierra                                                        |
| --------- | ------------------------- | ------------------------------------------------------------- |
| **D0**    | Triage + nota ADR-035     | Este stamp docs                                               |
| **DEX-1** | PostgreSQL SubmitIntent   | Tabla + store PG + fases mínimas + DI Confirm                 |
| **DEX-2** | Real crash/restart tests  | Persist → submit → store/cliente fresco → UNKNOWN · 0 re-POST |
| **DEX-3** | Reconciliation resolution | Incident → review → resolve → clear                           |
| **DEX-4** | Confirm decomposition     | Confirm = orquestador                                         |
| **DEX-5** | Operational invariants    | Batería formal anclada a spine                                |

---

## 5. Decisiones adoptadas (este stamp)

| #   | Decisión                                                 | Cuándo         |
| --- | -------------------------------------------------------- | -------------- |
| 1   | Congelar arquitectura v1.12; cerrar agujero físico OR-2  | Ya             |
| 2   | OR-2 docs → **PARTIAL** (no invalidar tag)               | Este stamp     |
| 3   | Extender ADR-035 (nota post-audit); no ADR-036           | Este stamp     |
| 4   | Primer código = **DEX-1** (Alembic `013` + PG store)     | Chat siguiente |
| 5   | No refactor Confirm / Incident / property suite en DEX-1 | Disciplina     |
| 6   | No LIVE / AUTO / thaw / Accept estricto                  | Freeze         |
| 7   | Pack auditor v113 = al tag v1.13                         | Cierre de fase |

---

## 6. Qué reutilizar / no inventar

**Reutilizar:** puerto `SubmitIntentStore`, `DurableSubmitIntent`, flujo `_record_before_submit` / `_try_recover_in_flight`, Alembic patrón `011`/`012`, DI en `dependencies.py`.

**No construir ahora:** segundo motor de riesgo, OrderIntent-dios, auto-heal, OMS broker, AUTO on, thin nuevos, Consola plena, mass sim.

---

## 7. Qué no hacer

- No declarar OR-2 «100 % cerrado» otra vez sin PG + test cross-PID.
- No indicadores / IA / páginas / rankings / ML en v1.13.
- No broker producción ni capital XTB.
- No default-on `PAPER_D_EXECUTE` · no AUTO on · no Accept estricto sin thaw.
- No auto-heal en reconciliación.
- No reabrir OR-1/3/4/5/6 ni OI-1…OE-1 a ciegas.
- No DEX-3…DEX-5 en el mismo chat que DEX-1.
