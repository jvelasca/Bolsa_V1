# Decisión · `window:freeze` / `TREE_MOVED` en un dispatch de rama · 2026-11-12

> **AsOf:** 2026-11-12
> **Padre:** [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md)
> **Objeto:** resolver documentalmente por qué el gate `window:freeze` sale rojo al medir una rama de
> slice y qué se puede hacer sin mover la ventana PAPER.
> **Naturaleza:** decisión **documental**. No modifica el pin, el gate, los workflows, `WINDOW_CONFIG`
> ni el árbol de trabajo. No crea tags, Releases ni commits.
> **Referencia medida:** rama `feat/f4-067-opinion-account-scope`, `HEAD` `bcdc4584`; pin `90d07886`;
> tag `v2.88.188-beta` (`53285f18`).

---

## 1 · Objeto y alcance

### 1.1 Qué se decide

El acta [`acta-f4-067-opinion-account-scope-2026-11-12.md`](./acta-f4-067-opinion-account-scope-2026-11-12.md)
§5 registra un bloqueo independiente: el job `shared` del `Release tag CI` falla en el paso
`Window freeze gate (pin == HEAD:apps/packages)` con `TREE_MOVED`, y el job `certify` arrastra ese fallo
por agregación. El slice que se certifica, en cambio, tiene verdes sus jobs de Python, frontend,
`lifecycle-pg`, `replay-repro`, `dr-verify` y `a7-gate` (§4 del acta).

La pregunta pendiente no es «¿cómo arreglo el slice?», sino:

1. **qué objeto debe comparar el gate** cuando el workflow no se dispara sobre un tag;
2. **qué significa “congelado”** en una corrida de rama;
3. **qué opciones no mueven la ventana PAPER** y cuáles sí, con sus riesgos y autorizaciones.

### 1.2 Qué queda dentro

- La lectura de los hashes del pin, `HEAD`, `main` y el tag `.188`.
- El catálogo de opciones, separando las que **no alteran la ventana PAPER** de las que sí.
- La deuda del `DEFAULT_TAG` del instrumento de medición.
- La recomendación y la autorización mínima de cada opción no segura.

### 1.3 Qué queda fuera

- Re-anclar el pin (`node scripts/window-pin.mjs --write`), aunque sea con `--dry-run`.
- Editar `scripts/window-pin.mjs`, `scripts/lib/window-forward.mjs`, `WINDOW_CONFIG` o
  `.github/workflows/release-tag-ci.yml`.
- Introducir `continue-on-error`, `WARN`, `skip` por rama o cualquier override por entorno.
- Tocar `apps/`, `packages/`, `PROJECT_STATE.md`, `CHANGELOG.md` o los planes de `.cursor/plans`.
- Crear o mover tags/Releases. Este documento **no** certifica PAPER ni autoriza operar con dinero real.

---

## 2 · Hechos medidos

### 2.1 El instrumento del gate

