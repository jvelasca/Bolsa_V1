# Cierre ratificado de la auditoría independiente `v2.88.187-beta`

**Fecha del cierre:** 2026-11-10 · **Objeto:** tag anotado `v2.88.187-beta` → commit
`11161223e3c5d13b1db2a5fc422256066fc5bad4` (`package.json` `2.11.187-beta`) · **Dictamen ratificado:**
`PASS CON HALLAZGOS` como **auditoría independiente**, con **0 bloqueantes**, **2 mayores** (`M-1`,
`M-2`) y **6 menores**.

**Naturaleza de este documento:** cierre **documental**. No hay bump, no hay tag nuevo, no se
re-etiqueta ni se re-publica `.187` y **no se toca** `apps/` ni `packages/`. El motor, el contrato y la
Release quedan exactamente como se auditaron.

Informe comentado: [auditoria-independiente-v2.88.187-beta-2026-11-09.md](./auditoria-independiente-v2.88.187-beta-2026-11-09.md).

---

## 1. Veredicto ratificado

| Campo | Valor |
|---|---|
| Veredicto | **`PASS CON HALLAZGOS`** |
| Bloqueantes | **0** |
| Mayores | **2** — `M-1` (cifra «185/185 verbatim» no reproducible), `M-2` (cambio de costes por defecto no declarado) |
| Menores | **6** |
| Observaciones | **5** |
| Estado del objeto | Tag y Release publicados e intactos; **sin reapertura** |

El sello **no** es un aprobado limpio: es un objeto publicable con **dos afirmaciones que debían
corregirse** y **cuatro límites de certificación** que siguen abiertos. Ninguno de los disparadores de
`FAIL` se cumple —no hay ruptura de contrato, ni error monetario reproducible, ni cambio de motor no
declarado— y por eso no procede reabrir `.187`.

## 2. Discrepancia de los tests Python: resuelta

La ampliación de evidencia cierra la diferencia entre la cifra citada por el sello y la reproducida por
la auditoría:

| Comprobación | Resultado |
|---|---|
| `pytest` de los **10 ficheros objetivo** en una sola invocación | **`89 passed in 5.93s`** |
| Suma de las ejecuciones individuales | **89** — coincide |
| `test_health.py` | **Excluido**: su `lifespan` exige PostgreSQL y Redis locales, que no están disponibles en la máquina de auditoría. En CI corre en `lifecycle-pg` (con `--ignore` explícito en el job offline) y pasó |
| Códigos de salida `4294967295` | **No son fallos de pytest**: son `0xFFFFFFFF`, la lectura sin signo de un `exit == -1`, que corresponde a la **terminación manual** de los procesos que esperaban servicios |

Conclusión: la cifra `89 passed` es correcta y el aparente rojo era del arnés de ejecución, no de la
suite. No queda hallazgo por este motivo.

## 3. Condiciones de cierre

| # | Condición | Estado en este cierre |
|---|---|---|
| `C-1` | No repetir la afirmación «185 métodos verbatim»; describir la equivalencia con las cifras AST verificadas y, en una versión futura, disponer de un verificador **versionado y ejecutado en CI** | **Cumplida en documentación** (§4). El verificador versionado queda como deuda (§9) |
| `C-2` | Documentar expresamente el cambio de costes por defecto `0/0/0 → 10/5/2`, porque modifica resultados de backtests | **Cumplida** (§5) |
| `C-3` | Declarar los límites de certificación: PostgreSQL real, E2E, replay, ventana PAPER y bundle | **Cumplida** (§6) |
| `C-4` | Declarar la seguridad operativa: AUTO **OFF**, PAPER **`INCONCLUSIVE`**, **100 % SIM** | **Cumplida** (§7) |

No se reabre `.187` ni se modifica el motor para cerrar esta auditoría. Los dos hallazgos mayores se
conservan en la **deuda de la siguiente entrega** (§9).

## 4. `M-1` corregido — la equivalencia, con cifras reproducibles

### 4.1 Qué se afirmaba y por qué no era reproducible

`CHANGELOG.md`, `PROJECT_STATE.md`, el documento del split y la Release afirmaban «los **185** métodos se
movieron **verbatim** … un verificador compara `inspect.getsource` por MRO: **0 ausentes, 0
distintos**». La afirmación **de contenido** se sostiene —el refactor no altera el motor—, pero la
**cifra** es inexacta y el verificador que la producía **no está versionado**, no corre en CI y no puede
reconstruirse desde el tag.

### 4.2 Medición reproducible (comparación AST por nombre y cuerpo normalizado)

Comparando `cc1775de^` (fichero único) con `cc1775de` (facade + 6 módulos), emparejando por **nombre de
método** dentro de `AutoSimulationWorker` y de las cuatro mixins:

```text
pre-split AutoSimulationWorker.methods = 183
split facade+mixins resolved by MRO  = 185
by class: AutoSimulationWorker=18, _PriceMixin=33, _StateMixin=47, _SafetyMixin=50, _ExecutionMixin=37
missing = 0 []
different = 3 ['_settle', '_v2_governor_drawdown_pct', '_v2_snapshot']
added = 2 ['_v2_account_drawdowns', '_v2_account_max_drawdown_pct']
name collisions = 0 []
```

