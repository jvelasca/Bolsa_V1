# Evidencia — C-4 (coste ambiguo de una adopción) contra PostgreSQL real

**Fecha:** 2026-10-26 · **Rama:** `audit/c1-c4-integrity-fold-2026-10-25` ·
**HEAD certificado:** `b3456897` · **Migraciones:** ninguna ·
**Alcance:** prueba de integración + cableado de CI. Sin cambios de motor, `package.json`,
PR #76 ni tag `v2.88.161-beta`.

Cierra la reserva declarada en el dictamen del lote C-1–C-4: el hallazgo estaba cubierto
con dobles (`test_a9_1_crash_battery.py`) pero **no** contra las filas reales de
`sim_auto_positions`, que es donde la ambigüedad existe.

## 1. SHAs y CI — con el fallo previo declarado

| SHA | Contenido | Python CI |
| --- | --- | --- |
| `a1f8af71` | C-1..C-4 | **ROJO** — run [`40242343455`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40242343455), `quality` falló por Ruff (`I001`) |
| `2b9d258d` | ordena imports con la config raíz | **VERDE** — run [`40280315744`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40280315744) |
| `712c2529` | prueba PG de C-4 + cableado | **ROJO** — run [`40286724846`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40286724846): `auto-v2-durable-pg` verde, `quality` rojo por `I001` (misma lección, §4) |
| `b3456897` | ordena imports con la config raíz (CI) | **VERDE 5/5** — run [`40287111793`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40287111793) |

En el run verde, `auto-v2-durable-pg` ejecutó el paso dedicado y su guarda:

- `Pytest C-4 coste ambiguo PG (fail if skipped)` → **`3 passed in 1.79s`**.
- `Fail on skipped C-4 coste ambiguo PG (no skip silencioso)` → **ejecutada** (el job no
  puede quedar verde con el fichero omitido ni con un test saltado).

## 2. Qué certifica la prueba

`apps/api-python/tests/test_auto_v88_161_c4_ambiguous_cost_pg.py` siembra en PostgreSQL
real **dos filas vivas** del mismo símbolo (dos motores), el fill `APPLIED` con su
contexto financiero y, según el escenario, el espejo y/o el `position_state`; luego usa el
store (`PostgresSimAutoPositionStore`) y el lector canónico de PRODUCCIÓN para readoptar.

| Escenario | Hecho sembrado | Resultado exigido |
| --- | --- | --- |
| 1. Libro ambiguo **con** espejo | `entry_price=10.4`, libro `10.3335`, dos motores | `projection_ambiguous_ledger`; adopción declarada `RECONCILIATION_REQUIRED` con stop **por debajo** del mercado; journal con `entrySource` y `source=reconstructed` |
| 2. Libro ambiguo **sin** espejo | `entry_price=NULL`, libro `10.3335`, dos motores | `ledger_ambiguous`; no se adopta, hueco declarado con motivo propio (no `cost_basis_missing`); la fila durable queda con `entry_price NULL` y cantidad intacta |
| 3. **Plan durable** | `position_state` verificado + coste ambiguo | la geometría del plan prevalece (`PROTECTED`, mismo `tradePlanId`/stop); no se declara hueco de coste; el plan se consume una sola vez |

## 3. Gobierno de honestidad (gate)

- `C4_AMBIGUOUS_COST_PG_REQUIRED=1` en el job `auto-v2-durable-pg` (`python-ci.yml`) y en
  `lifecycle-pg` del sello (`release-tag-ci.yml`).
- El fichero va en `--ignore` del job offline de ambos workflows: sin PG skipearía en mudo.
- Paso **propio** en `python-ci.yml` con guarda anti-skip: omitir el fichero rompe el step
  (pytest exit 4) y un skip rompe la guarda.
- Comprobación local del gate: con `C4_AMBIGUOUS_COST_PG_REQUIRED=1` y sin PG,
  `_require_or_skip` lanza `AssertionError` (no skip); sin la variable, `pytest.skip`.

## 4. Lección de lint (misma clase que `a1f8af71`)

`712c2529` falló `quality` por `I001` en dos imports diferidos. La causa no es el contenido
sino la **resolución de configuración**: invocar Ruff sobre un fichero de
`apps/api-python` hace que resuelva el `pyproject.toml` más cercano
(`apps/api-python/pyproject.toml`), mientras el CI fuerza la config raíz
(`uv run ruff check packages/py apps/api-python --config pyproject.toml`). El orden de
`known-first-party` difiere (`bolsa_api` antes que `bolsa_application`).

Verificación correcta en local, idéntica al CI:

```bash
uv run --no-sync python -m ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync python -m ruff format --check apps/api-python/tests/test_auto_v88_161_c4_ambiguous_cost_pg.py --config pyproject.toml
```

## 5. Fuera de alcance (observaciones de suite local)

- Deadlock de `test_migration_036_roundtrip`: reproducido y verde aislado; no forma parte
  de este lote.
- Fallo de carga de `llvmlite.dll` que interrumpió la colección inicial de la suite local:
  incidencia de entorno, sin ejecución de pruebas; no se usa como evidencia de CI.
