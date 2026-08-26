# Audit pack — estado global v1.12-beta (Operational Reliability)

> **AsOf:** 2026-08-26 · **Tag:** **`v1.12-beta`** (SHA = commit del stamp; pin docs post Release tag CI GREEN).
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · roadmap [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035 · pack previo [`audit-pack-estado-global-2026-08-26-v111.md`](./audit-pack-estado-global-2026-08-26-v111.md).
> **Partida:** `v1.11-beta` → `76d0f951`.
> **Para:** auditoría externa / GitHub Actions Release tag CI.

---

## 0. Veredicto interno

Operational Reliability v1.12 **CERRADA (D0 + OR-1…OR-6)**: idempotencia E2E Confirm paper, crash/restart con `DurableSubmitIntent` → `UNKNOWN`, state machine PaperOrder, veto de apertura por recon drift / live unavailable, suite de escenarios A–L (+ retry + crash) en Decision Spine, y certificación SEMI con readiness de 4 estados + CTA `Ejecutar en PAPER|LIVE` + UI preferencia venue por cuenta. Producto sigue **BETA / no producción**. Confirm = **única** firma transaccional. Accept estricto **NO**. `PAPER_D_EXECUTE` repo **OFF**. LIVE **experimental** (nunca `PAPER_READY` / nunca trading accepted).

| Slice | Nombre                          | Estado  |
| ----- | ------------------------------- | ------- |
| D0    | Diseño / triage + ADR-035       | CERRADO |
| OR-1  | End-to-end idempotency          | CERRADO |
| OR-2  | Crash/restart recovery          | CERRADO |
| OR-3  | Full order state machine        | CERRADO |
| OR-4  | Reconciliation → opening veto   | CERRADO |
| OR-5  | Broker execution scenario suite | CERRADO |
| OR-6  | SEMI operational certification  | CERRADO |

**Mensaje clave:** v1.11 **integró** post-fill; v1.12 **valida** timeout, retry, crash, drift y readiness operativa. **No** Accept estricto. **No** default-on execute. **No** AUTO on. **No** broker producción.

---

## 1. Batería (local, pre-tag / 2026-08-26)

| Gate                                                              | Resultado                                          |
| ----------------------------------------------------------------- | -------------------------------------------------- |
| `pnpm test:decision-spine`                                        | **433** passed                                     |
| OR pytest (ops-self-eval + readiness + OR-5 + recon gate + venue) | **42** passed                                      |
| Vitest mesa bar + account venue                                   | **5** passed                                       |
| Vitest shared readiness / veto / submit-intent                    | **13** passed                                      |
| Release tag CI                                                    | `release-tag-ci.yml` — al pushear tag `v1.12-beta` |

```bash
pnpm test:decision-spine
python -m pytest packages/py/application/tests/test_ops_self_eval.py \
  packages/py/application/tests/test_operational_readiness.py \
  packages/py/application/tests/test_or5_broker_execution_scenarios.py \
  packages/py/application/tests/test_reconciliation_opening_gate.py -q
pnpm --filter @bolsa/web exec vitest run \
  src/features/operations/mesa-operational-bar.test.tsx \
  src/features/accounts/account-venue-preference.test.tsx
pnpm --filter @bolsa/shared exec vitest run \
  src/operational-readiness.test.ts \
  src/reconciliation-opening-veto.test.ts \
  src/submit-intent.test.ts
```

Spine progression: **367** (v1.11) → **372** (OR-1) → **382** (OR-2) → **387** (OR-3) → **403** (OR-4) → **418** (OR-5) → **433** (OR-6).

---

## 2. Qué entra en el tag

- **OR-1:** `decision_id` canónico · `INT-`/`ORD-` estables · short-circuit pre-`adapter.submit`.
- **OR-2:** `DurableSubmitIntent` pre-submit · recovery `UNKNOWN` sin re-POST · store InMemory de proceso.
- **OR-3:** PaperOrder `CREATED…FILLED` + `REJECTED`/`CANCELLED`/`EXPIRED`/`UNKNOWN` · PaperBroker boom → `UNKNOWN`.
- **OR-4:** OI-6 `drift` / LR-1 live `drift|unavailable` → DENY aperturas; exits ALLOW; sin auto-heal.
- **OR-5:** `test_or5_broker_execution_scenarios.py` A–L + retry + crash anclado a spine.
- **OR-6:** `operationalReadiness` 4 estados · CTA `Ejecutar en PAPER|LIVE` · chip mesa · UI preferencia cuenta.
- ADR-035 · roadmap v1.12 · pack v112 · HELP sync · `CURRENT_SYSTEM.md`. ADR-034 intacto (integridad).

---

## 3. Qué no entra / parked

| Excluido                            | Notas                                          |
| ----------------------------------- | ---------------------------------------------- |
| Accept estricto P1–P5               | Deuda; DoD runbook §4 + palabra **thaw**       |
| `PAPER_D_EXECUTE` default on        | Opt-in local; repo **off**                     |
| AUTO on / AUTO como modalidad       | Confirm = firma                                |
| Alembic DurableSubmitIntent         | Store proceso; Redis multi-worker parked       |
| UI resolución recon / auto-heal     | Detect → Explain → Require resolution (futuro) |
| Live trading accepted / XTB capital | LIVE experimental only                         |
| Simulación 1k–10k sesiones          | Post-v1.12                                     |
| `contract:gen` por campo OE-1       | Campo aditivo sin regen obligatorio            |
| Thin 5.x/8.x / brokers nuevos       | Congelados                                     |

---

## 4. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-035 → código → tests → HELP → OE-1 scorecard + readiness

Confirm SEMI = firma
OE-1 = medir (SEMI · AUTO) ≠ autorizar
Readiness = 4 estados discretos (sin %)
Venue: memory ?? redis ?? account ?? env ?? paper
Un FAIL crítico no se promedia · AUTO FAIL no tumba PAPER_READY
```

---

## 5. Freeze (v1.12)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · Confirm = firma · thin 5.x/8.x congelados · I1–I3 + RX1 · OI-1…OE-1 **no se reabren** · OR-1…OR-6 **no se reabren** · `PAPER_D_EXECUTE` **off** · mesa default **paper** · LIVE experimental · Accept estricto **parked** · **BETA / no producción**.

---

## 6. Docs clave (lectura auditor)

| Tipo       | Documento                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------- |
| SoT vivo   | [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)                                                                                      |
| Contrato   | [`035-operational-reliability.md`](../adr/035-operational-reliability.md)                                                        |
| Integridad | [`034-operational-integrity-continuity.md`](../adr/034-operational-integrity-continuity.md)                                      |
| Roadmap    | [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)                     |
| Triage     | [`audit-ext-v111-operational-reliability-triage-2026-08-26.md`](./audit-ext-v111-operational-reliability-triage-2026-08-26.md)   |
| Relevo tag | [`traspaso-relevo-tag-v1-12-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-12-beta-2026-08-26.md)                                 |
| OR-6       | [`plan-or6-semi-operational-certification-2026-08-26.md`](./plan-or6-semi-operational-certification-2026-08-26.md) · relevo OR-6 |
| Pack prev. | [`audit-pack-estado-global-2026-08-26-v111.md`](./audit-pack-estado-global-2026-08-26-v111.md)                                   |
| Thaw deuda | [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md)                                       |

---

## 7. Checklist auditor (E1)

1. Checkout tag **`v1.12-beta`** (SHA del stamp; contrastar pin docs post-CI).
2. Verificar GitHub Actions **`release-tag-ci.yml`** GREEN en el push del tag.
3. Ejecutar `pnpm test:decision-spine` → esperar **433** passed.
4. Contrastar ADR-035 (OR-1…OR-6) con código: idempotencia, DurableSubmitIntent, state machine, opening veto, suite A–L, readiness + CTA.
5. Confirmar freeze §5: sin Accept estricto, sin default-on, sin AUTO on, mesa paper, Confirm = firma, LIVE experimental.
6. Opcional SEMI UI: TRIGGERED → Confirm → CTA `Ejecutar en PAPER` · chip readiness ≠ Autoeval.
7. Emitir triage/findings si aplica (`audit-ext-*-triage-*.md`).

**Preguntas que este pack no resuelve:** Accept estricto · default-on · AUTO on · Alembic intent durable · UI resolución recon · broker producción · mass sim.