| Métrica | Valor |
|---|---|
| Métodos definidos antes del split | **183** |
| Métodos resueltos por el MRO del split | **185** (`18 + 33 + 47 + 50 + 37`) |
| Ausentes | **0** |
| Cuerpos distintos | **3** |
| Nuevos | **2** |
| Colisiones de nombre entre mixins | **0** |

### 4.3 Los 3 cuerpos distintos, y por qué no son un cambio encubierto

| Método | Diferencia | Naturaleza |
|---|---|---|
| `_settle` | añade `created_at=self._time` al fill | Feature declarada (`v2.101`, hueco de `created_at`) |
| `_v2_governor_drawdown_pct` | extrae el cálculo a `_v2_account_drawdowns()` | Feature declarada (gate pico-valle) |
| `_v2_snapshot` | publica `max_drawdown_pct` desde `_v2_account_drawdowns()` | Feature declarada (gate pico-valle) |

El gate pico-valle nace **vacío/OFF**, así que con los flags por defecto ninguna de las tres diferencias
altera una decisión. Por eso el hallazgo es **de declaración y reproducibilidad**, no de comportamiento.

### 4.4 Formulación que sustituye a la anterior

> El split resuelve **185** métodos por el MRO del facade (18 propios + 33 `_PriceMixin` + 47
> `_StateMixin` + 50 `_SafetyMixin` + 37 `_ExecutionMixin`), **sin colisiones** de nombre; **0 ausentes**
> respecto a los **183** métodos del fichero único previo; **3** conservan el cambio declarado
> (`created_at` del fill y gate pico-valle de cuenta) y **2** son nuevos, ambos del gate. El verificador
> `inspect.getsource` fue **temporal** y no está versionado.

### 4.5 Criterio de aceptación para la versión futura

`M-1` se considerará cerrado cuando exista un verificador **versionado en el repositorio**, ejecutado en
**CI** sobre el tag publicado, que:

1. compare método a método por nombre y cuerpo normalizado entre el fichero previo y el split;
2. publique el recuento esperado y el obtenido (`183 → 185`, `0` ausentes, `3` distintos, `2` nuevos);
3. **falle** si aparece cualquier diferencia no declarada en una lista explícita de excepciones.

## 5. `M-2` declarado — costes de backtest `0/0/0 → 10/5/2`

### 5.1 Qué cambia

| Antes | Ahora |
|---|---|
| Un payload que **omitía** los costes ejecutaba con `0/0/0` bps («backtest gratis») | Un payload que **omite** los costes ejecuta con **`10/5/2` bps** |
| `body.commission_bps or 0` | `_cost_bps(body.commission_bps, _DEFAULT_COSTS.commission_bps)` |
| DTO sin distinguir el silencio de un `0` | DTO con `default=None` (`commissionBps`/`slippageBps`/`spreadBps`), de modo que el silencio se distingue de un `0` explícito |

