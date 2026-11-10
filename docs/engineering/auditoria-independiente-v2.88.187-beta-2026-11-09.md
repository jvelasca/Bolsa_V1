# Auditoría funcional independiente — `v2.88.187-beta`

> **Objeto auditado:** tag anotado `v2.88.187-beta` (objeto `f60cc2a9…`) → commit
> `11161223e3c5d13b1db2a5fc422256066fc5bad4`; `package.json` `2.11.187-beta`.
> **Fecha del informe:** 2026-11-09. **Alcance:** verificación de identidad/publicación +
> revisión estática del delta contra `v2.88.186-beta` + suites objetivo ejecutadas en local.
> **Fuera de alcance (declarado en §9):** PostgreSQL real, E2E/Playwright, replay de mercado,
> repetición de la ventana PAPER y re-medición del bundle.

---

## 1. Veredicto

| Campo | Valor |
|---|---|
| **Veredicto** | **`PASS CON HALLAZGOS`** |
| Bloqueantes | **0** |
| Mayores | **2** (`M-1` verificabilidad de la cifra «185/185 verbatim»; `M-2` cambio de default de costes de backtest no declarado) |
| Menores | **6** |
| Observaciones | **5** |

No hay **ruptura de contrato**, ni **error monetario reproducible**, ni **cambio de motor no
declarado**: los tres cambios de cuerpo detectados en el worker son exactamente las features
que el `CHANGELOG` declara (`created_at` del fill; gate pico-valle de cuenta) más siete
`cast()` de tipado sin efecto en runtime.

Aplicando **literalmente** el criterio del plan (§8: `PASS` solo «sin hallazgos bloqueantes ni
mayores»), este sello **no** alcanza `PASS`: los dos mayores son de **declaración y
reproducibilidad**, no de comportamiento. Tampoco procede `FAIL`, porque ninguno de sus cuatro
disparadores se cumple. Por eso el veredicto es `PASS CON HALLAZGOS` con la salvedad explícita:
**no es un aprobado limpio; es un sello publicable con dos afirmaciones que deben corregirse o
reproducirse.**

---

## 2. Identidad y publicación

| Afirmación | Comprobación ejecutada | Resultado |
|---|---|---|
| El tag existe en el remoto y es el mismo objeto | `git ls-remote --tags origin v2.88.187-beta` vs `git rev-parse` | **OK** — `f60cc2a9…` en ambos |
| El tag es **anotado** y apunta a `11161223` | `git cat-file -p v2.88.187-beta` | **OK** — `object 11161223…`, `type commit`, `tag v2.88.187-beta`, tagger `jvelasca`, `1794252343 +0100` (= `2026-11-09T19:25:43Z`) |
| El pin del freeze es el árbol del tag | `git rev-parse "v2.88.187-beta^{commit}:apps" ":packages"` | **OK** — `apps d4921f79…` / `packages 030d6c4d…` |
| El pin commiteado coincide | `node scripts/window-pin.mjs --check` | **`freeze OK (11161223)`** + los dos tree hashes |
| `.186` no es el mismo árbol | `git rev-parse "v2.88.186-beta^{commit}:apps/:packages"` | **OK** — `d39a04a7…` / `2de53cda…` (distintos) |
| El `commit` del pin resuelve al árbol correcto | `git rev-parse bb605ebe:apps/:packages` | **OK** — mismos dos hashes que `HEAD`; posteriormente solo se tocaron `scripts/` y `docs/` |
| Release publicada, no borrador, no prerelease | `gh release view v2.88.187-beta --json tagName,targetCommitish,isDraft,isPrerelease,publishedAt,assets` | **OK** — `targetCommitish: main`, `isDraft: false`, `isPrerelease: false`, `2026-11-09T19:26:01Z`, **sin assets** |
| El CI del commit del tag está verde | `gh run list --commit 11161223` | **OK** — `Release tag CI` `42683260022`, `Optimize lab` `42683259958`, `Fase 2 scientific` `42683259791`, `Python CI` `42683259894`, `Frontend CI` `42683259972`: **5/5 `success`** |
| El CI del tag cubre los gates duros | `gh run view 42683260022 --json jobs` | **OK** — 14 jobs `success`; único `skipped`: `playwright (integrated E2E, opt-in)`. Incluye `Window freeze gate (pin == HEAD:apps/packages)`, `Window runner guards`, `contract:check`, `Mypy`, `Pytest offline`, `lifecycle-pg`, `replay-repro` (assert SHA-256 del artefacto), `a7-gate`, `dr-verify`, `decision-spine` |
| Bump correcto | `rg -c "2\.11\.187-beta"` + `rg "2\.11\.186-beta" apps packages package.json` | **OK** — 14 literales `meta.bump` en 13 scripts (`v2_100` ×2) + `package.json`; **0** restos `.186`; el literal congelado `"bump": "2.11.0-beta"` de `v2_87` sigue intacto (`v2_87_replay_oos_durable_cycle.py:1374`) |
| Sin migración nueva | recuento de `revision`/`down_revision` sobre `packages/py/infrastructure/alembic/versions` | **OK** — 66 revisiones, **una sola head**: `066_account_evidence_policy`; ningún fichero `067*` |

