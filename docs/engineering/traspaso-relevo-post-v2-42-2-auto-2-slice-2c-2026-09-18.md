# Traspaso de relevo — post `v2.42.2-beta` (AUTO-2 slice 2c cerrado) → **AUTO-3** (Risk & Market Governor)

**Fecha:** 2026-09-18 · **Versión:** `1.67.2-beta` · **Tag:** `v2.42.2-beta` → `3e8aa359` · **Migración:**
**ninguna** (Alembic head sigue en `042_portfolio_reservations`). Sello **verde**: `Python CI` **5/5** en
`main` ([`35312788454`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312788454); `quality` **1935
passed / 38 skipped**, `auto-v2-durable-pg` **39 passed / 0 skipped**) y **5/5** en la ref del tag
([`35312807393`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312807393)); `Release tag CI`
([`35312807338`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312807338)) **GREEN** con `certify` en
`success` (job `python` offline **1946 passed / 35 skipped**, `mypy` 487 ficheros 0 issues; `lifecycle-pg`
con **PG real** **144 + 45 passed**).

**Punto de entrada obligatorio para quien siga:** el
[audit-pack-v2.42.2](./audit-pack-v2.42.2-auto-2-slice-2c-2026-09-18.md) y el
[arranque del auditor](./arranque-auditor-v2-42-2-auto-2-slice-2c-2026-09-18.md). Después, este documento.

---

## 1. Estado en una frase

`AUTO-2` está **cerrado con evidencia**: el día cuenta y declara sus motivos de salida
(`time_exit`/`thesis_exit`/`structural_stop`, con `undeclared` para lo no declarado), la procedencia del ATR
se **mide**, y con `AUTO_ENGINE_SIM_V2=1` la política de protección antigua **no se evalúa en ningún caso**
(condición estructural, con un sensor que explota si alguien la reintroduce). Lo que queda es **`AUTO-3`**:
el gobernador de riesgo y mercado.

## 2. Lo que este slice cierra (y cómo se mide)

| Criterio del §4 del roadmap de `AUTO-2`                             | Evidencia                                                                                                                                    |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `TIME_EXIT`/`THESIS_EXIT` con evidencia en el journal de **un día** | `exit_reasons = {time_exit: 1, thesis_exit: 1, structural_stop: 1}` con `exits = 3` y `sum(motivos) == exits`, `healthy = true`, libro plano |
| `ProtectionConfig` sin lectura con `AUTO_ENGINE_SIM_V2=1`           | `legacy_policy_reads = 0` **con un sensor que lanza** si se llama (el día entero corre igual)                                                |
| Medición del ATR real (D3)                                          | `atr.sources = {real: 15, fallback: 0, missing: 0}`, `real_share_pct = 100`, `veto = "0"` (OFF)                                              |

Reproducible: `uv run python apps/api-python/scripts/v2_42_2_golden_day_evidence.py --out dia.json` (sale ≠ 0
si el día no cumple el criterio).

## 3. Qué queda abierto (deuda declarada, por orden de importancia)

1. **`AUTO-3` — Risk & Market Governor** (`V2.43` / `1.68.0-beta`, el siguiente objetivo): régimen de mercado
   y riesgo de cartera como **eventos del FSM** (`REGIME_EXIT`, `RISK_EXIT`), hoy inexistentes como tales.
   `REGIME_EXIT` **sí** existe en el camino legacy con **precedencia absoluta** (vende antes que cualquier
   otra protección) pero **no** es un evento del FSM: al cablearlo hay que decidir precedencia y atribución.
2. **Flip del veto de ATR** (`AUTO_ENGINE_SIM_V2_ATR_REQUIRED=1`): **exige firma del owner** (dinero) y el
   número delante. El `100 % real` del día golden es un día **inyectado**; el número útil es el de un día con
   datos reales de mercado (`atr_source_counts()`), que es lo que D3 pidió medir antes de flipar.
3. **Productor del nivel de invalidación**: hoy el `TradePlan` **no** manda `invalidation_price` y el test del
   día lo escribe con un seam declarado. Cablear el productor (del stop estructural o del thesis level de la
   estrategia) es el siguiente paso natural para que `THESIS_EXIT` no dependa del stop.
4. **Emisor de `RECONCILED`**: sigue sin existir en el camino del worker (H-1 endurece la puerta, no la abre).
   Una posición adoptada sin estado verosímil queda degradada (`RECONCILIATION_REQUIRED` +
   `PROTECTION_MISSING`), que es el comportamiento fail-closed correcto — pero sin emisor no hay salida de la
   degradación dentro del día.
5. **Horizonte por plantilla**, no por estrategia (`resolve_holding_horizon` lee `trading_policy_templates`).
6. **`_v2_last_exit_label` y ventas parciales**: el conteo del día es por **cierre** (una salida puede
   materializarse en dos ventas). Si en `AUTO-3` aparece una atribución que necesite granularidad por venta,
   hay que extender la fila.

## 4. Trampas medidas (no las repitas)

- **Medir con una copia a mano de la lista de CI**: dos veces dio una medición que **no** era CI. Usa
  `scripts/verify/offline_ci_run_yaml.py` (extrae el `run` **del YAML**, verifica que cada ruta existe — una
  ruta inexistente es `exit 4` — y mide por **JUnit XML**, porque bajo `subprocess` en Windows el stdout de
  pytest llega truncado).
- **Ficheros PG en local**: el `connect` de los tests que hablan con PG **se cuelga** (no responde ni
  rechaza). Deben ir a `--ignore` (`--with-pg-ignores` del runner). Un skip mudo **no** certifica nada: la
  durabilidad la certifica CI en sus jobs con PG real.
- **`--noconftest`** en la medición offline: el conftest de la app también habla con PG.
- **Mutaciones "verdes" que no son agujero de cobertura**: en 2b pasó dos veces (una rama desactivada dejaba
  pasar el `full_exit` del plan; dos sensores de la marca se tapaban entre sí). Antes de "añadir cobertura",
  comprueba que la mutación rompe **comportamiento**, no una línea.
- **Trabajo concurrente sobre el mismo worktree**: la auditoría de 2a dejó una medición inválida por medir
  con el árbol moviéndose. Mutación y auditoría, en worktrees **separados**.

## 5. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`. El restructure de 2c cambia
  **una** cosa declarada ahí: una SELL legacy con `qty <= 0` ya no emite `hold_no_op`. Cualquier otro cambio
  en ese camino es un hallazgo.
- **Semántica del FSM**: forward-only, `RECONCILED` endurecido, `PROTECT` nunca mudo, y **los motivos no se
  cruzan** (el decisorio manda).
- **Sin migración**: todo lo nuevo de 2b/2c vive en el JSONB `sim_auto_positions.position_state`.
- **Los gates PG** (`AUTO_V2_LIFECYCLE_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline:
  un skip mudo no certifica.

## 6. Checklist de verificación antes de tocar `AUTO-3`

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src \
             --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter
uv run pytest packages/py/application/tests/test_auto_daily_journal.py \
              apps/api-python/tests/test_auto_v2_golden_day_evidence.py \
              apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py -q
uv run python apps/api-python/scripts/v2_42_2_golden_day_evidence.py --out dia.json; echo "exit=$?"
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Los dos bloques offline deben quedar **verdes** y el script de evidencia **exit 0**. Si alguno cambia sin que
nadie haya tocado su código, la primera sospecha es el **entorno** (PG/DSN), no el test.
