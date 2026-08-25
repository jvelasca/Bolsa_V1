# Thaw readiness audit — Camino D / AUTO (E1.5) · 2026-08-25

> **Checklist run only.** Flag remains **off**. This document does **not** authorize thaw.  
> **AsOf:** 2026-08-25 · HEAD audit base **`b759a55`** (post Ciclo 8.2)  
> **Padres:** [ADR-023](../adr/023-camino-d-thaw.md) (Proposed) · [checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) · [A2–A5 prep](./camino-d-a2-a5-prep-2026-08-04.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md) · [audit pack A0–A5](./audit-pack-pre-auto-a0-a5-2026-08-04.md)

---

## Verdict

**NOT READY TO THAW.**

P1–P5 have **no measured evidence** attached in repo (rows still ☐ in ADR-023). Prep A0–A5 code behind flags is present; that does **not** satisfy the product gate.

**Actual thaw** requires, in order:

1. Owner fills P1–P10 with concrete evidence (attach numbers / run IDs / dates).
2. Owner says the literal word **thaw**.
3. Then: ADR-023 → Accepted, freeze amend (Camino D thaw parcial), and only then opt-in `PAPER_D_EXECUTE=1` on a controlled DEMO.

This audit did **not** flip env, did **not** Accept ADR-023, did **not** amend freeze to authorize execute.

---

## Flag confirmation (unchanged)

| Check                                              | Result                                                                                                      |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `paper_d_execute_allowed()` default                | **off** unless env ∈ `{1,true,yes,on}` — `packages/py/application/src/bolsa_application/paper_d_propose.py` |
| `.env.example`                                     | `# PAPER_D_EXECUTE=0` (commented; not `=1`)                                                                 |
| `docker-compose.yml` / `docker-compose.ollama.yml` | **no** `PAPER_D_EXECUTE`                                                                                    |
| Local `.env`                                       | **absent** in this workspace (nothing setting `=1`)                                                         |
| ADR-023                                            | **Proposed** (not Accepted)                                                                                 |
| Freeze §8                                          | Prep A2–A5 ≠ thaw; evidencia P1–P5 pendiente                                                                |

---

## P1–P10 checklist audit

Legend: ✅ evidence · ⚠ partial · ☐ empty · ❌ blocked

| #       | Criterio                                  | Status | Evidence                                                                                                                                                                                                                                                                                                               |
| ------- | ----------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P1**  | ≥60 días DEMO con dictámenes estables     | ☐      | **No data in repo.** Telemetry _capability_ exists (`daily_opinion_telemetry.py` → `daysWithOpinions`; `GET …/telemetry`). ADR-023 row «P1 ≥60d» = `—` / ☐. No dump of day counts meeting ≥60.                                                                                                                         |
| **P2**  | ≥50 operaciones SEMI Confirm (fills DEMO) | ☐      | **No data in repo.** Outcomes / DecisionSession / ledger DEMO counts not attached anywhere under `docs/` or committed metrics. Checklist & ADR rows ☐.                                                                                                                                                                 |
| **P3**  | Precisión BUY proxy 5d ≥70%               | ☐      | **No data in repo.** A0 exposes `buyPrecision5d` but no recorded sample ≥70%. ADR-023 «P3» = ☐.                                                                                                                                                                                                                        |
| **P4**  | Recall ≥55%                               | ☐      | **No data in repo.** A0 exposes `buyRecall5d` / recall move sample; no attached ≥55%. ADR-023 «P4» = ☐.                                                                                                                                                                                                                |
| **P5**  | MaxDD DEMO ≤ min(10%, 1.2× MaxDD Lab)     | ☐      | **No data in repo.** No DEMO equity-curve MaxDD vs Lab comparison committed. ADR-023 «P5» = ☐.                                                                                                                                                                                                                         |
| **P6**  | 0 violaciones Gate en execute de prueba   | ⚠      | **Prep code + unit tests**, not product proof of zero violations on real AUTO executes (execute path still env-blocked). Risk Engine / `check_opening`: `risk_engine.py`, `test_risk_engine.py`, I1–I3 honesty (`paper_auto_http_gate.py`, RX1). Checklist marks ☐; cannot claim ✅ without measured test-execute log. |
| **P7**  | Kill switch &lt;1 s (UI + flag server)    | ⚠      | **Prep.** API `GET/POST /api/risk/kill-switch` (`routes/risk.py` · `risk_runtime.py`); UI Operativa / `demo-book-mode-panel.tsx`. **No** documented latency run proving &lt;1 s. Checklist: «Prep».                                                                                                                    |
| **P8**  | Confirmación doble UI para activar AUTO   | ⚠      | **Prep.** Armado local `ACTIVAR AUTO` — `demo-book-auto-arm.ts`; pill still off (`DEMO_BOOK_AUTO_UI_ENABLED=false` in `demo-book-auto-copy.ts`). Arm ≠ execute. Checklist: «Prep · pill sigue off».                                                                                                                    |
| **P9**  | ADR thaw con evidencia adjunta            | ⚠      | `docs/adr/023-camino-d-thaw.md` exists, estado **Proposed**. Tabla evidencia P1–P5 vacía (`—` / ☐). Not Accepted.                                                                                                                                                                                                      |
| **P10** | Amend freeze: thaw parcial / condicionado | ⚠      | Freeze note §8 documents **prep ≠ thaw** (`post-audit-decision-freeze-2026-08-03.md`). **No** Accepted amend authorizing Camino D execute. Checklist: «Nota prep · no Accepted».                                                                                                                                       |

### Prep code cross-check (A0–A5 / P6–P8 related)

| Fase                    | Status            | Path / note                                                                                               |
| ----------------------- | ----------------- | --------------------------------------------------------------------------------------------------------- |
| A0 telemetría           | Hecho (capacidad) | `daily_opinion_telemetry.py` · Asesor strip — **measures**, does not satisfy P1–P4 until numbers attached |
| A1 Libro AUTO UI        | Hecho (disabled)  | `DemoBookModePanel` · coerce auto→semi                                                                    |
| A2 execute detrás flag  | Hecho (flag off)  | `paper_d_propose.py` · idempotencia · DecisionSession                                                     |
| A3 kill + doble confirm | Hecho (prep)      | kill-switch API/UI · arm local                                                                            |
| A4 ADR + freeze nota    | Borrador          | ADR-023 Proposed · freeze §8                                                                              |
| A5 opt-in cuenta        | Hecho (gate)      | `PAPER_D_ACCOUNT_ID`                                                                                      |

---

## Gate summary

| Gate                  | Result                                  |
| --------------------- | --------------------------------------- |
| P1–P5 product metrics | **FAIL** — all ☐ empty                  |
| P6–P8 prep vs product | **PARTIAL** — code/prep only            |
| P9–P10 governance     | **PARTIAL** — drafts only; not Accepted |
| `PAPER_D_EXECUTE`     | **OFF** (defaults unchanged)            |
| **Thaw**              | **NOT READY**                           |

---

## Next step (owner)

Fill P1–P5 evidence (run Asesor telemetry + SEMI fill counts + DEMO MaxDD), then say the literal word **thaw** before any ADR Accept / freeze amend / `PAPER_D_EXECUTE=1`.
