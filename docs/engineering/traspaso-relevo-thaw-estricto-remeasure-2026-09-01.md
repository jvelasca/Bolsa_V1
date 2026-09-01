# RELEVO — Thaw estricto re-measure (2026-09-01)

> **Padre:** [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md) · ADR-023 **Accepted BETA-D** (sin Accept estricto).  
> **Fase:** C1 remeasure semanal **W+3 2026-09-01**.  
> **Método:** `node scripts/thaw_estricto_snapshot.mjs` (API `http://127.0.0.1:8000` UP · Postgres `bolsa-postgres` UP).

---

## 0. Gobernanza (sin cambios)

| Guardrail                           | Medido                                         |
| ----------------------------------- | ---------------------------------------------- |
| Accept estricto                     | **NO**                                         |
| `PAPER_D_EXECUTE`                   | **false** (`paperDExecuteEnv=false`, kill off) |
| `stance=buy` inventado / fills fake | **NO**                                         |
| Código tocado                       | **NO** (solo docs)                             |

---

## 1. Resultados P1–P5 (estricto)

| #      | Umbral                             | Medido 2026-09-01                                                          | Pass            |
| ------ | ---------------------------------- | -------------------------------------------------------------------------- | --------------- |
| **P1** | ≥60 días con dictámenes            | **34** (`daysWithOpinions`; gap **26**)                                    | **FAIL**        |
| **P2** | ≥50 SEMI Confirm fills seed DEMO   | **2** confirm seed · **8** journal_seed · **0** buys_seed · buys_testish=0 | **FAIL**        |
| **P3** | Precisión BUY-alarma 5d ≥70%       | `buyPrecision5d=null` · `alarmaBuyCount=0` · `matureBuySample=0`           | **FAIL**        |
| **P4** | Recall BUY ≥55%                    | `buyRecall5d=0.0` · `recallCaught=0` / `recallMoveSample=4544`             | **FAIL**        |
| **P5** | MaxDD trading ≤ min(10%, 1.2× Lab) | `trade_like=0` · cash proxy **0.20%** (no válido sin trades)               | **WARN / FAIL** |

**Veredicto estricto:** **0/5 PASS** · deuda estricto **abierta** · BETA-D + waivers W2–W4 **sin levantar**.

---

## 2. Delta vs W+2 (2026-08-26)

| Métrica               | W+2                  | W+3                             |
| --------------------- | -------------------- | ------------------------------- |
| P1 días               | 28                   | **34** (+6)                     |
| P2 confirm seed       | 1                    | **2** (+1)                      |
| P3/P4 alarma / mature | API down             | **0 / 0** (telemetría completa) |
| P4 recall sample      | —                    | **4544** moves                  |
| P5                    | 0 trades · 0.2% cash | igual                           |

---

## 3. Evidencia

- Snapshot CLI (read-only): `scripts/thaw_estricto_snapshot.mjs`
- Fila registrada: runbook §3 tabla **W+3 2026-09-01**
- Health mismo momento: `components.risk.paperDExecuteEnv=false`

---

## 4. Next (owner, no métricas fake)

1. **P1:** seguir EOD Estudio/Asesor (~26 días laborables más hacia 60).
2. **P2:** SEMI Confirm en `default-account-seed` (48 confirms restantes hacia 50).
3. **P3/P4:** esperar `stance=buy` natural del motor; re-medir cuando `alarmaBuyCount>0`.
4. **P5:** re-correr tras `trade_like>0` + anotar Lab MaxDD.
5. Próxima fila **W+4** en runbook §3.
