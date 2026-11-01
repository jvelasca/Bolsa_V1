# Dictamen de aceptación — `v2.88.176-beta` (Overview simplificada)

> **AsOf:** 2026-11-01 · **Objeto:** tag anotado **`v2.88.176-beta`** (objeto `cbade319…`) → commit
> **`081cb4c0`** sobre `fix/059-060-proveedores`, árbol del sello `2.11.176-beta`.
> **Naturaleza:** registro de aceptación **POST-TAG**. Acepta el **tag ya publicado**, no lo crea: el acto de
> aceptar vive en un commit posterior al objeto aceptado.
> **Veredicto:** aceptación **favorable** del sello, con **dos límites abiertos** (`L-OVW-1`, `L-OVW-2`) que se
> declaran y no se cierran aquí.

---

## 0. Qué añade este documento

El sello tiene evidencia propia ([`evidence/v2.88.176/README.md`](./evidence/v2.88.176/README.md)) y tres
registros de la cadena previa: el [dictamen de Overview](./dictamen-overview-simplificada-2026-11-01.md), su
[aceptación POST-COMMIT](./dictamen-commit-62665ff7-2026-11-01.md) y el
[seguimiento](./seguimiento-ui-overview-2026-11-01.md). Lo que faltaba es el **acto de aceptación del tag**:
qué se da por bueno del run que sella, contra qué se ancla y **qué no se acepta como cerrado** al aceptarlo.

Este documento **no re-mide** las suites en local: lee el `Release tag CI` del tag y lo contrasta con el
expediente. Donde el CI no mide algo, lo dice en vez de inferirlo del verde.

---

## 1. Identidad y CI del objeto aceptado

| Elemento | Valor |
| --- | --- |
| Tag | **`v2.88.176-beta`** (anotado, objeto `cbade319055934123da0e5346b29133ddaac24b5`) |
| Commit | **`081cb4c0`** (`081cb4c0555642a37346c7e9a1dcd5abc883bef5`), `docs(evidence): evidencia del sello v2.88.176-beta` |
| Rama | `fix/059-060-proveedores` (remoto en `081cb4c0`) |
| Árbol | `package.json` en `2.11.176-beta` · pin PAPER `apps` `e080cca1…` / `packages` `7091cc8d…` |
| Run del sello | `Release tag CI` [`41360000070`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41360000070) |
| Ventana del run | `2026-11-01T23:01:15Z` → `23:15:11Z` (**13m56s**) |
| Resultado | **GREEN**: **12 jobs `success`** + `certify` `success`; **1** `skipped` (`playwright (integrated E2E, opt-in)`, que no certifica) |
| Artefacto | `release-tag-ci-summary` ⇒ `status: GREEN`, `asOf 2026-11-01T23:15:08Z`, los 12 jobs en `success` |

## 2. Qué se acepta

### 2.1 El resultado del sello

| Comprobación | Medido en el CI del tag | Dónde |
| --- | --- | --- |
| `Window freeze gate` (pin == `HEAD:apps/packages`) | **`freeze OK`** sobre `081cb4c0` | job `shared`, step 10 |
| `Test web` | **2 686 passed** (357 ficheros), `172,16 s` | job `frontend`, step 9 |
| `Contract check (no gen)` | **success** (sin regeneración) | job `frontend`, step 10 |
| axe integrado con API real | **32 passed** (`3,0m`), con `/overview` @desktop y @móvil 390×844 en **0 `critical`/`serious` + heading-order** | job `playwright (integrated axe)`, step 16 |
| `replay-repro` | **`REPRODUCIDO`**: `sha256 E9B7376B…7F5625`, `3 383 461` bytes de contenido (el sello está en CRLF, `3 488 758`) | job `replay-repro`, step 10 |
| `a7-gate` | **success** con `LIVE_A7_PG_REQUIRED=1` y BD dedicada `bolsa_v1_a7` | job `a7-gate`, step 8 |

El digest del replay es **el mismo** que el del sello `.175` (`E9B7376B…`): eso es lo que convierte
«`Δ motor = 0`» en una afirmación **medida por el CI** y no en una lectura del diff.

### 2.2 La separación de los tres niveles de aceptación

Se acepta que la cadena distingue **tres** objetos y no los confunde:

