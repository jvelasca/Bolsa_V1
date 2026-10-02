# Entrega a auditoría externa MIA — `v2.88.22-beta` (correcciones semánticas de `M1` en el monitor AUTO: `SETTLEMENT`, «última decisión», precio real y concurrencia, 2026-10-02)

> **Objeto auditado:** tag anotado **`v2.88.22-beta`** → **`e904ad3f`** (tag object **`0ca503c0`**), versión **`2.11.22-beta`**,
> base del diff **`v2.88.21.1-beta`** → **`be388124`**, Alembic head **`046_fill_reference_mid`** (**sin migración**).
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Evidencia cruda:** [`evidence/v2.88.22/`](./evidence/v2.88.22/README.md) ·
> [`evidence/v2.88.21.1/`](./evidence/v2.88.21.1/README.md) · [`evidence/v2.88.21/`](./evidence/v2.88.21/README.md) ·
> [`evidence/v2.88.20/`](./evidence/v2.88.20/README.md).

---

## 0. Qué es y qué NO es esta entrega

**Es** la auditoría de una corrección de **honestidad semántica** del monitor AUTO (`M1`): el monitor
deja de afirmar cosas que no puede demostrar (un `SETTLEMENT` derivado de un ciclo cerrado, un
heartbeat presentado como «última decisión», un claim perdido contado como carrera). **`Δ motor = 0`**:
`auto_simulation_worker.py` **NO aparece en el diff**; no cambia ninguna decisión de inversión.

**NO es** una auditoría de un incremento que añada **productores durables**. Esta versión **no** crea
las fuentes que faltan: `SETTLEMENT` y `ENTRY_ORDER` siguen **`NO MEDIDO`**. Lo que se certifica es que
el monitor **declara honestamente** lo que mide y **no sintetiza** lo que no.

**Trampa nº 1 que debe evitarse:** leer «`SETTLEMENT` corregido» como «`SETTLEMENT` cerrado». Aquí se
corrige **cómo se declara** (`unknown` salvo hecho durable explícito), **no** que ya exista el productor
durable que lo alimenta. Es exactamente lo que la auditoría previa pedía: dejar de afirmarlo.

**Trampa nº 2:** en sellos anteriores «`Δ = 0`» significaba «el motor se tocó pero el resultado
observable es idéntico». **Aquí no**: el motor está **literalmente ausente del diff** (`Δ motor = 0`
estricto), y la prueba es el listado de ficheros, no una narración.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado está **dentro del tag**; esta **entrega** viaja
> **POST-TAG en `main`**, porque el tag es inmutable y se selló antes de escribirse su cita. Clona
> `main` para **leer**, y haz `checkout` del tag para **verificar**. Dentro del tag **no** encontrarás
> los `docs/engineering/*auditor*`: es diseño, no un fichero perdido.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
# (A) leer la entrega  -> rama main (default tras el clon)
# (B) verificar el producto -> el tag
git checkout v2.88.22-beta
git log --oneline -1                       # e904ad3f (sello v2.88.22)
```

| Verdad | Valor |
| --- | --- |
| Tag anotado | `v2.88.22-beta` (tag object `0ca503c0`) → `e904ad3f` |
| Versión (`package.json`) | `2.11.22-beta` |
| Base del diff | `v2.88.21.1-beta` → `be388124` |
| Alembic head | `046_fill_reference_mid` — **SIN migración** |
| `src` de producto | **13 ficheros, `+523 / −113`** (`packages/` + `apps/`) |
| Delta tag-a-tag total | **19 ficheros, `+651 / −123`** (incluye docs) |
| `Δ motor` | **`auto_simulation_worker.py` NO está en el diff** |
| Commit siguiente (POST-TAG, `main`) | `bb6e453e` — cita del CI (docs-only, no es el sello) |
| CI del tag | `Release tag CI` run **`36972156676`** — **TODO VERDE** |

**Cómo recalcularlo en el clon (sin creerme nada):**

```bash
git diff --stat v2.88.21.1-beta v2.88.22-beta                       # 19 ficheros, +651/-123
git diff --numstat v2.88.21.1-beta v2.88.22-beta -- packages apps    # 13 ficheros, +523/-113
git diff --name-only v2.88.21.1-beta v2.88.22-beta -- "*auto_simulation_worker*"   # VACÍO = Δ motor 0
git diff --name-only v2.88.21.1-beta v2.88.22-beta -- "*alembic*" "*versions*"     # VACÍO = sin migración
```

---

## 2. Firma de estado verificada **antes** de auditar

Corrida **por el auditor en su clon**, no heredada:

| Comprobación | Esperado |
| --- | --- |
| `git cat-file -t v2.88.22-beta` | `tag` (anotado) |
| `git rev-list -n 1 v2.88.22-beta` | `e904ad3f` |
| Árbol limpio en el checkout del tag | sí |
| Migración | **ninguna** (head `046_fill_reference_mid`) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS` | intactos |
| `auto_simulation_worker.py` en el diff | **ausente** |
| CI del tag | **11 `success`** + `playwright` integrado `skipped` por diseño (opt-in); `certify` `success` |

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **`SETTLEMENT` no queda «cerrado»: queda «honesto».** La costura
   `build_operational_monitor(..., settlements=...)` **consume** un hecho durable, pero
   `read_operational_monitor` **todavía no lee ninguna fuente** (no existe). Sin hecho ⇒ `unknown` +
   `settlement_not_durable`, y **sin** facts de PnL (el PnL vive en `CYCLE_CLOSED`). Es el estado
   **correcto** de una costura declarada, no un olvido.
