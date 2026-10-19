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

_Pendiente de rellenar al publicar el tag `v2.88.151-beta`: run del `Release tag CI`, resultado de
`window:freeze` sobre el commit del sello y estado del run forward de las 18:00._
