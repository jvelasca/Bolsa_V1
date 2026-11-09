# Entrega para auditoría externa — `v2.88.186-beta`

> **Objeto entregado:** tag anotado `v2.88.186-beta` (identidad en §7).
> **Rama:** `chore/sello-2.11.186-beta` → fusionada en `main`.
> **Naturaleza:** **acto nuevo de publicación documental y de operación**. No es una auditoría y no es un
> sello de corrección: no reabre `.183` ni los dos árboles que quedaron sin tag (`.184`/`.185`). No cambia
> motor, decisión, contrato HTTP, UI ni migraciones.
> **Nota posterior (`2026-11-09`):** esta entrega describe **`.186`**. El sello siguiente,
> `2.11.187-beta`, **sí es funcional**: publica el árbol que vivía en la rama (`apps` 86 ficheros,
> `packages` 43, sin migración y con contrato aditivo). Este documento **no** se reescribe; el delta
> acumulado desde `.186` está en `CHANGELOG.md` §`2.11.187-beta` y en el `AsOf (V2.88.187-beta)` de
> [`PROJECT_STATE.md`](./PROJECT_STATE.md).
> **Para quién:** auditor externo que no conoce la historia del repositorio y necesita un punto de
> entrada único, verificable y con sus límites escritos.

---

## 0. Qué recibe el auditor (y qué no)

Este documento **no** es un dictamen. Es un **índice verificable** de lo publicado y una declaración
explícita de procedencia: qué se midió, qué se cita y qué queda fuera.

| Afirmación | Procedencia | ¿Re-verificada al escribir esto? |
| --- | --- | --- |
| El repositorio es **público** | `gh repo view` | **Sí** |
| `main` está en `2.11.185-beta` **antes** de este sello y en `67af497c` | `git show origin/main:package.json` | **Sí** |
| El último tag **publicado** antes de este acto era `v2.88.183-beta` | `git tag --list`, `gh release list` | **Sí** |
| `v2.88.183-beta` = objeto `6de48f9c…` → commit `2ffc037b` | `git rev-parse` sobre los refs del tag | **Sí** |
| Los árboles `.184` y `.185` **existen** pero **no** tienen tag ni Release | `git tag --list '*184*' '*185*'` (vacío), `gh release view v2.88.185-beta` (`release not found`) | **Sí** |
| El pin del sello casa con el árbol del sello | `node scripts/window-pin.mjs --check` | **Sí** |
| CI, recuentos de suites y enlaces de este sello | **Evidencia aportada** en §7, no re-medida aquí | **No** (§7) |

Consecuencia práctica: lo verificable **sin confiar en nadie** es la **identidad del objeto**, el
**alcance del diff** y la **posición de `main`**. Lo relativo a runs de CI se acepta **como evidencia
aportada** por quien lo firmó.

---

## 1. Índice del expediente (todo dentro del árbol del tag)

| Documento | Qué es |
| --- | --- |
| [`evidence/v2.88.186/README.md`](./evidence/v2.88.186/README.md) | Evidencia y falsabilidad de este sello |
| [`cierre-medicion-2026-11-06.md`](./cierre-medicion-2026-11-06.md) | Expediente que cierra la corrida `20261106` (`292/400`, `INCONCLUSIVE`) |
| [`auditoria-paper-vivo-2026-11-06.md`](./auditoria-paper-vivo-2026-11-06.md) | Acta del corte externo a las 24 h |
| [`cierre-medicion-2026-11-06.md`](./cierre-medicion-2026-11-06.md) §10 | Preparación de la medición del `2026-11-09` |
| [`PROJECT_STATE.md`](./PROJECT_STATE.md) | Bloque `AsOf (V2.88.186-beta)` al principio |
| [`errata-alcance-diff-v2.88.186-2026-11-08.md`](./errata-alcance-diff-v2.88.186-2026-11-08.md) | Errata de alcance: separa `.185 → .186` de `.183 → .186` (POST-TAG, no está en el tag) |
| [`../../CHANGELOG.md`](../../CHANGELOG.md) §`2.11.186-beta` | Declaración del acto nuevo |
| [`../ops/final_package.py`](../../scripts/ops/final_package.py) | Paquete de cierre **read-only** con terminación declarada |
| [`../ops/window-preflight.ps1`](../../scripts/ops/window-preflight.ps1) | Preflight **read-only** de las 6 precondiciones |

---