| Nivel | Objeto | Qué certifica |
| --- | --- | --- |
| Técnico | `62665ff7` | la implementación y su registro de aceptación, medidos sobre el árbol (16 ficheros, `+1006/−460`) |
| Documental del commit | `23c9c689` | que **ese** commit es lo que dice ser: identidad, integridad y verificaciones, sin re-medir el objeto |
| Del sello | `v2.88.176-beta` → `081cb4c0` | que el **tag** pasó el `Release tag CI`, con el pin re-anclado antes |

El primer nivel no se publica; el tercero sí. Que el segundo exista es lo que impide que un commit se
certifique a sí mismo, y que el tercero esté separado es lo que impide que un verde local se lea como sello.

### 2.3 La cadena del pin, con la predicción cumplida

| Commit | `appsHash` | `packagesHash` |
| --- | --- | --- |
| `23c9c689` (docs-only) | `ac05717e536f64820f64b8d2b5503eed6a6d70b2` | `7091cc8d05624249a35377d7e541773c1313b889` |
| `2c7d8b11` (bump) | `e080cca169533e73e4dcbc21ea7ab5031e75428f` | `7091cc8d05624249a35377d7e541773c1313b889` |
| `27e918c9` (re-anclaje) | igual | igual |
| `081cb4c0` (evidencia, docs-only) | igual | igual |

Se acepta que **solo** `appsHash` se movió con el bump y **solo** en el commit del bump: el commit
documental ni lo movió ni necesitó re-anclar. Es exactamente lo que el
[POST-COMMIT](./dictamen-commit-62665ff7-2026-11-01.md) §3 predijo.

## 3. Alcance exacto de la evidencia

* **2 686 passed** en el `frontend` del tag acredita la suite web completa **de este árbol**, no «la aplicación
  no tiene defectos». El número coincide con el que el expediente citaba del árbol de trabajo: la coincidencia
  se registra, no se usa como herencia.
* **32 passed** de axe integrado acredita 0 `critical`/`serious` en esas rutas con datos sembrados por el CI. No
  es el barrido de `35/35` rutas tocadas que cita el expediente, ni una auditoría de accesibilidad completa.
* **`REPRODUCIDO`** acredita que el artefacto del replay se regenera byte a byte desde el fixture con el mismo
  script. Acredita `Δ motor = 0`; no acredita rentabilidad.
* **`freeze OK`** acredita que el pin casa con `HEAD:apps`/`HEAD:packages` del commit del tag. No acredita que
  la ventana PAPER haya certificado: el estado de la ventana es **`INCONCLUSIVE`** y este sello no lo cambia.

## 4. Límites expresos de la aceptación

### 4.1 `L-OVW-1` — el estado de sincronización dejó de mostrarse en Overview

**Estado:** límite **nombrado y aceptado**, **abierto**. No es deuda silenciosa ni un cierre.

La información vive en Configuración → «Automatización: velas y servidores» (`SyncSettingsPanel` +
`MarketProvidersStatusCard`, `case "other"` de `platform-config-dialog.tsx`), alcanzable desde la barra
superior y la paleta de comandos. Se reabre si esa superficie pierde la cola o el estado por proveedor, o si
deja de ser alcanzable: entonces el estado de sync no estaría en ninguna superficie.

### 4.2 `L-OVW-2` — «otras cuentas activas» cubierto **solo** por test

**Estado:** límite **nombrado y aceptado**, **abierto**. El caso unitario
`señala cuántas otras cuentas activas hay` fija texto y enlace con dos cuentas; nada mide el
comportamiento en navegador con dos cuentas activas (texto, enlace, cambio de cuenta y repintado de métricas y
movimientos a 390×740). Hasta esa prueba, se cita por su identificador y **no** se lee como verificado.

### 4.3 Lo demás que este dictamen no certifica

| No certifica | Por qué |
| --- | --- |
| **Que `596 px` valga con cualquier contenido** | se midió con la cuenta demo canónica (2 asientos); con nombres largos, muchas posiciones o ledger lleno no se midió |
| **La convivencia de `chaos/live_a7` con el stack sobre `bolsa_v1` compartida** | `L-175-1` sigue vigente: ahí la guarda diagnostica y salta a propósito; el criterio de certificación de A7 es el job `a7-gate` con BD dedicada |
| **Rentabilidad u operativa** | AUTO **OFF**; PAPER **`INCONCLUSIVE`**; un sello de producto no añade evidencia de resultados |
| **Que un `GREEN` del artefacto sea el sello** | el artefacto lo escribe `certify`, que no se ejecuta si el gate de fallo hace `exit 1`: el `GREEN` prueba que los jobs obligatorios fueron `success` |

