# RELEVO — Thaw estricto re-measure (2026-09-07)

> **Padre:** [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md) · [W+4](./traspaso-relevo-thaw-estricto-remeasure-2026-09-06.md) · [path pack](./audit-pack-thaw-estricto-path-post-v2101-2026-09-06.md) · [probe NO W+5](./traspaso-relevo-pista-a-probe-no-w5-2026-09-07.md).  
> **Fase:** C1 remasure post–probe · **W+5 2026-09-07**.  
> **Método:** stack UP → `node scripts/thaw_estricto_snapshot.mjs` + `node scripts/ops_operativa_self_eval.mjs --account=default-account-seed`.  
> **Regla:** measure ≠ Accept · **no** `PAPER_D_EXECUTE` flip · **no** `brokerVenue=live` · **no** código producto.

---

## 0. Gobernanza (sin cambios)

| Guardrail                           | Medido                                                       |
| ----------------------------------- | ------------------------------------------------------------ |
| Accept estricto                     | **NO**                                                       |
| `PAPER_D_EXECUTE`                   | **false** (`paperDExecuteEnv=false`; kill `effective=false`) |
| `brokerVenue`                       | **paper** (`accountPref=unset`)                              |
| `stance=buy` inventado / fills fake | **NO**                                                       |
| Código de producto tocado           | **NO** (arranque stack + remasure / docs)                    |

---

## 1. Resultados P1–P5 (estricto)

| #      | Umbral                                              | Medido 2026-09-07                                                          | Pass            |
| ------ | --------------------------------------------------- | -------------------------------------------------------------------------- | --------------- |
| **P1** | ≥60 días con dictámenes                             | **39** (`daysWithOpinions`; gap **21**)                                    | **FAIL**        |
| **P2** | ≥50 SEMI Confirm fills seed DEMO                    | **2** confirm seed · **8** journal_seed · **0** buys_seed · buys_testish=0 | **FAIL**        |
| **P3** | Precisión BUY-alarma 5d ≥70%                        | `buyPrecision5d=null` · `alarmaBuy=0` · `mature=0`                         | **FAIL**        |
| **P4** | Recall BUY ≥55%                                     | `buyRecall5d=0` · caught **0** / **7570** moves                            | **FAIL**        |
| **P5** | MaxDD trading ≤ min(10%, 1.2× Lab) y `trade_like>0` | `trade_like=0` · cash proxy **0.20%** (inválido)                           | **WARN / FAIL** |

**Veredicto estricto:** **0/5 PASS** · deuda estricto **abierta** · BETA-D + waivers W2–W4 **sin levantar**.

OE-1: SEMI **PASS** · AUTO **FAIL** (`strictAcceptReady=false`) · recon=`error`.

---

## 2. Delta vs W+4 (2026-09-06)

| Métrica                 | W+4       | W+5 (2026-09-07) | Δ                    |
| ----------------------- | --------- | ---------------- | -------------------- |
| P1 días                 | 39        | **39**           | **0**                |
| P2 confirm seed         | 2         | **2**            | 0                    |
| P3/P4 alarma / mature   | 0 / 0     | **0 / 0**        | 0                    |
| P4 recall sample        | 7542      | **7570**         | +28 sample; caught=0 |
| P5 trade_like · cash DD | 0 · 0.20% | **igual**        | 0                    |
| `paperDExecuteEnv`      | false     | **false**        | OK                   |

**Nota:** remasure válido tras stack UP; **sin delta de gates** (fila W+5 = sello de medida, no progreso).

---

## 3. Evidencia

- `scripts/thaw_estricto_snapshot.mjs`
- `scripts/ops_operativa_self_eval.mjs --account=default-account-seed`
- Health: `paperDExecuteEnv=false` · venue paper · API `:8000` OK · Postgres OK

---

## 4. Qué NO afirmar

1. Accept estricto / `strictAcceptReady`.
2. P5 PASS por cash MaxDD sin `trade_like>0`.
3. Precisión/recall útiles con `alarmaBuy=0`.
4. Que el remasure autorice flip execute o venue live.
5. Levantar W2–W4 o amend ADR-023 a Accepted estricto.
6. Progreso material vs W+4 (gates planos).

---

## 5. Next (owner, no métricas fake)

1. **P1:** ~**21** días laborables más hacia 60.
2. **P2:** **48** confirms restantes en `default-account-seed`.
3. **P3/P4:** re-medir cuando `alarmaBuyCount>0` (natural).
4. **P5:** tras `trade_like>0` + Lab MaxDD.
5. Fila registrada en runbook §3 como **W+5 2026-09-07**.