2. **`lastDecisionAt = NO MEDIDO` con `AUTO_OPERATIONAL_AUDIT` OFF no es un `0`.** Es «no medido». El
   campo que **sí** se llena en su lugar es `lastHeartbeatAt` (latido del motor). Si ves `nextDecisionAt
   = null`, es correcto: sólo se deriva de una decisión **medida**.
3. **«Precio real habilitado» (SÍ/NO) es CONFIGURACIÓN, no la fuente por operación.** La configuración
   (`AUTO_ENGINE_SIM_REAL_PRICE`) **no** prueba qué fuente usó una operación concreta; el campo por
   ciclo/fill (`XTB`/`MARKET_CLOSE`/`REPLAY`/`SYNTHETIC`) está **declarado pendiente y NO se inventa**.
   Un auditor que lea `SÍ` como «AUTO opera con precio real» está leyendo lo que la corrección
   precisamente impide.
4. **`raceConflicts` sólo cuenta carreras DECLARADAS por el productor** (`payload.conflict is True`).
   `claimed = False` **no** implica carrera: puede ser `invalid`/`expired`/`already_released`/
   `wrong_state`. Por eso se separan `claimAttempts` / `successfulClaims` / `lostClaims` / `raceConflicts`.
5. **`ENTRY_ORDER`/`ORDER` sigue `unknown` (`entry_order_not_durable`).** Sin fuente durable de la orden
   de entrada, no se falsea. No es una regresión: es la regla de la casa (`NO HAY EVIDENCIA → UNKNOWN`).
6. **El delta `src` es de presentación, no de motor.** Toca read model + contrato + UI. No hay ninguna
   escritura nueva del motor: el job `replay-repro` sale `REPRODUCIDO` por eso, no por casualidad.
7. **Dentro del tag, la evidencia y esta entrega son POST-TAG (en `main`).** El tag sólo lleva el
   producto + la evidencia del sello. Los `*auditor*` y esta entrega viven en `main`.
8. **La estabilización del test PG es `test-only`.** `_seed_fill` usa `execution_id` determinista
   (`...-buy`/`...-sell`) porque el store sella `created_at` con `_now()` y `cycles_from_fills` empareja
   por `(created_at, execution_id)`; con ids aleatorios una venta podía leerse antes de su compra y
   descartar el ciclo (**flaky pre-existente**, ~50 %). `Δ producto = 0`.

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

**P1.** La regla nueva de `SETTLEMENT`: ¿existe **algún** camino por el que un ciclo cerrado vuelva a
producir `reached` (p. ej. una ruta que rellene `settlements` desde `cycles_from_fills`, o un default
que se cuele cuando la costura no se inyecta)? ¿Es *fail-closed* de verdad?

**P2.** La separación `lastHeartbeatAt` / `lastDecisionAt`: ¿queda **algún** punto del DTO, del read
model o de la UI que siga publicando un latido como «decisión»? ¿`nextDecisionAt` sólo se deriva de una
decisión medida en **todos** los caminos?

**P3.** El productor de claim: ¿**todos** los caminos que pueden perder un claim declaran
`conflict`/`conflictReason` cuando de verdad hay conflicto? ¿Hay alguna ruta del productor que escriba
el claim sin la marca, de forma que una carrera real quede como `lostClaims` en vez de `raceConflicts`?

**P4.** Honestidad de medición en la UI: ¿hay algún sitio donde `NO MEDIDO` se degrade a `0` o a `—`
silencioso? ¿La etiqueta «Precio real habilitado» es imposible de leer como fuente usada?

**P5.** Contrato: `openapi.json` + `schema.d.ts` ¿coinciden con el read model sin drift residual?
(`contract:check` en verde es necesario pero ¿es **suficiente**? ¿hay campos nuevos sin consumidor o
viceversa?)

**P6.** Como este sello **no** añade productores durables para `SIGNAL`/`TOP-N`/`RISK`/`ENTRY_ORDER`:
¿el monitor sigue afirmando algo que no puede demostrar en esas áreas, o el hueco está **declarado**?
Señala cualquier sitio donde el paso se marque alcanzado sin hecho durable explícito.