### 2.1 Matiz de secuencia (hallazgo `m-4`)

| Evento | Instante (UTC) |
|---|---|
| Tag creado (tagger) | `19:25:43` |
| Push del tag → CI del tag | `19:25:53` |
| **Release publicada** | `19:26:01` |
| `Frontend CI` de `main` para `11161223` **termina** | `19:28:46` |
| `Release tag CI` del tag **termina** | `19:39:29` |
| `Frontend CI` del PR #113 (`7c57a9e1`, **mismo árbol**) verde | `19:12:52` |

El árbol del commit de `main` es **idéntico** al del PR ya verde
(`git rev-parse 11161223^{tree}` = `7c57a9e1^{tree}` = `fe2d0d59…`), así que la afirmación
«el pin se re-ancla antes de etiquetar y el tag llega después de verde» es **cierta para el
árbol** y **falsa para las corridas**: ni el CI de `main` ni el del tag habían terminado al
crear el tag y publicar la Release. No hay defecto de contenido (todo acabó verde), pero la
frase del `CHANGELOG`/Release no es literalmente exacta.

---

## 3. Método y comandos ejecutados

Todo se ejecutó en local sobre el árbol del tag (`HEAD = 11161223`, sin cambios), con
`uv run python 3.12.13`. Los scripts auxiliares de auditoría (`AST`/`inspect`, diffs
estructurales, recuentos) fueron temporales y **se eliminaron** al cerrar el informe.

| Comando | Resultado literal |
|---|---|
| `node --test scripts/lib/window-forward.test.mjs scripts/lib/window-measurement-check.test.mjs scripts/lib/stack-ports.test.mjs` | `tests 86 · pass 86 · fail 0` |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `pnpm --filter @bolsa/web typecheck` | `tsc -b --noEmit` sin salida (limpio) |
| `pnpm exec vitest run` (suite web completa) | `Test Files 373 passed (373)` · `Tests 2777 passed (2777)` |
| `vitest run` (8 ficheros objetivo) | `Test Files 8 passed (8)` · `Tests 40 passed (40)` |
| `pytest packages/py/domain/tests/test_money_decimal_guard.py` | `15 passed in 0.11s` |
| `pytest test_baseline_arms.py test_sim_fill_created_at.py test_account_max_drawdown_gate.py` | `29 passed in 0.42s` |
| `pytest test_dia_d_bump_guard.py test_backtest_cost_defaults.py` | `5 passed in 5.30s` |
| `pytest test_auto_runtime.py` | `5 passed in 4.93s` |
| `pytest test_dia_d_equity_evidence.py test_v2_101_baseline_arms.py` | `29 passed in 4.92s` |
| `pytest test_auto_v2_closed_bars_and_bar_idempotency.py` | `6 passed in 5.23s` |
| `pytest` (los 10 ficheros objetivo en una sola invocación) | `89 passed in 5.93s` (re-ejecutado al cierre; coincide con la suma de las filas anteriores) |
| `pytest test_health.py` | **no completado en local** (el `lifespan` espera PG/Redis y no hay servicio; los dos intentos se terminaron tras ~7 min y ~2,5 min de espera). En CI corre en `lifecycle-pg` (no en el job offline, `--ignore` explícito) y **pasó** |
| `alembic heads` | bloqueado por el control de aplicaciones de Windows; sustituido por cálculo sobre los ficheros → head única `066` |

