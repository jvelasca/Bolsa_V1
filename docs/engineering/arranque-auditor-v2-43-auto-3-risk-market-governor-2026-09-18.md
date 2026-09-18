# Arranque auditor — V2.43 / AUTO-3 slice 1: `MarketRegime` × `RiskRegime` × `OperationalState` (`1.68.0-beta`)

**Qué auditas:** el **primer slice de `AUTO-3`**. Es un slice de superficie **media** (módulo puro nuevo +
gate en el motor + cableado de una medida que no llegaba + evidencia), y su afirmación fuerte es una sola:
**la tabla gobierna la decisión de entrada, no la decora**. La auditoría rentable está en el **§4 del pack**
(la matriz de mutaciones, con dos mutaciones que nacieron verdes y hubo que rehacer), en el **§6** (límites)
y en las **preguntas abiertas** de abajo.

**Pack:** [`audit-pack-v2.43-auto-3-risk-market-governor-2026-09-18.md`](./audit-pack-v2.43-auto-3-risk-market-governor-2026-09-18.md)

**Hilo de la auditoría (GitHub):** [issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62) — petición
publicada el 2026-09-18, con los puntos de entrada fijados a la ref del tag. **Reporta ahí** (formato del
§8 del issue: severidad · afirmación atacada · ruta:línea · comando · salida · si el pack ya lo declaraba).

**Qué auditar exactamente:** versión **`1.68.0-beta`**, partiendo de `v2.42.2-beta` → `3e8aa359`. El sello es
el tag anotado **`v2.43-beta`**, que apunta al **commit de sellado** (docs-only) e incluye el commit de fase
del código **`7ca4a0e1`** (23 ficheros, `+3677/−58`). `Python CI` del commit de fase: **GREEN 5/5** en `main`
(run [`35322991385`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35322991385); `quality` **1983
passed, 38 skipped** y `auto-v2-durable-pg` **39 passed**). **Ref del tag ya certificada:** `Python CI` en la
ref **GREEN 5/5** (run [`35323452519`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452519)) y
`Release tag CI` **GREEN** con `certify` en `success` (run
[`35323452639`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452639); job `python` **1994 passed,
35 skipped**, `lifecycle-pg` con PG real **144 + 45 passed**). Detalle en el §8.1 del pack.

**Contexto que NO tienes que re-auditar:** `AUTO-1` (reservas) y `AUTO-2` (FSM, `TIME_EXIT`/`THESIS_EXIT`,
ATR, cierre con evidencia) ya se auditaron en sus packs. Aquí basta comprobar que este slice **no los
degrada** (las baterías completas van en el §8.2 del pack) y que el gobernador **no** invade el camino de
salida.

---

## 1. Orden de lectura (20–30 min)

1. **§1 y §6 del pack**: qué **afirma** y qué **no** afirma la versión. Si una afirmación no se sostiene con
   lo que leas después, ese es el hallazgo.
2. `packages/py/analytics/src/bolsa_analytics/cognitive/operational_governor.py` **entero** (≈650 líneas,
   puro): los cinco `_*_CAP` son **la política** y se leen en 20 líneas; `resolve_operational_state` es el
   máximo de severidad. Empieza por ahí: si un techo no coincide con el roadmap, es un hallazgo de política.
3. `packages/py/application/src/bolsa_application/portfolio_decision_engine.py` l. 462-513 (lectura +
   **paso 3.b**) y l. 243-276 (`PortfolioDecision` / `to_dict`).
4. `packages/py/application/src/bolsa_application/auto_v2_entry.py`: `decision_config` (l. 237-266),
   `_governor_env_overrides` (l. 350-405), `plan_v2_tick` (l. 776-880) y `_journal_entry` (l. 1351-1357).
5. `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py::_v2_governor_drawdown_pct` (l. 1153)
   y el sitio donde se alimenta `_sim_realized_pnl` (l. 3025-3030) — **es donde vive el riesgo real de la
   medición** (¿qué es "la equity del día"?).
6. `apps/api-python/scripts/v2_43_governor_evidence.py` (la escalera con control por tramo; **sale ≠ 0** si
   la tabla no gobierna) y los 3 ficheros de test del slice.

## 2. Afirmaciones verificables (con su medida)

| #   | Afirmación                                                             | Cómo la rompes                                                                                         |
| --- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| A1  | La tabla es **total** (ninguna combinación sin respuesta)              | Añade una etiqueta de eje y mira si `resolve_operational_state` la trata como `UNKNOWN` o la ignora    |
| A2  | La tabla es **monótona** (más riesgo nunca es más permisivo)           | Sube un eje de severidad con los demás fijos y busca un salto hacia un estado más permisivo            |
| A3  | Ningún `UNKNOWN` es "libre"                                            | Quita un `UNKNOWN` de un `_*_CAP` (M2 del pack: 3 rojos) y comprueba que los tests lo defienden        |
| A4  | El gobernador solo **endurece**                                        | Haz que `EXIT_ONLY` deje pasar entradas (M3: 4 rojos) y mira si el journal lo delata                   |
| A5  | El **tamaño** sale del veredicto (0,75 / 0,50)                         | Ignora `risk_scale` en `decision_config` (M7: 2 rojos); en la evidencia, compara contra **su control** |
| A6  | Las **tres dimensiones** viajan en toda decisión que pasó por el motor | Quítalas de `_journal_entry` (M6: 2 rojos) y comprueba los vetos y los no-trade                        |
| A7  | Con el flag OFF el camino V2 es **byte-idéntico**                      | Quita el guard: el control del script y el test de byte-identidad deben caer                           |
| A8  | El **drawdown se mide** (no se asume 0)                                | Publica `0.0` siempre (M5: 3 rojos) y mira la escalera y la pata no realizada                          |
| A9  | `LOW_VOL` es producible **sin** cambiar `v0`                           | Toca `_classify_v0` o la tabla de `v0` y comprueba que los tests de `v0` caen                          |
| A10 | La env se sanea **como bloque**                                        | Pon un corte no creciente o un factor 0,5 y comprueba que caen **todos** los umbrales, no algunos      |