**P7.** **Orden del siguiente trabajo.** Candidatos: (a) el productor durable de `SETTLEMENT_EVENT`;
(b) el de `ENTRY_ORDER`; (c) la ventana PAPER real (`P3-2`); (d) el campo de fuente de precio por
ciclo/fill. ¿Cuál reduce más riesgo por unidad de esfuerzo, y cuál es **prerrequisito** de cuál?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

* **Productores durables pendientes:** `SETTLEMENT` y `ENTRY_ORDER` siguen **`NO MEDIDO`**;
  `read_operational_monitor` no lee ninguna fuente de settlement todavía. **No cerrado en este sello.**
* **Fuente de precio por operación ausente:** sólo se corrigió la etiqueta; el campo por ciclo/fill
  (`XTB`/`MARKET_CLOSE`/`REPLAY`/`SYNTHETIC`) **no existe** aún.
* **`activeSessions` sigue siendo un SUELO**, no un censo vivo (sin productor de latido durable).
* **`lastDecisionAt` es `NO MEDIDO` con `AUTO_OPERATIONAL_AUDIT` OFF.**
* **`P3-2`/`P3-3`** (ventana PAPER real) y las compuertas **`G1`–`G7`** — **ABIERTAS**.
* **`OBS-19`** — causa estructural aún abierta (listas de pytest a mano).
* **Sin migración:** Alembic head sigue en `046_fill_reference_mid`.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-22-m1-honestidad-semantica-2026-XX-XX.md`, con veredicto **por pieza**
(`SETTLEMENT` / «última decisión» vs heartbeat / precio real / concurrencia / contrato+UI) y respuesta a
la **pregunta de fondo**: **¿el monitor AUTO declara honestamente lo que mide, y falla cerrado cuando no
puede demostrarlo?** Hallazgos **nuevos** separados de la deuda **ya declarada** (§5); lo que **no** se
pudo medir; y la **recomendación de siguiente trabajo** (P7).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO: tag anotado v2.88.22-beta -> commit e904ad3f (tag object 0ca503c0), version 2.11.22-beta,
base del diff v2.88.21.1-beta (be388124), Alembic head 046_fill_reference_mid (SIN migracion).
Clase: correccion SEMANTICA de honestidad del monitor AUTO (M1). DELTA MOTOR = 0:
auto_simulation_worker.py NO aparece en el diff. NO añade productores durables.

PRIMERO lee, en este orden:
  1) docs/engineering/entrega-auditoria-externa-mia-v2.88.22-2026-10-02.md   (trampas §3 y preguntas §4)
  2) docs/engineering/evidence/v2.88.22/README.md    (afirmaciones falsables C1..C10 + limites §3)
  3) docs/engineering/evidence/v2.88.21.1/README.md y evidence/v2.88.21/README.md  (M2 y su hotfix)

VERIFICA PRIMERO (firma de estado, en el clon):
  git cat-file -t v2.88.22-beta                                          (tag anotado)
  git rev-list -n 1 v2.88.22-beta                                        (e904ad3f)
  git diff --name-only v2.88.21.1-beta v2.88.22-beta -- "*auto_simulation_worker*"   (VACIO = delta motor 0)
  git diff --name-only v2.88.21.1-beta v2.88.22-beta -- "*alembic*" "*versions*"     (VACIO = sin migracion)
  git diff --numstat v2.88.21.1-beta v2.88.22-beta -- packages apps                  (13 ficheros, +523/-113)

QUE QUEREMOS (respuestas concretas a las 7 preguntas de §4 de la entrega):
  a) SETTLEMENT: ¿algun camino donde un ciclo cerrado vuelva a producir 'reached'? ¿es fail-closed?
  b) lastHeartbeatAt vs lastDecisionAt: ¿queda algun punto que publique un latido como decision?
  c) El productor de claim: ¿todos los caminos que pierden un claim declaran conflict/conflictReason?
  d) UI: ¿algun sitio donde 'NO MEDIDO' se degrade a 0 o a un guion silencioso?
  e) Contrato: ¿openapi.json/schema.d.ts coinciden sin drift? ¿sobra o falta algun campo?
  f) Como NO se añaden productores durables: ¿el monitor afirma algo no demostrable en
     SIGNAL/TOP-N/RISK/ENTRY_ORDER, o el hueco esta declarado?
  g) Orden del siguiente trabajo: SETTLEMENT_EVENT durable, ENTRY_ORDER durable, ventana PAPER (P3-2),
     o fuente de precio por ciclo/fill. ¿Cual es prerrequisito de cual?

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo publico, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (la entrega §5 la lista).
  - NO leas 'SETTLEMENT corregido' como 'SETTLEMENT cerrado': se corrige la DECLARACION, no se crea el
    productor durable. Lo mismo con 'Precio real habilitado' = configuracion, NO fuente por operacion.
  - 'NO MEDIDO' NO es 0 ni '-'. Y ENTRY_ORDER sigue unknown a proposito.
  - Los documentos de auditoria (esta entrega, evidencia ampliada) estan en MAIN (POST-TAG), no dentro
    del tag. El checkout de main es bb6e453e; el sello es e904ad3f.
```
