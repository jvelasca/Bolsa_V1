# Evidencia `v2.88.151-beta` — Ayuda de usuario: cómo se elige y se confirma la operativa de cada valor (DÍA D)

> **Bump:** `2.11.150-beta` → **`2.11.151-beta`** (`package.json` + `meta.bump` de los **13** CLIs;
> guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py)
> **2 passed**). Tag **unsigned**.
>
> **Cambio:** **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`**
> (`openapi.json`/`schema.d.ts` **sin diff**; `contract:check` **OK**) · **SIN migración**
> (head `056_auto_ops_jobs`). Incremento **solo de UI/Ayuda + documentación**: no toca
> motor, umbrales, pesos A/B, gobernador, sizing, salidas ni esquema.

## 1. El hueco

El usuario veía el embudo del Laboratorio (Probar → Coach → Lab → Revalidar → Finalistas) y el
estado `lab_validated`, pero **no existía una explicación legible** de:

- *por qué* se propone una operativa concreta para **ese** valor (y no otra);
- cómo se mide «mejor» y cómo se comprueba que el resultado no es suerte;
- qué puertas hay que pasar y quién confirma;
- con qué reglas se decide **entrar** y **salir**.

El conocimiento existía disperso en ADR-021/046/047 y en la evidencia de ingeniería, fuera del
alcance del usuario. **No era un defecto de motor**: era un hueco de **producto/Ayuda**.

## 2. Qué cambió (y qué no)

| Pieza | Cambio |
| --- | --- |
| [`backtesting-tracker.ts`](../../../../apps/web/src/features/settings/backtesting-tracker.ts) | NUEVO `BACKTESTING_STRATEGY_CHOICE_GUIDE`: 5 secciones y 5 notas (embudo · métricas · puertas · entrada · salida). |
| [`backtesting-help-section.tsx`](../../../../apps/web/src/features/settings/backtesting-help-section.tsx) | Renderiza la guía como `<Card>` en **Ayuda → Backtesting**. |
| [`help-content-as-of.ts`](../../../../apps/web/src/features/help/help-content-as-of.ts) | `HELP_CONTENT_AS_OF = "2026-10-19"` (sincronía Ayuda ↔ docs). |
| [`docs/HELP.md`](../../../HELP.md) | Sección nueva: «Cómo se elige la operativa de un valor (usuario · DÍA D · sync 2026-10-19)». |
| Tests | [`backtesting-tracker.test.ts`](../../../../apps/web/src/features/settings/backtesting-tracker.test.ts) y [`hoy-en-la-mesa.test.tsx`](../../../../apps/web/src/features/help/hoy-en-la-mesa.test.tsx) asertan la guía y la sincronía con `HELP_CONTENT_AS_OF`. |

**No** se toca: `auto_v2_entry`, `classify_market_regime`, `regime_allows_entry_for`,
`replay_oos` (contenido), `TOP_N`, umbrales, pesos A/B, gobernador, sizing, salidas, contrato HTTP
ni esquema. El único cambio fuera de UI/docs es el `meta.bump` de los 13 CLIs (etiqueta).

## 3. Qué explica la guía (resumen verificable)

1. **Embudo:** Probar (familias genéricas + propias/Finalistas) → Coach (TOP ★ ≤ 3, ACK humano) →
   Lab (parámetros **solo** con la primera parte del histórico, IS) → Revalidar (hold-out OOS,
   walk-forward, CPCV con purga/embargo, PBO, DSR) → Finalistas (`runId` + `lab_validated` + ACK
   final). El #1 es **operativa propuesta**, no una orden.
2. **«Mejor» medido:** `score = retorno % − 0,25 × peor caída %`; OOS 10–40 % con mínimos
   50 barras IS / 30 OOS; WFE y % de pliegues positivos; PBO < 0,5 baja / ≥ 0,7 alta; DSR ≥ 0,7.
3. **Confirmación:** 7 puertas fail-closed (`backtest`, `robustness`, `walk_forward`, `oos`,
   `risk`, `dsr`, `coach`); `NOT_EVALUATED` **no** es `PASS`; veredicto global siempre
   `NO CONFIRMADO`; ventana PAPER `INCONCLUSIVE` mientras no haya operación suficiente.
4. **Entrada:** señal → ranking explicable (edge 30 %, robustez 20 %, régimen 15 %, momentum 10 %,
   liquidez 10 %, R/R 10 %, ejecución 5 %) → `TOP_N = 5` → barrera de régimen **por valor**
   (ADR-047; `RISK_OFF`/`CRISIS` globales, `UNKNOWN` no opera) → stop `1,5 × ATR` → sizing por
   riesgo (1 % por operación, 20 % por posición, 40 % por sector, 6 % abierto) → `TradePlan` →
   permiso de apertura (SEMI firma; AUTO solo PAPER).
5. **Salida:** precedencia única `kill switch > régimen > riesgo > manual > stop estructural >
   tesis invalidada > riesgo de cartera > T1 > T2 > trailing > tiempo`; T1/T2 reducen 30 %;
   trailing solo aprieta (ratchet); techo de 45 días; tesis confirmada con el MAE; gobernador.

## 4. Verificación (medida)

| Comprobación | Resultado |
| --- | --- |
| `vitest run src/features/settings/backtesting-tracker.test.ts src/features/help/hoy-en-la-mesa.test.tsx` | **2 ficheros · 11 tests passed** (7 + 4) |
| `test_dia_d_bump_guard` | **2 passed** |
| `typecheck` | **OK** |
| `eslint` | **OK** |
| `contract:check` | **OK** (sin diff de contrato) |
| `window:freeze` | **OK** tras re-anclar el pin al árbol del sello |

## 5. Freeze y ventana PAPER

El commit `ea3a1734` (Ayuda) movió el árbol `apps` (`de832655…`), por lo que el pin PAPER
(`c5967218…`) quedaba `TREE_MOVED` y **el run de las 18:00 habría abortado fail-closed**. Se
re-ancla el pin al árbol del sello (`Δ motor = 0`) y `window:freeze` vuelve a **OK**. El
re-anclaje **no** edita código: solo `commit`/`appsHash`/`packagesHash` en `scripts/`.

## 6. Límites declarados (sin fabricar)

- La Ayuda explica el **criterio**, **no** promete rentabilidad: un backtest bueno puede fallar en
  el futuro, y la app lo declara (`NO CONFIRMADO` / `INCONCLUSIVE`).
- La evidencia agregada DÍA-D es del **valor**; lo exacto es la fila del ciclo verificado con su
  identidad de estrategia.
- La ventana PAPER **no** se re-mide en este sello; sus filas PRE siguen `NO_MEDIDO_REGIMEN`.
- Operativa **100 % SIM** (PAPER / dinero virtual); no se envían órdenes reales a ningún bróker.
- Tag **unsigned**.

## 7. Publicación (POST-TAG)

- Tag anotado **`v2.88.151-beta` → `8bef1757`** (bump `fae6d0d2` + re-anclaje `8bef1757`), `main`
  publicada (`894637b4..8bef1757`).
- `Release tag CI` [run `39282296257`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39282296257)
  **VERDE** en el reintento (`7m44s`; `shared`, `python`, `playwright` ×3, `security`,
  `decision-spine`, `frontend`, `lifecycle-pg`, `replay-repro`, `a7-gate`, `dr-verify` y `certify`
  en `success`). `shared` ⇒ **`freeze OK`**; `replay-repro` ⇒ **`REPRODUCIDO`** (el artefacto del
  sello `.150` no cambia: **`Δ decisión = 0`**).
- **Incidencia declarada:** el primer intento (`29m24s`) quedó **rojo** en `frontend → Test web`
  por `Test timed out in 5000ms` en
  [`dia-d-auto-run.test.tsx:162`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-run.test.tsx)
  (los `waitFor` usan `SLOW_CI = 10 s` pero el timeout global de Vitest es `5 s`), coincidiendo con
  el incidente de GitHub Actions (`15:49Z`–`16:0xZ`, impacto *critical*). El **mismo** test pasó en
  `Frontend CI` de `main` y en el reintento ⇒ se declara **flaky por timeout**, no un fallo del
  sello. Queda como hueco: alinear `testTimeout` con `SLOW_CI` en ese fichero.

## 8. Operación del día (2026-10-19)

El `run-day` programado de las `18:00` se ejecutó (`18:00:01–04`) pero terminó **`HARD_ERROR` /
`API_NOT_READY`**: el runner cargó `.env` (`loadEnvFile`) y resolvió el puerto como
`API_PYTHON_PORT → API_PORT → 8000`; el `.env` solo definía **`API_PORT=3001`** (puerto de la web)
⇒ probó `http://127.0.0.1:3001/api/health/ready` mientras la API Python escuchaba en **`:8000`**.
El preflight sí era correcto (`ALLOWED`, `per_symbol`, `15/35` operables) y el `freeze` estaba
**OK**. Arreglo aplicado (local, `.env`): `API_PYTHON_PORT=8000`. El día se recuperó con
`run-day --force`; el `forward` (35 símbolos) declara `PRODUCER_READY` pero **1 ciclo medible**
⇒ el día se sella como **`DECLARADO`**, no `MEDIDO`: la ventana sigue necesitando operación real
(≥32 ciclos) y este sello **no demuestra rentabilidad**. Hueco de código declarado: el runner no
debería caer a `API_PORT` (puerto de la UI) para el health de la API Python.

