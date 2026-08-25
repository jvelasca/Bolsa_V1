# Deuda thaw estricto — runbook tracking (P1–P5) · 2026-08-25

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) §5 · [ADR-023](../adr/023-camino-d-thaw.md) Accepted **BETA-D**.  
> **AsOf baseline:** 2026-08-25 · fuentes [`thaw-p1-p5-measurement-2026-08-25.md`](./thaw-p1-p5-measurement-2026-08-25.md) · [`thaw-beta-adapted-remeasure-2026-08-25.md`](./thaw-beta-adapted-remeasure-2026-08-25.md).  
> **Regla:** medir ≠ Accept estricto · **no** inventar `stance=buy` · **no** `PAPER_D_EXECUTE=1` por este runbook · **no** broker live.

Helper opcional (solo lectura): `node scripts/thaw_estricto_snapshot.mjs`.

---

## 1. Baseline (estricto FAIL · BETA-D PASS + W2–W4)

| #      | Umbral estricto                    | Medido 2026-08-25                                                                        | Pass |
| ------ | ---------------------------------- | ---------------------------------------------------------------------------------------- | ---- |
| **P1** | ≥60 días distintos con dictámenes  | **28** (`2026-07-22`…`2026-08-25`) · A0 `daysWithOpinions=28`                            | ❌   |
| **P2** | ≥50 SEMI Confirm fills DEMO reales | **0** `confirm` · **0** journal · **0** buys seed · ~49 ledger buys = cuentas test       | ❌   |
| **P3** | Precisión BUY-alarma 5d ≥70%       | `buyPrecision5d=null` · `alarmaBuyCount=0` · `matureBuySample=0`                         | ❌   |
| **P4** | Recall BUY ≥55%                    | `buyRecall5d=0.0` · `recallCaught=0` / `recallMoveSample=4650`                           | ❌   |
| **P5** | MaxDD DEMO ≤ min(10%, 1.2× Lab)    | Cash proxy seed **0.2%** (deposit+fee) · **0 trades** → **no válido** como MaxDD trading | ⚠    |

**BETA-D (Accepted):** P1'–P5' PASS con waivers **W2** (fills live), **W3** (precisión diferida), **W4** (recall diferido). Ver remasure.

**Gap numérico (orientativo, no compromiso de fecha):**

| Criterio | Falta                                                          |
| -------- | -------------------------------------------------------------- |
| P1       | ≥**32** días laborables más con opiniones                      |
| P2       | ≥**50** confirms reales en `default-account-seed` (excl. test) |
| P3/P4    | ≥1 muestra madura `stance=buy` alarma; luego umbrales 70%/55%  |
| P5       | Curva equity **con trades** DEMO + MaxDD Lab de referencia     |

---

## 2. Cómo re-medir (exacto)

Prerrequisitos: API `http://127.0.0.1:8000` · Postgres docker `bolsa-postgres` · DB `bolsa_v1` · user `bolsa`.  
Cuenta DEMO canónica: `default-account-seed`.

### P1 + P3 + P4 — telemetría A0

```http
GET /api/instrument-daily-opinions/telemetry?lookbackDays=120
```

PowerShell:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/instrument-daily-opinions/telemetry?lookbackDays=120" |
  Select-Object -ExpandProperty data |
  Format-List daysWithOpinions, opinionRows, alarmaBuyCount, matureBuySample, buyPrecision5d, buyRecall5d, recallMoveSample, recallCaught
```

SQL cruzado P1 / stances (no inventar buys):

```sql
SELECT COUNT(DISTINCT as_of_bar_date) AS days,
       MIN(as_of_bar_date), MAX(as_of_bar_date), COUNT(*) AS rows
FROM instrument_daily_opinions;

SELECT stance, COUNT(*) FROM instrument_daily_opinions GROUP BY stance ORDER BY COUNT(*) DESC;
```

**Pass P1:** `daysWithOpinions` (o `COUNT(DISTINCT as_of_bar_date)`) ≥ **60**.  
**Pass P3:** `buyPrecision5d` ≥ **0.70** con `matureBuySample` > 0 (null = fail).  
**Pass P4:** `buyRecall5d` ≥ **0.55**.

Health (mismo momento):

```http
GET /api/health
```

Anotar `components.risk.paperDExecuteEnv` (esperado default **false** en repo).

### P2 — SEMI Confirm fills (excluir ruido test)

**Primario — sesiones Confirm:**

```sql
SELECT COUNT(*) AS confirm_sessions
FROM decision_sessions
WHERE kind = 'confirm';

SELECT COUNT(*) AS confirm_seed
FROM decision_sessions
WHERE kind = 'confirm' AND account_id = 'default-account-seed';

SELECT COUNT(*) AS journal_total FROM decision_journal_entries;
SELECT COUNT(*) AS journal_seed
FROM decision_journal_entries
WHERE account_id = 'default-account-seed';
```

**Ledger / transactions solo seed DEMO:**

```sql
SELECT type, COUNT(*)
FROM ledger_entries
WHERE account_id = 'default-account-seed'
GROUP BY type ORDER BY COUNT(*) DESC;

