# Traspaso de relevo — post `V2.43` (AUTO-3 slice 1: ejes, tabla y gate de ENTRADAS) → **slice 2** (eventos FSM `REGIME_EXIT`/`RISK_EXIT`)

**Fecha:** 2026-09-18 · **Versión:** `1.68.0-beta` · **Punto de partida:** tag `v2.42.2-beta` →
`3e8aa359` (AUTO-2 cerrado). **Migración: ninguna** (Alembic head sigue en `042_portfolio_reservations`).
**Sello:** commit de fase + tag anotado **`v2.43.0-beta`**; **pendiente en el momento de redactar** — el
commit docs-only de evidencia de CI añade los runs y las cifras del sello (patrón de `v2.42.2`).

**Punto de entrada obligatorio para quien siga:** el
[audit-pack v2.43](./audit-pack-v2.43-auto-3-risk-market-governor-2026-09-18.md) y el
[arranque del auditor](./arranque-auditor-v2-43-auto-3-risk-market-governor-2026-09-18.md). Después, este
documento.

---

## 1. Estado en una frase

`AUTO-3` arranca con los **tres ejes instalados** (`MarketRegime` × `RiskRegime` × `OperationalState`), la
tabla de decisión **total y monótona** con su gate puro, y el **permiso gobernando solo las ENTRADAS**
detrás de un flag **OFF por defecto** (con OFF, byte-idéntico). Lo que queda de `AUTO-3` es lo más
delicado: **convertir el régimen y el riesgo en eventos del FSM** (`REGIME_EXIT`/`RISK_EXIT`) y decidir la
**precedencia y la atribución** del día.

## 2. Lo que este slice cierra (y cómo se mide)

| Afirmación del slice                                                               | Evidencia                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| La tabla es **total y monótona** y no hay eje `UNKNOWN` "libre"                    | `test_operational_governor.py` (1 728 combinaciones, techo por eje, monotonía por dominancia) + mutación M4 ⇒ **11 rojos**                                                                                                                                     |
| La tabla **gobierna** la decisión (escalera de drawdown con **control** por tramo) | `v2_43_governor_evidence.py`: 0 % → `ENTRY_ALLOWED` (×1,00), 6 % → `ENTRY_REDUCED` (**×0,75**), 12 % → `ENTRY_RESTRICTED` (veto por listón de edge; ×0,50 con factor relajado), 15 % → `EXIT_ONLY` (`governor_exit_only`), 22 % → `HALTED` (`governor_halted`) |
| El **drawdown se mide** (no se asume 0) y la pata no realizada entra               | `EquityMarkBook` en el worker + tramo `unrealizedLeg` (posición viva −10 % ⇒ 6 % de DD con la equity base intacta)                                                                                                                                             |
| El permiso y el hecho de mercado son **hechos distintos** con motivo propio        | `PortfolioDecision.to_dict()` + `_journal_entry`: `marketRegime`/`riskRegime`/`operationalState` y `governor_*` vs `regime_invalid`                                                                                                                            |
| Con el flag OFF **no cambia nada**                                                 | test de byte-identidad + control del script (`reasonCodes` iguales, sin claves, `drawdownPct` ni se mide)                                                                                                                                                      |
| `LOW_VOL` deja de ser **valor muerto** sin tocar `v0`                              | `MATH_VERSION_MARKET_REGIME_V1` + `test_math_v1_adds_low_vol_without_changing_v0`                                                                                                                                                                              |

Reproducible: `uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json` (sale
≠ 0 si la tabla no gobierna).

## 3. Qué queda abierto (deuda declarada, por orden de importancia)

1. **`REGIME_EXIT` / `RISK_EXIT` como eventos del FSM** (el resto de `AUTO-3`): hoy **no** existen como
   eventos. `REGIME_EXIT` existe en el camino **legacy** con **precedencia absoluta** (vende antes que
   cualquier otra protección) pero no es un evento del FSM: al cablearlo hay que decidir **precedencia y
   atribución** del día (`day_exit_reason`), que es donde se cruza con la contabilidad de motivos de
   `AUTO-2` slice 2c. El gobernador de este slice **solo gobierna entradas**, así que ese cruce **no** está
   resuelto todavía.
2. **Flip del gobernador a default ON** (`AUTO_ENGINE_SIM_V2_GOVERNOR=1`): exige el **número delante**
   (días medidos con datos reales) y firma del owner, igual que el veto de ATR. Con OFF, el camino V2 es
   byte-idéntico ⇒ no hay prisa, y el número que falta es de **producto**, no de código.