## 3. Comandos listos

```bash
# estático (invocación EXACTA de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src \
             --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# suites del slice
uv run pytest packages/py/analytics/tests/test_operational_governor.py \
              packages/py/application/tests/test_auto_v3_governor_gate.py \
              apps/api-python/tests/test_auto_v3_governor_evidence.py -q

# evidencia (JSON) y su self-check: exit != 0 si la tabla no gobierna
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# bloques offline de CI tal cual están en el YAML (+ verificación de rutas y medición por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

**Matriz de mutación (7 mutaciones, 7 rojos)**: §4 del pack. Si vas a rehacerla, hazlo en un **worktree
separado** (el traspaso §4 documenta que medir con el árbol moviéndose dejó una medición inválida).

## 4. Preguntas abiertas que deberías intentar romper

1. **`binding_axis` y los empates.** El eje que se declara como culpable sale de `_AXIS_ORDER`, que es
   determinista. ¿Puede el journal declarar un eje que **no** fue el que fijó el techo? ¿Y si dos ejes
   empatan? El test cubre el caso nominal, no todas las combinaciones: **esto es terreno fértil**.
2. **El depósito de referencia de la marca.** `_v2_governor_drawdown_pct` pasa `initial_deposit=base` en
   **cada** tick. ¿Qué pasa si la base cambia dentro del día (inyección/retirada, o un cambio de
   `AUTO_ENGINE_SIM_V2_EQUITY`)? ¿Un rebase puede **ocultar** una caída previa o fabricar una caída falsa?
   El test de la escalera usa base constante, así que **no lo cubre**.
3. **`_sim_realized_pnl`.** Se alimenta con `(price - entry_ref) * applied_qty` en la venta aplicada. ¿Es
   `entry_ref` el precio de entrada de la posición o el stop? Si fuera el stop, el realizado (y por tanto el
   drawdown) estaría mal y la escalera no lo vería.
4. **Ventas parciales.** Una posición que se cierra en dos ventas: ¿el realizado se acumula bien y la
   entrada se limpia una sola vez? ¿Qué pasa con `_sim_realized_pnl` y `_open` si la segunda venta llega en
   otro tick?
5. **El eje de liquidez por defecto.** `min_liquidity_notional` nace en **0,0**, así que `OK` se cumple con
   cualquier notional positivo: el eje **solo ata** cuando la liquidez es desconocida (o cuando el operador
   calibra el umbral). ¿Es una banda real o un no-op por defecto? El pack lo declara como banda con umbral
   **calibrable**; decide si eso basta o merece un hallazgo de diseño.
6. **`RESTRICTED` y el listón de edge.** El tramo de 12 % se mide **vetado** con el factor por defecto (2,0)
   y **aprobado** con el factor relajado (1,2). ¿Es el factor por defecto una política razonable o hace que
   `ENTRY_RESTRICTED` sea de facto un `EXIT_ONLY` para candidatas del rango alcanzable?
7. **Candidatas descartadas antes del motor.** `governor_states` acumula el estado de las candidatas
   **evaluadas**; una candidata descartada antes de decidir (identidad duplicada) no publica dimensiones.
   ¿Es correcto (no hay lectura que publicar) o se pierde trazabilidad de qué habría decidido el gobernador?
8. **Composición declarada.** Dos ejes al 75 % dan **75 %**, no 56 % ("el más estricto gana", §1.5). ¿Es la
   lectura correcta del roadmap de `AUTO-3` o subestima la restricción conjunta? Está declarado, así que el
   hallazgo sería de **política**, no de implementación.

## 5. Qué NO es un hallazgo (declarado antes de que lo encuentres)

- Que el gobernador **no cierre posiciones**: es el alcance del slice (§1 del pack, decisión del owner).
- Que `REGIME_EXIT` / `RISK_EXIT` **no** sean eventos del FSM: se difieren al slice siguiente, con la
  decisión de precedencia/atribución.
- Que `HALTED` **no** tenga productor propio, y que el flip a **default ON** no esté hecho.
- Que los umbrales de drawdown (5/10/15/20 %) **no** estén calibrados con datos.
- Que la evidencia sea **hermética** (sin PG ni sesión de mercado): lo que sí sería hallazgo es que el pack
  la presentara como sesión real.
- Que **PG real** no se haya medido en la máquina del autor: se declara y lo certifica CI. Este slice no
  toca ningún fichero PG por diseño.
- Que existan **alias aditivos** por colisión de nombre (`MacroRegime`, `FinancialIntegrityState`,
  `GovernorMarketRegime`): son la forma de no romper el árbol; lo que sería hallazgo es que un alias
  cambiara el significado de un eje existente.
