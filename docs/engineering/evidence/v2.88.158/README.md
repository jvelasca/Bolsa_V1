# Evidencia `v2.88.158-beta` — identidad de motor estable y cadencia con barras frescas

## 1. Qué publica este sello

Cierra **W-157-1** y **W-157-2** del plan de la ventana PAPER. No toca el motor de decisión,
umbrales, pesos, régimen, sizing, `TOP_N`, orquestador ni replay OOS: **`Δ motor = 0`** y
**sin migración** (`head` sigue `057_top3_opportunity_identity`).

## 2. W-157-1 — la ventana PAPER no podía cerrar un ciclo

La readopción de posición va scoped por `(account_id, engine_id)`, pero
`v2_76_forward_market_material` acuñaba `engine_id = auto-v76-<os.urandom(4)>` **en cada corrida**.
El día N no adoptaba la posición del día N-1: la posición quedaba huérfana en su motor efímero, no
se gestionaba y nunca se cerraba — `measurableCycles` era 0 **por construcción**.

Medido el 2026-10-21 en `1484e253d2d54645945a6b1d7`: dos posiciones vivas del **mismo** símbolo bajo
`auto-v76-61bd1569` y `auto-v76-3ad9a1c8`, y 0 ciclos cerrados en los días con fills
(`2026-10-19`: 8 fills / 0 ciclos; `2026-10-20`: 4 fills / 0 ciclos).

**Corrección.** El runner honra `AUTO_ENGINE_SIM_ENGINE_ID` (fallback: motor efímero histórico) y la
ventana fija `auto-window-1484e253` en `operatorEnv` (`scripts/lib/window-forward.mjs`, **fuera del
freeze**). Declarado por el `CHANGELOG`: con la variable fijada el productor sella `engineBase`
estable y abre/cierra su ciclo (`canary-stable-engine`, 2 ticks, `cycles=1/1`).

## 3. W-157-2 — la cadencia medía sin barras

Con `AUTO_ENGINE_SIM_REAL_PRICE=1` el productor marca con la **apertura** de la barra del día B y
`OhlcvPriceSource.execution()` devuelve `None` si esa barra no está persistida: todo cae a `HOLD`
fail-closed y el día se mide con 0 fills. Medido el 2026-10-21 a las 12:15: cobertura **1/80**.

**Corrección.** Pieza `sync-bars` en el runner (`POST /api/sync/queue/enqueue-stale`, idempotente,
falla declarada si el API no responde o exige auth) y tarea `BolsaV1_BarsSync` a las **17:40**; el
run-day pasa a las **18:30**. `--no-bars` / `--bars-at` permiten ajustarlo.

## 4. Verificación medida

La verificación de este árbol es la del **CI del tag** (`Release tag CI`, ver §7). Las cifras
locales del sello se declararon en el `CHANGELOG` §`2.11.158-beta` y **no** se re-ejecutaron al
publicar: esta evidencia no las reatribuye.

Lo comprobado al publicar:

- `window-pin --check` sobre el commit del tag ⇒ **`freeze OK`**.
- `Bump` `2.11.157-beta` → `2.11.158-beta` en `package.json` y en el `meta.bump` de los **13** CLIs.

## 5. Límites declarados

- Los días anteriores al re-anclaje quedan **`STALE`**: no cuentan para la ventana.
- Las posiciones huérfanas de los motores efímeros previos **no** se backfillean ni se adoptan.
- AUTO sigue **OFF** y `CONFIRMED` no se emite. La rentabilidad **no** está certificada.

## 6. Freeze

| Elemento | Valor |
| --- | --- |
| Commit del tag | `6b6dd6f0` |
| `apps` | `4c9d5cc3de6307dc210866291ddd032de483d00e` |
| `packages` | `55571608ca700d82752a7b2b8d274d2d7c39c170` |
| Etiqueta `commit` del pin | `9c485c64` (el freeze real son los dos tree hashes) |

El commit `6b6dd6f0` toca **solo** `scripts/`, que no participa del freeze: los dos tree hashes son
idénticos a los del commit de re-anclaje `c867c624`.

## 7. Publicación

**Nota de honestidad (crítica).** Este sello se trabajó el **2026-10-21**, pero quedó **sin
publicar** hasta el **2026-10-22**, junto con `.159` y `.160`. El tag es **anotado y unsigned** y se
creó sobre el commit que ya contenía el árbol del sello; no se reescribió historia ni se movió el
contenido. La fecha del tag en GitHub es posterior a la fecha de la evidencia: **es publicación
diferida, no fabricación**.

**Alcance de este documento.** El tag `v2.88.158-beta` apunta a `6b6dd6f0`, que **no** incluye este
README: se escribió al publicar y vive en el `tip` del árbol (commit `97d61cbc`, junto a `.159` y
`.160`). Lo que el tag sí contiene es el código, el `CHANGELOG` y el pin del sello. Cite este
documento por su ruta en `main`, no por el tag.
