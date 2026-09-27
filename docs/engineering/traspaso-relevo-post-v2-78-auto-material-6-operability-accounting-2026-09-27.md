# Traspaso / relevo — tras `v2.78-beta` (`AUTO-MATERIAL-6`: OPERABILITY ACCOUNTING)

> **AsOf:** 2026-09-27 · **Etiqueta:** `v2.78-beta` (`2.03.0-beta`) · **Base:** `v2.77-beta`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto** · **Reparto
> congelado** (`auto18-v1` / `auto15-v1`) · **`ALLOCATION = none`**.
> **Lectura:** fase de **corrección del instrumento**. Cierra **`P3-6`** (MEDIUM) y **`P3-7`** (LOW)
> de la auditoría externa de `v2.77-beta`, **sin** tocar el motor, el gobernador (`aggregate_trial_regime`),
> `TOP_N` ni un umbral.

## Qué quedó hecho

1. **Contrato del dueño (aditivo)** `auto_reason_codes.py`: `DAY_EXIT_REASONS` publica los valores del
   mapa decisorio `_DAY_EXIT_REASON_BY_PRIMARY` (`time_exit`, `risk_exit`, `regime_exit`,
   `kill_switch`, `structural_stop`, …).
2. **Contabilidad de vetos PUROS (`P3-6`)** `market_operability.py`: `NON_VETO_REASON_CODES` y
   `split_journal_reasons` separan VETOS de **ATRIBUCIONES** (`approved` ∪ motivos de salida ∪ saltos
   de gestión) **antes** de clasificar. `build_operability_record` clasifica sólo los vetos y
   **publica** las atribuciones aparte (`nonVetoByCode` / `nonVetoCounted`); un código desconocido
   sigue iendo a `other` y **se cuenta**. En un día operado: `vetoCounted == vetoes` y `other` **vacía**.
3. **Ausencia fail-closed (`P3-7`)** `operability_state` comprueba **primero** la ausencia
   (`not record` / `measured == False` / falta de `proposals`-`vetoes`) ⇒ `STATE_UNKNOWN`; un payload
   sin `turnTotals` (`measured = bool(turnTotals)`) se lee **no medido**, nunca `no_signal`.
4. **Render declarado**: la línea `aprobaciones/salidas: … (NO son vetos)` sale **sólo si existen**
   (el smoke no la lleva).
5. **Puros 25 → 37**: contrato del dueño **exhaustivo y exclusivo** (cada literal de
   `DecisionReasonCode` en exactamente uno de `VETO_BUCKET_BY_REASON` ∪ `NON_VETO_REASON_CODES`),
   **día operado** (`approved=3` + `risk_exit=1`, `proposals>0`) y casos de `P3-7`.
6. **Mutaciones 210 → 213** (`M211`–`M213`: no-veto que se filtra; ausencia que no se comprueba;
   no-veto que se descarta) con restauración **byte a byte** y árbol **intacto**.
7. **Bump** `2.02.0-beta` → **`2.03.0-beta`**; tag **`v2.78-beta`**. **Sin migración.**

## El hallazgo, en una línea

El smoke sellado **no cambia** (0 propuestas ⇒ ningún `approved`): `2026-09-26 · BEAR_TREND · Long=NO ·
SimbOper=4/8 · Veto=64 · Fills=0 · CAPAZ` con `regime=40` + `top_n=24` y `nonVetoCounted=0`. Lo que
cambia es que **un día que sí opere** ya se lee como **censo**:

| Día (fixture operado) | Régimen | Long | SimbOper | Decid | Prop | Veto | Fills | Par | `vetoCounted` | `nonVetoCounted` |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-26 | `BEAR_TREND` | `NO` | `4/8` | 10 | 3 | **2** | 3 | `CAPAZ` | **2** (== `vetoes`) | 4 (`approved=3`, `risk_exit=1`) |

## Lo que NO quedó hecho (y por qué)

- **La ventana de ≥4 días de calendario**: **NO ejecutada**. Los cubos salen de
  `sim_fill_finance_context.created_at = datetime.now(UTC)`; es operación de **tiempo real**.
- **`P3-2` / `P3-3`**: **ABIERTAS**. El instrumento está **listo y ahora correcto**: falta **tiempo de
  mercado**, no código.
- **`AUTO-22` / `AUTO-23`**: **no corridos** (sin material que acreditar).
- **`OBS-3`/`OBS-4`/`OBS-5`**: **declaradas**, no abordadas (proceso / contrato defensivo).
- **`P3-5`** y la deuda PG `assert 17 == 26`: **ABIERTAS**, preexistentes y ajenas al diff.

## Lo que hereda el siguiente

**El bloqueante sigue siendo de CALENDARIO.** El instrumento ya dice **por qué** no se opera cada día y
ya **cuenta vetos puros**; la tarea es **operar** y **capturar**:

```bash
# 0) Barras reales frescas (ATR y régimen reales):
#    SyncInstrumentDailyBars / auto_sync_worker
# 1) ¿Puede operar el universo HOY? (read-only; exit 2 = vetado)
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --preflight-only --watch-size 20
# 2) Forward con reloj real (bridge XTB opcional: sin él, respaldo por cierre diario):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --watch-size 20 --interval-seconds 60 --json --out operability_runs/forward-YYYYMMDD.json
# 3) Journal de operabilidad del día (tabla + desglose por familia + aprobaciones/salidas):
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

Cómo leer el journal (ya con `v2.78`):

- `vetoed` con `regime=N` ⇒ hecho de mercado. `vetoed` con `governor=N` ⇒ **permiso**. `vetoed` con
  `top_n=N` ⇒ tope de **evaluación**. `no_signal` ⇒ no hubo ni propuestas ni vetos. `unknown` ⇒ **no
  medido** (payload vacío/truncado), **no** un hecho del mercado.
- `vetoCounted` = **vetos puros**; `nonVetoCounted` (línea `aprobaciones/salidas`) son **atribuciones**
  que **no** son vetos. En un día operado, `vetoCounted == vetoes` y `other` debe estar **vacía**.
- `SimbOper=k/n` alto con `Long=NO` ⇒ el **agregado conservador** veta símbolos que por sí solos
  operarían.

Notas de operación:

- **Prerrequisito** `<vB>`: sin estrategia **ACTIVE** promovida + `EdgeReport`, la versión B no opera y
  `pairActive=false` (declarado, no disfrazado).
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

- [Plan](./plan-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
  [Audit-pack](./audit-pack-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
  [Auditor](./arranque-auditor-v2-78-auto-material-6-operability-accounting-2026-09-27.md) ·
  [Agente](./arranque-agente-v2-78-auto-material-6-operability-accounting-2026-09-27.md)
- Evidencia: `evidencia-operabilidad-v2.78-2026-09-27.txt` ·
  `evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt`
- Contexto previo: [relevo v2.77](./traspaso-relevo-post-v2-77-auto-material-5-2026-09-26.md) ·
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