## 5. Lo verificado aquí y lo que no

**Contrastado en este acto (2026-11-01, POST-TAG):** que el run `41360000070` terminó en `success` con 12 jobs
`success` + `certify` y un único `skipped` opt-in; que el step `Window freeze gate` del job `shared` da
`freeze OK`; que `frontend` mide **2 686 passed** en 357 ficheros y `Contract check (no gen)` `success`; que el
`axe` integrado da **32 passed** con `/overview` @desktop y @móvil en 0 `critical`/`serious`; que `replay-repro`
dictamina `REPRODUCIDO` con digest **idéntico** al de `.175`; que el artefacto resumen dice `status: GREEN`,
`asOf 2026-11-01T23:15:08Z`, `sha 081cb4c0`.

**No verificado aquí:** no se re-ejecutaron las suites en local sobre el árbol del tag; no se repitió la
medición de alturas en navegador; no se ejecutó la prueba con dos cuentas activas de `L-OVW-2`; no se revisó
GitHub de forma independiente más allá del run y su artefacto.

## 6. Falsabilidad de esta aceptación

| # | Afirmación aceptada | Cómo se rompe |
| --- | --- | --- |
| 1 | El objeto aceptado es `v2.88.176-beta` → `081cb4c0` | mover o borrar el tag ⇒ esta aceptación deja de apuntar a nada |
| 2 | El run del sello es **GREEN** con 12 jobs obligatorios `success` | reaparecer un job obligatorio en `failure` o `skipped` ⇒ el artefacto no diría `GREEN` |
| 3 | El pin casa con el árbol del tag | cambiar `apps/` o `packages/` en un commit posterior al re-anclaje ⇒ `TREE_MOVED` y `Window freeze gate` rojo |
| 4 | `Δ motor = 0` medido por el CI | cambiar el digest de `replay-repro` respecto de `E9B7376B…` ⇒ el motor se movió |
| 5 | La suite web del tag es 2 686 | cambiar el número en `frontend` ⇒ el árbol difiere del que cita el expediente |
| 6 | `L-OVW-1` y `L-OVW-2` siguen abiertos | declararlos cerrados sin la comprobación de §4.1/§4.2 ⇒ la aceptación dice más de lo que midió |
| 7 | El commit documental no mueve el pin | cambiar `appsHash` en `081cb4c0` ⇒ se coló contenido fuera de `docs/` |
| 8 | El sello no reescribe la cadena previa | reescribir `62665ff7` o `23c9c689` ⇒ cambian sus SHA y sus aceptaciones dejan de apuntar a nada |

## 7. Alcance de este registro (no-cambios)

* **No** modifica código, tests, evidencia cruda, contrato, migraciones ni versión.
* **No** enmienda `62665ff7`, `23c9c689`, `2c7d8b11`, `27e918c9` ni `081cb4c0`: les añade un descendiente.
* **No** mueve el tag: lo acepta tal como se publicó. Si el tag se moviera, este dictamen quedaría inválido.
* **No** re-ancla el pin ni lanza CI: cita el run del tag.
* **No** cierra `L-OVW-1` ni `L-OVW-2`.

## 8. Cierre

Se acepta `v2.88.176-beta` como **sello publicado** de la simplificación de Overview: la pantalla de entrada
responde a una sola pregunta, con **596 px** sin scroll a 1440×900 (`524 + 72`), cuatro accesos a cuatro destinos,
sin jerga de implementación en el primer nivel y sin código muerto, sobre un árbol con **2 686** pruebas web
verdes, `Contract check` sin regeneración, axe integrado **32/32** incluyendo `/overview` en desktop y móvil, y
un replay **`REPRODUCIDO`** con digest idéntico al sello anterior.

Se acepta **con** `L-OVW-1` y `L-OVW-2` abiertos: el estado de sync cambió de superficie y el caso de varias
cuentas activas está cubierto por test, no por navegador. Ninguno de los dos impide aceptar la simplificación;
ambos impiden llamarla «completamente verificada».

Lo aceptado son los **escenarios y contratos cubiertos** por el run citado. No es una garantía de que Overview
no pueda degradarse: para eso están los ocho puntos del dictamen de Overview y los de §6 de este documento, que
sí se rompen si algo de esto vuelve.