## 2. Cómo obtener el objeto

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git fetch --tags
git checkout v2.88.186-beta
```

**Un clon por defecto entrega `main`, que contiene este expediente** (el sello se fusionó en `main`, al
contrario que los sellos `.177`…`.185`). El tag es el objeto certificado; `main` puede haber avanzado
después.

---

## 3. Qué certifica este acto y qué no

| Ámbito | Dictamen |
| --- | --- |
| **Publicación** | **Sí**: existe un objeto etiquetado, con notas de Release y un punto de entrada único |
| **Trazabilidad** | **Sí**: tag anotado → commit → árbol, verificable con `git rev-parse` |
| **Alcance del diff del sello** (`.185 → .186`) | **Sí**: `package.json`, los 14 `meta.bump`, `CHANGELOG`, `docs/`, el pin del sello, los fixtures del Policy Gate P2 y un job del workflow del tag (§7.1). **Nada funcional** |
| **Alcance del diff acumulado** (`.183 → .186`) | **Sí, y no es solo documental**: 116 commits, 231 ficheros, migraciones `063`–`066` y cambios en `auto_simulation_worker.py` (+1 158), `auto_orchestrator_worker.py` y `paper_auto_engine_worker.py`. Provienen de los árboles `.184`/`.185`; el acto `.186` los **publica**, no los introduce ([errata](./errata-alcance-diff-v2.88.186-2026-11-08.md)) |
| **Integridad del cierre** | **Sí**: la corrida `20261106` queda cerrada con terminación declarada, `0` ciclos y sus desviaciones escritas |
| **Rentabilidad** | **No**. AUTO **OFF**; PAPER **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`) |
| **Eficacia operativa de AUTO** | **No**. **0** ciclos cerrados; 292/400 ticks y 263 ciegos |
| **P&L neto de comisiones** | **No**. `P2-03` **abierto** |
| **Multidivisa** | **No**. `P2-11` **abierto** |
| **Publicación de `.184`/`.185`** | **No**. Nunca se etiquetaron; este acto **no re-etiqueta el pasado** |
| **Re-certificación de `.183`** | **No**. Su objeto queda **intacto** |

---

## 4. Hallazgos y deudas abiertas

| Elemento | Qué exige | Estado |
| --- | --- | --- |
| **Terminación prematura `20261106`** | Corrida de 24 h que acabe sin `forward.json` | **Abierto** (causa observada: suspensión) |
| **`days` cuenta días sin sesión** | Que un día sin sesión o sin decisión no cuente como día de ventana | **Abierto** (deuda de producto) |
| **Tramo ciego por frontera de barra** | Que la barra del día corriente exista **antes** de medianoche UTC | **Abierto** |
| **Suspensión del equipo** | Desactivada **por CA** el `2026-11-08`; por batería sigue activa | **Mitigado, no cerrado** |
| **E2E live/integrated** | API + PostgreSQL + barras; `skipped` no certifica | **Abierto** |
| `P2-03`, `P2-11`, `P2-05…P2-12`, `P3` | Según el dictamen de `.170` | **Abiertos** |

**No se abre ningún issue en este acto.** Si más adelante se abren, deben enlazar a este documento y no
sustituirlo.

---

## 5. Invariantes que este acto no cambia

- `v2.88.183-beta`: **byte-idéntico**, sin re-anotar.
- `main`: contiene este expediente; **el tag es el objeto**, no `main`.
- AUTO: **OFF**.
- PAPER: **`INCONCLUSIVE`**; rentabilidad **no demostrada**; sin órdenes reales.
- Motor, decisión, contrato HTTP, migraciones y `@bolsa/shared`: **sin cambios respecto a `.185`** (el
  contenido acumulado desde `.183` sí los incluye; ver §3 y la errata).
- Umbrales de la ventana (`minDays 4`, `minEpisodes 2`, `minCycles 32`): **sin rebajar**.
- Pin PAPER: re-anclado **solo** porque el acto mueve `apps` (bump y fixtures del gate P2); `packages` no se movió; los días anteriores quedan `STALE`.

---

## 6. Cómo se falsa esta entrega

```bash
# §0 — main estaba en 2.11.185-beta antes del sello (commit 67af497c)
git show 67af497c:package.json | grep '"version"'

# §0 — el tag anterior publicado era .183 y .184/.185 no existen como tag
git tag --list '*184*' '*185*'      # vacío
git rev-parse 'v2.88.183-beta^{tag}' 'v2.88.183-beta^{}'   # 6de48f9c… / 2ffc037b

# §3 — el diff del sello no toca producto
git diff --name-only v2.88.183-beta^{} v2.88.186-beta^{}

# §3 — el bump casa con el monorepo
pytest apps/api-python/tests/test_dia_d_bump_guard.py -q

# §3 — el pin casa con el árbol del tag
node scripts/window-pin.mjs --check

# §5 — el literal congelado del replay no se movió
grep -n '2\.11\.0-beta' apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py
```

Si alguno discrepa, **esta entrega es falsa en ese punto** y debe corregirse con un acto nuevo, no
reescribiendo el pasado.

---

## 7. Identidad y publicación (POST-TAG)