Verificaciones de comportamiento ejecutadas contra el árbol (no solo lectura):

```text
DepositCashDto(amount=0)        -> ValidationError greater_than
DepositCashDto(amount=-1)       -> ValidationError greater_than
DepositCashDto(amount=True)     -> ValidationError decimal_type
DepositCashDto(amount=NaN/Inf)  -> ValidationError finite_number
DepositCashDto(amount='abc')    -> ValidationError decimal_parsing
DepositCashDto(amount='12.34')  -> Decimal('12.34')  | json: {"amount":12.34,...}
CreateInvestmentAccountDto()    -> initial_deposit Decimal('100000.0') | json: 100000.0
AUTO_..._ACCOUNT_MAX_DD_PCT=0   -> /health declara 0.0 | motor resuelve None
```

---

## 4. Hallazgos

### 4.1 Bloqueantes

Ninguno.

### 4.2 Mayores

#### `M-1` — «185 métodos verbatim, 0 distintos» no es reproducible desde el árbol y, medido contra el padre del split, es inexacto

- **Qué se afirma:** `CHANGELOG.md` §`2.11.187-beta` (1), `PROJECT_STATE.md` (AsOf .187) y la
  Release: «Los **185** métodos se movieron **verbatim** y un verificador compara
  `inspect.getsource` por MRO: **0 ausentes, 0 distintos**.»
- **Qué se mide** (`cc1775de^` = fichero único → `cc1775de` = facade + 6 módulos, comparando
  por nombre y cuerpo normalizado):

| Métrica | Valor medido |
|---|---|
| Métodos definidos antes del split | **183** |
| Métodos definidos en el split | **185** |
| Ausentes | **0** |
| **Cuerpos distintos** | **3**: `_settle`, `_v2_governor_drawdown_pct`, `_v2_snapshot` |
| **Nuevos** | **2**: `_v2_account_drawdowns`, `_v2_account_max_drawdown_pct` |
| Colisiones de nombre entre las 4 mixins del MRO | **0** |

- **Naturaleza de las 3 diferencias** (todas declaradas como features del sello, ninguna como
  «refactor»):
  - `_settle`: añade `created_at=self._time` al fill (`v2.101`, «hueco de `created_at`»).
  - `_v2_governor_drawdown_pct` + `_v2_snapshot`: extraen el cálculo a
    `_v2_account_drawdowns()` y publican `max_drawdown_pct` (gate pico-valle, OFF por defecto).
- **Estado en el tag:** contra `.186` difieren **10** métodos; **7** son solo `cast(...)`
  (`_multiple_live_rows`, `_v2_adopt_position`, `_v2_edge`, `_v2_regime`,
  `_v2_release_reservation`, `_v2_sector`, `_v2_sectors_for` — no-op en runtime) y **3** son
  los funcionales anteriores.
- **Por qué es mayor y no bloqueante:** la afirmación **de contenido** («el refactor no cambia
  el motor») **se sostiene** tras revisar las 3 diferencias: son las features declaradas y
  ninguna altera decisiones con los flags por defecto (gate vacío/OFF). Lo que no se sostiene
  es **la cifra y su reproducibilidad**: el verificador `inspect.getsource` **no está
  versionado**, no corre en CI, y no puede reconstruirse desde el tag. Verificado el árbol,
  hay que corregir la frase a «185 métodos resueltos por el MRO; 3 con el cambio declarado del
  `created_at`/gate y 2 nuevos», o versionar el verificador.

#### `M-2` — El default de costes de backtest pasa de `0/0/0` a `10/5/2` sin declararlo en la entrega

- **Código** (`apps/api-python/src/bolsa_api/api/v1/routes/backtests.py`):

```diff
-            commission_bps=body.commission_bps or 0,
-            slippage_bps=body.slippage_bps or 0,
-            spread_bps=body.spread_bps or 0,
+            commission_bps=_cost_bps(body.commission_bps, _DEFAULT_COSTS.commission_bps),
+            slippage_bps=_cost_bps(body.slippage_bps, _DEFAULT_COSTS.slippage_bps),
+            spread_bps=_cost_bps(body.spread_bps, _DEFAULT_COSTS.spread_bps),
```

  con `_DEFAULT_COSTS = CampaignCosts()` (10/5/2 bps) y los DTO con `default=None`.
  El frontend acompaña el cambio (`backtest-cost-defaults.ts`, 10/5/2) y hay tests de paridad.
