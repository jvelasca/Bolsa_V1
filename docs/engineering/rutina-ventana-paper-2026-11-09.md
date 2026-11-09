# Rutina operativa de la ventana PAPER (desde 2026-11-09)

Este documento es la referencia de OPERACIÓN de la ventana longitudinal del
[ADR-046](../adr/046-protocolo-longitudinal-paper.md). No explica el protocolo: explica
qué hay que hacer cada día, qué se automatizó y qué evidencia deja cada paso.

## 1. Qué quedó arreglado el 2026-11-09 (para que la ventana pueda certificar)

| Bloqueo medido | Estado |
| --- | --- |
| BD en Alembic `038`, sin `sim_fill_finance_context.cycle_id` | Migrada a `066_account_evidence_policy` |
| `portfolio_reservations` inexistente | Creada por la migración `058` |
| `signal_alert_subscriptions` con 1597 attnums (1580 *dropped*) | Reconstruida compacta (17 attnums, 0 *dropped*) |
| Pin de freeze con etiqueta obsoleta | Re-anclado a `cc1775de` (apps `2675ed02…`, packages `27df4722…`) |

`VACUUM FULL` **no** libera los *slots* de columnas borradas: PostgreSQL conserva la fila
de `pg_attribute` con `attisdropped = true` y el `attnum` sigue contando para el límite
de 1600. La única vía que renumera es reconstruir la tabla. Se hizo con
`CREATE TABLE … (LIKE … INCLUDING ALL)` + `DROP` + `RENAME` (la tabla tenía **0 filas**;
las dos FK, que `LIKE` no copia, se recrearon a mano) y se restituyó el nombre del índice
de la PK. Queda declarado: si otra tabla vuelve a acercarse al límite, el mismo
procedimiento aplica, y **nunca** se hace a ciegas sobre una tabla con filas.

Evidencia: `alembic_version = 066`, `sim_fill_finance_context.cycle_id` existe,
`portfolio_reservations` existe. `auto_paper_evidence_snapshot` **no es una tabla**: es un
`event_type` del spine `decision_journal_entries` (el `paper_evidence_snapshot_worker` lo
escribe). La comprobación correcta es esa, no un `information_schema.tables`.

## 2. Cadencia automática (Windows `schtasks`)

Instalada con `node scripts/window-forward-runner.mjs task:install --at 18:30 --bars-at 17:40`:

| Hora | Tarea | Qué hace |
| --- | --- | --- |
| 17:40 | `BolsaV1_BarsSync` | Encola en el API las diarias desfasadas y deja que el worker las drene |
| 18:30 | `BolsaV1_WindowForward` | `run-day`: preflight → forward → `v2_77` → `v2_80` → `v2_83` |
| 20:20 | `BolsaV1_WindowWatch` | Vigía: evalúa el día y el arrastre de días perdidos, avisa por log/email |

Las tres tienen `StartWhenAvailable = true` (si el equipo estaba apagado, corren al
encenderse). La ingesta va **antes** del `run-day` a propósito: con
`AUTO_ENGINE_SIM_REAL_PRICE=1` el productor marca con la **apertura de la barra del día**;
sin esa barra todo cae a `HOLD` y el día se mide con 0 fills.

**No lances `run-day` a mano antes de las 17:40.** Un día terminal (incluido un
`HARD_ERROR`) se omite en la siguiente ejecución salvo `--force`: un run prematuro
quemaría el día. `--dry-run run-day` sí es seguro a cualquier hora (valida config, freeze
y cadena sin abrir el motor).

## 3. Rutina diaria

```powershell
pnpm run window:status
```

Lee `operability_runs/window-runs/ledger.jsonl` y publica, por día, su estado
(`MEDIDO`, `NO_MEDIDO_REGIMEN`, `NON_MARKET_DAY`, `HARD_ERROR`) y el régimen. El gate solo
se abre con **≥4 días MEDIDOS con provenance válida**, **≥2 episodios** y **≥32 ciclos
cerrados**. Antes del re-anclaje el gate salía `STALE` por `apps_hash_no_congelado`; desde
`cc1775de` los días nuevos quedan `FROZEN`.

