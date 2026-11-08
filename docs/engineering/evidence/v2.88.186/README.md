# Evidencia `v2.88.186-beta` — el cierre de la medición `20261106` sale de la rama y el sello deja un objeto auditable

## 1. Qué publica este sello

Sello de **cierre y de operación**, posterior a `2.11.185-beta`. No mueve motor ni decisión:

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **SIN migración** (`head` sigue `066_account_evidence_policy`).
- **Bump** `2.11.185-beta` → `2.11.186-beta` (+ los **14** literales `meta.bump` de **13** scripts DÍA-D;
  `test_dia_d_bump_guard` **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` **no** se toca).
- **Pin de ventana re-anclado DESPUÉS del bump** (`node scripts/window-pin.mjs --check` → `freeze OK`).
  `apps` `e9486e12…` → `f50042c1…` (bump) → **`d39a04a7…`** (fixtures del Policy Gate P2, §5.1);
  `packages` `2de53cda…` **sin cambio** en todo el acto.

Lo que este sello entrega es lo que hasta ahora **solo existía en una rama**: el cierre documental de la
corrida `20261106`, la declaración de terminación en el paquete y el preflight ejecutable de la ventana.
`main` estaba en `2.11.185-beta` y los tags **solo llegaban a `v2.88.183-beta`**: no había ningún objeto
etiquetado que un auditor externo pudiera reconstruir.

| Entrega | Fichero | Qué aporta |
| --- | --- | --- |
| Declaración de terminación | [`scripts/ops/final_package.py`](../../../scripts/ops/final_package.py) | `--declare-termination`, `--expected-ticks`, `--cycles-export-exit`; bloques `termination`/`certification`/`windowDays` separados |
| Preflight de ventana | [`scripts/ops/window-preflight.ps1`](../../../scripts/ops/window-preflight.ps1) | Las 6 precondiciones en un comando, **read-only**, exit `1` si falla una dura |
| Expediente del cierre | [`../cierre-medicion-2026-11-06.md`](../cierre-medicion-2026-11-06.md) | Dictamen `292/400`, `PAPER INCONCLUSIVE`, §8.1 y §10 |
| Corrección del diagnóstico de locks | [`scripts/lib/window-forward.mjs`](../../../scripts/lib/window-forward.mjs) | Mismo host + PID muerto ⇒ `reclaim` **sin** `--force` |
| Re-anclaje del sello | idem | `commit`/`appsHash` al árbol del sello; bloque `RE-ANCLAJE 2026-11-08` |

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Rentabilidad ni eficacia de AUTO** | **0** ciclos cerrados: `episodes 0/2`, `measurable_cycles 0/32`, `paper_forward_results = 0`. `PAPER INCONCLUSIVE`. |
| **Que la corrida `20261106` llegara a su tope** | **292/400** ticks durables. Terminación **prematura**, sin `forward.json` y **sin fila propia en el ledger**. |
| **Comportamiento en mercado abierto del tramo ciego** | **263** de los 292 ticks sin barra del día corriente (`idle`, 0 vetos). Un tick recorrido sin precio **no es un turno**. |
| **Cobertura completa de la barra** | **62/181** al arrancar y **84/181** en la frontera de medianoche. El tramo que decidía se midió con 62-84 instrumentos. |
| **El criterio `days`** | `days 4/4` **incluye un día sin sesión** (sábado `20261107`: barra `0`, `0` fills, 263 ticks `idle`). Deuda declarada. |
| **Continuidad temporal** | Hueco `23:40:09Z` → `07:40:53Z` por suspensión del equipo. Causa **observada**, no certificada. |
| **Publicación de `.184` y `.185`** | **Nunca** recibieron tag ni Release. Este acto **no re-etiqueta el pasado**. |
| **Los E2E live/integrated** | Exigen API + PostgreSQL + barras; un `skipped` **no** certifica. |

## 3. Verificación medida en local

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Guardián del bump | `pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | **2 passed** |
| Literales sustituidos | búsqueda de `2.11.185-beta` en `apps/` y `package.json` | **0** restos; **14** con `2.11.186-beta` |
| Literal congelado | `v2_87` | `"bump": "2.11.0-beta"` **intacto** |
| Freeze | `node scripts/window-pin.mjs --check` | **`freeze OK`**, `apps f50042c1…` tras el bump y **`d39a04a7…`** sobre el tag (también tras el commit de docs) |
| Tests del pin | `node --test scripts/lib/window-forward.test.mjs` | **50 pass / 0 fail** |
| Ruff (scope CI) | `ruff check apps/api-python --config pyproject.toml` | **`All checks passed!`** |
| Preflight (en el sello) | `window-preflight.ps1 -Day 20261109` sobre el tag | **18 OK / 1 WARN / 0 FAIL** — medido el `2026-11-08` con el worktree ya en `v2.88.186-beta`. El `WARN` es `task.nextrun` (el disparo del domingo precede al día objetivo); antes del checkout del tag la misma medida daba **2 FAIL** (`freeze.seal` y `seal.tree`), que era exactamente lo que este sello viene a cerrar. |

Nota sobre Ruff: sin `--config pyproject.toml` los 13 scripts arrastran **7** `I001` **preexistentes**
(verificado con los cambios en `stash`). CI ejecuta con `--config`, y ahí pasa limpio. No se han
corregido: están fuera del alcance de este sello.


## 4. Ficheros del sello

- `package.json` — versión `2.11.186-beta`.
- `apps/api-python/scripts/v2_87`, `v2_89`…`v2_100` — **13** ficheros, **14** literales `meta.bump`.
- `CHANGELOG.md` — sección `2.11.186-beta`.
- `scripts/lib/window-forward.mjs` — re-anclaje del pin (**no** participa del freeze: `scripts/`).
- `apps/api-python/tests/test_lifecycle_golden_{v191,v195,v196}.py` — fixtures de los golden que el
  Policy Gate P2 exige medir (PR #107; **tests**, no producto).
- `.github/workflows/release-tag-ci.yml` — el job `playwright (live AUTO daily chain)` corre en mundo
  hermético (PR #109; **arnés del job**, sin tocar gate ni aserción).
- `docs/engineering/cierre-medicion-2026-11-06.md` — §8.1 y §10, ya en `main` desde el PR #105.
- `docs/engineering/evidence/v2.88.186/README.md` — este documento.
- `docs/engineering/entrega-auditoria-externa-v2.88.186-beta-2026-11-08.md` — índice para el auditor.
- `docs/engineering/PROJECT_STATE.md` — bloque `AsOf (V2.88.186-beta)`.

**Fuera del sello:** motor, decisión, umbrales (`minDays 4`, `minEpisodes 2`, `minCycles 32`), migraciones,
contrato HTTP y `operability_runs/`.

## 5. Identidad y publicación (POST-TAG)

| Dato | Valor |
| --- | --- |
| Tag anotado | `v2.88.186-beta` |
| Objeto de tag | `db919045004dee71d6acbc1b58b84dc52a29f677` |
| Commit | `a5013f753fd417103e5a22f4d82c84ba1d185471` |
| `Release tag CI` | [run 42479490551](https://github.com/jvelasca/Bolsa_V1/actions/runs/42479490551) — **GREEN** (13 jobs + `certify`; el opt-in `playwright (integrated E2E)` queda `skipped` por diseño) |
| GitHub Release | <https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.186-beta> — publicada, **no** pre-release; `latest` apunta a este objeto |
| Artefacto de certificación | `release-tag-ci-summary` (id `13617316287`): `status: GREEN`, `sha: a5013f75`, `asOf: 2026-11-08T12:32:54Z` |
| `freeze OK` en el job `shared` | **success**, `apps d39a04a7…` / `packages 2de53cda…` |
| `replay-repro` | **success** — artefacto `replay-oos-durable-v2.88.7` |
| `playwright (live AUTO daily chain)` | **success** — artefacto `playwright-live-auto-daily` |
| Preflight de la ventana `2026-11-09` | **18 OK / 1 WARN / 0 FAIL** (el `WARN` es el disparo del domingo, previsto) |
| Tag anterior publicado | `v2.88.183-beta` = objeto `6de48f9c…` → commit `2ffc037b` |
| Commits desde `.183` | **116** |
| `main` al sellar | `a5013f75` |

### 5.1 Movimiento del tag — declarado, no reescrito

El tag se creó sobre `67af497c` y su **primer** `Release tag CI` salió rojo en **dos** jobs. Se corrigió
el arnés y se **re-apuntó** el objeto (criterio `.153`/`.156`): no se reescribe el pasado, se declara.

| Corrección | Job en rojo | Causa medida | Arreglo (sin tocar producto) |
| --- | --- | --- | --- |
| [PR #107](https://github.com/jvelasca/Bolsa_V1/pull/107) | `lifecycle-pg` | Los golden de ciclo de vida insertaban instrumentos **sin** `market_cap_usd`/`average_daily_volume_usd`; el **Policy Gate P2** (fail-closed desde `99bd9872`) los vetaba con `MinMarketCap_unmeasured`/`MinADV_unmeasured` | Los fixtures siembran las medidas (`profile_snapshot.fundamentals`) en `test_lifecycle_golden_{v191,v195,v196}.py` |
| [PR #108](https://github.com/jvelasca/Bolsa_V1/pull/108) | `shared` | El arreglo anterior toca `apps/` ⇒ movió `HEAD:apps` | Re-anclaje del pin (`apps d39a04a7…`) |
| [PR #109](https://github.com/jvelasca/Bolsa_V1/pull/109) | `playwright (live AUTO daily chain)` | `status = no_plan`, `why = regime`: el parte cablea `YahooMacroSnapshotPort` y pedía `^VIX` **vivo** (VIX 23,8 / percentil 91,3 ⇒ `crisis` ⇒ plan `BLOCKED` por Golden G) | Ese job corre en **mundo hermético**: el proveedor externo se declara inalcanzable (`/etc/hosts` → `127.0.0.1` + `YAHOO_MAX_RETRIES=1`). Ni un gate, umbral ni aserción rebajados |
| [PR #110](https://github.com/jvelasca/Bolsa_V1/pull/110) | — | La etiqueta `commit` del pin quedó un merge por detrás y `--check` lo advertía | Re-anclaje de la etiqueta (`freeze OK` era y es idéntico) |

Consecuencia de alcance, declarada: el diff `v2.88.183-beta..v2.88.186-beta` incluye, además de
`package.json`/`meta.bump`/`docs/`/pin, **fixtures de test** (`apps/api-python/tests/`) y **un** job del
workflow del tag (`.github/workflows/release-tag-ci.yml`). **Nada de motor, decisión, contrato, UI ni
migraciones.**


## 6. Cómo se falsa esta evidencia

```bash
# el bump no dejó restos de la versión anterior fuera de docs/
git grep -n '2\.11\.185-beta' -- apps package.json | grep -v '^.docs' || echo "sin restos"

# el bump casa con el monorepo
python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# el literal congelado del replay sigue congelado
grep -n '2\.11\.0-beta' apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py

# el pin casa con el árbol del tag
node scripts/window-pin.mjs --check

# el diff del sello no toca producto
git diff --name-only v2.88.185-beta..v2.88.186-beta 2>/dev/null || git diff --name-only v2.88.183-beta^{} v2.88.186-beta^{}
```

Si alguno discrepa, **esta evidencia es falsa en ese punto** y debe corregirse con un acto nuevo, no
reescribiendo este documento.

## 7. Límites declarados

- AUTO **OFF**; operativa **100 % SIM**; sin autorización para dinero real.
- PAPER **`INCONCLUSIVE`** hasta que existan ciclos cerrados con fill durable.
- La corrida del `2026-11-09` se atribuye a **este** árbol; el `2026-11-08` (domingo) generará su propia
  fila `NON_MARKET_DAY`, que no es medición.
- Un hueco se declara, no se rellena: ausencias en `null`, nunca en `0`.