- **Impacto:** una petición que **omitía** los costes (antes: backtest «gratis») ahora paga
  10/5/2. Es una mejora de honestidad, pero **cambia resultados de backtests repetidos con el
  mismo payload** y no aparece en `CHANGELOG.md`, ni en `respuesta-auditoria-externa-2026-11-09.md`,
  ni en los expedientes de `docs/engineering/`. Solo está declarado en comentarios de código y
  en los tests.
- **Por qué es mayor:** el plan califica «cambio no declarado» como mayor. No es el motor AUTO
  (no dispara `FAIL`), pero es un instrumento de medida: la trazabilidad exige decirlo.

### 4.3 Menores

| Id | Hallazgo | Evidencia | Impacto |
|---|---|---|---|
| `m-1` | `/health.auto_runtime.accountMaxDrawdownPct` declara **`0.0`** con `AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT=0`, mientras el motor lo interpreta como **OFF** (`None`) | Ejecutado: health `0.0` / `tunables_from_env().account_max_drawdown_pct` `None`; `auto_v2_entry._account_max_dd_from_env` (`value <= 0 → None`) vs `bolsa_api/auto_runtime.py` (`env_finite_float(..., minimum=0.0)`) | El operador ve un corte de 0 % «configurado» que **no veta nada**. Contradice la regla del propio módulo («nunca se presenta como configurado algo que nadie configuró»). No hay test para `=0` en el snapshot |
| `m-2` | Buy & hold se publica como **neto** y la nota del runner dice «pasivo: paga un round-trip declarado, no opera gratis», pero `buy_hold_curve()` **no deduce coste** | `baseline_arms.buy_hold_curve` → `_basket_curve` sin `cost_fraction`; el test clava `curve[-1] == 150_000` para 100→200 sin coste; `v2_101` pasa `realized_cost_round_trip_bps=32` solo al **check** del umbral | El `netReturnPct` de B&H es **bruto** y el `excessVsBuyHoldPct` de los brazos activos se mide contra un benchmark ~**0,32 pp optimista**. No cambia el veredicto publicado (B&H falla por DD 23,59 % y ventanas 52,47 %) pero la etiqueta «neto» y la nota son incorrectas |
| `m-3` | Recuentos documentales incoherentes | `evidence/v2.88.186/README.md`: «`apps/` (86 ficheros) y `packages/` (43)». Medido: **apps 99** (35 tests / 64 sin tests), **packages 49** (6 tests / **43 sin tests**). El 43 cuadra; el 86 no cuadra con ninguna partición. Además «10.593 → 2.813»: medido **10 538** líneas pre-split y **2 813** en `cc1775de`, **2 823** en el tag | Documentación del sello desalineada con el objeto que publica (una errata de conteo y una cifra tomada en el commit del split, no en el tag) |
| `m-4` | Secuencia tag/Release/CI (§2.1) | Tag `19:25:43`, Release `19:26:01`, CI de `main` `19:28:46`, CI del tag `19:39:29` | La frase «tag después de verde» es cierta para el árbol del PR, no para las corridas citadas. Sin efecto en el contenido |
| `m-5` | `_v2_account_max_drawdown_pct()` (en `auto_worker_safety.py:527`) **no tiene llamadores**: la lógica real vive en `portfolio_decision_engine` (`_reject("HOLD", "account_max_drawdown_exceeded")`) | `rg _v2_account_max_drawdown_pct` devuelve solo la definición | Código muerto que sugiere un cableado inexistente; invita a creer que el worker aplica el corte desde ese método |
| `m-6` | El libro de caja vuelve a `float` en la frontera | `_debit_cash_row`/`_credit_cash_row` devuelven `float`; `append_*` del ledger aceptan `float \| Decimal` y hacen `Decimal(str(...))`; `custody.py` convierte `float(to_charge)`/`float(fee_amount)` antes de persistir | Exacto para céntimos (la repr más corta recupera el valor). Riesgo residual: `Numeric(18,6)` admite 18 dígitos significativos y un `float` solo garantiza ~17; un saldo de 12 enteros + 6 decimales podría no sobrevivir el viaje. La política «dinero en `Decimal`» es cierta en el dominio, no en el borde |

