# Auditoría de la PR #76 — aviso durable del vigía de la ventana PAPER

**Fecha:** 2026-10-25 · **Objeto:** PR [#76](https://github.com/jvelasca/Bolsa_V1/pull/76), rama
`fix/window-day-watch-durable-alert`, cabeza `fccdd69a`, base `main` `26250187`
· **Naturaleza:** auditoría **read-only** (no fusiona, no etiqueta, no comenta, no re-ancla el pin).

**Veredicto (actualizado tras la reproducción del §9):** la PR **sostiene** su alcance declarado
—dos ficheros, sin bump, sin `CHANGELOG`, sin `PROJECT_STATE`, sin migración— y su CI está **verde**
sobre la cabeza exacta. Queda **técnicamente validada** y se mantiene en **borrador**, **sin
autorización de fusión**: el único bloqueo propio de la PR es la decisión de fusionarla.

| Elemento | Estado | Conclusión |
|---|---|---|
| H1 — aislamiento de la PR | **Cerrado** | Worktree independiente sobre `fccdd69a`, con entorno Python propio (§9.1) |
| H2 — pin `.161` | **Pendiente (reformulado)** | El re-anclaje del sello `.161` no está publicado en `origin/main`: es un asunto de **publicación y gobernanza**, no un fallo del pin ni de la PR |
| H3 — `main` local desfasado | **Controlado** | `main` local (`815ed4d0`) y `origin/main` (`26250187`) se leen por separado |
| PR #76 — checks | **Verde** | 11/11 en `SUCCESS` sobre `fccdd69a` (§1) |
| Pruebas locales | **Verde** | **45** en el módulo y **49** en la corrida selectiva ampliada (§9.3) |
| `window-pin --check` | **Pendiente** | `TREE_MOVED` en el árbol de auditoría; `origin/main` es **autoconsistente** con el pin `.160` (§9.4, §9.5) |
| Fusión de #76 | **Sin decidir** | No fusionada y **no autorizada** |

`TREE_MOVED` **no** es un fallo funcional de los tests: es el gate de freeze declarando que el árbol
no casa con el pin declarado en esa cabeza. La precisión del §9.5 acota ese resultado a las cabezas
que no son `origin/main` y descarta atribuirlo a `main`.

**No se ha modificado nada en GitHub en este paso.**

---

## 0. Alcance y método

Se auditan: (a) la metadata y los checks de la PR; (b) el diff real contra `main`; (c) el estado del
pin PAPER (`scripts/lib/window-forward.mjs` → `WINDOW_CONFIG`); (d) la relación entre el árbol de
`origin/main`, el del sello `v2.88.161-beta` y el del árbol de trabajo local.

Método: `gh pr view`/`gh pr checks` sobre la PR, `git diff --stat` entre commits concretos,
`git merge-base --is-ancestor` para la genealogía, `git rev-parse <rev>:apps` / `:packages` para los
tree hashes. Todo lo que se declara medido abajo se puede reproducir con los comandos del §7.

---

## 1. Evidencia de la PR (medida)

| Comprobación | Valor observado |
|---|---|
| Estado | `isDraft: true` |
| Cabeza | `fccdd69ab81e112f76b5e1e2ffb5a4defc5ba58e` |
| Base | `main` @ `26250187a61ef3e71ea5e7a0e0b8387a7347f404` |
| Mergeabilidad | `mergeable: MERGEABLE`, `mergeStateStatus: CLEAN` |
| Ficheros tocados | **2**: `apps/api-python/src/bolsa_api/background/window_day_watch_worker.py` (+153/−27) y `apps/api-python/tests/test_window_day_watch.py` (+167/−1) |
| Checks del head | **11/11 en `SUCCESS`** (Gitleaks `scan`; Python CI: `quality`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`) |
| Runs citados | [`40212620361`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40212620361) (16:38–16:41Z) y [`40214861819`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40214861819) / [`40214861787`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40214861787) (17:06–17:09Z) |
| Tests del módulo | **45 passed** (36 → 45) según el cuerpo de la PR; **49 passed** en la corrida selectiva `test_window_day_watch` + `test_scheduler_worker` + `test_dia_d_bump_guard` |

**Alcance respetado.** El diff **no** incluye `packages/py/**`, ni `058_*`, ni `package.json`, ni
`CHANGELOG.md`, ni `PROJECT_STATE.md`, ni `auto_*`. Coincide con lo que la PR declara: sólo el aviso
del vigía y sus tests.

---

## 2. Hallazgos (tres desviaciones de contexto, ninguna de la PR)

Ninguna de las tres es un defecto de #76. Las tres afectan a **cómo se verifica** la PR y a **qué se
puede concluir** de un `window:freeze` ejecutado en este clon. Tras la reproducción del §9 quedan
**H1 cerrado**, **H2 reformulado** (sigue pendiente como asunto de publicación) y **H3 controlado**.

### H1 · **Cerrado** · el árbol de trabajo no es la PR

`HEAD` del clon está en `audit/auto-daily-chain-ui` (`b64a6cb4`), no en
`fix/window-day-watch-durable-alert`. El diff entre ambas cabezas es de **83 ficheros, +9.265/−317**:
es la rama de la cadena AUTO + `058_estudio_daily_proposals` más la UI diaria.

**Consecuencia:** ejecutar `pytest apps/api-python/tests/test_window_day_watch.py` o
`pnpm window:freeze` en este árbol **no mide #76**; mide la rama de integración. La verificación
pre-fusión tiene que hacerse en un `git worktree` sobre `fccdd69a` (§6, paso 5).

**Riesgo si se ignora:** atribuir a la PR un resultado (verde o rojo) producido por otro código.

**Cierre (2026-10-25, §9.1):** el `git worktree` sobre `fccdd69a` se creó con su propio entorno
(`uv sync`, `.venv` del worktree) y el intérprete importa
`…\pr76-verify\apps\api-python\src\bolsa_api\__init__.py`, **no** el de la rama de integración. El
aislamiento queda reproducido; el método del worktree se conserva como paso 5 del §6 y no se repite
en cada comprobación.

### H2 · **Pendiente (reformulado)** · el sello `.161` no está publicado en `main`

`WINDOW_CONFIG` declara:

| Campo | Valor |
|---|---|
| `commit` | `64e23eaf` |
| `appsHash` | `d06695aba31c3e9c1db821b304a3a5a8089fccd0` |
| `packagesHash` | `243cd09cfe16752e4e18ad47eedad858a1389192` |

Esos hashes son el árbol del sello **`v2.88.161-beta`** (tag anotado `9de9e08f` → commit
`9b6d3252`, re-anclaje del pin). Pero:

- `git merge-base --is-ancestor 64e23eaf origin/main` ⇒ **falso**. El commit del sello `.161`
  **no está en `origin/main`**.
- `origin/main` (`26250187`) conserva el árbol del **`.160`**: `apps 4be4a32f…` /
  `packages 0824c030…` (el del re-anclaje `f2caa2a0`).
- Las únicas ramas que contienen `64e23eaf` son `audit/auto-daily-chain-ui` y
  `fix/audit-815ed4d0-real-route` (local y `origin`).

**Consecuencia (corregida el 2026-10-25, §9.5).** El pin `.161` **no está roto**: comparado consigo
mismo da `OK`, porque sus `appsHash`/`packagesHash` son exactamente los de `64e23eaf`/`9b6d3252`.
`freezeStatus` compara **sólo los dos tree hashes** y el campo `commit` es una **etiqueta**
informativa (`scripts/window-pin.mjs`). De ahí:

| Revisión | Árbol real | Freeze esperado |
|---|---|---|
| `origin/main` (`26250187`) | `apps 4be4a32f…` / `packages 0824c030…` = pin `.160` | **`OK`** con `commitLabelStale` (`4a76d477` ≠ `26250187`) |
| `fccdd69a` (#76) | `apps 0e9fef5b…` / `packages 0824c030…` | **`TREE_MOVED`**, por los dos ficheros de la PR |
| Ramas con el re-anclaje `9b6d3252` | `apps d06695ab…` / `packages 243cd09c…` = pin `.161` | **`TREE_MOVED`** frente al pin de `main` |

El `TREE_MOVED` que la PR anticipa es correcto —su pin es el del `.160`—, pero **no** se extiende a
`origin/main`, que es **autoconsistente** con el `.160` y daría `OK`. El problema **no** es el pin
`.161`: es que **el sello `.161` y la rama publicada `main` representan estados distintos del
proyecto**. `git merge-base --is-ancestor 64e23eaf origin/main` es **falso** y
`git rev-list --left-right --count origin/main...64e23eaf` ⇒ `0 7`: el sello se construyó **sobre**
`main` pero **no** se ha publicado en `main`. Regularizarlo es una operación de **publicación y
gobernanza del sello**, no de esta PR, y por eso **no se toca el pin aquí** ni se decide qué árbol es
el operativo.

### H3 · **Controlado** · `main` local no es `origin/main`

La rama local `main` está en `815ed4d0` y va **3 commits por delante** de `origin/main`
(`815ed4d0`, `11a52fbe`, `6f4a6e4c`), sin publicar.

**Consecuencia:** «la base `main` no ha cambiado» es cierto **sólo** para `origin/main`
(`26250187`). Cualquier comprobación pre-fusión debe leer `git rev-parse origin/main` tras un
`git fetch`, no `git rev-parse main`.

**Control (2026-10-25, §9.5):** la distinción se ha aplicado y se sostiene —
`git rev-list --left-right --count origin/main...main` ⇒ `0 3` (`815ed4d0`, `11a52fbe`,
`6f4a6e4c`) y `origin/main` sigue en `26250187`. Queda como **regla de lectura**, no como desviación
abierta.

---

## 3. Dictamen sobre el pin y el sello

- **`TREE_MOVED` no es un fallo de tests.** El módulo bajo prueba (`window_day_watch_worker.py`) es
  independiente del pin; que su suite esté verde no dice nada del freeze, y que el freeze esté en
  `TREE_MOVED` no invalida la suite.
- **El pin `.161` tampoco está roto.** Comparado consigo mismo da `OK`: sus `appsHash`/`packagesHash`
  son los de `64e23eaf`/`9b6d3252`. Lo que falta es que ese estado se **publique** en `main`.
- **La discrepancia es de publicación.** `origin/main` es autoconsistente con el `.160`; el sello
  `.161` vive **7 commits por delante** y fuera de `main`. Son dos estados distintos del proyecto y
  no se elige aquí cuál es el operativo.
- **No se da por resuelto.** Se declara **pendiente** hasta decidir si `main` publica el estado que
  sustenta el sello o si conserva el árbol `.160` y se regulariza el sello por el procedimiento
  correspondiente (re-anclaje con `pnpm window:pin` en un commit **posterior** y tag sobre el
  re-anclaje, porque el gate `window:freeze` del job `shared` es fail-closed).
- **No se adelanta ni se mueve el pin accidentalmente.** Este documento no toca
  `scripts/lib/window-forward.mjs`. Un `window:pin --write` aquí sería un error: fijaría el árbol de
  la rama de integración AUTO/`058`, no el de un sello decidido.

---

## 4. Qué NO se hace en este paso

- Sin merge, sin cerrar la PR, sin quitarle el borrador, sin labels, sin comentarios, sin tags, sin
  releases.
- Sin re-anclaje del pin, sin `window:pin --write`, sin `window:freeze` ejecutado sobre la rama de
  integración.
- Sin bump de versión ni `CHANGELOG`.
- Sin integrar la cadena AUTO ni la migración `058_estudio_daily_proposals`.
- Sin tocar el grafo Alembic.

---

## 5. Tres vías separadas (no se mezclan)

1. **#76 — sólo el arreglo del vigía.** Requiere **decisión explícita de fusión** y el checklist del
   §6. Su merge **no** incorpora AUTO ni `058`.
2. **Pin de versión — regularizar el sello `.161`.** Es un asunto de **publicación**: decidir si `main`
   publica el estado que sustenta el sello o si conserva el árbol `.160` y se regulariza por el
   procedimiento de sello, sin adelantar ni mover el pin fuera de ese procedimiento. Antes hay que
   decidir **qué árbol es el operativo** (H2).
3. **AUTO + migración `058`** — propuesta de integración completa y aparte: grafo Alembic validado
   (`057_top3_opportunity_identity` → `058_estudio_daily_proposals`, sin ramas huérfanas) y pruebas
   sobre una base **desechable** representativa de 057.

Mientras las tres no se decidan: **AUTO OFF** · **PAPER virtual** · `evidence_ready = false` ·
**0/32 ciclos medibles** · ventana **`INCONCLUSIVE`** · nada de esto es evidencia de rentabilidad.

---

## 6. Checklist read-only de pre-fusión (ejecutar sólo si se decide fusionar)

Todos los pasos son de **lectura**; el único que escribe algo es el `git worktree add`, que crea un
directorio **fuera** del árbol de trabajo y no altera ramas ni commits.

1. **Cabeza y base sin cambios**
   ```powershell
   gh pr view 76 --json number,isDraft,headRefOid,baseRefOid,mergeable,mergeStateStatus
   ```
   Exigir: `headRefOid = fccdd69ab81e112f76b5e1e2ffb5a4defc5ba58e` y
   `baseRefOid = 26250187a61ef3e71ea5e7a0e0b8387a7347f404`. Si cualquiera difiere, **parar**: la PR
   cambió después de esta auditoría y hay que re-auditarla.

2. **Checks requeridos en verde sobre esa cabeza**
   ```powershell
   gh pr checks 76
   ```
   Exigir los 11 en `pass` (`scan`, `quality`, `lifecycle-pg`, `paper-forward-pg`,
   `grammar-discovery-pg`, `auto-v2-durable-pg`). Un `pending` no es un verde.

3. **Base `main` sin mover** (usar `origin/main`, no `main` — ver H3)
   ```powershell
   git fetch origin main
   git rev-parse origin/main
   ```
   Debe seguir siendo `26250187`.

4. **Alcance sigue siendo dos ficheros**
   ```powershell
   gh pr view 76 --json files
   ```
   Exigir exactamente `window_day_watch_worker.py` y `test_window_day_watch.py`. Si aparece cualquier
   `auto_*`, `058_*`, `package.json`, `CHANGELOG.md` o `PROJECT_STATE.md`, **no fusionar**: la PR ya no
   es la que se auditó.

5. **Tests del módulo sobre la cabeza real** (no en este árbol — ver H1)
   ```powershell
   git worktree add ..\pr76-verify fccdd69a
   cd ..\pr76-verify
   python -m pytest apps/api-python/tests/test_window_day_watch.py -q
   uv run ruff check apps/api-python/src/bolsa_api/background/window_day_watch_worker.py apps/api-python/tests/test_window_day_watch.py --config pyproject.toml
   uv run mypy apps/api-python/src --follow-imports=silent
   ```
   Exigir **45 passed** en el módulo. Registrar la cifra obtenida; si no es 45, anotar el delta y no
   fusionar sin explicarlo.

6. **Freeze declarado, no re-anclado**
   ```powershell
   node scripts/window-pin.mjs --check
   ```
   Sobre la cabeza de la PR se **espera** `TREE_MOVED` en `apps` (el pin de `fccdd69a` es el del
   `.160`, §9.4); **no** se espera en `origin/main`, que daría `OK` con `commitLabelStale` (§9.5). Se
   registra el resultado y **no** se ejecuta `--write`. Este paso documenta el estado del sello; no lo
   arregla.

7. **Registrar el resultado** en este documento (o en un anexo fechado): run ids, SHA observados,
   timestamps y cifra de tests. Si algo no casa con el §1, **no fusionar**.

---

## 7. Reproducción de lo medido aquí

```powershell
# PR
gh pr view 76 --json isDraft,headRefOid,baseRefOid,mergeable,mergeStateStatus,statusCheckRollup
gh pr view 76 --json files
git diff --stat 26250187 fccdd69a

# H1 — el árbol de trabajo no es la PR
git rev-parse HEAD
git diff --stat fccdd69a b64a6cb4

# H2 — el pin es el árbol del .161 y .161 no está en origin/main
git rev-parse 64e23eaf:apps 64e23eaf:packages
git rev-parse origin/main:apps origin/main:packages
git merge-base --is-ancestor 64e23eaf origin/main   # exit != 0 ⇒ no está
git branch -a --contains 64e23eaf
git rev-parse v2.88.161-beta                        # tag anotado → 9b6d3252

# H3 — main local por delante de origin/main
git rev-parse main origin/main
git log --oneline origin/main..main
```

---

## 8. Criterios de desbloqueo

| Vía | Se desbloquea cuando |
|---|---|
| #76 | Decisión explícita de fusión **y** §6 completo sobre la misma cabeza `fccdd69a` y la misma base `26250187` |
| Pin / sello | Se decida qué árbol es el operativo (H2) y, si procede, se publique ese estado en `main` o se regularice el sello con tag sobre el re-anclaje |
| AUTO + `058` | Grafo Alembic validado y suite completa sobre base desechable en 057, en su propia revisión de integración |

**Límites del dictamen.** CI verde **no** certifica rentabilidad; 45 tests verdes **no** certifican la
ventana; `TREE_MOVED` pendiente **no** invalida el arreglo del vigía y **no** se da por resuelto. La
PR #76 queda **validada técnicamente** y **sin autorización de fusión**; la discrepancia del sello
`.161` es un asunto **independiente de publicación y gobernanza**. La ventana PAPER sigue
**`INCONCLUSIVE`** con **0/32** ciclos medibles y `evidence_ready = false`.

---

## 9. Anexo — reproducción sobre `fccdd69a` (2026-10-25, read-only)

Ejecución: **2026-10-25 18:50–18:53 +01:00** (`17:50–17:53Z`). Nada de esta sección se ejecutó en
GitHub ni alteró ramas, tags o pin.

### 9.1 Entorno aislado (cierra H1)

```powershell
git worktree add ..\pr76-verify --detach fccdd69a
cd ..\pr76-verify
uv sync
```

- `git rev-parse HEAD` ⇒ `fccdd69ab81e112f76b5e1e2ffb5a4defc5ba58e` (**detached**, sin rama).
- `uv run python -c "import bolsa_api, sys; print(bolsa_api.__file__); print(sys.prefix)"` ⇒
  `…\pr76-verify\apps\api-python\src\bolsa_api\__init__.py` y `…\pr76-verify\.venv` ⇒ **se importa el
  código de la PR**, no el de `audit/auto-daily-chain-ui`.
- Python `3.12.13` (venv propio del worktree), `uv 0.12.3`, `node v24.18.0`.
- El árbol del worktree queda limpio (`git status --short` vacío; `.venv` no versionado).

### 9.2 Entradas observadas (coinciden con §1)

| Campo | Valor observado |
|---|---|
| `headRefOid` | `fccdd69ab81e112f76b5e1e2ffb5a4defc5ba58e` |
| `baseRefOid` | `26250187a61ef3e71ea5e7a0e0b8387a7347f404` |
| `isDraft` | `true` |
| `mergeable` / `mergeStateStatus` | `MERGEABLE` / `CLEAN` |
| Ficheros | `window_day_watch_worker.py` (+153/−27) y `test_window_day_watch.py` (+167/−1) |
| Checks | **11/11 `pass`** (`quality`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg` × runs [`40212620361`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40212620361) y [`40214861819`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40214861819); `scan` en [`40214861787`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40214861787)) |

`git rev-parse origin/main` ⇒ `26250187…` (la base **no** se ha movido desde la auditoría).

Los dos recuentos del §1 también se reprodujeron: `git diff --stat 26250187 fccdd69a` ⇒ **2 ficheros**,
`320 insertions(+), 28 deletions(-)` (la suma de +153/−27 y +167/−1), y `git diff --stat fccdd69a
b64a6cb4` ⇒ **83 ficheros**, `9265 insertions(+), 317 deletions(-)` (H1).

### 9.3 Suites y calidad estática (medido)

| Comando | Resultado |
|---|---|
| `uv run pytest apps/api-python/tests/test_window_day_watch.py -q` | **45 passed** en `1.93 s` |
| `uv run pytest …test_window_day_watch.py …test_scheduler_worker.py …test_dia_d_bump_guard.py -q` | **49 passed** en `3.50 s` |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | `All checks passed!` |
| `uv run mypy` (5 rutas de `src` del job `quality`) | `Success: no issues found in 567 source files` |
| `uv run lint-imports --config packages/py/.importlinter` | `4 kept, 0 broken` |

El `mypy` se ejecutó con la misma lista de rutas que el CI (no con `uv run mypy` a secas, que aborta
por falta de objetivos):

```powershell
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src `
  packages/py/application/src apps/api-python/src --follow-imports=silent
```

Las dos cifras del §1 quedan confirmadas sobre la cabeza exacta: **45** en el módulo y **49** en la
corrida selectiva. Los dos warnings de `conftest` (`la BD no responde`) son la limpieza de residuos
omitida: la suite es **hermética** y no toca PostgreSQL, así que ningún resultado depende de la base.

### 9.4 Freeze: `TREE_MOVED` declarado, pin intacto

```powershell
node scripts/window-pin.mjs --check     # exit 1
```

| Campo | Pin | `HEAD` (`fccdd69a`) | ¿Casa? |
|---|---|---|---|
| `commit` | `4a76d477` | `fccdd69a` | n/a (etiqueta informativa, no entra en el gate) |
| `appsHash` | `4be4a32f…` | `0e9fef5b…` | **no** |
| `packagesHash` | `0824c030…` | `0824c030…` | **sí** |

Lectura: el desvío está **sólo en `apps`** y corresponde exactamente a los dos ficheros de la PR
(`src/bolsa_api/background/` + `tests/`); `packages` no se mueve, como declara el alcance. El pin de
esta cabeza es el del `.160` (`commit: 4a76d477`), no el del `.161` ⇒ **`TREE_MOVED` local esperado**
y **sin relación** con la discrepancia de gobernanza de H2.

**No se ejecutó `--write`.** `scripts/lib/window-forward.mjs` queda sin tocar.

### 9.5 Precisión sobre H2 (corrección de una afirmación, no una decisión)

| Revisión | Pin declarado | Árbol real | Freeze |
|---|---|---|---|
| `origin/main` (`26250187`) | `4a76d477` (`apps 4be4a32f…` / `packages 0824c030…`) | `apps 4be4a32f…` / `packages 0824c030…` | **`OK`** |
| `fccdd69a` (#76) | `4a76d477` (ídem) | `apps 0e9fef5b…` / `packages 0824c030…` | `TREE_MOVED` por la PR |
| `b64a6cb4` (árbol de trabajo) | `64e23eaf` (`apps d06695ab…` / `packages 243cd09c…`) | `apps 58137292…` / `packages 545db2c9…` | `TREE_MOVED` (deducido de los hashes) |
| `9b6d3252` (tag `v2.88.161-beta`) | `64e23eaf` (`apps d06695ab…` / `packages 243cd09c…`) | `apps d06695ab…` / `packages 243cd09c…` | **`OK`** (deducido; es el re-anclaje) |

Las filas **`OK`** y el `TREE_MOVED` de `b64a6cb4` se deducen de comparar los tree hashes con
`git rev-parse <rev>:apps <rev>:packages`, que es exactamente lo que compara `freezeStatus`; el único
freeze ejecutado en este turno es el de `fccdd69a` (§9.4).

- `origin/main` es **autoconsistente** con el pin del `.160` ⇒ **no** declararía `TREE_MOVED`, sino
  `freeze OK` con `commitLabelStale` (`4a76d477` ≠ `26250187`), porque el freeze real son los dos tree
  hashes y `commit` es sólo la etiqueta (`freezeStatus` en `scripts/window-pin.mjs`). La frase del
  §2/H2 queda acotada a las ramas que portan el re-anclaje `9b6d3252`, ya corregida allí.
- `64e23eaf` va **7 commits por delante** de `origin/main` y `main` no aporta ninguno que le falte
  (`rev-list --left-right --count origin/main...64e23eaf` ⇒ `0  7`): el sello `.161` se construyó
  **sobre** `main` pero **no** se ha publicado en `main`. `9b6d3252` va 8 por delante.
- H2 **sigue pendiente y sin decisión**: qué árbol es el operativo no se elige aquí.
- H3 reproducido: `git rev-list --left-right --count origin/main...main` ⇒ `0  3`
  (`815ed4d0`, `11a52fbe`, `6f4a6e4c`), y `origin/main` sigue en `26250187`.

### 9.6 Qué no se hizo

Sin comentarios, labels, revisión, merge ni cambios de borrador en GitHub; sin `window:pin --write`,
sin tags, sin ramas nuevas, sin bump, sin `CHANGELOG` y **sin commit** durante la reproducción. El
worktree `..\pr76-verify` se retiró al terminar; `main`, `origin/main`, tags y pin quedan intactos. El
commit posterior de este documento es **sólo de documentación** y se declara en §9.7.

### 9.7 Estado final del dictamen (cierre de la reproducción)

| Elemento | Estado | Base de la conclusión |
|---|---|---|
| H1 — aislamiento de la PR | **Cerrado** | §9.1: worktree sobre `fccdd69a`, `.venv` propio, importa el código de la PR |
| H2 — pin `.161` | **Pendiente, reformulado** | §9.5: `freezeStatus` compara sólo los dos tree hashes; `origin/main` es autoconsistente con el `.160` (`OK` + `commitLabelStale`); `TREE_MOVED` sólo donde vive el re-anclaje `9b6d3252`; `64e23eaf` va `0 7` respecto de `origin/main` ⇒ **asunto de publicación**, no fallo del pin |
| H3 — `main` local desfasado | **Controlado** | §9.5: `origin/main...main` ⇒ `0 3`; se lee `origin/main` en toda comprobación |
| PR #76 — checks y alcance | **Verde** | §1 y §9.2: 11/11 `SUCCESS`, 2 ficheros, `MERGEABLE`/`CLEAN` |
| PR #76 — pruebas | **Verde** | §9.3: **45 passed** en el módulo, **49** en la corrida selectiva, estáticos limpios |
| `window-pin --check` | **Pendiente** | §9.4: `TREE_MOVED` en `apps` sobre `fccdd69a`; sin `--write` |
| Fusión de #76 | **Sin decidir** | Sin merge, sin revisión, sin cambio de borrador; requiere autorización explícita |

**Corrección que este anexo deja asentada.** La atribución anterior de `TREE_MOVED` a `origin/main`
queda **retirada**: el pin `.161` no está roto y `origin/main` es autoconsistente con el `.160`. Lo
que hay es un **desfase de publicación** entre el sello `.161` y la rama `main` publicada. Este
anexo **no** decide cuál de los dos estados es el operativo y **no** modifica el pin.

**Tres decisiones independientes.** (1) #76: mantenerla en borrador hasta autorización expresa; la
evidencia técnica disponible es favorable. (2) Sello `.161`: decidir si se publica en `main` el estado
que lo sustenta o se conserva `main` en el árbol `.160` y se regulariza por el procedimiento de sello,
sin adelantar el pin. (3) AUTO/`058`: integración separada, con grafo Alembic validado y arranque
sobre una base representativa antes de abrir su propia PR.

**Límites.** AUTO **OFF** · PAPER virtual · ventana **`INCONCLUSIVE`** · `evidence_ready = false` ·
**0/32** ciclos medibles · sin evidencia de rentabilidad. `main`, `origin/main`, tags, ramas y pin
quedan intactos.
