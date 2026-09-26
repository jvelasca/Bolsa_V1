# Traspaso / relevo — tras `v2.77-beta` (`AUTO-MATERIAL-5`: MARKET OPERABILITY)

> **AsOf:** 2026-09-26 · **Etiqueta:** `v2.77-beta` · **Versión:** `2.02.0-beta` · **Base:** `v2.76-beta`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto** · **Reparto
> congelado** (`auto18-v1` / `auto15-v1`) · **`ALLOCATION = none`**.

## Qué quedó hecho

1. **Journal de operabilidad (puro, nuevo)** `market_operability.py`: `classify_veto_reasons` reparte
   cada código de motivo en su **familia** (`regime`/`governor`/`liquidity`/`risk`/`top_n`/`data`/
   `other`); las siete salen siempre; un código sin familia va a `other` y **se cuenta** (nunca se
   descarta). `symbols_operable` mide cuántos símbolos admiten LONG **por sí mismos**;
   `operability_state` separa `operated`/`vetoed`/`no_signal` con la regla fail-closed **`no_signal`
   sólo si no hubo ni propuestas ni vetos**; `render_operability_table` arma la serie diaria.
2. **CAPABLE ≠ ACTIVE (aditivo)** `v2_76_forward_market_material.py` publica `pairCapable`
   (arquitectura lista) y `pairActive` (dos versiones operando), conservando `pairAvailable` como
   **alias** de `pairActive`.
3. **Sonda I/O (nueva)** `v2_77_market_operability.py`: lee los JSON del runner (`--forward`, admite
   glob), los traduce a filas diarias y **acumula un journal JSONL** no versionado
   (`operability_runs/`); `--render`, `--no-write`; el día se **declara con su procedencia**. **Sin
   PostgreSQL, sin material, sin recalcular el gate**; `exit 2` sin registros.
4. **Puros registrados en CI** (`quality` **y** `python` del tag): `test_market_operability.py`
   (**25**), **explícito** en los dos workflows (para no repetir el hueco de registro de `v2.76`).
5. **Matriz de mutaciones 205 → 210** con `M206`–`M210` (familia única; código perdido; CAPABLE como
   ACTIVE; `no_signal` falso; contabilidad que pierde `other`). **210/210**, restauración **byte a
   byte**, árbol **intacto**.
6. **Evidencia cruda** en 2 `.txt` (operabilidad + matriz) y **bump** `2.01.0-beta` →
   **`2.02.0-beta`**; tag **`v2.77-beta`**.

## Hallazgo central (declarado y medido)

La tabla de operabilidad del forward smoke real **por fin se lee en una línea**:

| Día | Régimen | Long | SimbOper | Decid | Prop | Veto | Fills | Ciclos | Par |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-26 | `BEAR_TREND` | `NO` | `4/8` | 64 | 0 | 64 | 0 | 0 | `CAPAZ` |

- Vetos por familia: **`regime=40`** (`regime_invalid`) + **`top_n=24`** (`top_n_excluded`). `NO
  SIGNAL` **no aplicable** (hubo vetos): el instrumento impide leer «no hay señal» donde hubo causa.
- **`4/8` símbolos operables por sí mismos** con el eje en `BEAR_TREND`: la tensión del **agregado
  conservador** queda **cuantificada**, no narrada. El instrumento **mide** su impacto; **no**
  concluye que sea la causa (para eso hace falta la serie de ≥4 días).
- `pairCapable=true` / `pairActive=false`: la arquitectura del par está lista, la **segunda versión
  no opera** (falta ACTIVE + `EdgeReport`).

## Lo que NO quedó hecho (y por qué)

- **La ventana de ≥4 días de calendario**: **NO ejecutada**. Los cubos salen de
  `sim_fill_finance_context.created_at = datetime.now(UTC)`; es operación de **tiempo real** y la fase
  se cerró el mismo día (`2026-09-26`, sábado, mercado cerrado).
- **`P3-2` / `P3-3`**: **ABIERTAS**. El instrumento está **listo**: ya no falta código, falta **tiempo
  de mercado**.
