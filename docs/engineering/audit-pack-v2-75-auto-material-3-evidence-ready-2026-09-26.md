# Audit-pack — `v2.75-beta` · `AUTO-MATERIAL-3`: EVIDENCE READY (muestra acumulada)

> **AsOf:** 2026-09-26 · **Versión:** `2.00.0-beta` · **Base auditada (diff):** `v2.74-beta`
> **Alcance:** (A) **acumular `≥32` ciclos medibles por estrategia** sobre una **cuenta PAPER nueva**
> conduciendo el camino REAL del productor; (B) pasar el gate a **`EVIDENCE_READY`** sin bajar
> umbrales; (C) correr **`AUTO-22`** y **`AUTO-23`** sobre ese material; (D) **declarar** que la
> muestra no permite cerrar `P3-2` / `P3-3`. **Cambio de código = un script de I/O** (harness); el
> **instrumento no cambia**.
> **SIN migración** (head `046_fill_reference_mid`). **Freeze intacto.** **`auto18-v1` / `auto15-v1` no
> se mueven.**
> **Aviso de procedencia:** la muestra la produce el **productor determinista** del repo (precio
> guionizado). Es PAPER durable, **no** mercado. El audit-pack lo declara para que nadie lea
> `P(R>0)` como inferencia de mercado.

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Evidencia |
|---|---|---|---|
| 1 | El productor determinista acumula `≥32` ciclos medibles **sin** bajar el mínimo | harness + gate | `evidencia-sample-accumulation-v2.75` (42 medibles) |
| 2 | El gate pasa de `PRODUCER_READY` a **`EVIDENCE_READY`** con el MISMO material | `paper_material_readiness.py --level evidence` | §5, `EXIT=0` |
| 3 | El veredicto lo firma **una sola pieza** (la del gate), no el harness | harness llama a `build_paper_material_readiness` | lectura del script (`_read_readiness`) |
| 4 | `AUTO-22` produce bundle inmutable de **3 niveles** con huella | `auto_evidence_run.py` | `evidencia-auto22-run-v2.75` |
| 5 | Lo no medido se declara (`NO MEDIDO` / `null`), nunca `0` de relleno | reporte AUTO-22 / AUTO-23 | `WFE`, `Correlación`, `size=64` |
| 6 | `AUTO-23` **no** inventa pares de correlación sin cubos | `minBuckets=4` | `activeBuckets=1` ⇒ `pairs=[]` |
| 7 | `AUTO-23` **no** baja `min_episodes` para forzar un veredicto | instrumento | régimen `INCONCLUSIVE`, `episodes=1` |
| 8 | El material **no** acredita diversidad de calendario/régimen ⇒ `P3-2`/`P3-3` abiertas | diagnóstico de buckets/episodios | §6 |
| 9 | El freeze, el reparto y la migración siguen intactos | `git diff` + Alembic head | §7 |

## 2. Qué cambia (y qué no)

**Cambia.**

- `apps/api-python/scripts/v2_75_paper_sample_accumulation.py` (**NUEVO**, solo I/O): siembra cuenta +
  instrumento que llena **a ambos lados**, encadena round-trips con **worker/engine nuevo + día
  distinto por round-trip**, lee el material con la pieza del gate y publica `--json` / `--out`.
- `docs/engineering/evidencia-*-v2.75-2026-09-26.txt` (**3 capturas crudas**), plan, audit-pack,
  arranques y relevo.
- `CHANGELOG.md` + `package.json` (`1.99.0-beta` → **`2.00.0-beta`**).
- `docs/engineering/PROJECT_STATE.md`, `engineering-index`, `deuda-p3-post-auditoria-v2.70`.

**No cambia.**

- **El instrumento**: `paper_material_readiness.py`, `auto_evidence_run.py`,
  `auto_evidence_validate.py`, `auto_paper_material.py` — **intactos**. Ni un umbral.
- **El worker congelado** `auto_simulation_worker.py`: **intacto** (no se desactiva ningún dedupe ni
  gate; el harness respeta el SIM tal cual).
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`; `ALLOCATION = none`. **Sin migración** (head `046`).
- **`evidence_runs/` / `evidence_validations/`**: gitignoreados (se reproducen con el comando, no se
  versionan); el bundle producido queda como artefacto local inmutable.
- **La UI**: no cambia.

## 3. Sin mutaciones nuevas

V2.75 **no añade lógica pura** (el instrumento YA soportaba `EVIDENCE_READY` desde `v2.74`, cubierto por
`M199`/`M200`). Por eso la matriz de mutaciones **no crece**: sigue en **200/200** (`v2.74`). El nuevo
código es un **harness de I/O** (`scripts/`), que no entra en el gate ni en el reparto.

## 4. Cómo auditar (desde un clon de GitHub)

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.75-beta
uv sync
# Compuerta estática (debe salir limpia):
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
# Alembic (head esperado 046_fill_reference_mid):
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
# 1) Acumular muestra y ver el gate pasar a EVIDENCE_READY (requiere PostgreSQL):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_75_paper_sample_accumulation.py --round-trips 44 --json
# 2) AUTO-22 sobre la cuenta que imprima el paso 1 (--account-id <uuid>):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/auto_evidence_run.py \
    --account-id <uuid> --strategy-version v75-producer-orb-v1 --bucket day --folds 3
# 3) AUTO-23:
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/auto_evidence_validate.py \
    --account-id <uuid> --strategy-version v75-producer-orb-v1 --sizes 16,32,64 --buckets day,week
```

> El harness **no** es determinista en el número EXACTO de cierres (el SIM sortea la cola): pide 44
> para dejar margen sobre 32. La cuenta/instrumento son **nuevos** en cada corrida (no toca legacy).

## 5. Evidencia cruda (resumen)

- **Gate**: `EVIDENCE_READY`, `EXIT=0`, sello `paper_material_readiness_v2`; 42 ciclos medibles / 504
  fills con `cycle_id` / 126 exit intents con `cycle_id` / 168 reservas / 0 reservas vivas.
- **AUTO-22**: `auto22_evidence_run_bundle_v1`, huella `sha256:70418d88…`, `P(R>0)=0.0000`,
  `Effective-N=1`, `WFE=NO MEDIDO`, `Correlación=NO MEDIDO`.
- **AUTO-23**: `auto23_evidence_validation_v2`; barrido `16→medido`, `32→medido`, `64→insufficient`;
  correlación `activeBuckets=1` (sin pares); régimen `INCONCLUSIVE`.

## 6. Lo que este tag NO acredita (declarado)

- **No** acredita inferencia de mercado ni edge de estrategia: el material es determinista y
  degenerado (`R` casi constante, un solo bucket, un solo régimen).
- **No** cierra `P3-2` / `P3-3`: exigen material PAPER REAL de mercado en `≥4` cubos y `≥2` episodios.
  Se declaran **ABIERTAS**. Cerrarlas no se puede por código: es acumulación operativa.
- `read_paper_material` etiqueta el material durable como `paper_real`; el auditor debe leerlo como
  **PAPER virtual durable**, no como cotización real (la nota del propio lector lo dice).

## 7. Verificación de invariantes

```bash
git diff v2.74-beta..v2.75-beta -- apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # vacío
git diff v2.74-beta..v2.75-beta -- packages/py/application/src/bolsa_application/auto_adaptive.py       # vacío
cd packages/py/infrastructure && uv run alembic heads   # 046_fill_reference_mid (única head)
```