### 4.4 Observaciones

| Id | Observación |
|---|---|
| `o-1` | `_basket_curve` equipondera **solo los símbolos ya iniciados**: cuando uno nuevo entra a nivel 1.0 el nivel de la cesta **salta** (rebalanceo a coste cero). Afecta a retorno/DD absolutos; ambos brazos pasivos usan la misma cesta, así que el **exceso comparativo** está menos expuesto |
| `o-2` | `evaluate_baseline(..., thresholds=...)` admite un override de los cinco umbrales. El script no lo usa y el test los clava, pero la puerta existe para mover el listón a posteriori |
| `o-3` | `.env.example` abre con «Todos nacen APAGADOS/VACÍOS» y luego documenta `AUTO_ENGINE_SIM_V2_COST_MODEL` como «Default ON en el motor». Precisión mejorable (el resto de interruptores sí nacen OFF) |
| `o-4` | `/health.auto_runtime` es contrato aditivo **sin lector en la web** (solo el tipo generado en `schema.d.ts`). No es un defecto; es superficie declarativa sin UI todavía |
| `o-5` | `quantize_price`/`PRICE_QUANT` existen pero **no se aplican en el borde HTTP**: `PlainSerializer(float)` publica el `Decimal` íntegro. Coherente con «cuantizar es explícito», pero no hay punto único de cierre para precios publicados |

---

## 5. Delta funcional por área

### 5.1 Refactor del worker AUTO — **VERDE (con `M-1`)**

- `auto_simulation_worker.py` **10 538 → 2 813** líneas en `cc1775de` (2 823 en el tag tras el
  fix de mypy); 6 módulos nuevos: `shared` 1 023, `price` 704, `state` 1 459, `safety` 1 898,
  `execution` 1 867, `runtime` 1 944.
- Facade: 25 entradas en la clase (**19 métodos**, incluido `__init__`, + 6 atributos/dunders),
  **0 colisiones** entre `_PriceMixin`/`_StateMixin`/`_SafetyMixin`/`_ExecutionMixin`; el MRO
  resuelve cada nombre a un único cuerpo.
- Seams `monkeypatch` y `logger` conservados (los tests de `test_auto_runtime` y
  `test_auto_v2_closed_bars_and_bar_idempotency` pasan sin tocar módulos internos).
- **Conclusión:** el refactor no cambia el motor; los 3 cuerpos distintos son features
  declaradas. La cifra «185/185» debe corregirse (**`M-1`**).

### 5.2 Baseline Arms — **VERDE (con `m-2`, `o-1`, `o-2`)**

- Los cinco umbrales están **clavados por test** (`BASELINE_THRESHOLDS == {...}`, incluido
  `minRoundTripCostBps = 22.0`), sin parámetros que los muevan; el script no pasa `thresholds`.
- **Sin look-ahead:** la señal se evalúa con `closes[:index+1]` (cierre del día, conocido al
  cierre) y la orden se ejecuta en el **open del día siguiente** (`pending`). El test de
  tendencia valida `100 000 × (1 − 12/10 000) × 200/150`.
- Costes: `round_trip_bps = 2 × (commission + slippage) + spread = 32 bps`; el brazo tendencia
  paga `per_side` en cada entrada y salida; el pasivo **no** (ver `m-2`).
- `None` = no medido en todo el camino (`signalUnmeasurableDays`, `NOT_MEASURED`), sin ceros
  fabricados.
- La conclusión publicada («ningún brazo razonable gana con 32 bps») es coherente con las
  tablas: B&H falla por DD y ventanas; tendencia falla además por exceso (−17,48 pp).

### 5.3 Dinero y contabilidad en `Decimal` — **VERDE (con `m-6`)**

- `money.py` es política única y se comporta como declara: `to_decimal` vía `str`, rechazo de
  `bool`/`None`/`NaN`/`Inf`/texto, `quantize_*` HALF_EVEN, `None` preservado por
  `coerce_money_fields`. Construir la entidad **no** redondea.