Fuente única en el servidor:
[`apps/api-python/src/bolsa_api/api/v1/routes/backtests.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/backtests.py)
— `_DEFAULT_COSTS = CampaignCosts()` y `_cost_bps(value, default)` (líneas 62-71), aplicado en las líneas
175-177. Los tres campos nacen `None` en
[`schemas/backtests.py`](../../apps/api-python/src/bolsa_api/schemas/backtests.py) (`BacktestRunRequestDto`,
líneas 93-95). Un `0` **explícito** sigue siendo válido para análisis de sensibilidad; lo que ya no vale
es **el silencio**.

El frontend acompaña el cambio con la misma fuente:
[`apps/web/src/features/backtests/lib/backtest-cost-defaults.ts`](../../apps/web/src/features/backtests/lib/backtest-cost-defaults.ts)
— `DEFAULT_BACKTEST_COSTS = { 10, 5, 2 }` y `optionalCostBps()` devolviendo `undefined` para campo vacío,
de modo que el default lo aplique el backend y no se dupliquen dos números distintos.

### 5.2 Impacto, dicho sin adornos

- **Cambia resultados de backtests repetidos con el mismo payload.** Un backtest que antes salía «gratis»
  ahora paga 10/5/2 bps por operación.
- Es una mejora **de honestidad**, no una regresión: el motor mide ~12,7 bps por lado en el replay, y
  comparar contra un `0` era un techo optimista.
- La cobertura de paridad existe:
  [`apps/api-python/tests/test_backtest_cost_defaults.py`](../../apps/api-python/tests/test_backtest_cost_defaults.py)
  clava que el default de la ruta es el de `CampaignCosts`, que `None` se convierte en el default, que un
  `0` explícito se respeta y que los DTO dejan los costes ausentes en `None`; el test del frontend cubre
  la resolución del texto y el `undefined` del campo vacío.
- **No** afecta al motor AUTO, ni al replay sellado, ni a la ventana PAPER: es un instrumento de medida
  del laboratorio de backtests.

## 6. Límites de certificación (siguen abiertos)

Estos puntos **no** están certificados por la auditoría independiente ni por este cierre, y no deben
presentarse como medidos:

| Límite | Estado |
|---|---|
| **PostgreSQL real** | No reproducido en local. Las suites PG se citan por el verde de `lifecycle-pg`, no se re-validan |
| **E2E / Playwright** | No ejecutado (`playwright (integrated E2E, opt-in)` figura `skipped` en el CI del tag) |
| **Replay de mercado** | No re-ejecutado; se acepta el verde de `replay-repro`, no se reconstruye el SHA-256 |
| **Ventana PAPER** | No repetida; el gate está **`STALE`** y la jornada del `2026-11-09` **no está medida** |
| **Bundle** | No re-medido; `−950,38 kB / −26,8 %` se acepta como cifra declarada |

## 7. Seguridad operativa

| Interruptor | Estado |
|---|---|
| AUTO | **OFF** |
| PAPER | **`INCONCLUSIVE`** |
| Ejecución | **100 % SIM** — ninguna orden real |
| Rentabilidad | **No demostrada** |

Nada de lo publicado en `.187` autoriza a pasar a dinero real. Los bloqueos de dinero real siguen
declarados en
[respuesta-auditoria-externa-2026-11-09.md](./respuesta-auditoria-externa-2026-11-09.md) §1.4 y §6:
stop en firme en el bróker, invariante `protective_order_present` por tick, kill switch de aperturas y
corrección del `mark = 0.0` que hoy infla la métrica de toques.

## 8. No reapertura

- El tag `v2.88.187-beta` (`f60cc2a9…` → `11161223…`) y su Release **no se borran, ni se mueven, ni se
  vuelven a publicar**.
- No se parchea el motor para cerrar esta auditoría.
- Las correcciones de `M-1` y `M-2` son **documentales** y quedan fechadas donde corresponde
  (`CHANGELOG.md`, `PROJECT_STATE.md` y `dividir-worker-auto-2026-11-08.md`), sin cambiar lo que el tag
  contiene.

## 9. Deuda de la siguiente entrega

| Id | Deuda | Criterio de cierre |
|---|---|---|
| `M-1` | Verificador de equivalencia **versionado** y ejecutado en **CI** | El job publica `183 → 185`, `0` ausentes, `3` distintos, `2` nuevos y falla ante diferencias no declaradas (§4.5) |
| `M-2` | Cambio de defaults ya declarado; falta comprobar su efecto en backtests guardados | Documentar en el `CHANGELOG` de la versión el efecto sobre resultados previos y la paridad cliente↔servidor en el CI |
| `m-1` | `/health.auto_runtime.accountMaxDrawdownPct` declara `0.0` mientras el motor lo interpreta como OFF (`None`) | El snapshot declara `null`/OFF cuando el valor no veta nada |
| `m-2` | Buy & hold se publica como «neto» sin deducir coste | La curva pasiva deduce el round-trip declarado o la etiqueta deja de decir «neto» |
| `m-5` | `_v2_account_max_drawdown_pct()` sin llamadores | Cablear el corte o retirar el método muerto |
| `m-6` | El libro de caja vuelve a `float` en la frontera | `Decimal` de extremo a extremo, incluida la persistencia `Numeric(18,6)` |

Los menores restantes (`m-3`, `m-4`) son erratas de conteo y de secuencia y no requieren código.

## 10. Protocolo de revisión de la siguiente versión

Cuando exista la siguiente versión, la revisión **parte del tag publicado** y no de la rama de trabajo:

1. **Identidad:** objeto anotado del tag, commit al que apunta, `package.json`, Release (no borrador, no
   prerelease) y CI del commit del tag.
2. **`M-1`:** ejecutar el verificador versionado y comprobar que publica las cifras y que falla ante
   diferencias no declaradas.
3. **`M-2`:** comprobar que el cambio de costes está declarado y que la paridad cliente↔servidor se
   mantiene.
4. **Cadena completa `Decimal → PostgreSQL → API → React`:** origen en `Decimal`, persistencia
   `Numeric`, serialización en la API como número y consumo en la web, con comprobación de ida y vuelta.
5. **Rentabilidad:** el CI verde **no** certifica rentabilidad. Solo una ventana PAPER medida y no
   `STALE` puede sostener una afirmación de resultado.

## 11. Artefactos

| Artefacto | Ruta |
|---|---|
| Informe de auditoría (cita histórica, sin cambios) | [auditoria-independiente-v2.88.187-beta-2026-11-09.md](./auditoria-independiente-v2.88.187-beta-2026-11-09.md) |
| Este cierre | `docs/engineering/cierre-auditoria-independiente-v2.88.187-beta-2026-11-10.md` |
| Sección del sello corregida | [CHANGELOG.md](../../CHANGELOG.md) §`2.11.187-beta` |
| Estado del proyecto corregido | [PROJECT_STATE.md](./PROJECT_STATE.md) `AsOf (V2.88.187-beta)` |
| Documento del split corregido | [dividir-worker-auto-2026-11-08.md](./dividir-worker-auto-2026-11-08.md) |

El delta de este cierre es **solo de documentación**: `git status --porcelain -- apps packages` queda
vacío y no se crea commit, tag ni Release en este paso.
