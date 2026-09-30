# Evidencia cruda — Consolidación `v2.88.10`: el tag pasa a ser **autoconsistente** (cita de su CI + corrección del recuento local) y **queda como objeto auditado** (2026-09-30)

Resumen **verificable** del sello, y **punto de entrada de la auditoría externa**. Las cifras están
**transcritas** de las mediciones. Este sello **no cambia ni una línea de código**: su contenido es
**documentación** que repara dos defectos que el tag `v2.88.9-beta` dejó abiertos **en su propio dossier**,
y su objeto es que **el artefacto que se audita contenga su propia certificación y sus propias
correcciones**, sin depender de leer commits posteriores.

> **Por qué existe este tag (el problema que cierra).** `v2.88.9-beta` se selló en `1e2985f5` y su CI salió
> **VERDE** (`36685888972`), pero la **cita** de esa corrida y una **corrección de exactitud** se hicieron
> **después**, en `main` (`58189fb1`, `d7d89708`). Efecto medido: **8 ficheros de `docs/` divergían** entre el
> tag y `main`, y en el tag su dossier decía **§9 `PENDIENTE DE CITAR`** y arrastraba el recuento **`59`** que
> ahora sabemos **inflado** (`50`). Auditar desde el tag significaba auditar un dossier **sin su certificación
> y con una cifra incorrecta**. Este sello lo consolida.

## Identidad del sello