SELECT COUNT(*) AS buys_seed
FROM ledger_entries
WHERE account_id = 'default-account-seed' AND type ILIKE '%buy%';
```

**Anti-ruido — buys globales vs testish (mismo filtro que remasure BETA-D):**

```sql
WITH buys AS (
  SELECT le.account_id, a.name, COUNT(*) AS n
  FROM ledger_entries le
  JOIN investment_accounts a ON a.id = le.account_id
  WHERE le.type ILIKE '%buy%'
  GROUP BY 1, 2
)
SELECT
  COALESCE(SUM(n) FILTER (
    WHERE name ~* 'idempotency|stamp auth|tax test|test fees|http retry|position policy|sin policy|perfil custom'
  ), 0) AS buys_testish,
  COALESCE(SUM(n) FILTER (
    WHERE name !~* 'idempotency|stamp auth|tax test|test fees|http retry|position policy|sin policy|perfil custom'
  ), 0) AS buys_non_testish,
  COALESCE(SUM(n), 0) AS buys_all
FROM buys;
```

**Pass P2:** ≥**50** fills SEMI Confirm atribuibles a operativa DEMO real. Contar **`confirm` sessions** en seed (o journal `human_confirm` / buys seed). **No** sumar `buys_testish`. Baseline: confirm=0 · buys_seed=0 · buys_non_testish≈0 en seed.

```bash
docker exec bolsa-postgres psql -U bolsa -d bolsa_v1 -c "SELECT COUNT(*) FROM decision_sessions WHERE kind='confirm' AND account_id='default-account-seed';"
```

### P5 — MaxDD trading DEMO (+ Lab)

Solo válido si hay **trades** (buys/sells) en seed, no solo deposit+fee.

```sql
-- Actividad trading seed
SELECT COUNT(*) AS trade_like
FROM ledger_entries
WHERE account_id = 'default-account-seed'
  AND type NOT IN ('deposit', 'fee', 'withdraw');

-- Cash MaxDD proxy (misma query medición 2026-08-25)
WITH cash AS (
  SELECT executed_at, balance_after::float AS bal
  FROM ledger_entries
  WHERE account_id = 'default-account-seed'
  ORDER BY executed_at, created_at
),
peaks AS (
  SELECT executed_at, bal,
         MAX(bal) OVER (ORDER BY executed_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS peak
  FROM cash
)
SELECT COUNT(*) AS points,
       MIN(bal) AS min_bal,
       MAX(bal) AS max_bal,
       MAX(CASE WHEN peak > 0 THEN (peak - bal) / peak ELSE 0 END) AS max_dd_frac
FROM peaks;
```

Lab MaxDD: adjuntar medición Lab comparable (trial / Lab Health / informe acordado) el mismo asOf.  
**Pass P5:** MaxDD DEMO ≤ **min(10%, 1.2 × MaxDD Lab)** **y** `trade_like` > 0.

---

## 3. Checklist semanal + trayectoria

Registrar cada semana en nota corta (chat o anexo dated) — **números medidos**, no objetivos inventados.

| Semana                  | P1 días | P2 confirm seed | alarmaBuy / matureBuy | Prec / Recall | P5 trade_like · MaxDD  | Notas          |
| ----------------------- | ------: | --------------: | --------------------- | ------------- | ---------------------- | -------------- |
| **Baseline 2026-08-25** |      28 |               0 | 0 / 0                 | null / 0.0    | 0 · 0.2% cash inválido | BETA-D + W2–W4 |
| W+1                     |         |                 |                       |               |                        |                |
| W+2                     |         |                 |                       |               |                        |                |
| W+3                     |         |                 |                       |               |                        |                |
| W+4                     |         |                 |                       |               |                        |                |

**Trayectoria owner (acciones, no métricas fake):**

1. **P1:** mantener corrida Estudio/Asesor EOD (días laborables con dictámenes).
2. **P2:** operar SEMI Confirm en mesa DEMO seed hasta ≥50 confirms reales (no baterías de test).
3. **P3/P4:** dejar que el motor emita `stance=buy` cuando corresponda; **no** INSERT manual. Re-correr A0 cuando `alarmaBuyCount` > 0 y haya madurez 5 barras.
4. **P5:** tras fills reales, re-correr MaxDD seed + anotar Lab MaxDD.
5. Semanal: `node scripts/thaw_estricto_snapshot.mjs` (o §2 a mano) y pegar fila en la tabla.

**Hitos orientativos (no SLA):** P1 ≈ +5–6 días/semana laborable → ~6–8 semanas a 60d si no hay gaps; P2/P3/P4 dependen de operativa real.

---

## 4. Definition of done — levantar W2–W4 y Accept **estricto**

**No** Accept estricto en este documento. Cuando **todas** las filas verdes:

| Gate       | Condición                                                                                                                   |
| ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| P1–P5      | Pass estricto con evidencia dated (API + SQL) adjunta                                                                       |
| W2         | Levantado: ≥50 SEMI Confirm live seed (no test)                                                                             |
| W3         | Levantado: precisión ≥70% con muestra madura                                                                                |
| W4         | Levantado: recall ≥55%                                                                                                      |
| P5         | MaxDD trading válido + Lab                                                                                                  |
| Gobernanza | Owner dice **thaw** (estricto) de nuevo                                                                                     |
| ADR-023    | **Amend** nota: Accepted estricto (o sección «Estricto») + tabla evidencia · **no** reescribir BETA-D como si nunca existió |
| Freeze     | Amend §8: estricto cerrado; broker live **sigue** fuera                                                                     |
| Env        | Opt-in `PAPER_D_EXECUTE` solo si el owner lo decide **después** del amend; default repo puede seguir off                    |

Hasta entonces: ADR-023 permanece **Accepted BETA-D**; deuda estricto **abierta**.

---

## 5. Freeze residual

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · W3/W4 = sin claim precisión Estudio · snapshot helper ≠ autorización · I1/I3/RX1 intactos.
