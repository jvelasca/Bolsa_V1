# Evidencia `v2.88.174-beta` — Cuentas deja de afirmar lo que no midió: la ficha pide la cuenta que muestra y una cerrada deja de romper la lista

## 1. Qué publica este sello

Sello de **Cuentas** (CTA-D1…CTA-D10) sobre `2.11.173-beta`. No mueve motor ni decisión:

- **`Δ motor = 0`** · **`Δ decisión = 0`** (`replay-repro` **success** en CI, no solo declarado).
- **Contrato HTTP ADITIVO**: el diff de `openapi.json` es **+42 líneas y 0 eliminaciones** (respuestas
  `409 account_closed` y `X-Account-Id` en `/portfolio`). `contract:check` **OK**, sin `contract:gen`
  posterior.
- **SIN migración**: `head` sigue `060_provider_check_policy`.
- **Bump** `2.11.173-beta` → `2.11.174-beta` (+ los **13** `meta.bump`, **14 literales**;
  `test_dia_d_bump_guard` **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` **no** se toca).
- **Pin de ventana re-anclado DESPUÉS del bump** (`pnpm window:freeze` → `freeze OK`).

Dos cambios de producto:

1. **La ficha pide la cartera de la cuenta que muestra.** `AccountDetailPanel` llamaba a
   `GET /portfolio` sin identificador: con «seleccionar ≠ activar» como decisión de producto, la
   pestaña **Posiciones** de la cuenta seleccionada **B** pintaba la cartera de la cuenta **activa A**.
   Ahora la petición viaja con `X-Account-Id` explícito.
2. **Una cuenta cerrada es registro histórico, no una cuenta vacía.** `PATCH /settings`,
   `PUT /active-profile`, `ensure-defaults` y `make-default` devuelven ahora **`409 account_closed`**
   (antes solo lo hacía `update_account`), y `GET /accounts/summaries` deja de responder **500** con
   una cerrada en la base: la lista omite las cerradas.

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **El tag `v2.88.174-beta` ni la Release** | **No se han creado.** Este documento mide el árbol; la publicación requiere autorización explícita y el run del tag sobre el cierre documental. |
| **Rentabilidad ni operativa** | Un sello de Cuentas no añade evidencia de resultados. AUTO **OFF**; PAPER **`INCONCLUSIVE`**. |
| **Re-scope de `/fiscal`** | `CTA-D7` se cerró con rótulo honesto («Informe fiscal (cuenta activa)»), no re-scopeando la página. `/fiscal` sigue informando de la cuenta activa. |
| **Paginación del ledger** | El historial pinta los primeros 30 movimientos sin «cargar más». |
| **`api.ensureDefaultInvestorProfiles`** | Sigue sin llamadores (AUD-02). |
| **El E2E en la nube** | La ejecución de §5 es **local**. El job `playwright (mock E2E)` del CI es otro recorrido (mock, sin API real) y no acredita este. |
| **El commit del cierre documental** | El run medido es el del árbol `c1326295` (docs-only sobre `ea1432fb`). El cierre real del sello es el run del **tag**, que se dispara sobre ese cierre. |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Backend | `apps/api-python/src/bolsa_api/api/v1/routes/accounts.py`, `.../routes/investor_profiles.py`, `apps/api-python/tests/test_accounts_closed_guard_pg.py` |
| Dominio / infra | `packages/py/application/src/bolsa_application/accounts/summary.py`, `packages/py/application/tests/test_list_account_summaries.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/account_repository.py`, `.../investor_profile_repository.py` |
| Frontend | 8 ficheros de `apps/web/src/features/accounts` + sus tests, `lib/api.ts`, contrato generado (`api/openapi.json`, `src/api/schema.d.ts`) y **18 envoltorios** de `getPortfolio` que preservan el scope ambiente |
| Docs | `docs/engineering/seguimiento-ui-cuentas-muestra-config-2026-10-31.md`, `verificacion-grafo-cuentas-2026-10-31.md`, `pre-sello-v2.88.174-2026-10-31.md`, la evidencia cruda de `evidence/cuentas-muestra-config-2026-10-31/`, `CHANGELOG.md`, este README |
| Bump | `package.json` + `meta.bump` de `v2_87`, `v2_89`…`v2_100` (el literal congelado `2.11.0-beta` de `v2_87` **no** se toca) |
| Pin | `scripts/lib/window-forward.mjs` (`commit`/`appsHash`/`packagesHash` + bloque `RE-ANCLAJE`) |

Diff acumulado del sello sobre la base integrada `51c3bdfc`: **77 ficheros, +4.449 / −121**, en cuatro
áreas (`apps/api-python`, `apps/web`, `packages/py`, `docs`) y sin salir de ellas. No toca `alembic` ni
el motor. Los 18 envoltorios de `getPortfolio` son el único cambio fuera de `features/accounts` en el
frontend y no alteran comportamiento: conservan el scope ambiente.

## 4. Verificación medida (local, sobre el árbol del código)

| Comprobación | Resultado | Fichero |
| --- | --- | --- |
| `pytest` del área (9 ficheros) | **72 passed, 0 skipped** | [`pytest-area.txt`](../cuentas-muestra-config-2026-10-31/pytest-area.txt) |
| `vitest` del área (8 suites) | **8 files · 51 tests** | [`vitest-area.txt`](../cuentas-muestra-config-2026-10-31/vitest-area.txt) |
| `vitest` web completo | **356 files · 2.673 tests** | [`vitest-web-full.txt`](../cuentas-muestra-config-2026-10-31/vitest-web-full.txt) |
| `tsc -b --noEmit` (web) | **limpio** | [`tsc.txt`](../cuentas-muestra-config-2026-10-31/tsc.txt) |
| `eslint` ficheros tocados | **0 errores**, 6 avisos `exhaustive-deps` preexistentes | [`eslint.txt`](../cuentas-muestra-config-2026-10-31/eslint.txt) |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden | [`contract-check.txt`](../cuentas-muestra-config-2026-10-31/contract-check.txt) |
| `ruff check` (8 ficheros Python tocados) | **All checks passed** | [`ruff.txt`](../cuentas-muestra-config-2026-10-31/ruff.txt) |
| `pnpm types:py` (mypy) | **582 ficheros**, sin errores | [`types-py.txt`](../cuentas-muestra-config-2026-10-31/types-py.txt) |

Sobre el **árbol del sello** (`ea1432fb`) se re-midieron los gates que dependen de la versión y del pin:

| Comprobación | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:test` | **50/50** |
| `pnpm window:freeze` | **`freeze OK`** — `appsHash 1a5bc7c4…`, `packagesHash 741ed1a8…` |
| `pnpm contract:check` | **OK** |

Las cifras de suites (72 / 51 / 2.673 / 582) se midieron sobre el árbol del código y **no** se
re-midieron localmente tras el bump: el bump solo cambia literales `meta.bump` de scripts CLI. Esa
continuidad la cierra el CI de §7.1, que sí ejecuta `python`, `frontend` y `optimize` sobre `ea1432fb`.

## 5. E2E en vivo sobre el árbol del sello (2026-11-01)

Playwright con Chrome del sistema contra el proxy Vite → API 8000 (`E2E_BASE_URL=http://127.0.0.1:5173`;
se usa la IP literal porque Node resuelve `localhost` a `::1` y Vite escucha en IPv4), cuenta semilla
para lectura y cuentas/perfiles desechables `CU-REV-*` / `PROF-REV-*` para escritura.

| Dato | Valor |
| --- | --- |
| Procedencia | `e2e-result.json` → `provenance`: rama `fix/059-060-proveedores`, `head ea1432fb…`, `2.11.174-beta`, **`dirty: false`**, `startedAt`/`finishedAt` |
| Comprobaciones | **90/90 OK** (`e2e-result.json`, `ok: true`) |
| Peticiones API observadas | 309 |
| Escrituras | 42 |
| `pageerror` / `console.error` | **0 / 0** |
| `ensure-defaults` desde la UI | 0 |
| Capturas | `e2e-01-lista.png` … `e2e-11-cerrada.png` (14 imágenes de recorrido) |
| Trazas | `console.txt`, `network.txt` (ambas con línea `# procedencia`), `e2e-run.log` |
| Foto de BD | contenido **idéntico**: SHA-256 del snapshot sin el bloque `provenance` = `8c8e2966…` en `db-before.json` y `db-after.json`; `residue_like: []`; `tables` declara el alcance (`investment_accounts`, `investor_profiles`) |
| Semilla restaurada | `is_default = true`, `active_profile_id = PROF-996fcd3d6ec6` |

**Por qué el `dirty` cambia entre las dos fotos y por qué la comparación es por contenido.** El
recorrido **reescribe esta misma evidencia** (capturas, `console.txt`, `network.txt`, `e2e-result.json`),
así que `db-before.json` se captura con el árbol limpio (`dirty: false`) y `db-after.json` con el árbol
ya sucio por esos ficheros (`dirty: true`). La única línea distinta entre ambos ficheros es ese flag:
`Compare-Object` sobre los dos JSON devuelve solo `"dirty": false` / `"dirty": true`. Por eso la prueba
de 0 residuos se hace sobre el **contenido** (SHA-256 del snapshot sin `provenance`), no byte a byte.

**Por qué el árbol servido es el árbol medido.** La API la sirve `run_dev.py` (sin `--reload`, proceso
iniciado el 2026-10-31 20:41) y Vite `5173`. La equivalencia está comprobada, no supuesta:
`git diff --name-only 2c02178a..HEAD -- apps/api-python/src packages/py` está **vacío**, es decir
ningún fuente servido cambió desde el SHA que midió el CI de rama.

## 6. Límites declarados

- El E2E es **local**: acredita el árbol `ea1432fb`, no el tag. El job `playwright (mock E2E)` del CI es
  un recorrido distinto.
- El recuento de peticiones oscila entre pasadas (312 en `4f8308bb`, 309 en `ea1432fb`) porque el
  *shell* deja lecturas de fondo en vuelo al cerrar la captura. Quedan listadas como **aviso**, nunca
  como fallo ni como escritura. En esta pasada fueron 16, entre ellas un `PUT supervised-f3-queue` del
  poller del shell, ajeno a la superficie de Cuentas y contabilizado fuera de las 42 escrituras.
- La foto de BD declara sus tablas: prueba ausencia de residuos en ellas durante el recorrido, no que
  toda operación posible sea correcta.
- Los 6 avisos de ESLint (`exhaustive-deps`) son preexistentes y ya estaban en `HEAD`.
- `CTA-D7` (`/fiscal`), la paginación del ledger, el catálogo completo de Configuración → Perfil
  inversor y `ensureDefaultInvestorProfiles` (AUD-02) quedan **fuera** de este sello.

## 7. Publicación (estado a 2026-11-01)

| Dato | Valor |
| --- | --- |
| Rama | `fix/059-060-proveedores` (`7993f7ca..c1326295`) |
| Cierre del expediente | `afef4fd1` (docs: atribución CI separada y bloqueo del pin) |
| Commit del sello (bump) | `3792ae19` (`chore(release)`: `2.11.174-beta` + 14 literales + `CHANGELOG`) |
| Re-anclaje del pin | `ea1432fb` (`chore(window)`; `appsHash 1a5bc7c4…`, `packagesHash 741ed1a8…`) |
| Evidencia E2E | `c1326295` (docs + evidencia; docs-only sobre `ea1432fb`) |
| Tag | **NO creado** — `v2.88.174-beta` no existe (`git tag --list "*174*"` vacío) |
| PR / Release | sin PR (el grafo lo descarta); GitHub Release **no emitida** |

### 7.1 Runs de CI medidos

| Run | Workflow | Ref | `headSha` | Resultado |
| --- | --- | --- | --- | --- |
| [`41292199040`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41292199040) | `Python CI` | rama | `ea1432fb` | **success** |
| [`41292198768`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41292198768) | `Frontend CI` | rama | `ea1432fb` | **success** |
| [`41292198835`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41292198835) | `Optimize lab` | rama | `ea1432fb` | **success** |
| [`41292811777`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41292811777) | `Release tag CI` (**`workflow_dispatch`**) | rama | `c1326295` | **success** — 13 jobs `success` + `certify` `success`; `playwright (integrated E2E, opt-in)` `skipped` |

El despacho de `Release tag CI` no crea tag ni versión: los jobs no filtran por `github.ref_type`, así
que produce evidencia cloud sobre el árbol final y publica su resumen como
`dispatch-c132629513abc33854b2c323640651404b6c6708` (`status: GREEN`). Los dos steps que el dictamen
daba por pendientes quedan acreditados ahí:

| Job | Step | Resultado |
| --- | --- | --- |
| `shared` | `Window runner guards (lock/config/provenance)` | **success** |
| `shared` | `Window freeze gate (pin == HEAD:apps/packages)` | **success** |
| `frontend` | `Contract check (no gen)` | **success** |

`replay-repro` **success** ⇒ **`Δ motor = 0`** confirmado en CI. `Fase 2 scientific` no se disparó en
`ea1432fb`, y es correcto: el bump no toca `packages/py/application`, `domain`, `infrastructure` ni las
rutas de `research`.

Runs históricos del expediente, ya **no** atribuibles al árbol del sello: `Python CI`
[`41236648769`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41236648769) verde en `2c02178a`, y
`Python CI` [`41234889187`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41234889187) en rojo
(8 `I001`) en `15ad62ac`, que es el defecto que `2c02178a` reparó.

### 7.2 Verificación local del sello

| Comprobación | Resultado |
| --- | --- |
| `pnpm window:freeze` | **`freeze OK`** — `appsHash 1a5bc7c4…`, `packagesHash 741ed1a8…` |
| `pnpm window:test` | **50/50** |
| `pnpm contract:check` | **OK** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| E2E `e2e-cuentas.mjs` sobre `ea1432fb` | **90/90**, `dirty: false` |

La etiqueta `commit` del pin dice `3792ae19` mientras el árbol medido es `ea1432fb`; el freeze real son
los dos tree hashes, y el commit del re-anclaje vive en `scripts/`, que no participa del freeze.

### 7.3 Qué falta para el tag

1. Autorización explícita del sello.
2. `git tag -a v2.88.174-beta` sobre el cierre documental y `push` del tag.
3. Leer el `Release tag CI` **del tag** (12 jobs + `certify`), que es el que certifica el sello. Lo de
   §7.1 es el mismo procedimiento sobre la misma rama, con el artefacto llamado `dispatch-<sha>`: sirve
   de preflight, **no** de sello.
4. Decidir explícitamente si `.174` emite GitHub Release (`.173` no la emitió).

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La ficha pide la cartera de la cuenta seleccionada | `account-detail-panel.test.tsx` y el chequeo `CTA-12 · la ficha pide el portfolio de la cuenta seleccionada` del E2E |
| 2 | Ninguna petición usa el scope de una tercera cuenta | `CTA-12 · portfolio nunca con el scope de una tercera cuenta` |
| 3 | Una cerrada no admite escrituras | `test_accounts_closed_guard_pg.py` (409 en settings, perfil, nombre) y `CTA-D5` en el E2E |
| 4 | Una cerrada no rompe la lista de resúmenes | `test_list_account_summaries.py` + `CTA-10`/`CTA-11` del E2E |
| 5 | Las notas con espacios sobreviven | test RTL del texto tecleado + round-trip por API (`CTA-D3`) |
| 6 | El contrato no se movió a mano | `pnpm contract:check` (local y step `Contract check (no gen)` en CI) |
| 7 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 8 | El pin casa con el árbol | `pnpm window:freeze` ⇒ `freeze OK` (y el step `Window freeze gate` del CI) |
| 9 | El motor no cambió | `replay-repro` regenera el artefacto desde el fixture y lo compara byte a byte |
| 10 | El E2E es de este árbol | `provenance.head` = `ea1432fb` y `dirty: false` en `e2e-result.json` |

## 9. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | `afef4fd1`: el expediente separa la atribución de CI y documenta el pin `TREE_MOVED`. |
| 2 | `3792ae19`: bump `2.11.174-beta` (14 literales) y `CHANGELOG`; guardián `2 passed`. |
| 3 | `ea1432fb`: re-anclaje del pin; `window:freeze` → `freeze OK`; `window:test` 50/50. |
| 4 | Push; `Python CI`, `Frontend CI` y `Optimize lab` verdes sobre `ea1432fb`. |
| 5 | E2E 90/90 repetido sobre `ea1432fb` con `dirty: false`; `c1326295` publica la evidencia. |
| 6 | `Release tag CI` despachado sobre `c1326295`: **GREEN**, `Window freeze gate` y `Contract check (no gen)` `success`. |
| 7 | Este documento. Tag y Release **no** creados. |

## 10. Cierre de hallazgos posteriores (auditoría `AUDITORIA 1`) — sellado en `.175`

Los cinco hallazgos abiertos de la auditoría de `.174` (**P-1b**, **N-1**, **N-2**, **N-3**, **N-4**) y sus
dos observaciones (rol de los `purge` y atribución del fichero creado) quedan cerrados en
[`../cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md`](../cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md),
con su causa raíz, la corrección, la prueba que la rompe y las mediciones locales.

El tag `v2.88.174-beta` **no contiene** ese código: se auditó y ni la guarda de exclusividad ni el documento
de cierre existen ahí. Por eso el delta se selló aparte como **`v2.88.175-beta`** (bump `2.11.175-beta`, tag
sobre el cierre documental y su `Release tag CI`). Este documento sigue describiendo lo que `.174` publicó y
no se reescribe por el cierre posterior; `head` de `.174` sigue siendo `060_provider_check_policy`.
`AUDITORIA 2` (dictamen de publicación y certificación por el CI del tag) es informativa y no requería
acción.
