# Thaw readiness audit — Camino D / AUTO (E1.5) · 2026-08-25

> **Checklist run only.** Flag remains **off**. This document does **not** authorize thaw.  
> **AsOf:** 2026-08-25 · HEAD audit base **`b759a55`** (post Ciclo 8.2)  
> **Padres:** [ADR-023](../adr/023-camino-d-thaw.md) (Proposed) · [checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) · [A2–A5 prep](./camino-d-a2-a5-prep-2026-08-04.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md) · [audit pack A0–A5](./audit-pack-pre-auto-a0-a5-2026-08-04.md)

---

## Verdict

**NOT READY TO THAW.**

P1–P5 were **measured** 2026-08-25 against live `bolsa_v1` — all fail or invalid. Detail: [`thaw-p1-p5-measurement-2026-08-25.md`](./thaw-p1-p5-measurement-2026-08-25.md). Prep A0–A5 code behind flags is present; that does **not** satisfy the product gate.

**Actual thaw** requires, in order:

1. Owner accumulates until P1–P5 pass (see measurement «Qué falta»).
2. Owner says the literal word **thaw** again with green rows.
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
| **P1**  | ≥60 días DEMO con dictámenes estables     | ❌     | **Measured:** 28 distinct opinion days (`2026-07-22`…`2026-08-25`); A0 `daysWithOpinions=28`. Need ≥60.                                                                                                                                                                                                                |
| **P2**  | ≥50 operaciones SEMI Confirm (fills DEMO) | ❌     | **Measured:** 0 `confirm` sessions · 0 journal · 0 buys on `default-account-seed`. 16 propose-only sessions.                                                                                                                                                                                                           |
| **P3**  | Precisión BUY proxy 5d ≥70%               | ❌     | **Measured:** `buyPrecision5d=null` · `alarmaBuyCount=0` · no `stance=buy` rows in opinions.                                                                                                                                                                                                                           |
| **P4**  | Recall ≥55%                               | ❌     | **Measured:** `buyRecall5d=0.0` (0 caught / 4650 moves ≥+2%/5d).                                                                                                                                                                                                                                                       |
| **P5**  | MaxDD DEMO ≤ min(10%, 1.2× MaxDD Lab)     | ⚠      | **Measured:** cash proxy 0.2% on seed (deposit+fee only; 0 trades). Lab MaxDD n/d — **not a valid trading MaxDD**.                                                                                                                                                                                                     |
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

| Gate                  | Result                                               |
| --------------------- | ---------------------------------------------------- |
| P1–P5 product metrics | **FAIL** — measured 2026-08-25 (see measurement doc) |
| P6–P8 prep vs product | **PARTIAL** — code/prep only                         |
| P9–P10 governance     | **PARTIAL** — drafts only; not Accepted              |
| `PAPER_D_EXECUTE`     | **OFF** (defaults unchanged)                         |
| **Thaw**              | **NOT READY**                                        |

---

## Next step (owner)

Close gaps in [`thaw-p1-p5-measurement-2026-08-25.md`](./thaw-p1-p5-measurement-2026-08-25.md) §«Qué falta», then say **thaw** again before any ADR Accept / env flip.
