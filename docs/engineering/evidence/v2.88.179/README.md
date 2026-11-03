# Evidencia `v2.88.179-beta` — **SELLO CORRECTOR de `.178`**: la carrera multi-proceso espera la trancha, no la reserva

## 1. Qué corrige

El tag **`v2.88.178-beta`** quedó **ROJO** en
[`Release tag CI` 41594625695](https://github.com/jvelasca/Bolsa_V1/actions/runs/41594625695). Un solo job
falló; los otros **once** fueron `success`.

| Job del tag `.178` | Resultado |
| --- | --- |
| `lifecycle-pg (Alembic + auth + golden restart)` | **failure** — step `Pytest multiprocess AUTO`: `assert Decimal('0') > 0` · *debe haber materializado ≥1 trancha* (**5,68 s**) |
| `python (ruff/imports/mypy/pytest offline)` | success (**incluye** el `--ignore` de `.178`) |
| `frontend` · `shared` · `replay-repro` · `a7-gate` | success |
| `security` · `dr-verify` · `decision-spine` | success |
| `playwright` ×3 | success |

Dentro de `lifecycle-pg` pasaron **todos** los steps anteriores al del fallo, incluido el **nuevo**
`Pytest persistencia del workspace PG` que `.178` venía a implantar: la corrección de `.178` **queda
certificada en el tag**; lo que cayó fue un test preexistente, de otro bloque, que corre **después**.

### 1.1 Causa raíz

`test_auto_v46_multiprocess_pg.py` arranca tres procesos reales que compiten por una señal y espera a que
«la carrera se resuelva»: posición abierta **y** una reserva `OPEN` con `remaining_qty > 0`.

El problema es que ese estado se cumple **en el instante en que la reserva nace**: toda reserva `OPEN` nace
con `released_qty = 0` y `remaining_qty = pedido`. La primera trancha la materializa el *fill*, en un ciclo
posterior del `auto_sim`. La condición de salida daba la carrera por resuelta **antes** de esa materialización
y el `assert released > 0` inmediato fallaba **sin margen**.

Es una **carrera del test**, no un fallo del producto:

- falló en el runner de CI a los **5,68 s** (el primer poll cayó en la ventana «reserva creada, trancha no»);
- las dos corridas locales tardaron **158 s** en ver el estado, así que el *fill* ya había liberado y el
  assert pasaba.

Nada del motor, la reserva durable ni la contabilidad cerrada (`released + remaining == requested`) cambia:
ese segundo invariante se sigue comprobando en el mismo punto.

## 2. Qué cambia (solo un test)

`apps/api-python/tests/test_auto_v46_multiprocess_pg.py`, fase 1:

```python
if (
    positions >= 1
    and any(float(r.remaining_qty or 0) > 0 for r in live)
    and any(float(r.released_qty or 0) > 0 for r in live)
):
    break
```

La condición de salida exige ahora también `released_qty > 0`, con el **mismo** presupuesto
(`_MAX_POLLS` = 160 × 0,5 s = **80 s**). El test **no se debilita**: si la trancha no llega, el
`assert released > 0` sigue fallando con el log de los tres procesos. **Ningún** fichero de producto, CI,
contrato o migración cambia en este sello.

## 3. Verificación medida

| Comprobación | Comando | Salida |
| --- | --- | --- |
| Carrera multi-proceso (con la corrección) | `pytest apps/api-python/tests/test_auto_v46_multiprocess_pg.py -q` | **1 passed in 158,08 s** |
| Carrera multi-proceso (antes de la corrección) | idem | **1 passed in 158,06 s** — el rojo es de **carrera**, no reproducible por timing local |
| Guardián del bump | `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| Pin PAPER | `node scripts/window-pin.mjs --check` · `pnpm window:test` | **`freeze OK`** · **50 / 50** |
| Persistencia (heredada de `.177`) | `pytest test_workspace_persistence.py test_batch_caps.py` | **14 passed** |
| Suites web / shared (heredadas) | `pnpm --filter @bolsa/web test` · `@bolsa/shared test` | **364 / 2728** · **101 / 883** |

Entorno de las corridas locales: PostgreSQL real (`DATABASE_URL=…/bolsa_v1_audit`),
`AUTO_MULTIPROCESS_PG_REQUIRED=1`, `_PROCESSES = 3`.

Cadena del pin en este sello:

| Commit | `appsHash` | `packagesHash` | `window:freeze` |
| --- | --- | --- | --- |
| `c5c96068` (fix del test) | `246edde7…` | `0f8efb9b…` | `TREE_MOVED` (previsto: el pin apuntaba a `.178`) |
| `91af003b` (bump) | `bcaacc9f…` | `0f8efb9b…` | **`freeze OK`** tras el re-anclaje |
| `c1280773` (pin) | `bcaacc9f…` | `0f8efb9b…` | **`freeze OK`** |

`packages/py` no se mueve en todo el sello: solo `apps` (los `meta.bump`) y la raíz.

## 4. Qué NO cambia respecto de `.177` / `.178`

- **Producto**: los seis defectos P0-1, P0-2, P1-3, P1-4, P1-7, P2-5 y P2-6 y la causa raíz de la membresía
  `newest-wins` son los de [`evidence/v2.88.177`](../v2.88.177/README.md), sin tocar.
- **CI del tag**: el `--ignore` offline y el step `Pytest persistencia del workspace PG` de
  [`evidence/v2.88.178`](../v2.88.178/README.md) se heredan tal cual (y ese step **pasó** en el run rojo).
- **Contrato HTTP**: sin cambios (`contract:check` **OK**).
- **Motor y decisión**: `Δ motor = 0`, `Δ decisión = 0`, sin migración (head
  `062_sync_settings_check_backfill`).
- **Revisión independiente**: la de `.177`
  ([`revision-independiente-workspace-2026-11-02.md`](../../revision-independiente-workspace-2026-11-02.md))
  sigue siendo válida: el diff de este sello **no** toca `packages/py/**` ni `apps/web/**`.
- **Límites**: `L-RIW-1`…`L-RIW-4` se heredan tal cual.

## 5. Publicación

| Paso | Estado |
| --- | --- |
| `v2.88.177-beta` | **publicado y ROJO** (run `41592978552`); registro, **sin** GitHub Release |
| `v2.88.178-beta` | **publicado y ROJO** (run `41594625695`); registro, **sin** GitHub Release |
| `c5c96068` fix de la carrera del test | hecho |
| `91af003b` bump `2.11.179-beta` | hecho |
| `c1280773` re-anclaje del pin | hecho |
| Tag anotado `v2.88.179-beta` | `8fe47426`, pusheado |
| `Release tag CI` del tag | **`success`** — run `41597599762`, **12 min 04 s** (**§5.1**) |
| GitHub Release | [publicada](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.179-beta) (**§5.1**) |
| Despliegue en `:8000` | **no realizado** y fuera de este sello |

### 5.1 POST-TAG — `Release tag CI` del sello

[`Release tag CI` 41597599762](https://github.com/jvelasca/Bolsa_V1/actions/runs/41597599762) sobre
`8fe47426` (`v2.88.179-beta`): **`success`**, `2026-11-03T07:37:55Z` → `07:49:59Z` (**12 min 04 s**),
**14 jobs `success`** + `certify (aggregate + artifact)` `success` + `playwright (integrated E2E, opt-in)`
`skipped` (opt-in, como en los sellos anteriores).

| Job | Duración | Evidencia del log |
| --- | --- | --- |
| `lifecycle-pg` | 7 m 24 s | **`Pytest persistencia del workspace PG` → `9 passed in 7,44 s`** (la certificación de `.178`, verde en el tag) · **`Pytest multiprocess AUTO` → `1 passed in 114,31 s`** |
| `frontend` | 4 m 30 s | web **364 / 2728** · `contract:check` OK (aviso heredado: *uv no disponible; se omite la validación contra FastAPI*) |
| `python` | 3 m 34 s | ruff **All checks passed!** · mypy **582** ficheros · `pytest` offline **5883 passed, 98 skipped** |
| `playwright (mock E2E)` | 11 m 52 s | **144 passed** |
| `replay-repro` | 5 m 15 s | **VEREDICTO `REPRODUCIDO`** (mismo contenido; sello en CRLF, fixture en LF) |
| `playwright (integrated axe)` | 4 m 05 s | **32 passed** |
| `playwright (integrated AUTO S5)` | 2 m 52 s | **7 passed** |
| `playwright (live AUTO daily chain)` | 1 m 43 s | **2 passed** |
| `shared` | 41 s | shared **101 / 883** (+1 todo) · **`window-pin freeze OK (8fe47426)`** |
| `a7-gate` · `dr-verify` · `decision-spine` · `security` | 55 s · 50 s · 27 s · 11 s | `success` |
| `certify (aggregate + artifact)` | 5 s | `success` |

**Nota sobre `Pytest multiprocess AUTO`: 114,31 s.** Ese número es la prueba del diagnóstico: en el runner
de CI la trancha tardó cerca de **dos minutos** en materializarse después de que la reserva existiera. La
condición de salida vieja daba la fase 1 por resuelta en el primer poll, y el `assert released > 0` caía
**5,68 s** después de arrancar. Con la salida corregida el test **espera lo que de verdad tiene que esperar**
y mide el estado final, no el intermedio.

**GitHub Release:** [**`v2.88.179-beta`**](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.179-beta)
publicada como *latest* de la serie `v2.88.x`, con el resumen del sello y los enlaces a este expediente y a la
revisión independiente. Los tags `v2.88.177-beta` y `v2.88.178-beta` siguen **sin** release: quedan como registro
del rojo. **Despliegue en `:8000`:** no realizado (fuera del alcance del sello), igual que en `.176`–`.178`.

## 6. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La fase 1 no se cierra antes de que exista la trancha | lectura de la condición de salida: exige `released_qty > 0` |
| 2 | El test no se debilita | los asserts (`positions ≥ 1`, `released > 0`, `released + remaining == requested`, 1 sola reserva y 1 sola orden BUY) se conservan |
| 3 | Nada de producto cambia | el diff del sello solo toca `apps/api-python/tests/test_auto_v46_multiprocess_pg.py`, `package.json`, `CHANGELOG.md`, `apps/api-python/scripts/*` y `scripts/lib/window-forward.mjs` |
| 4 | La certificación de persistencia del tag sigue viva | step `Pytest persistencia del workspace PG` verde en el run rojo de `.178` y en el de `.179` |
| 5 | El pin casa con el árbol | `freeze OK`; rojo en el step `Window freeze gate` del tag si no |

## 7. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | Tag `.178` → run `41594625695` **ROJO** en `Pytest multiprocess AUTO` (`assert Decimal('0') > 0`, 5,68 s); el step de persistencia de `.178` **verde**. |
| 2 | Diagnóstico: la condición de salida de la fase 1 se cumple con la reserva **recién creada**, antes del *fill*. |
| 3 | `c5c96068`: la salida exige `released_qty > 0`; mismo presupuesto de 80 s; `1 passed in 158,08 s`. |
| 4 | `91af003b`: bump `2.11.179-beta`; bump guard `2 passed`; pin re-anclado. |
| 5 | `c1280773`: commit del pin; `freeze OK`, `window:test` 50/50. |
| 6 | Este documento, tag `v2.88.179-beta` y su `Release tag CI` (**§5.1**). |
