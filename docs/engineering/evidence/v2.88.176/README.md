# Evidencia `v2.88.176-beta` — Overview responde a una sola pregunta: la pantalla de entrada deja de repetir la navegación y de hablar en jerga interna

## 1. Qué publica este sello

Sello de **producto**, solo frontend, posterior a `2.11.175-beta`. No mueve motor ni decisión:

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **SIN migración**
  (`head` sigue `062_sync_settings_check_backfill`).
- **Bump** `2.11.175-beta` → `2.11.176-beta` (+ los **13** `meta.bump`, **14 literales**;
  `test_dia_d_bump_guard` **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` no se toca).
- **Pin de ventana re-anclado DESPUÉS del bump** (`pnpm window:freeze` → `freeze OK`).

El cambio: `/overview` medía **1749 px** de contenido sobre 853 px de viewport útil a 1440×900, con jerga de
implementación en el primer nivel (`Score_FUND`, `Piotroski`, `FIE`, `Paper D`, `whitelist`,
`PAPER_D_EXECUTE=1`) y **ocho** tarjetas de acceso que repetían la barra L1 y el `AdminRail`. Ahora responde a
*¿qué tengo y por dónde sigo?* con tres bloques —cuenta activa con cuatro métricas, cuatro accesos rápidos
(`/trading`, `/operations`, `/history`, `/accounts`) y últimos movimientos—, cada hecho una sola vez.

| Resultado | Medida | Ancla |
| --- | --- | --- |
| Desktop 1440×900 | **596 px** sin scroll (`scrollH = clientH = 853`) | `../overview-simplificada-2026-11-01/overview-despues-1440x900.png` |
| Composición de la altura | **56 / 209 / 85 / 174 px** + **72 px** de `space-y-6` = 524 + 72 = **596** | captura anterior + árbol |
| Móvil 390×740 | `scrollWidth = 390`, sin desbordamiento horizontal | `../overview-simplificada-2026-11-01/overview-despues-movil-390x740.png` |
| Jerarquía | `h1` → tres `h2`, sin saltos | `../overview-simplificada-2026-11-01/vitest-area.txt` |
| Área tocada | **19/19** | ídem |
| Tipado / lint | `tsc -b --noEmit` limpio · **0** problemas ESLint en las tres áreas | `tsc.txt` / `eslint.txt` |
| Contrato | `contract:check` **OK**, sin diff de DTO | `contract-check.txt` |
| Código muerto | `data-sync-summary-card.tsx` **sin consumidores** | contraste con `platform-config-dialog.tsx` (`case "other"`) |

El expediente completo está en el [`dictamen de Overview`](../../dictamen-overview-simplificada-2026-11-01.md),
su [`aceptación POST-COMMIT`](../../dictamen-commit-62665ff7-2026-11-01.md) y el
[`seguimiento`](../../seguimiento-ui-overview-2026-11-01.md).

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Las suites completas sobre este árbol** | `2 686/2 686` de la suite web y `35/35` de axe son del **árbol de trabajo** y se citan como **citadas**: aquí solo se re-miden el área (`19/19`), `tsc`, ESLint de las tres áreas y el guardián del bump. La suite completa la cubre el `Release tag CI`, no este documento. |
| **`L-OVW-1` — el estado de sync ya no se ve en Overview** | Límite **nombrado y aceptado**: la información vive en Configuración → «Automatización: velas y servidores» (`SyncSettingsPanel` + `MarketProvidersStatusCard`). Sigue **abierto** hasta confirmar en esa superficie que el estado se conserva y es alcanzable. |
| **`L-OVW-2` — «otras cuentas activas»** | Cubierto **solo** por test (`señala cuántas otras cuentas activas hay`). No se ejecutó en navegador con dos cuentas activas: falta texto, enlace, cambio de cuenta y repintado a 390×740. |
| **Que `596 px` valga con cualquier contenido** | Se midió con la cuenta demo canónica (2 asientos). No se midió con nombres largos, muchas posiciones o ledger lleno: la altura depende del contenido. |
| **Que axe sustituya una revisión manual** | `35/35` acredita 0 `critical`/`serious` en las rutas tocadas con datos de mock, no una auditoría de accesibilidad completa. |
| **Rentabilidad ni operativa** | Un sello de producto no añade evidencia de resultados. AUTO **OFF**; PAPER **`INCONCLUSIVE`**. |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Frontend (`62665ff7`) | `apps/web/src/features/dashboard/dashboard-page.tsx` (reescrito), `.../dashboard-page.test.tsx` (**nuevo**), `apps/web/src/features/settings/data-sync-summary-card.tsx` (**borrado**) |
| Documentación y evidencia (`62665ff7`) | `docs/engineering/dictamen-overview-simplificada-2026-11-01.md`, `docs/engineering/seguimiento-ui-overview-2026-11-01.md`, `docs/engineering/evidence/overview-simplificada-2026-11-01/` (README + 6 ficheros de texto + 4 capturas) |
| Aceptación separada (`23c9c689`) | `docs/engineering/dictamen-commit-62665ff7-2026-11-01.md` (**nuevo**, docs-only) |
| Bump (`2c7d8b11`) | `package.json`, `CHANGELOG.md`, `meta.bump` de `v2_87` (banda financiera) y `v2_89`…`v2_100` (**14 literales**) |
| Pin (`27e918c9`) | `scripts/lib/window-forward.mjs` (`commit`/`appsHash`/`packagesHash` + bloque `RE-ANCLAJE`) |

Reparto por commit, para que ninguna aceptación se lea fuera de su objeto: `62665ff7` = **16 ficheros,
`+1006/−460`** (código + su aceptación técnica); `23c9c689` = **2 ficheros, `+177`** (acepta el anterior sin
enmendarlo); `2c7d8b11` = **15 ficheros, `+79/−15`** (bump); `27e918c9` = **1 fichero, `+10/−2`** (pin).

## 4. Verificación medida (local, 2026-11-01)

Cada fila es una ejecución distinta; no se suman.

| Comprobación | Comando | Salida | Código |
| --- | --- | --- | --- |
| `vitest` del área (tras el `lint-staged` de `62665ff7`) | `vitest run src/features/dashboard src/test/heading-order.test.tsx` | **19/19** | `0` |
| `tsc -b --noEmit` (web) | `pnpm --filter @bolsa/web typecheck` | **limpio** | `0` |
| `eslint` en `dashboard` / `settings` / `sync` | — | **0 problemas** (23 avisos preexistentes en `src/` completo) | `0` |
| `pnpm contract:check` | — | **OK** | `0` |
| `pytest` bump guard | `apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** | `0` |
| `pnpm window:freeze` | tras el re-anclaje | **freeze OK** (`2c7d8b11`) | `0` |
| `pnpm window:test` | — | **50 / 50** | `0` |
| Codificación de `api-overview.txt` | lectura por bytes | **UTF-8 sin BOM**, 426 bytes, `47 45 54` (`GET`), **0** NUL | `0` |

Cadena de hashes del pin, medida en cada paso (la predicción del
[`dictamen POST-COMMIT`](../../dictamen-commit-62665ff7-2026-11-01.md) §3 se cumple):

| Commit | `appsHash` | `packagesHash` | `window:freeze` |
| --- | --- | --- | --- |
| `23c9c689` (dictamen, docs-only) | `ac05717e536f64820f64b8d2b5503eed6a6d70b2` | `7091cc8d05624249a35377d7e541773c1313b889` | `TREE_MOVED` (previsto) |
| `2c7d8b11` (bump) | `e080cca169533e73e4dcbc21ea7ab5031e75428f` | `7091cc8d05624249a35377d7e541773c1313b889` (**sin cambio**) | `TREE_MOVED` (previsto) |
| `27e918c9` (re-anclaje) | `e080cca169533e73e4dcbc21ea7ab5031e75428f` | `7091cc8d05624249a35377d7e541773c1313b889` | **`freeze OK`** |
| Este documento (docs-only) | **sin cambio** (esperado) | **sin cambio** (esperado) | **`freeze OK`** |

Solo `appsHash` se movió, que es exactamente lo que produce tocar `apps/web/src` y los `meta.bump` de
`apps/api-python/scripts/`.

## 5. Límites declarados

- El sello es el `Release tag CI` **del tag**: los gates de rama no lo sustituyen.
- `L-OVW-1` y `L-OVW-2` siguen **abiertos** con su condición de reapertura escrita en el
  [`dictamen de Overview`](../../dictamen-overview-simplificada-2026-11-01.md) §4. Ninguno impide aceptar la
  simplificación; ambos impiden llamarla «completamente verificada».
- `Δ motor = 0` se sostiene porque el diff del sello **no toca** `packages/py` ni el motor de decisión: solo
  `apps/web/src` y literales de versión. Lo confirma el `replay-repro` del CI del tag, que regenera el artefacto
  congelado desde el fixture y lo compara byte a byte.

## 6. Publicación

| Paso | Estado |
| --- | --- |
| Implementación + aceptación técnica | `62665ff7` |
| Aceptación POST-COMMIT | `23c9c689` |
| Push de la rama (`62997f81` → `23c9c689`, fast-forward) | hecho |
| Bump `2.11.176-beta` | `2c7d8b11` |
| Re-anclaje del pin | `27e918c9` |
| Tag anotado `v2.88.176-beta` | sobre el commit de este documento (patrón `.173`…`.175`) |
| `Release tag CI` del tag | **ver §6.1** |
| GitHub Release | **se emite** — cambio de criterio respecto a `.173`…`.175` |

### 6.1 Runs del tag medidos

Esta sección se añade **POST-TAG**, así que no viaja en el árbol del tag (mismo patrón que `.173` y `.175`).
Se completa en el commit documental posterior al run.

## 7. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Overview no muestra jerga interna en primer nivel | rojo en el caso anti-jerga de `dashboard-page.test.tsx` |
| 2 | Hay cuatro accesos y apuntan a cuatro destinos | rojo en `resume la navegación en cuatro enlaces con su destino` |
| 3 | La jerarquía es `h1` + tres `h2` sin saltos | rojo en `tiene un solo h1 y no salta de nivel` y en `heading-order.test.tsx` |
| 4 | El borrado no deja código muerto | reaparecer un `import` de `data-sync-summary-card` ⇒ falla la resolución del módulo |
| 5 | No cambia el contrato API | tocar `openapi.json`/`schema.d.ts` sin backend ⇒ rojo en `contract:check` |
| 6 | El bump es coherente en los 14 literales | `test_dia_d_bump_guard` (y el literal congelado `2.11.0-beta` sigue anclado por su propio test) |
| 7 | El pin casa con el árbol | `pnpm window:freeze` ⇒ `freeze OK`; rojo en el step `Window freeze gate` del CI del tag |
| 8 | El motor no cambió | `replay-repro` regenera el artefacto congelado y lo compara byte a byte |
| 9 | La aceptación no enmienda el objeto aceptado | reescribir `62665ff7` o `23c9c689` ⇒ cambia el SHA y ambas aceptaciones dejan de apuntar a nada |
| 10 | `L-OVW-1` / `L-OVW-2` siguen abiertos | declararlos cerrados sin la comprobación de §4 del dictamen ⇒ la aceptación dice más de lo que midió |

## 8. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | `62665ff7`: reescritura de Overview + expediente y evidencia en el mismo commit (16 ficheros, `+1006/−460`). |
| 2 | `23c9c689`: aceptación POST-COMMIT en un descendiente, para no certificar un commit dentro de sí mismo; medido que `appsHash` y `packagesHash` no se mueven. |
| 3 | Push de la rama con el pre-check repetido: remoto en `62997f81`, sin divergencia, fast-forward. |
| 4 | Bump `2.11.176-beta` (`2c7d8b11`): guardián 2 passed; `appsHash` pasa a `e080cca1…`, `packagesHash` intacto. |
| 5 | Re-anclaje del pin (`27e918c9`): `window:freeze` → `freeze OK`, `window:test` 50/50. |
| 6 | Este documento y el tag anotado `v2.88.176-beta` sobre él; push de rama y tag. |
| 7 | `Release tag CI` del tag y `GitHub Release`: **§6.1**, anotados POST-TAG. |