- **`AUTO-22` / `AUTO-23`**: **no corridos** (sin bundle que producir: el material forward es de
  mercado cerrado, 0 fills; un bundle sobre vacío no acreditaría nada y no se fabrica).
- **`market_live`**: con el bridge XTB caído los 8/8 precios salen por `market_close` (respaldo
  declarado). No es un fallo silencioso.
- **La deuda PG de `AUTO-23`** (`assert 17 == 26`): **pre-existente** y **ajena** al diff; en CI el
  test **se salta** (job `quality` sin Postgres). Sigue **declarada** (ver [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)).

## Lo que hereda el siguiente

**El bloqueante sigue siendo de CALENDARIO.** El instrumento ya dice **por qué** no se opera cada día;
la tarea es **operar** y **capturar**:

```bash
# 0) Barras reales frescas (ATR y régimen reales):
#    SyncInstrumentDailyBars / auto_sync_worker
# 1) ¿Puede operar el universo HOY? (read-only; exit 2 = vetado)
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --preflight-only --watch-size 20
# 2) Forward con reloj real (bridge XTB opcional: sin él, respaldo por cierre diario):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --watch-size 20 --interval-seconds 60 --json --out operability_runs/forward-YYYYMMDD.json
# 3) Journal de operabilidad del día (tabla + desglose por familia):
uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py \
    --forward 'operability_runs/forward-*.json' --journal operability_runs/journal.jsonl --render
# 4) Gate con cada avance (NO debe bajar umbrales):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \
    --account-id <u> --strategy-version <vA> --strategy-version <vB> --level evidence
# 5) Con >=4 cubos compartidos y >=2 episodios:
#    auto_evidence_run.py      --account-id <u> --strategy-version <vA> --strategy-version <vB> \
#                              --bucket day --folds 3                       # AUTO-22
#    auto_evidence_validate.py --account-id <u> --strategy-version <vA> --strategy-version <vB> \
#                              --sizes 16,32,64,128 --buckets day,week,month # AUTO-23
```

Cómo leer el journal (sin sesgo):

- `vetoed` con `regime=N` ⇒ hecho de mercado. `vetoed` con `governor=N` ⇒ **permiso** (AUTO no puede
  abrir). `vetoed` con `top_n=N` ⇒ tope de **evaluación**. `no_signal` ⇒ no hubo ni propuestas ni vetos.
- `SimbOper=k/n` alto con `Long=NO` ⇒ el **agregado conservador** veta símbolos que por sí solos
  operarían. Es el dato para decidir si conviene **reducir el watch** (`--watch-size`, parámetro
  operativo, **no** política) o seguir acumulando.

Notas de operación:

- **Prerrequisito** `<vB>`: sin estrategia **ACTIVE** promovida + `EdgeReport`, la versión B no opera y
  `pairActive=false` (declarado, no disfrazado). Sin eso, `P3-2` no tiene par.
- **No** se fuerza `AUTO_ENGINE_SIM_V2_REGIME` (forzarlo garantiza **1 solo** episodio).
- El journal vive en `operability_runs/` (**gitignoreado**): se reproduce con el comando, no se versiona.

## Reglas duras que siguen vigentes

- **No** se rellena el histórico legacy (sin backfill de `cycle_id`); el productor solo **acuna**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **No** se infiere `cycle_id` ni `reserved_risk`; **no** se convierte N fills en N operaciones.
- **No** se sobrescribe una corrida o validación (`evidence_runs/`, `evidence_validations/`).
- **Forward, no replay:** no se inyecta ni se backdatea `created_at`.
- **No** se toca el freeze. **Sin migración.** `ALLOCATION = none`.

## Ficheros de la fase

- [Plan](./plan-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
  [Audit-pack](./audit-pack-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
  [Auditor](./arranque-auditor-v2-77-auto-material-5-market-operability-2026-09-26.md) ·
  [Agente](./arranque-agente-v2-77-auto-material-5-market-operability-2026-09-26.md)
- Evidencia: `evidencia-operabilidad-v2.77-2026-09-26.txt` ·
  `evidencia-matriz-mutaciones-v2.77-210-2026-09-26.txt`
- Contexto previo: [relevo v2.76](./traspaso-relevo-post-v2-76-auto-material-4-2026-09-26.md) ·
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