| Pieza | Dónde vive | Qué hace |
| --- | --- | --- |
| Script del gate | [`package.json:83`](../../package.json#L83) | `"window:freeze": "node scripts/window-pin.mjs --check"` |
| Paso de CI | [`.github/workflows/release-tag-ci.yml:61-67`](../../.github/workflows/release-tag-ci.yml#L61-L67) | El job `shared` ejecuta `pnpm window:freeze` después de `pnpm window:test` |
| Comparación | [`scripts/window-pin.mjs:60-69`](../../scripts/window-pin.mjs#L60-L69) | `freezeStatus` compara **solo** `appsHash` y `packagesHash`; `commit` es etiqueta informativa |
| Lectura del árbol | [`scripts/window-pin.mjs:112-115`](../../scripts/window-pin.mjs#L112-L115) | `git rev-parse HEAD:apps HEAD:packages` |
| Salida roja | [`scripts/window-pin.mjs:190-196`](../../scripts/window-pin.mjs#L190-L196) | `TREE_MOVED` + los tres campos y el comando de re-anclaje |

El gate dispara en `push` de tags `v*` y en `workflow_dispatch`
([`.github/workflows/release-tag-ci.yml:6-12`](../../.github/workflows/release-tag-ci.yml#L6-L12)).
No distingue el tipo de ref: siempre compara el `HEAD` del checkout con el pin.

El pin efectivo está en [`scripts/lib/window-forward.mjs:960-963`](../../scripts/lib/window-forward.mjs#L960-L963):

```js
export const WINDOW_CONFIG = Object.freeze({
  commit: '90d07886',
  appsHash: '5310f21dece29a4421acd16930856bec39e807ba',
  packagesHash: '7c31fca31e8825012d53bddc561ccde7501fd617',
```

El bloque de comentario inmediatamente anterior documenta el re-anclaje
([`scripts/lib/window-forward.mjs:952-959`](../../scripts/lib/window-forward.mjs#L952-L959)): fecha
`2026-11-11`, commit `90d07886`, motivo «sello 2.11.188-beta (066)». Ese `90d07886` es el commit del bump,
no el commit del tag.

### 2.2 Tabla de árboles medida

Comandos de lectura ejecutados el `2026-11-12` (sin escribir nada):

```powershell
git rev-parse HEAD:apps HEAD:packages
git rev-parse "ae6410bf:apps" "ae6410bf:packages"
git rev-parse "v2.88.188-beta^{}:apps" "v2.88.188-beta^{}:packages"
git rev-parse "v2.88.186-beta^{}:apps" "v2.88.186-beta^{}:packages"
```

| Ref | Commit | `appsHash` | `packagesHash` | Freeze contra el pin |
| --- | --- | --- | --- | --- |
| **Pin** (`WINDOW_CONFIG`) | `90d07886` (etiqueta) | `5310f21dece29a4421acd16930856bec39e807ba` | `7c31fca31e8825012d53bddc561ccde7501fd617` | — (referencia) |
| **`HEAD` de la rama** | `bcdc4584` | `c552a16ec77bbf6a65700b171a08bbd7f3d7a6e5` | `07647bd08598fd537e7a9bfc8ab57d2d9446f0d3` | **`TREE_MOVED`** (ambos campos) |
| **`main` local** | `ae6410bf` | `53100a32a6b49c9d5364797f19a600bea3ca008c` | `7c31fca31e8825012d53bddc561ccde7501fd617` | **`TREE_MOVED`** (solo `appsHash`) |
| **Tag `v2.88.188-beta`** | `53285f18` | `5310f21dece29a4421acd16930856bec39e807ba` | `7c31fca31e8825012d53bddc561ccde7501fd617` | **`freeze OK`** (coincide exactamente) |
| **Tag `v2.88.186-beta`** (`DEFAULT_TAG` del medidor) | `a5013f75` | `d39a04a7f544704d05033dc8ea8772ebb22272d0` | `2de53cda49ed847dbd5d4b9572c826c6368ddc52` | **`TREE_MOVED`** (ambos campos) |

Lectura de la tabla:

- El pin **no** coincide con la punta actual de `main`. Coincide con el **árbol del tag** `.188`.
  La etiqueta `commit` del pin (`90d07886`) y el commit del tag (`53285f18`) son distintos, pero
  `freezeStatus` no compara etiquetas: compara árboles
  ([`scripts/window-pin.mjs:60-69`](../../scripts/window-pin.mjs#L60-L69)).
- `main` ya no está verde **por hash**: `ae6410bf` movió cuatro goldens de cockpit y un test bajo
  `apps/web` (`git diff --stat "v2.88.188-beta^{}:apps" "ae6410bf:apps"`: 5 rutas, +37 líneas), de modo
  que `appsHash` pasó de `5310f21d…` a `53100a32…`. `packages` no se movió.
- El tag `.186` —el `DEFAULT_TAG` del medidor— **tampoco** coincide con el pin actual. Es deuda
  independiente, tratada en §2.5.

### 2.3 Por qué el rojo es de encuadre y no de calidad

El gate no mide la corrección del slice: mide **identidad de árbol**. Su contrato es explícito y
fail-closed: el runner declara `TREE_MOVED` y aborta antes de medir nada
([`scripts/lib/window-forward.mjs:43-44`](../../scripts/lib/window-forward.mjs#L43-L44)); la comprobación de
la ventana exige que el árbol del tag que se certifica sea el pin
([`scripts/lib/window-measurement-check.mjs:115-127`](../../scripts/lib/window-measurement-check.mjs#L115-L127)),
y su prueba fija que ese desajuste es **fallo duro** con código `TREE_MOVED`
([`scripts/lib/window-measurement-check.test.mjs:116-125`](../../scripts/lib/window-measurement-check.test.mjs#L116-L125)).

Con esa definición:

1. El pin es el árbol del último sello (`.188`).
2. Cualquier rama que toque `apps/` o `packages/` cambia al menos uno de los dos hashes.
3. El slice toca **ambos** árboles: sus 18 rutas incluyen guardias de head y pruebas bajo `apps/`, y
   migración, modelo, repositorio y pruebas bajo `packages/` (acta §2).
4. Por construcción, ese `HEAD` **no puede** casar con el pin. No es *drift* del pin: es el gate midiendo
   un objeto distinto del que el pin congela.

El propio log del run de rama `43169810570` lo separa con claridad: el subtest
`S1: TREE_MOVED es fallo duro e invalida la medicion` pasa, `python`, `frontend`, `lifecycle-pg`,
`replay-repro`, `dr-verify` y `a7-gate` pasan, y solo fallan `shared` (freeze) y `certify` (agregación).
El acta §4 documenta ese reparto. Un hash que no coincide no dice nada sobre la calidad de la migración
`067`; dice que el árbol medido no es el árbol pinneado.

Además, el rojo **no es específico del slice**: `main` (`ae6410bf`) tampoco casaría hoy por `appsHash`
(§2.2). Si el gate se ejecutara contra la punta de `main`, saldría igualmente 1. Eso confirma que el
problema es de encuadre del gate, no del cambio bajo revisión.

### 2.4 Qué sí certifica el tag `.188`

El tag `v2.88.188-beta` apunta al commit `53285f18` y su árbol es **exactamente** el pin:

| Comprobación | Resultado |
| --- | --- |
| `git rev-parse "v2.88.188-beta^{}:apps"` | `5310f21dece29a4421acd16930856bec39e807ba` |
| `git rev-parse "v2.88.188-beta^{}:packages"` | `7c31fca31e8825012d53bddc561ccde7501fd617` |
| Coincidencia con `WINDOW_CONFIG` | sí, en ambos campos |
| Run del tag | `42983709708`, verde, con `certify` en `success` (según [`auditoria-independiente-v2.88.188-beta-2026-11-11.md`](./auditoria-independiente-v2.88.188-beta-2026-11-11.md) §2) |

Por tanto, la certificación de la ventana se puede anclar al tag `.188` sin re-anclar nada. El run de la
rama no es el objeto que el pin congela.

### 2.5 Deuda específica: `DEFAULT_TAG` del medidor

El validador de medición tiene un valor por defecto que ya no representa el pin:

- [`scripts/window-measurement-check.mjs:49`](../../scripts/window-measurement-check.mjs#L49):
  `const DEFAULT_TAG = "v2.88.186-beta";`
- Ese tag mide `apps d39a04a7…` / `packages 2de53cda…` (§2.2), frente al pin
  `5310f21d…` / `7c31fca3…`.
- Una corrida **sin `--tag`** resolvería el árbol de `.186` y emitiría `S1.seal` en `FAIL` con
  `TREE_MOVED` duro ([`scripts/lib/window-measurement-check.mjs:115-127`](../../scripts/lib/window-measurement-check.mjs#L115-L127)),
  invalidando la medición aunque el material durable sea correcto.

Esto es **deuda independiente del gate** y debe resolverse **antes de cualquier re-anclaje**. Opciones
aditivas, sin tocar el pin: derivar el tag por defecto del `commit`/árbol del pin, exigir `--tag` de forma
explícita, o hacer que el valor por defecto sea el último tag cuyo árbol case con `WINDOW_CONFIG`, con una
prueba que falle si el `DEFAULT_TAG` deja de coincidir. Ninguna de esas opciones se implementa en este
documento: solo se declara la deuda y su precedencia.

---

## 3 · Catálogo de opciones

Convención: **segura** significa que **no altera la ventana PAPER** —no mueve `WINDOW_CONFIG`, no cambia
el árbol que se mide y no convierte `TREE_MOVED` en un aviso—. «Segura» no significa «sin revisión»: una
opción que toca el gate o un workflow sigue exigiendo su propia revisión y su propio commit, aunque no
mueva la ventana.

### 3.1 Opciones seguras

#### A. Declarar el rojo y certificar sobre el tag `.188`

**Qué es.** No tocar pin, gate ni workflows. Registrar el run de rama como **PARTIAL PASS** por encuadre
(ya hecho en el acta §4-§5) y apoyar la certificación del slice y de la ventana en el tag `.188`
(`53285f18`), cuyo árbol coincide con el pin y cuyo run de tag está verde.

**Por qué es segura.** No mueve la ventana PAPER: el árbol medido sigue siendo `5310f21d…` /
`7c31fca3…`. No cambia el significado de `TREE_MOVED`. No altera tags, Releases ni el pin.

**Riesgos.**

| Ámbito | Riesgo | Mitigación |
| --- | --- | --- |
| CI de la rama | El `Release tag CI` de la rama sigue rojo y `certify` sigue fallando por agregación | Se declara la causa en el acta §5 y en este documento; el rojo no se presenta como verde |
| Lectura humana | Alguien puede leer el rojo como fallo de calidad del slice | La tabla §2.2 y el reparto de jobs del acta §4 separan identidad de árbol y calidad |
| Tags/Releases | Ninguno: no se crea ni mueve ningún tag | — |
| PAPER | Ninguno: no se mueve el pin ni se mide otro árbol | — |

**Autorización.** Ninguna adicional para el acto documental. Si se quisiera **publicar** esa lectura como
certificación oficial, basta la firma del responsable del acta; no requiere autorización de PAPER porque
no se toca la ventana.

#### B. Instrumentación aditiva de auditoría

**Qué es.** Añadir, en un cambio separado, una herramienta **read-only** que enfrente el pin con un ref
arbitrario (`HEAD`, `main`, un tag) y publique los tres campos y el veredicto, sin escribir ni ejecutar
`--write`. También puede ser una lista de comprobación documental. No se conecta al gate ni a ningún
workflow.

**Por qué es segura.** Es aditiva. `scripts/` no participa del freeze
([`scripts/window-pin.mjs:8-12`](../../scripts/window-pin.mjs#L8-L12)); una herramienta que solo lee no
mueve el árbol ni cambia el pin. El gate sigue siendo el único que decide.

**Riesgos.**

| Ámbito | Riesgo | Mitigación |
| --- | --- | --- |
| Gate | Que alguien confunda el informe con el gate y lo use como sustituto | Nombre explícito de «auditoría, no gate»; no añadirlo a `release-tag-ci.yml` |
| PAPER | Ninguno mientras sea read-only y no se use `--write` | Prohibir escritura y testear que no modifica `WINDOW_CONFIG` |
| Mantenimiento | Duplicar lógica de `freezeStatus` | Reutilizar la función pura, no reimplementarla |

**Autorización.** Revisión de código normal. No requiere autorización de PAPER porque no mueve la ventana.
Si la herramienta se añadiera como paso de CI, dejaría de ser puramente aditiva y pasaría al régimen de la
opción C (revisión del gate).

#### C. Cambiar el sujeto de comparación del gate al ref que se certifica

**Qué es.** Hacer que el gate compare el pin contra el **ref certificado**, no contra el `HEAD` genérico:

- en `push` de tag, contra `github.ref` (el tag) o su commit;
- en `workflow_dispatch`, contra un input explícito `ref`/`tag`, obligatorio y fail-closed si falta;
- nunca contra un `HEAD` de rama que no se haya declarado como objeto de certificación.

El comportamiento en tag debe quedar **idéntico** al actual cuando `HEAD` es el tag.

**Por qué es segura para PAPER.** No mueve `WINDOW_CONFIG` ni cambia el árbol medido: solo alinea el
sujeto de la comparación con el objeto que se certifica. Es la corrección estructural del encuadre, no un
re-anclaje.

**Riesgos.**

| Ámbito | Riesgo | Mitigación |
| --- | --- | --- |
| Gate | Que un dispatch de rama pase comparando contra un tag viejo y se lea como certificación de la rama | Hacer el ref obligatorio, imprimirlo en el log y fallar si no se declara; distinguir «freeze del tag» de «auditoría de rama» |
| Tags/Releases | Si se implementa mal, un tag podría compararse contra otro ref | Test que fije el comportamiento actual en `push` de tag y que verifique `ref == tag` |
| Otros workflows | Cambia `.github/workflows/release-tag-ci.yml` o el script del gate | Revisión del dueño de release/CI; no tocar el runner ni el pin |
| PAPER | Ninguno si el pin no se mueve | Test que asegure que `WINDOW_CONFIG` no cambia en el cambio |

**Autorización.** No requiere autorización de PAPER (no mueve la ventana), pero **sí** revisión y aprobación
del dueño de release/CI, un commit dedicado y un run de tag verde que demuestre que el comportamiento en
tag no cambió. Es una opción segura respecto de PAPER, no una opción «sin gate».

### 3.2 Opciones no seguras

#### D. Re-anclar el pin

**Qué es.** Ejecutar `node scripts/window-pin.mjs --write` (o `pnpm window:pin`) para fijar el pin al árbol
de `HEAD`, de `main` o de otro ref.

**Por qué no es segura.** Mueve la ventana PAPER: cambia el árbol que el runner considera congelado y, con
él, qué código se mide y qué días se declaran `STALE`. Deja de ser una decisión documental y pasa a ser un
acto operativo sobre la medición.

**Riesgos.**

| Ámbito | Riesgo |
| --- | --- |
| PAPER | Los días posteriores se miden sobre un árbol no certificado por el sello `.188`; se rompe la comparabilidad con la ventana anterior; un árbol de rama puede acabar siendo el sujeto de la ventana sin haber pasado por un tag |
| Tags/Releases | El tag `.188` deja de casar con el pin: si se re-ejecuta su `window:freeze` o su medición, `S1.seal` sale `TREE_MOVED`. La Release publicada y el pin dejarían de describir el mismo objeto |
| Otros workflows | `window:freeze`, `window:preflight`, el runner (`run-day`/`watch`) y el medidor pasan a operar sobre otro árbol; cualquier evidencia que compare contra el pin anterior queda obsoleta |
| Instrumento | El `DEFAULT_TAG` `.186` sigue sin casar (§2.5): un re-anclaje sin arreglar esa deuda no deja el instrumento coherente |

**Autorización concreta que exigiría.** No se concede en este documento. Para hacerlo haría falta:

1. autorización escrita y nominal del **responsable de la ventana PAPER** (no del slice), con el árbol
   exacto, la fecha y el motivo;
2. un commit dedicado de re-anclaje, **posterior** al tag que se certifique, con el bloque `RE-ANCLAJE`
   que genera la herramienta y sin mezclar cambios funcionales;
3. la deuda del `DEFAULT_TAG` resuelta **antes** (§2.5);
4. un plan explícito de qué días se re-miden, cuáles quedan `STALE` y cómo se conserva la comparabilidad;
5. revisión del dueño de release y un run de tag verde sobre el nuevo pin;
6. constancia en un acta propia, no en este documento.

#### E. Relajar el gate (`continue-on-error`, `WARN` o `skip` por rama)

**Qué es.** Convertir el paso en no bloqueante (`continue-on-error: true`), degradar `TREE_MOVED` a aviso,
o saltarlo cuando el ref no sea un tag (`if: startsWith(github.ref, 'refs/tags/')`).

**Por qué no es segura.** Rompe el contrato fail-closed: `TREE_MOVED` deja de invalidar la medición y el
gate pasa a ser advisory. Un árbol distinto del pin podría llegar a `certify` en verde. Contradice
directamente la prueba que declara el fallo como duro
([`scripts/lib/window-measurement-check.test.mjs:116-125`](../../scripts/lib/window-measurement-check.test.mjs#L116-L125)).

**Riesgos.**

| Ámbito | Riesgo |
| --- | --- |
| PAPER | Una medición podría correr sobre un árbol no pinneado sin que nadie la invalide; el `freeze` deja de proteger la identidad del objeto medido |
| Tags/Releases | Un tag con árbol distinto del pin podría publicarse en verde; la Release certificaría un objeto que el pin no describe |
| Otros workflows | `certify` y cualquier consumidor del freeze heredan una garantía más débil; la semántica de `TREE_MOVED` deja de ser única |
| Documentación | Habría que reescribir el contrato §G.1 y la prueba S1; no es un parche local, es un cambio de política |

**Autorización concreta que exigiría.** No se concede en este documento. Exigiría:

1. decisión de política del **dueño de release** y revisión de calidad/seguridad;
2. un invariante sustituto explícito (qué sustituye al freeze y cómo se detecta el drift real);
3. actualización consciente del contrato y de la prueba `S1.seal`, no un `continue-on-error` aislado;
4. un run de tag verde que demuestre que el tag sigue protegido;
5. constancia en un acta de política. Aun con eso, la recomendación es **no** hacerlo.

#### F. Override por entorno `UNSAFE`

**Qué es.** Usar el override que ya existe en `windowConfig(env, { unsafeOverride: true })`
([`scripts/lib/window-forward.mjs:1013-1035`](../../scripts/lib/window-forward.mjs#L1013-L1035);
claves en [`scripts/lib/window-forward.mjs:1002-1008`](../../scripts/lib/window-forward.mjs#L1002-L1008))
o añadir una variable equivalente al gate para que `appsHash`/`packagesHash` se lean del entorno.

**Por qué no es segura.** Un bypass por entorno es invisible en el diff y puede activarse desde una shell,
una tarea o un runner sin cambiar el repositorio. El gate `window-pin.mjs --check` lee el pin del fichero y
el árbol de `git` ([`scripts/window-pin.mjs:112-115`](../../scripts/window-pin.mjs#L112-L115)); si se le
añadiera un override, `TREE_MOVED` dejaría de depender del árbol real. En el runner, el override ya existe
pero está marcado como `unsafe` precisamente para que no se confunda con el freeze.

**Riesgos.**

| Ámbito | Riesgo |
| --- | --- |
| PAPER | Medición sobre un árbol arbitrario sin rastro en el repositorio; el manifest puede declarar `configMode` no congelado, pero si se ignora, el resultado se lee como válido |
| Tags/Releases | Certificación falsa: el tag y el pin pueden no describir el árbol efectivamente medido |
| Otros workflows | Cada entorno puede producir un freeze distinto; se pierde la reproducibilidad y la auditoría por diff |
| Seguridad | Es un mecanismo de bypass, no una corrección: cualquiera con acceso al entorno puede alterar la identidad de la ventana |

**Autorización concreta que exigiría.** No se concede en este documento. Solo tendría cabida, si acaso, en
un **sandbox** con fines de diagnóstico y con:

1. autorización del **responsable de PAPER** y de **seguridad/operaciones**;
2. un modelo de amenaza y un registro de auditoría de quién activó el override y con qué valores;
3. la prohibición explícita de usarlo en el gate de release o en una certificación;
4. un manifest que declare `configMode` no congelado y un veredicto que **no** pueda ser `GREEN`;
5. reversión inmediata y constancia en un acta de incidente. Para el gate de release, la recomendación es
   **nunca**.

### 3.3 Matriz de decisión

| Opción | ¿Mueve PAPER? | ¿Deja el gate intacto? | ¿Resuelve el rojo de la rama? | ¿Es aceptable ahora? |
| --- | --- | --- | --- | --- |
| A. Declarar el rojo y certificar sobre el tag | No | Sí | No lo oculta: lo declara | **Sí, como decisión vigente** |
| B. Instrumentación aditiva | No | Sí (si no se cablea al CI) | No; solo lo hace legible | Sí, opcional y en cambio aparte |
| C. Cambiar el sujeto del gate al ref certificado | No | Cambia el gate, no el pin | Sí, si se implementa con ref explícito | Sí, como corrección estructural con revisión propia |
| D. Re-anclar el pin | **Sí** | Cambia el pin | Sí, pero por la vía que mueve la ventana | No sin autorización de PAPER |
| E. Relajar el gate | No | **No** | Sí, pero destruye el fail-closed | No recomendado |
| F. Override `UNSAFE` | **Sí** (de facto) | **No** | Sí, de forma invisible | No; solo sandbox con autorización |

---

## 4 · Recomendación razonada

### 4.1 Decisión recomendada

**Se adopta A como decisión vigente**, con B como mejora opcional y C como corrección estructural futura.
No se adoptan D, E ni F.

1. **El rojo se declara, no se corrige en este slice.** El run de rama `43169810570` es un `PARTIAL PASS`
   por encuadre. La certificación del slice y de la ventana se apoya en el tag `.188` (`53285f18`), cuyo
   árbol coincide exactamente con el pin (§2.4), no en el `HEAD` de la rama.
2. **No se re-ancla el pin.** Re-anclar movería la ventana PAPER a un árbol de rama no certificado y
   rompería la relación entre el tag `.188` y el pin (§3.2-D). No es un arreglo del encuadre: es otro
   encuadre, con coste operativo.
3. **No se relaja el gate.** `TREE_MOVED` es un fallo duro por contrato y por prueba. Convertirlo en
   `WARN`/`skip` haría que el verde dejara de significar «árbol congelado» (§3.2-E).
4. **No se usa un override `UNSAFE`.** Es un bypass invisible en el diff; no corrige el encuadre, lo
   esconde (§3.2-F).
5. **Si hace falta verde en la rama, la vía es C**, no D: comparar contra el ref que se certifica, con el
   ref explícito y fail-closed si falta. C no mueve la ventana y conserva el comportamiento en tags.

### 4.2 Condiciones de la recomendación

- **Precedencia de la deuda:** el `DEFAULT_TAG` `.186` (§2.5) debe resolverse **antes de cualquier
  re-anclaje**. Si alguien decidiera D en el futuro, el instrumento seguiría apuntando a un tag que no
  casa con el pin y emitiría `TREE_MOVED` por defecto.
- **C no es un cambio de este acto:** requiere commit propio, revisión del dueño de release/CI y un run
  de tag que demuestre que el comportamiento en `push` de tag no cambió.
- **La certificación PAPER sigue anclada al tag:** ninguna opción de este documento convierte el run de
  rama en una certificación de la ventana. Solo el tag `.188` (o un tag futuro con su propio run verde y
  su propio pin) puede hacerlo.
- **AUTORIZACIÓN:** este documento **no** autoriza D, E ni F. La recomendación es explícitamente no
  ejecutarlas. Si el responsable de PAPER quisiera D, la secuencia de autorización de §3.2-D es la
  mínima exigible.

### 4.3 Qué queda resuelto

| Pregunta | Respuesta documentada |
| --- | --- |
| ¿El pin está mal? | No. Coincide con el árbol del tag `.188`; la etiqueta `commit` es informativa |
| ¿El slice rompió el freeze? | No por calidad: cualquier rama que toque `apps/`/`packages/` falla por construcción |
| ¿`main` está verde? | No por hash: `ae6410bf` movió `appsHash`; `packages` sigue igual |
| ¿Se re-ancla? | No en este acto. Requiere autorización de PAPER y la deuda del `DEFAULT_TAG` resuelta |
| ¿Se relaja el gate? | No. `TREE_MOVED` sigue siendo fallo duro |
| ¿Cómo se certifica el slice? | Sobre el tag `.188` (`53285f18`), no sobre el `HEAD` de la rama |
| ¿Qué haría falta para un verde de rama? | Opción C, con revisión propia y ref explícito |

---

## 5 · Verificación reproducible

```powershell
# 1) El pin y el arbol de HEAD (debe salir 1 con TREE_MOVED; es lo esperado)
node scripts/window-pin.mjs --check

# 2) Arboles medidos (solo lectura)
git rev-parse HEAD:apps HEAD:packages
git rev-parse "ae6410bf:apps" "ae6410bf:packages"
git rev-parse "v2.88.188-beta^{}:apps" "v2.88.188-beta^{}:packages"

# 3) El arbol de main frente al tag (5 rutas bajo apps/)
git diff --stat "v2.88.188-beta^{}:apps" "ae6410bf:apps"

# 4) Que este acto no toca el arbol ni el indice
git diff --stat
git diff --cached --stat
```

Resultado esperado de (1): exit `1`, `[window-pin] TREE_MOVED`, `appsHash` `c552a16e…` frente a
`5310f21d…` y `packagesHash` `07647bd0…` frente a `7c31fca3…`. **No se corrige**: es la evidencia de que
el pin sigue intacto y de que el `HEAD` de la rama no es el árbol del sello.

---

## 6 · Referencias

| Tema | Referencia |
| --- | --- |
| Gate en CI | [`.github/workflows/release-tag-ci.yml:61-67`](../../.github/workflows/release-tag-ci.yml#L61-L67) |
| Disparadores del workflow | [`.github/workflows/release-tag-ci.yml:6-12`](../../.github/workflows/release-tag-ci.yml#L6-L12) |
| Script `window:freeze` | [`package.json:83`](../../package.json#L83) |
| Comparación del freeze | [`scripts/window-pin.mjs:60-69`](../../scripts/window-pin.mjs#L60-L69) |
| Lectura de `HEAD:apps`/`HEAD:packages` | [`scripts/window-pin.mjs:112-115`](../../scripts/window-pin.mjs#L112-L115) |
| Salida `TREE_MOVED` | [`scripts/window-pin.mjs:190-196`](../../scripts/window-pin.mjs#L190-L196) |
| Pin y bloque de re-anclaje | [`scripts/lib/window-forward.mjs:952-963`](../../scripts/lib/window-forward.mjs#L952-L963) |
| Contrato fail-closed del runner | [`scripts/lib/window-forward.mjs:43-44`](../../scripts/lib/window-forward.mjs#L43-L44) |
| Override `unsafe` | [`scripts/lib/window-forward.mjs:1002-1035`](../../scripts/lib/window-forward.mjs#L1002-L1035) |
| `DEFAULT_TAG` del medidor | [`scripts/window-measurement-check.mjs:49`](../../scripts/window-measurement-check.mjs#L49) |
| `S1.seal` duro | [`scripts/lib/window-measurement-check.mjs:115-127`](../../scripts/lib/window-measurement-check.mjs#L115-L127) |
| Prueba de `TREE_MOVED` | [`scripts/lib/window-measurement-check.test.mjs:116-125`](../../scripts/lib/window-measurement-check.test.mjs#L116-L125) |
| Acta del slice | [`acta-f4-067-opinion-account-scope-2026-11-12.md`](./acta-f4-067-opinion-account-scope-2026-11-12.md) |
| Auditoría del tag `.188` | [`auditoria-independiente-v2.88.188-beta-2026-11-11.md`](./auditoria-independiente-v2.88.188-beta-2026-11-11.md) |