3. **Calibración de umbrales**: los cortes de drawdown (5/10/15/20 %) son **declarados**, no calibrados, y
   dos valores por defecto merecen decisión explícita antes del flip: `governor_min_liquidity_notional`
   nace en **0,0** (⇒ el eje de liquidez **no ata** salvo liquidez desconocida) y
   `governor_restricted_edge_factor` nace en **2,0** (⇒ en la práctica `ENTRY_RESTRICTED` veta a las
   candidatas del rango alcanzable; medido en la evidencia).
4. **Productor real de `HALTED`**: hoy se alcanza por la tabla (drawdown extremo, `UNKNOWN` de riesgo) y por
   el parámetro `halted`; no hay política propia de **kill switch** (p. ej. pérdida diaria máxima medida
   fuera del drawdown de banda).
5. **Medición fina de la equity de la marca**: `_v2_governor_drawdown_pct` pasa `initial_deposit=base` en
   **cada** tick y suma el realizado con `(price - entry_ref) * applied_qty`. Quedan por verificar (y son
   preguntas abiertas del §4 del arranque del auditor): qué pasa si **la base cambia dentro del día**, qué
   es exactamente `entry_ref`, y cómo se comportan **ventas parciales** en ticks distintos.
6. **Deuda viva de `AUTO-2`** (no se toca aquí): el **veto de ATR** sigue OFF (exige el número de sesiones
   reales y firma), el **emisor de `RECONCILED`** sigue sin existir en el camino del worker, el
   **productor del nivel de invalidación** no está cableado (`TradePlan` no lo manda) y el horizonte es por
   **plantilla**, no por estrategia.

## 4. Trampas medidas (no las repitas)

- **Medir el escalado contra lo que no es su control.** El factor del gobernador es
  `quantity_on / quantity_control` **sobre el mismo snapshot** (mismo equity ⇒ mismo presupuesto): comparar
  la cantidad del tramo de 6 % contra la del tramo de 0 % da **0,705** porque la equity también cambia, y
  parece que la escala declarada (0,75) es falsa. La evidencia lleva su `control` dentro de cada tramo
  justo por esto.
- **Mutaciones verdes que no son agujero de cobertura**: pasó **dos veces** aquí. (a) M5 en su primera
  versión ponía en rojo un test **por otro motivo**; (b) M6 quiso medir el journal quitando las claves de
  `to_dict()`, pero `_journal_entry` las volvía a poner: **dos sensores se tapaban entre sí**. Antes de
  "añadir cobertura", comprueba que la mutación rompe **comportamiento**.
- **Medir con una copia a mano de la lista de CI**: usa
  `scripts/verify/offline_ci_run_yaml.py` (extrae la lista **del YAML**, verifica que cada ruta existe —una
  ruta inexistente es `exit 4`— y mide por **JUnit XML**, porque bajo `subprocess` en Windows el stdout de
  pytest llega truncado).
- **Ficheros PG en local**: el `connect` de los tests que hablan con PG **se cuelga** (no responde ni
  rechaza). Van al `--ignore` con `--with-pg-ignores`. Un skip mudo **no** certifica nada.
- **Mutación y auditoría, en worktrees separados**: medir con el árbol moviéndose dejó una medición inválida
  en 2a.
- **Dos docs de `v2.40.4` aparecen como modificadas sin estarlo**: `git status` las marca ` M` pero
  `git diff` sale **vacío** — es un artefacto de **fin de línea** (CRLF). No las comitees "por si acaso":
  no tienen contenido que sellar.

## 5. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`. El gate del gobernador vive
  dentro del pipeline V2.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.42.2` (journal sin las tres
  claves, `governor_states` vacío, `drawdown_pct` `None`). Cualquier cambio ahí es un hallazgo.
- **`v0` del clasificador de régimen** (`discovery_market_regime`): inmutable, etiqueta a etiqueta.
- **Sin migración**: todo lo nuevo vive en memoria/JSONB; Alembic head en `042_portfolio_reservations`.
- **Los gates PG** (`AUTO_V2_LIFECYCLE_PG_REQUIRED`, `AUTO_RESERVATION_PG_REQUIRED`, …) y los ficheros PG en
  el `--ignore` de los jobs offline: un skip mudo no certifica.

## 6. Checklist de verificación antes de tocar el slice 2

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src \
             --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter
uv run pytest packages/py/analytics/tests/test_operational_governor.py \
              packages/py/application/tests/test_auto_v3_governor_gate.py \
              apps/api-python/tests/test_auto_v3_governor_evidence.py -q
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Los dos bloques offline deben quedar **verdes** (42 y 51 rutas objetivo respectivamente) y el script de
evidencia **exit 0**. Si alguno cambia sin que nadie haya tocado su código, la primera sospecha es el
**entorno** (PG/DSN), no el test.