| Dato | Valor |
| --- | --- |
| Tag anotado | `v2.88.186-beta` |
| Objeto de tag | `db919045004dee71d6acbc1b58b84dc52a29f677` |
| Commit | `a5013f753fd417103e5a22f4d82c84ba1d185471` |
| `Release tag CI` | [run 42479490551](https://github.com/jvelasca/Bolsa_V1/actions/runs/42479490551) — **GREEN** (13 jobs + `certify`; el opt-in `playwright (integrated E2E)` queda `skipped` por diseño) |
| Artefacto | `release-tag-ci-summary` (id `13617316287`): `status: GREEN`, `sha: a5013f75`, `asOf: 2026-11-08T12:32:54Z` |
| GitHub Release | <https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.186-beta> — publicada, **no** pre-release; `latest` = este objeto |
| Commit de `main` al sellar | `a5013f75` |
| Tag anterior publicado | `v2.88.183-beta` (objeto `6de48f9c…` → commit `2ffc037b`) |
| Commits desde `.183` | **116** |
| `freeze OK` en el job `shared` | `apps d39a04a7f544704d05033dc8ea8772ebb22272d0` / `packages 2de53cda49ed847dbd5d4b9572c826c6368ddc52` |
| Preflight de la ventana `2026-11-09` | **18 OK / 1 WARN / 0 FAIL** (el `WARN` es `task.nextrun`: el disparo del domingo precede al día objetivo) |

### 7.1 El tag se movió: declarado, no reescrito

El tag se creó sobre `67af497c` y su **primer** `Release tag CI` (run `42473826946`) salió **rojo** en dos
jobs. Se corrigió el arnés, se re-apuntó el objeto a `a5013f75` y se declaró aquí y en la evidencia
(criterio `.153`/`.156` del repositorio). **No** se reescribe el pasado ni se re-etiqueta `.184`/`.185`.

| Corrección | Job en rojo | Causa medida | Qué se cambió |
| --- | --- | --- | --- |
| [#107](https://github.com/jvelasca/Bolsa_V1/pull/107) | `lifecycle-pg` | Golden de ciclo de vida sin `market_cap_usd`/`average_daily_volume_usd`: el Policy Gate P2 (fail-closed desde `99bd9872`) los vetaba | **Fixtures** (`apps/api-python/tests/test_lifecycle_golden_v191/v195/v196.py`) |
| [#108](https://github.com/jvelasca/Bolsa_V1/pull/108) | `shared` | Los fixtures tocan `apps/` ⇒ mueven `HEAD:apps` | Re-anclaje del pin (`apps d39a04a7…`) |
| [#109](https://github.com/jvelasca/Bolsa_V1/pull/109) | `playwright (live AUTO daily chain)` | `no_plan` / `why = regime`: `YahooMacroSnapshotPort` pedía `^VIX` **vivo** (23,8 / percentil 91,3 ⇒ `crisis` ⇒ plan `BLOCKED`) | **Arnés del job**: mundo hermético (proveedor externo inalcanzable). Sin rebajar gate ni aserción |
| [#110](https://github.com/jvelasca/Bolsa_V1/pull/110) | — | La etiqueta `commit` del pin quedó un merge por detrás | Re-anclaje de la etiqueta (`freeze OK` idéntico antes y después) |

Alcance efectivo del **delta del sello** `31c2d3cd..v2.88.186-beta` (`.185 → .186`): `package.json`, los
14 `meta.bump`, `CHANGELOG`, `docs/`, el pin del sello, los **fixtures de test** del gate P2 y **un** job
del workflow del tag. **Nada de motor, decisión, contrato HTTP, UI ni migraciones.**

Alcance efectivo del **diff acumulado** `v2.88.183-beta..v2.88.186-beta` (`.183 → .186`): 116 commits y
**231 ficheros**, con migraciones `063`–`066` y cambios de producto (`apps/api-python/src/bolsa_api`:
15 ficheros, +1 564/−261, entre ellos `auto_simulation_worker.py`). Esos cambios proceden de los árboles
`.184`/`.185`; `.186` los publica. Detalle y falsación:
[errata de alcance](./errata-alcance-diff-v2.88.186-2026-11-08.md).

---

## 8. Alcance y no-cambios de este documento

- **No** modifica `packages/`, migraciones ni `operability_runs/` **respecto a `.185`**. El diff
  acumulado desde `.183` sí contiene migraciones (`063`–`066`) y cambios de producto previos a este acto
  ([§3](#3-qué-certifica-este-acto-y-qué-no), [errata](./errata-alcance-diff-v2.88.186-2026-11-08.md)).
- **Sí** toca `apps/api-python/scripts/` **solo** en los 14 literales `meta.bump` (no es cambio funcional).
- **Sí** toca, como arnés declarado en §7.1, `apps/api-python/tests/test_lifecycle_golden_{v191,v195,v196}.py`
  (fixtures) y `.github/workflows/release-tag-ci.yml` (un job). **No** alteran motor, decisión, contrato ni
  gates: el spec del journey conserva su `expect(status).toBe("ok")` y el Policy Gate P2 sigue fail-closed.
- **No** crea ni re-anota tags distintos de `v2.88.186-beta`; ese tag **se re-apuntó** una vez y se declara
  en §7.1.
- **No** reescribe el expediente del cierre: lo **indexa** y lo publica.
- **No** abre ni cierra hallazgos.