- Entidades (`account.py`, `portfolio.py`) blindadas en `__post_init__`; repos leen con
  `to_decimal`; acumuladores de `portfolio_repository` pasan a `Decimal(0)`; custodia calcula
  en `Decimal` y **cuantiza a céntimos antes** del ledger.
- **Borde HTTP intacto:** validado en runtime (`gt=0` → `greater_than`, `ge=0` →
  `greater_than_equal`, `bool` → `decimal_type`, `NaN/Inf` → `finite_number`) y serializado
  como **número** (`PlainSerializer(float)`), no como string.
- **Diff estructural del OpenAPI:** 240 paths sin cambios; +1 schema (`AutoRuntimeDto`);
  **5 líneas retiradas, todas cotas** (`minimum`×3, `exclusiveMinimum`×2). Ningún campo ni
  ruta desaparece.
- Guard ejecutable de 395 líneas (15 tests) con comprobación de exenciones no obsoletas.

### 5.4 Contrato API/UI — **VERDE**

- `contract:check` **OK**; `schema.d.ts` **+34/−0**; `openapi.json` **+101/−5** (verificado con
  `git diff --numstat`).
- 25 páginas por `import()` literal con export homónimo; `app.tsx` **no** importa ninguna
  página estáticamente (solo `PlatformShell`, `AuthGate` y el analizador de charts); test que
  recorre cada loader y falla si el export no existe.
- 401 global: `handleUnauthorizedError` devuelve un resultado comprobable
  (`not_401`/`auth_disabled`/`already_unauthenticated`/`session_expired`), `expireSession()`
  conserva `authEnabled` y **no** llama a logout; el `retry` de queries excluye 401 (corte de
  bucle). `globalThis.setTimeout` en el push diferido del mandato con test de regresión.
- Suites: 40 tests objetivo y **373 ficheros / 2777 tests** completos en verde; `typecheck`
  limpio.

### 5.5 Áreas secundarias — **VERDE (con `M-2`, `m-1`)**

- **Backtests:** defaults 10/5/2 alineados cliente↔servidor con tests; falta declararlo
  (`M-2`).
- **DÍA D:** `realized_cost_round_trip_bps = 2 × per_side (+ 2 × commission)` corrige el error
  de unidades; `curveBasis: "realized_cash"` y `curveBasisNote` declaran que el DD es de caja y
  no de cartera; `notMeasured`/`caveats` no fabrican ceros. Coherencia aritmética comprobada:
  12,7 bps/lado × 2 + 10 × 2 = **45,4 bps** (la tabla publica 45,41).
- **Entorno/AUTO:** todos los interruptores nacen OFF y `.env.example` los documenta; el
  modelo de coste nace ON y también se declara (`o-3`). El gate pico-valle nace vacío y veta
  **solo aperturas** (decisión en `portfolio_decision_engine`, las salidas no pasan por ahí).
  Único desajuste de declaración: `=0` en `/health` (`m-1`).
- **Herramientas PAPER:** `window:test` **86/86**; `window-pin --check` **freeze OK**;
  `window-measurement-check` declara `UNKNOWN`/`WARN` en vez de ceros (tests S1–S6).

---

## 6. Contraste documental