| | |
| --- | --- |
| Fase | **Consolidación POST-SELLO** de `v2.88.9` (cita del CI + corrección del recuento) |
| Versión de paquete | `2.11.9-beta` → **`2.11.10-beta`** |
| Tag (lo crea el propietario) | **`v2.88.10-beta`** (anotado) |
| Base del diff | **`d7d89708`** (= `main`; el tag anterior apunta a `1e2985f5`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Contenido del sello | **SÓLO documentación**. **CERO `src`, CERO tests, CERO migraciones** |
| Relación con `v2.88.9` | **El código es byte a byte el mismo.** Lo que cambia es que el dossier ahora **se certifica y se corrige a sí mismo** |

## 1. Perímetro — medido, no declarado

`git diff --name-only v2.88.9-beta..HEAD` — **8 ficheros, todos `docs/`** (más el `package.json` de este
bump). **Ninguno** bajo `src/`, `tests/`, `alembic/` ni `*.py`/`*.ts`/`*.tsx`: la comprobación por patrón
sale **vacía**.

| Fichero | numstat | Qué aporta |
| --- | --- | --- |
| `CHANGELOG.md` | `+33/−1` | sección `[2.11.9-beta]` completa + corrección anotada en `[2.11.8-beta]` |
| `docs/engineering/evidence/v2.88.9/README.md` | `+54/−16` | **§9 cita el run `36685888972`** + **§3 la corrección `50`** |
| `docs/engineering/deuda-p3-...-2026-09-26.md` | `+21/−4` | `FLAKE-1`: sello de cierre, cita y corrección; `OBS-21` |
| `docs/engineering/PROJECT_STATE.md` · `engineering-index-...md` | `+1/−1` cada uno | resumen del sello y entrada `194` |
| `docs/engineering/evidence/v2.88.7/README.md` · `evidence/v2.88.8/README.md` · `reproducibilidad-...-v2.88.7-...md` | `+4/−1`, `+1/−1`, `+4/−1` | **anotación fechada** que remite a la corrección (su afirmación original **no se sustituye**: reescribir evidencia sellada invalidaría la cadena) |

**Sin migración. Sin umbrales.** `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B y cualquier umbral: intactos. Sin
backdating. **El motor, no tocado.**

## 2. Lo que este tag consolida (los dos commits POST-SELLO)

**(a) La cita de la certificación** (`58189fb1`). El tag `v2.88.9-beta` es **VERDE**: `Release tag CI`
**`36685888972`** (`ref=v2.88.9-beta`, HEAD `1e2985f5`, `07:48:56Z → 07:57:11Z`, **~8m15s**) → `SUCCESS`:
**10 jobs reales verdes + `certify` GREEN** (**11 verdes, 0 rojos**; `playwright` integrado `skipped` por
diseño). Es el **primer tag verde desde `v2.88.7-beta`**.

| Job | Previsto | Observado | |
| --- | --- | --- | --- |
| `python` | `3115 passed, 37 skipped` | **`3115 passed, 37 skipped, 6 warnings in 45.70s`** | **COINCIDE** |
| `lifecycle-pg` (**el que daba el rojo**) | VERDE | **`165 passed, 2 warnings in 100.62s`** con **0 skips** | **VERDE** |
| `replay-repro` | `success` | **`REPRODUCIDO`**; render LF `3 290 062` B / `A4DA036C…13CB`; **2ª corrida IDÉNTICA**; artefacto `11083079436` | **COINCIDE** |
| `certify` | GREEN | **`"status": "GREEN"`**, artefacto `11083039890` | **COINCIDE** |

Head de Alembic **confirmado en el log del propio job**: última línea `Running upgrade 045_adaptive_gate_state
-> 046_fill_reference_mid`.

**(b) La corrección de exactitud** (`d7d89708`). Ver §3.

## 3. La corrección: el recuento local era `50` corridas válidas, no `59`

**Qué se decía.** Los sellos `v2.88.7`, `v2.88.8` y `v2.88.9` citaban **`0` rojos en `59` corridas locales**
(`50` directas del test objetivo + `9` del comando exacto del job `lifecycle-pg`) y colgaban de ahí
`P ≈ 1,7 %`.

**Qué dicen los logs crudos de la terminal** (medido, no recordado): de las **tres** tandas que componían ese
`59`, **dos no ejecutaron nada**.

| Tanda | Lo que de verdad pasó | Información sobre `FLAKE-1` |
| --- | --- | --- |
| `50` corridas directas (dos políticas de selector) | Las **`50`** murieron en **`0,00–0,06 s`** con `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'` — el bug de `win32` ya conocido del repo (`SelectorEventLoop`, PR #39) —: **nunca llegaron al dominio** | **ninguna** |
| `50` corridas re-hechas con el *event loop* correcto | **`50 ok`, `TOTAL fallos: 0`** (`25` + `25`, una por política) | **la buena** |
| `8` iteraciones del comando exacto del job | Cada una duró **`0,1–0,6 s`** y su `resumen` salió **VACÍO**; una corrida real de esa batería tarda **~`100 s`** ⇒ **la suite no se ejecutó** | **ninguna** |

⇒ **La evidencia local válida es `50` corridas, `0` rojos**: con tasa **`6,68 %`**,
`P(0 en 50) = (1 − 0,0668)^50 ≈ **3,2 %**` (no `1,7 %`). El «`9` corridas del comando exacto» se sostiene,
por tanto, en **una** corrida —la de `165 passed, 0 skipped`—, no en nueve.

**Y hay algo MEJOR que la suerte para explicar ese `0`, que sí está en esos logs.** La asimetría que salió en
local fue la **INOFENSIVA**: las iteraciones `001`, `002` y `020` registran
`buy=filled(60.000000/60,chunks=3)` con `sell=partial(30.000000/60,chunks=1)` — **venta cortada / compra
completa**: vende `30` de los `60` que hay en cartera ⇒ **nunca sobrevende**. La orientación que hacía daño es
la **contraria** —**compra cortada / venta completa**— y **no salió en ninguna de las `50`**. El `0` deja de
ser «mala suerte» y pasa a ser un **sesgo del sorteo observable en los propios logs**.

**Cómo se ha tratado a los ficheros sellados.** Su afirmación original **no se sustituye** (reescribir
evidencia sellada invalidaría la cadena): cada uno recibe una **anotación fechada** que remite a esta
corrección. La corrección **canónica** vive en `§3` de [`../v2.88.9/README.md`](../v2.88.9/README.md).

## 4. Estado del hallazgo `FLAKE-1` — 🟢 **CERRADA** (era el FIXTURE, no el motor)

La cadena completa, por si la auditoría quiere recorrerla entera:

1. **`v2.88.8`** — el `RETRY` **mudo** deja de serlo (`logger.exception` con `execution_id`/`instrument_id`) y
   el rojo llega **con causa** en el run `36681305812`.
2. **`v2.88.9`** — con la traza, la causa se aísla: **el fixture**, no el motor. `draw_queue_noise`/`mid_cut`
   derivan de **`(seed, side, instrument_id)`** — de la **PATA**, no de la orden —, así que con el mismo seed
   la pata `buy` puede cortar antes que la `sell`: **`BUY = 30`** vs **`SELL = 30 + 14,1 + 15,9 = 60`** ⇒
   `sell#1` vacía la cartera y `sell#2`/`#3` piden contra `held = 0.0` ⇒ `ValueError` ⇒ `RETRY`. **El motor
   hizo lo correcto** (`fail-closed`). Medido: **`1336/20 000 = 6,68 %`** con el fixture viejo (patrón
   `(2,3)` en el `100 %`), **`0/20 000`** con el arreglo; y contraste contra **PG real** con el **mismo**
   `instrument_id`: **ROJO con `60`**, **VERDE con `30`**.
3. **`v2.88.9` certificado** — run `36685888972` **VERDE** (§2a).
4. **`v2.88.10`** — el dossier del objeto auditado **se certifica y se corrige a sí mismo** (§2 y §3).

**Nota de honestidad (re-arrastrada).** La tasa medida (`6,68 %`) explica el rojo de `36681305812` pero **no**
del todo la racha de **3 rojos en 4 corridas** (~`0,1 %` si fueran independientes): o fue mala suerte, o
alguna corrida previa tuvo un aporte **invisible** porque el `RETRY` era mudo hasta `v2.88.8`. Con el arreglo
**la clase entera desaparece** (`0/20 000`) y ya no hay agujero donde esconderse.

## 5. Punto de entrada para la auditoría externa

| Qué | Dónde |
| --- | --- |
| **Objeto auditado** | tag anotado **`v2.88.10-beta`** (este dossier es su evidencia) |
| Certificación | `Release tag CI` del tag → **cita en §6** |
| El hallazgo y su cierre | [`../v2.88.9/README.md`](../v2.88.9/README.md) · [`../../flake-1-causa-raiz-2026-09-30.md`](../../flake-1-causa-raiz-2026-09-30.md) |
| La instrumentación y la traza origen | [`../v2.88.8/README.md`](../v2.88.8/README.md) · [`../../evidencia-ci-tag-v2.88.8-2026-09-30.txt`](../../evidencia-ci-tag-v2.88.8-2026-09-30.txt) |
| Reproducibilidad del replay OOS | [`../v2.88.7/README.md`](../v2.88.7/README.md) · [`../../reproducibilidad-replay-oos-v2.88.7-2026-09-29.md`](../../reproducibilidad-replay-oos-v2.88.7-2026-09-29.md) |
| Deuda viva y hallazgos | [`../../deuda-p3-post-auditoria-v2.70-2026-09-26.md`](../../deuda-p3-post-auditoria-v2.70-2026-09-26.md) |

**Atajos útiles para el auditor:** el artefacto del replay se **regenera** en CI y su hash se **asserta**
(job `replay-repro`), así que no hay que creerse el `7D998E4D…` del sello: **se comprueba en cada corrida**.
Y el head de Alembic se lee **en el log del job**, no en una declaración.

## 6. Cita real del CI del tag

`Release tag CI` del tag **`v2.88.10-beta`** → run **`36688942921`** (`ref=refs/tags/v2.88.10-beta`, HEAD
`6c2b964c`, `08:18:57Z → 08:27:20Z`, **~8m23s**) → **`SUCCESS`**: **10 jobs reales verdes + `certify`
GREEN** (**11 verdes, 0 rojos**; `playwright (integrated E2E, opt-in)` `skipped` por diseño). Artefacto del
agregado `release-tag-ci-summary` (**ID `11084264360`**, `414` B) con `"status": "GREEN"`, `tag` =
`v2.88.10-beta`, `sha` = `6c2b964c`, `asOf` = `2026-09-30T08:27:17Z` y los **10** jobs a `success`.

**(a) El job `python`, verbatim:** `ruff All checks passed!` / `Contracts: 4 kept, 0 broken.` /
`Success: no issues found in 508 source files` / **`3115 passed, 37 skipped, 6 warnings in 50.41s`** ⇒
**ESPERADO `3115/37` = OBSERVADO `3115/37` → COINCIDE**. **Y no es una coincidencia:** la terna
`3115 passed / 37 skipped` es **byte-idéntica** a la del run `36685888972` del tag `v2.88.9-beta`, que es
exactamente lo que **debía** pasar —**cero deriva de código** entre los dos tags, medido en el runner y no
solo declarado en el diff de ficheros.

**(b) El job que daba el rojo, VERDE:** `lifecycle-pg` **`165 passed, 2 warnings in 97.61s`** (**0 skips**:
los gates *fail-if-skipped* se cumplieron) — otra vez **la misma terna** que en `v2.88.9-beta` —, más
`45 passed` account-isolation, `1` golden day, `1` crash/recovery, `3` concurrent AUTO, `2` hard-kill,
`2` crash injection y `1` multiprocess (`112,91 s`); el head de Alembic queda **confirmado en el propio
log** (última línea de migración `Running upgrade 045_adaptive_gate_state -> 046_fill_reference_mid`).

**(c) `replay-repro` (tercera certificación a nivel de tag):** `# sembrado 20 instrumentos, 25700 barras
D1`, `watch congelado: 20 símbolos`, render **LF** `3 290 062` B /
`A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB` (con el sello en CRLF: `3 393 187` B ·
*mismo contenido en LF `3 290 062`*), **`VEREDICTO 2ª corrida IDÉNTICA (el runner es determinista consigo
mismo)`** + **`DIGEST igual en las dos corridas`** y veredicto **`REPRODUCIDO (mismo CONTENIDO; el sello
está en CRLF y este fichero en LF)`**; artefacto subido `replay-oos-durable-v2.88.7.zip` (**ID
`11084548512`**, `285 944` B, SHA-256 del zip `467f6db4…6561`). Totalizadores de la corrida:
`{"decided":24500,"fills":752,"orders":210,"proposals":238,"vetoes":24303}` — **idénticos** a los del tag
`v2.88.9-beta`, como corresponde al mismo código.

**(d) En `main` (push `6c2b964c`) corrieron solo los workflows cuyo filtro de rutas casa** — `Gitleaks`
`36688939425`, `Optimize lab` `36688939490` y `Frontend CI` `36688939793`, los tres **`success`**—:
**`Python CI` NO corre aquí** (el commit de sello no toca ninguna ruta de Python: bump + `CHANGELOG` +
docs), así que su ausencia **no** es un hueco de CI.

**Lo que este verde NO añade (límite declarado).** Aporta **encaje de cuentas, ausencia de deriva y
reproducibilidad**, no una demostración nueva de nada: este sello **no toca código**, así que **no
re-certifica** el arreglo de `FLAKE-1` —eso ya lo hicieron la medida `0/20 000` y el contraste PG de
`v2.88.9`—. Su objeto era que **el artefacto auditado contuviera su certificación y su corrección**, y eso
lo cumple **dentro del tag** (§2 y §3).

## 7. Límites de esta evidencia y deudas que NO cierra

**Lo que este tag NO es.** **No** es un cambio de motor, ni de tests, ni una corrección de `FLAKE-1`: el
arreglo de `FLAKE-1` entró en `v2.88.9-beta` y **ya estaba certificado**. Este tag **sólo** hace que el
objeto auditado **contenga su certificación y sus correcciones**. Quien audite **motor** debe auditar el
**código de `v2.88.9-beta`/`v2.88.10-beta`**, que es el mismo.

**Deudas que siguen ABIERTAS (no las cierra este tag):**

* **`OBS-21`** (`🔴 ABIERTA`) — `retryable_on_ineffective=True` marca como **REINTENTABLE** un rechazo
  **PERMANENTE** del dominio (`No tienes suficientes acciones`): un motor real lo reintentaría
  **indefinidamente** sobre un hecho que no cambia. Es la **derivada** que dejó a la vista la traza de
  `v2.88.8`. **Es el único trabajo pendiente que tocaría MOTOR** y exige clasificar transitorio vs permanente
  y **mutarlo**.
* **`OBS-19`** (`🔴 ABIERTA`) — la deriva estructural de las listas de pytest de los workflows (se cerraron
  sus tres casos, **no** la causa).
* **Deuda re-acarreada del replay** — fijar `newline="\n"` en el escritor del replay OOS para que el mismo
  contenido tenga **un** hash en cualquier SO, con **re-medida de los cinco digests de sección**.
* **`OBS-3`/`OBS-4`** — el patrón de cita POST-TAG (esta misma sección lo ejemplifica).

**Lo que NO acredita:** ni `P3-2`/`P3-3`, ni el cierre de `OBS-15`/`OBS-16`/`OBS-13`/`OBS-11`/`H-4`/`OBS-9`/
`P3-5`/`OBS-5`.
