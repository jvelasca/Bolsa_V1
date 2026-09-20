# Arranque del auditor — v2.44-beta (AUTO-4 · Portfolio Optimizer + valor esperado económico)

**Fecha:** 2026-09-20 · **Ref a atacar:** `v2.44-beta` (`1.69.0-beta`) · **Pack que manda:**
[`audit-pack-v2.44-auto-4-portfolio-optimizer-2026-09-20.md`](./audit-pack-v2.44-auto-4-portfolio-optimizer-2026-09-20.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase, con sus
**desviaciones declaradas**, es
[`plan-v2-44-auto-4-portfolio-optimizer-2026-09-20.md`](./plan-v2-44-auto-4-portfolio-optimizer-2026-09-20.md) §7.

Este documento es de **solo lectura** y existe para una cosa: que el auditor externo no gaste su
presupuesto redisculpiendo lo ya medido. Las rutas y líneas están **verificadas en el árbol**; cada
afirmación trae **el comando exacto** para medirla.

---

## 1. Qué se instala aquí (y por qué importa)

Una sola inversión de autoridad: **el ranking deja de ser la decisión**. Hasta `v2.43.3`,
`plan_v2_tick` recortaba al `TOP_N` y decidía **una a una** en ese orden (el ranking **era** la
respuesta). Ahora el `TOP_N` es el **tamaño del conjunto candidato** y la cartera elige la
**combinación** por valor esperado **económico** sujeto a restricciones duras.

Dos consecuencias que el auditor debe atacar:

1. **La economía entra en la decisión.** Hasta aquí el `edge` era una confianza declarada, no dinero;
   ahora hay `Expected R`/`Expected €` neto de coste. Si esa magnitud se puede **inventar** (un `0.0`
   por un dato ausente), el sistema pasa a decidir por números que no midió.
2. **El conjunto sustituye a la lista.** Si la búsqueda degenera (greedy, tope ignorado, "siempre
   encuentra algo que comprar"), la cartera deja de maximizar y el cambio es cosmético.

---

## 2. Orden de ataque recomendado (por coste/beneficio)

### A1 · El valor esperado se puede inventar (lo más caro si falla)

```bash
sed -n '115,235p' packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py
sed -n '240,275p' packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py   # _risk_geometry / _target_r
uv run pytest packages/py/analytics/tests/test_expected_value.py -q
```

Preguntas abiertas (busca el camino por el que un dato ininterpretable **se vuelve un número**):

- ¿Alguna rama de degradación deja `expected_r` **calculado** con una media que no se midió? (El
  camino del `target` **deriva** `avg_win_r`: ¿es siempre una declaración y nunca un relleno?)
- Un `avg_loss_r = 0.0` **explícito** vs ausente: ¿se distinguen? (`0.0` es "pierdo 0R", ausente es
  UNKNOWN). Un `bool` colado como `1`/`0` (`_finite` lo rechaza: verifícalo).
- `quantity` desde un `allocation` serializado (`str`) — ¿la geometría se degrada o revienta?
- ¿Puede `net_expected_currency` quedar `0.0` "medido" cuando el coste **no** se midió? (Debe quedar
  `None` + `cost_unmeasured` + `PARTIAL`.)

### A2 · La búsqueda degenera (greedy, tope, vacío)

```bash
sed -n '225,370p' packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py
sed -n '372,450p' packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py   # _better / verdicts
uv run pytest packages/py/analytics/tests/test_portfolio_optimizer.py -q
```

Preguntas abiertas:

- Con el tope superado, ¿**algún** camino devuelve un subconjunto (greedy encubierto) en vez de
  `UNKNOWN` + `optimizer_enumeration_cap_exceeded`?
- El desempate `_better`: ¿es **total** (valor → riesgo → lexicográfico)? ¿Puede un empate real quedar
  indeterminado según el orden de entrada? (test de orden invertido).
- La concentración sectorial: ¿se mide sobre la **combinación** (as-if) y no candidata a candidata?
  ¿Y con `equity = None`? (debe ser `optimizer_sector_unmeasured`, no "sin límite").
- `available_cash = 0` frente a `None`: ¿"no puedo gastar" vs "sin límite declarado"?
- La suma de valores: ¿`_round4` antes o después de sumar? (un redondeo por candidata puede cambiar el
  ganador de un empate; mide si eso es reproducible).

### A3 · El cableado no respeta OFF / el journal miente

```bash
sed -n '770,860p'   packages/py/application/src/bolsa_application/auto_v2_entry.py   # sonda de candidata + _optimize_candidate_set
sed -n '1000,1050p' packages/py/application/src/bolsa_application/auto_v2_entry.py   # bloque del optimizador en plan_v2_tick
rg -n "optimizer" packages/py/application/src/bolsa_application/auto_v2_entry.py
uv run pytest packages/py/application/tests/test_auto_v4_optimizer_wiring.py -q
```

Preguntas abiertas:

- Con el flag **OFF**, ¿se construye **alguna** candidata, se llama al optimizador o se emite **alguna**
  clave nueva? (byte-identidad: `V2TickPlan.optimizer is None` y ningún `reasonCodes` con prefijo
  `optimizer`).
- ¿Puede una candidata del TOP quedar **sin** motivo (ni elegida ni rechazada)? El invariante es que el
  conjunto candidato se reparte **exactamente** entre `selected` y las `rejections`.
- ¿Algún camino declara `edge_below_threshold` para una candidata del optimizador? (sería **falso**:
  su score es válido).
- La **sonda de sizing** (`_optimizer_candidate`) llama a `decide_portfolio` con el gobernador **OFF**:
  ¿puede dimensionar algo que el gobernador vetará después? (Sí, por diseño: el veto se aplica abajo.
  Lo que **no** puede es dimensionar con una geometría distinta a la de la decisión real: comprueba la
  caída de ATR `atr_pct_fallback`.)
- ¿El optimizador puede colar una candidata que el motor luego **no** aprueba? (Sí, y es correcto: la
  reserva/`RESERVATION_FAILED` sigue abajo. Mide que no se salte ninguna autoridad.)

### A4 · El gobernador y el kill switch siguen mandando

```bash
rg -n "new_risk_allowed|halted=halted|optimizer_blocks_new_risk" \
   packages/py/application/src/bolsa_application/auto_v2_entry.py \
   packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py
uv run pytest "apps/api-python/tests/test_auto_v2_worker_integration.py::test_v2_optimizer_on_without_an_economic_producer_is_fail_closed" -q
```

Preguntas abiertas: con `halted=True` y el optimizador ON, ¿el conjunto vacío gana **y** el motivo
declarado es `optimizer_drawdown_blocks_new_risk`?; ¿algún camino de `EXIT_ONLY` deja pasar una apertura
porque el optimizador la eligió?; ¿el flag ON sin gobernador cambia la tabla del gobernador? (no debe).

### A5 · Los límites declarados (no los redisculpas, los acotas)

```bash
rg -n "p_win|avg_win_r|target_price" apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
```

El worker **no** produce economía hoy (§7 del pack). Si encuentras un camino donde la ausencia de
economía se convierta en una **entrada** (en vez de en no operar declarado), eso **sí** es un hallazgo.

---

## 3. Qué **NO** es un hallazgo (declarado por adelantado)

- **Sin productor de `p_win`/medias ⇒ con el flag ON el tick no opera.** Es **fail-closed declarado**
  (pack §7) y está fijado en test. El productor es de `AUTO-7`. El flag es **OFF por defecto**.
- **`max_drawdown_used_pct` no existe como restricción numérica**: el veto de drawdown entra como
  permiso de cartera (`new_risk_allowed`). Desviación declarada **D3** (plan §7.1).
- **El «Golden Day con ON» se midió en dos capas** (tick + worker), no con un día dorado multi-fase.
  Desviación declarada **D5**.
- **Duplicidad de gates** (capital/sector/correlación/liquidez en el optimizador **y** en el motor, con
  fotos distintas): decisión declarada (pack §7), no un bug.
- **La correlación usa el dato de hoy** (`TradeContext`), no una matriz por pares: roadmap §11.
- **Umbrales sin calibrar** (`max_combinations = 4096`, `max_positions = top_n`): declarado.
- **Nota de método**: una mutación **verde** no es por defecto agujero de cobertura. Hay que descartar
  antes que el mutante sea **más fuerte** o **más débil** que el bug (errata de `v2.43.1`). En esta
  fase, **7/7** mutaciones mordieron (pack §4).

## 4. Comandos de arranque (copia-pega)

```bash
git log --oneline -5
cat package.json | head -5                      # 1.69.0-beta
cd packages/py/infrastructure && uv run alembic heads    # 043_exit_identity_and_kill_state (SIN CAMBIOS)

uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió (debe salir vacío y exit 0)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores      # baseline: 2042 passed (v2.43.3); +33 de v2.44 certificado por CI real -> pack §9
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores # baseline: 2053 passed (v2.43.3); +33 de v2.44 certificado por CI real -> pack §9
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py                                          # 7/7 muerden
```

## 5. Formato de hallazgo

`P0/P1/P2 · afirmación · ruta:línea · comando · salida · ¿ya declarado en el pack §7?` — a responder en
el hilo del [issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62).