Si un día sale `HARD_ERROR`, el motivo está en
`operability_runs/window-runs/<DIA>/manifest.json` (`reason`) y los logs de cada paso en
el mismo directorio (`preflight.*`, `forward.*`, `journal.*`).

## 4. Rutina semanal (certificado)

```powershell
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py `
    --account-id 1484e253d2d54645945a6b1d7 `
    --strategy-version v283-window-a --strategy-version v283-window-b --json
```

Es `read-only` (`readOnly: true`, `substitutesRealWindow: false`): certifica, no sustituye.
El `gate` del JSON trae `days`, `episodes`, `cycles` y `verdict`. Los ciclos **sin
`cycle_id`** (fills anteriores a la migración `044`) se excluyen y se declaran en
`excludedWithoutIdentity`: no se imputan.

## 5. Criterio falsable (qué concluir cuando haya días nuevos)

- Tras **≥4 días posteriores al arreglo**, si hay `cycles > 0` con `cycle_id` y
  `episodes` sigue en 0 ⇒ hueco real en el escritor de régimen
  (`_v2_journal_cycle_regime`), no en el protocolo.
- Si `cycles = 0` habiendo fills con `cycle_id` ⇒ auditar el veto de entrada con
  `forward.json` (`readiness.blockers`) y los motivos del motor.
- Si `cycles` crece pero < 32, es **operación**, no software: se declara el avance y se
  sigue corriendo. Con `TOP_N=5` y stops que tardan en saltar, el horizonte realista son
  2-3 semanas de operación.

## 6. Estado medido al arrancar (2026-11-09, 09:05 UTC)

- `window:status`: 4 días MEDIDOS (el eje días ya estaba cubierto), 0 episodios,
  `gate: STALE` (provenance de los runs anteriores).
- `v2_98`: `INCONCLUSIVE` · días 4 · episodios 0 · ciclos 0 ·
  `excludedCycles 4` (los cuatro por `excludedWithoutIdentity`).
- `/api/health/ready`: 200 · `schema_status: esquema en head (066_account_evidence_policy)` ·
  `git_sha cc1775de`.

Es decir: la causa raíz medida (`cycle_id` ausente) ya no puede repetirse; lo que falta
son fills **nuevos** que lo lleven.

## 7. Parte A — por qué el sesgo del simulador no era la geometría

`scripts/random_entry_control.py` gana `--exit-mode {policy,structural}` con los ejes
`--stop-trigger`, `--watermark`, `--breakeven`, `--arm`, `--partials`, y `--calibrate`
barre contra los 192 ciclos reales del ledger. Resultado (in-sample, declarado):

| Modelo | Sesgo | RMSE | corr | signo |
| --- | --- | --- | --- | --- |
| `policy` (referencia previa) | +0,141 R | 0,765 | 0,882 | 93 % |
| `structural` (ratchet real) | +0,198 R | 0,794 | 0,869 | 92 % |
| Ganador calibrado (`policy` sin T2) | +0,131 R | 0,748 | 0,888 | 93 % |

La descomposición del residuo es la respuesta: **ganadores** sesgo −0,06 R (la geometría
del trail está bien) y **perdedores** +0,27 R, concentrado en los ciclos en los que el
motor real tocó el stop y **no lo ejecutó** (`stopFiredNotFilled`, n=26, +0,35 R por
ciclo). Eso es arrastre de EJECUCIÓN, no una regla de salida: modelarlo sería modelar un
fallo. `--stop-trigger touch` (lo que hace el mercado) **empeora** el ajuste por el mismo
motivo. El residuo se publica en `fidelity.decomposition` de cada JSON y no se esconde;
el nivel absoluto queda *reproducido*, no *predicho*.

Artefactos: `operability_runs/dia-d-auto/calibracion_estructural.json`,
`control_entradas_aleatorias.json` (calibrado), `…_structural.json`,
`…_policy.json` (medición anterior conservada) y `fidelidad_*.csv` (cruce ciclo a ciclo).