| Cifra publicada | Medición | Dictamen |
|---|---|---|
| Delta: `apps` **99** / `packages` **49** | 99 / 49 (195 ficheros totales; 47 fuera de ambos) | **OK** |
| `openapi.json` **+101/−5**; `schema.d.ts` **+34/−0** | idéntico (`--numstat`) | **OK** |
| `window:test` **86 passed** | 86/86 | **OK** |
| Web **373 ficheros / 2777 tests** | 373 / 2777 | **OK** |
| Ratchet `S110`/`S112` en **23** módulos | 23 ficheros de producción con `logger.debug(..., exc_info=True)` añadido | **OK** |
| Worker **185** métodos **verbatim**, 0 distintos | 183 pre-split; 3 distintos; 2 nuevos | **NO reproducible / inexacto** (`M-1`) |
| Worker **10.593 → 2.813** líneas | 10 538 pre-split; 2 813 en el split; **2 823** en el tag | **Inexacto** (`m-3`) |
| `.186` evidence: `.187` toca `apps` **86** / `packages` **43** | 99 (64 sin tests) / 49 (43 sin tests) | **`packages` OK; `apps` no reproducible** (`m-3`) |
| `cierre-auditoria` README: `window:test` **79**; pin `c6cef5c9 / 2675ed02… / 27df4722…` | 86; pin final `d4921f79… / 030d6c4d…` | **Foto anterior al re-anclaje**, sin nota de supersesión (`m-3`) |
| Bump **14** literales de **13** scripts | 14 / 13 (`v2_100` ×2) + `package.json`; 0 restos `.186` | **OK** |
| Bump literal congelado `2.11.0-beta` de `v2_87` intacto | `v2_87_replay_oos_durable_cycle.py:1374` | **OK** |
| `head` de migraciones `066`, sin `067` | 66 revisiones, head única `066_account_evidence_policy` | **OK** |
| Release sin assets | `assets: []` | **OK** |

---

## 7. Deuda declarada por el sello (no es hallazgo)

- Gate de ventana **`STALE`**: las jornadas medidas son de árboles anteriores; la corrida del
  `2026-11-09` no llegó al ledger (`.run.lock` huérfano tras caída). **La jornada no está
  medida** y el sello no la reclama.
- AUTO **OFF**, PAPER **`INCONCLUSIVE`**, rentabilidad **no demostrada**, sin órdenes reales.
- Curva de evidencia en **caja realizada** (no cartera): el DD de 292,21 % del brazo AUTO se
  declara con esa lente.
- Universo de los brazos pasivos (catálogo actual) ≠ universo PIT anual del brazo AUTO: se
  declara y cada brazo usa su propio benchmark.

---

## 8. Criterio de veredicto aplicado

- `PASS` — identidad/publicación verdes y cinco áreas verdes **sin bloqueantes ni mayores**: no
  alcanzado (2 mayores).
- **`PASS CON HALLAZGOS` — sin bloqueantes, sin ruptura de contrato, sin error monetario, sin
  cambio de motor no declarado; dos mayores de declaración/reproducibilidad y menores de
  documentación: aplicado.**
- `FAIL` — ruptura de contrato (no: delta aditivo, `contract:check` OK), error de dinero (no:
  validación y serialización preservadas, sin regresión reproducida), cambio de motor no
  declarado (no: los 3 cuerpos distintos son features declaradas), claim central no
  reproducible (no: la afirmación *de contenido* se verificó por método independiente; lo que
  falla es la **cifra** y el verificador, no el hecho).

---

## 9. Límites de esta auditoría

1. **No se reprodujo PostgreSQL.** `test_simulated_finance_pg.py`,
   `test_auto_v2_real_price_production_pg.py`, `test_auto_v88_83_evidence_composition_pg.py` y
   `test_health.py` no se ejecutaron en local; `test_health.py` cuelga en el `lifespan` sin
   servicios. En CI corren en `lifecycle-pg` y **pasaron**, pero esta auditoría no re-valida esa
   certificación.
2. **No se ejecutó E2E/Playwright** ni el replay de mercado; no se comprobó que
   `replay-repro` produzca el SHA-256 del artefacto más allá de que el job del tag salió verde.
3. **No se repitió la ventana PAPER** ni la corrida del `2026-11-09`: el estado `STALE` del gate
   se toma como declaración del sello, no se certifica.
4. **No se re-midió el bundle** (`−950,38 kB / −26,8 %`, `−241,48 kB gzip`): se acepta como
   cifra declarada; no se reconstruyó el build previo para comparar.
5. **`alembic heads`** no se pudo invocar (bloqueo del sistema); la head se calculó por análisis
   de `revision`/`down_revision`, que no sustituye a `alembic` para detectar ciclos o errores de
   importación de las migraciones.
6. **`pnpm types:py` / `lint:py` / `mypy`**: no re-ejecutados; se citan los pasos del
   `Release tag CI` del tag (`Mypy`, `Ruff`, `Import-linter`, todos `success`).
7. El árbol de trabajo **no se modificó**: el único artefacto de esta auditoría es este informe.
   Los scripts temporales de verificación se eliminaron.
