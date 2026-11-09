# Evidencia del cierre de auditoría — 2026-11-09

Salidas literales de las comprobaciones hechas el `2026-11-09` entre las 11:30 y las 11:50 (hora local,
`Europe/Madrid`). Todas son **read-only** salvo la re-registración de tareas (§3) y el dump nuevo (§4),
y **ninguna toca `apps/` ni `packages/`**.

## 1. Tabla RANDOM/CSV

Artefacto: `operability_runs/dia-d-auto/control_entradas_aleatorias.json` (75 177 B, `09:58:59`), 100
ramas `random#0`…`random#99` más `csv` y `momentum`. Recalculado a las 11:30 con percentiles
interpolados: coincide en las siete métricas publicadas en
[`control-entradas-aleatorias-2026-11-09.md`](../../control-entradas-aleatorias-2026-11-09.md) §1.1.

Hallazgos nuevos que se fijan en el expediente:

- **Exposición media:** CSV **32,2 %** frente a mediana aleatoria **39,8 %** → percentil **1**.
- **Ciclos:** CSV **182** frente a mediana **204** → percentil **7**.

## 2. Puerta de barras

Lectura real de PostgreSQL (transporte `docker exec bolsa-postgres`, usuario `bolsa`, base `bolsa_v1`):

```text
2026-11-06 {"total":80,"covered":80,"error":null} {"ok":true,"ratio":1,"missing":0,"requiredCovered":76,"reason":null}
2026-11-09 {"total":80,"covered":0,"error":null}  {"ok":false,"ratio":0,"missing":80,"requiredCovered":76,"reason":"BARS_INCOMPLETE"}
```

Simulación del aborto (`WINDOW_BARS_MIN_COVERAGE=1`, `WINDOW_BARS_WAIT_SECONDS=0`, 11:47):

```text
[window] bars-gate: se agoto la espera de 0 s con 0/80 barras (0.0 %), faltan 80, minimo 80/80 [BARS_INCOMPLETE] — NO se mide el dia
[window] barras incompletas del 2026-11-09 (0/80, minimo 80/80) — dia NO terminal: sin fila en el ledger y sin medir
[window] dia 20261109 · INCOMPLETE_BARS (BARS_INCOMPLETE)
exit=1
```

`manifest.json` resultante (`operability_runs/window-runs/20261109/manifest.json`): `status =
INCOMPLETE_BARS`, `reason = BARS_INCOMPLETE`, `barsCoverage { covered: 0, total: 80, requiredCovered: 80,
attempts: 1, ok: false }`. `ledger.jsonl`: **0 filas** con `20261109`.

## 3. Tareas programadas

`node scripts/window-forward-runner.mjs task:install` (11:31) registró las cinco tareas. Verificación
POST-registro leyendo el XML del Programador (`schtasks /query /tn <t> /xml ONE`):

```text
tarea                  inicio               swa wake disallowBat stopBat
BolsaV1_StackReady     2026-11-09T17:33:00 True True       False   False
BolsaV1_StackReadyLate 2026-11-09T18:25:00 True True       False   False
BolsaV1_BarsSync       2026-11-09T17:40:00 True True       False   False
BolsaV1_WindowForward  2026-11-09T18:30:00 True True       False   False
BolsaV1_WindowWatch    2026-11-09T20:20:00 True True       False   False
```

`powercfg /query SCHEME_CURRENT SUB_SLEEP`:

```text
STANDBYIDLE    AC 0x00000000 (nunca)   DC 0x00000384 (15 min)
HIBERNATEIDLE  AC 0x00000000 (nunca)   DC 0x7fffffff (nunca)
```

Supervisor: `node scripts/window-stack-ready.mjs --no-start` → `stack listo (HTTP 200)`; no arranca nada
si el API responde.

## 4. Restauración del backup

Dos dumps, dos restauraciones en bases vacías, ambas con `pg_restore --no-owner --no-privileges
--exit-on-error` (exit 0) y `dropdb` al terminar. Cabeceras del archivo (`pg_restore -l`):

```text
pre-window : Archive created at 2026-11-09 09:00:08 UTC · dbname: bolsa_v1 · TOC 381
window-ready: Archive created at 2026-11-09 10:37:50 UTC · dbname: bolsa_v1 · TOC 453
```

| Medida | `bolsa_v1` | `scratch_restore` del **pre-window** | `scratch_restore` del **window-ready** (11:38) |
| --- | ---: | ---: | ---: |
| `alembic_version` | `066_account_evidence_policy` | **`038_research_trials_param_region`** | `066_account_evidence_policy` |
| Tablas `public` | 91 | **78** | 91 |
| `auto_engine_runs` | 1038 | **1037** | 1038 |
| `paper_forward_results` | 0 | 0 | 0 |
| `ohlcv_bars` | 226 780 | 226 780 | 226 780 |
| `decision_journal_entries` | 44 313 | 44 313 | 44 313 |
| `instrument_list_items` (`estudio`) | 80 | 80 | 80 |
| Último run | `2026-11-09 09:04:25` | `2026-11-08 20:26:53` | `2026-11-09 09:04:25` |

**El dump pre-window restaura pero no es la base actual** (13 migraciones y un run por detrás); el
`window-ready-2026-11-09.dump` (124 636 279 B) es el punto de restauración verificado.

## 5. Verificación del árbol

```text
pnpm window:test      → 79 tests, 79 pass, 0 fail
window:freeze         → freeze OK (c6cef5c9) · apps 2675ed02… · packages 27df4722…
git status --porcelain -- apps packages → 0 líneas
node scripts/window-forward-runner.mjs --dry-run run-day → exit 0 (incluye la linea de bars-gate)
```
