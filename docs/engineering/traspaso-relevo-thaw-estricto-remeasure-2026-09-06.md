# RELEVO — Thaw estricto re-measure (2026-09-06)

> **Padre:** [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md) · ADR-023 **Accepted BETA-D** (sin Accept estricto).  
> **Fase:** C1 remeasure post–W+3 · **W+4 2026-09-06**.  
> **Método:** `node scripts/thaw_estricto_snapshot.mjs` + `node scripts/ops_operativa_self_eval.mjs --account=default-account-seed` (API UP).  
> **Agente:** [B1 remasure](c398568f-d27a-456f-b9bd-1043d0b345cd).  
> **Regla:** measure ≠ Accept · **no** `PAPER_D_EXECUTE` flip · **no** `brokerVenue=live` · **no** código producto.

---

## 0. Gobernanza (sin cambios)

| Guardrail                           | Medido                                                       |
| ----------------------------------- | ------------------------------------------------------------ |
| Accept estricto                     | **NO**                                                       |
| `PAPER_D_EXECUTE`                   | **false** (`paperDExecuteEnv=false`; kill `effective=false`) |
| `brokerVenue`                       | **paper** (`accountPref=unset`)                              |
| `stance=buy` inventado / fills fake | **NO**                                                       |
| Código de producto tocado           | **NO** (solo remasure / docs)                                |

---

## 1. Resultados P1–P5 (estricto)

| #      | Umbral                                              | Medido 2026-09-06                                                          | Pass            |
| ------ | --------------------------------------------------- | -------------------------------------------------------------------------- | --------------- |
| **P1** | ≥60 días con dictámenes                             | **39** (`daysWithOpinions`; gap **21**)                                    | **FAIL**        |
| **P2** | ≥50 SEMI Confirm fills seed DEMO                    | **2** confirm seed · **8** journal_seed · **0** buys_seed · buys_testish=0 | **FAIL**        |
| **P3** | Precisión BUY-alarma 5d ≥70%                        | `buyPrecision5d=null` · `alarmaBuy=0` · `mature=0`                         | **FAIL**        |
| **P4** | Recall BUY ≥55%                                     | `buyRecall5d=0` · caught **0** / **7542** moves                            | **FAIL**        |
| **P5** | MaxDD trading ≤ min(10%, 1.2× Lab) y `trade_like>0` | `trade_like=0` · cash proxy **0.20%** (inválido)                           | **WARN / FAIL** |

**Veredicto estricto:** **0/5 PASS** · deuda estricto **abierta** · BETA-D + waivers W2–W4 **sin levantar**.

OE-1: SEMI **PASS** · AUTO **FAIL** (`strictAcceptReady=false`).

---

## 2. Delta vs W+3 (2026-09-01)

| Métrica                 | W+3       | W+4 (2026-09-06) | Δ                 |
| ----------------------- | --------- | ---------------- | ----------------- |
| P1 días                 | 34        | **39**           | **+5**            |
| P2 confirm seed         | 2         | **2**            | 0                 |
| P3/P4 alarma / mature   | 0 / 0     | **0 / 0**        | 0                 |
| P4 recall sample        | 4544      | **7542**         | +sample; caught=0 |
| P5 trade_like · cash DD | 0 · 0.20% | **igual**        | 0                 |
| `paperDExecuteEnv`      | false     | **false**        | OK                |

---

## 3. Evidencia

- `scripts/thaw_estricto_snapshot.mjs`
- `scripts/ops_operativa_self_eval.mjs --account=default-account-seed`
- Health: `paperDExecuteEnv=false` · venue paper

---

## 4. Qué NO afirmar

1. Accept estricto / `strictAcceptReady`.
2. P5 PASS por cash MaxDD sin `trade_like>0`.
3. Precisión/recall útiles con `alarmaBuy=0`.
4. Que el remasure autorice flip execute o venue live.
5. Levantar W2–W4 o amend ADR-023 a Accepted estricto.

---

## 5. Next (owner, no métricas fake)

1. **P1:** ~**21** días laborables más hacia 60.
2. **P2:** **48** confirms restantes en `default-account-seed`.
3. **P3/P4:** re-medir cuando `alarmaBuyCount>0` (natural).
4. **P5:** tras `trade_like>0` + Lab MaxDD.
5. Fila registrada en runbook §3 como **W+4 2026-09-06**.
