# Entrega a auditoría externa MIA — `v2.88.34-beta` (DÍA-D AUTO absorbido + **bucle de realimentación POR VALOR** sobre una ventana `D0..D1`, 2026-10-03)

> **Objeto auditado:** tag anotado **`v2.88.34-beta`** → tag object **`1034e4a5`** → commit **`a98996ed`**,
> versión **`2.11.34-beta`**, base del diff **`v2.88.32-beta`** → **`f87425ae`**, Alembic head
> **`048_journal_entry_dedupe_key`** (**sin migración**).
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Clase:** entrega de **investigación/sandbox** sobre el motor AUTO, **advisory y read-only**.
> **Evidencia cruda:** [`evidence/v2.88.34/`](./evidence/v2.88.34/README.md) ·
> [`evidence/v2.88.33/`](./evidence/v2.88.33/README.md) ·
> auditoría previa del predecesor: [`auditoria-externa-v2.88.32-beta-2026-10-03.md`](./auditoria-externa-v2.88.32-beta-2026-10-03.md).

---

## 0. Qué es y qué NO es esta entrega

**Es** la auditoría de **dos** incrementos que llegan juntos en **un solo tag**, porque `v2.88.33` **nunca
se etiquetó**:

1. **`v2.88.33` — DÍA-D AUTO por día.** Un sandbox **read-only** que sitúa el motor AUTO real en una
   **fecha pasada `D`** (reloj y precio inyectados, stores en memoria) y compara, paso a paso,
   **declarado vs ejecutado** (`MATCH`/`DIVERGENT`/`NOT_MEASURED`) + OOS real posterior.
2. **`v2.88.34` — bucle de realimentación POR VALOR.** Extiende lo anterior a una **ventana `D0..D1`**:
   por **instrumento** pliega lo **declarado** + lo **ejecutado** + el **OOS real**, emite un
   **veredicto** (`CONFIRMED`/`MIXED`/`REFUTED`/`NOT_MEASURED`) y un **catálogo de errores**
   (`SOFTWARE`/`OPERATIONAL`/`DATA`), y lo pinta en `/auto-monitor`.

**`Δ decisión motor = 0`.** Ningún fichero de motor aparece en el diff: el motor se **conduce** con
stores en memoria desde el mismo harness hermético de `v2_86`/`v2_87`/`v2_89`. No cambia ninguna decisión
de inversión, ningún umbral (`TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B) ni ninguna migración.

**NO es** una auditoría que cierre la **ventana PAPER real**. Este sello **no** opera días reales: un
replay **no** fabrica cubos de calendario durables. `≥4 días` / `≥2 episodios` / `≥32 ciclos` siguen
**NO MEDIDOS**.

> **Trampa nº 1 — `v2.88.33` viaja DENTRO de `v2.88.34`.** No existe el tag `v2.88.33-beta`. Quien audite
> sólo el «delta `v2.88.34`» se dejará fuera la mitad del objeto. El **diff base correcto es
> `v2.88.32-beta`**, no un inexistente `v2.88.33-beta`.
>
> **Trampa nº 2 — «`NOT_MEASURED`» no es un `0`.** En un `D` histórico **sin** hechos durables y **sin**
> ciclos medidos, el veredicto es `NOT_MEASURED` y el hueco viaja como `null`/`NO MEDIDO`. Encontrar 20
> valores `NOT_MEASURED` **no** es un fallo: es la regla de la casa (un hueco **nunca** se coacciona a `0`).
>
> **Trampa nº 3 — el artefacto va por HTTP, el motor no.** El motor AUTO vive en `scheduler_worker`
> (env-gated), **no** en el proceso FastAPI. La ruta `GET /api/auto/dia-d-feedback` **sólo sirve** el
> artefacto ya escrito por el CLI; no ejecuta el barrido.
>
> **Trampa nº 4 — `AUTO_ENGINE_SIM_REAL_PRICE = 0` en el barrido.** El precio del replay es el
> `price_script` histórico inyectado (opens reales), **no** una lectura en vivo. Que la capacidad de
> precio real exista **no** significa que el barrido la use.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado está **dentro del tag**; esta **entrega** viaja
> **POST-TAG en `main`**, porque el tag es inmutable y se selló antes de escribirse su cita. Clona
> `main` para **leer**, y `checkout` del tag para **verificar**. Dentro del tag **encontrarás** la
> evidencia del sello (`evidence/v2.88.33|v2.88.34`) y el informe previo
> `auditoria-externa-v2.88.32-beta-2026-10-03.md`; lo que **no** encontrarás es **esta** entrega.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
# (A) leer la entrega        -> rama main (default tras el clon)
# (B) verificar el producto  -> el tag
git checkout v2.88.34-beta
git log --oneline -1                       # a98996ed (sello v2.88.34)
```

| Verdad | Valor |
| --- | --- |
| Tag anotado | `v2.88.34-beta` (tag object `1034e4a5`) → `a98996ed` |
| Versión (`package.json`) | `2.11.34-beta` (base `2.11.32-beta`) |
| Base del diff | `v2.88.32-beta` → `f87425ae` |
| Alembic head | `048_journal_entry_dedupe_key` — **SIN migración** |
| Delta tag-a-tag total | **40 ficheros, `+7169 / −53`** (incluye docs) |
| Delta `packages/`+`apps/` | **25 ficheros, `+6311 / −13`** |
| `Δ motor` | **ningún** fichero de motor en el diff (verificado, §2) |
| Commit siguiente (POST-TAG, `main`) | `30294546` — cita del CI (docs-only, **no** es el sello) |
| CI del tag | `Release tag CI` run **`37109548555`** — **TODO VERDE** |

**Composición del delta `packages/`+`apps/` (25 ficheros):**

| Grupo | Ficheros | Nota |
| --- | --- | --- |
| Producto Python (lógica pura) | `2` (`dia_d_auto.py`, `dia_d_auto_feedback.py`) | sin reloj ni ULID, `sort_keys=True` |
| CLI del barrido (scripts) | `2` (`v2_89_dia_d_auto_replay.py`, `v2_90_dia_d_feedback.py`) | read-only |
| Rutas read-only | `3` (`auto_dia_d.py`, `auto_dia_d_feedback.py`, `router.py`) | fail-closed |
| Tests Python | `4` (2 de núcleo + 2 de ruta) | `16+6` y `17+7` passed |
| Contrato | `3` (`openapi.json`, `schema.d.ts`, `api.ts`) | `contract:gen` |
| Frontend | `11` (9 de código + 2 de test) | sub-vista «Feedback por valor» |

**Cómo recalcularlo en el clon (sin creerme nada):**

```bash
git diff --stat   v2.88.32-beta v2.88.34-beta                     # 40 ficheros, +7169/-53
git diff --numstat v2.88.32-beta v2.88.34-beta -- packages apps   # 25 ficheros, +6311/-13
git diff --name-only v2.88.32-beta v2.88.34-beta \
  -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
     "*market_operability*" "*replay_oos*"                        # VACÍO = Δ motor 0
git diff --name-only v2.88.32-beta v2.88.34-beta -- "*alembic*" "*versions*"   # VACÍO = sin migración
```

---

## 2. Firma de estado verificada **antes** de auditar

Corrida **por el auditor en su clon**, no heredada:

| Comprobación | Esperado |
| --- | --- |
| `git cat-file -t v2.88.34-beta` | `tag` (anotado) |
| `git rev-list -n 1 v2.88.34-beta` | `a98996ed` |
| Árbol limpio en el checkout del tag | sí |
| Migración | **ninguna** (head `048_journal_entry_dedupe_key`) |
| Umbrales `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B | intactos |
| Ficheros de motor en el diff | **ausentes** |
| Freeze del runner (`git rev-parse "HEAD:apps" "HEAD:packages"`) | `69bd72d81c64d24937f6e6af325e866586d76a71` / `2c15ecb8b017793f38bfee307d3573398b9d6ead` |
| CI del tag | **11 `success`** + `playwright (integrated E2E, opt-in)` `skipped` por diseño; `certify` `success` |

**Verificación local re-ejecutada en el momento del sello** (todos verdes): `pytest` `17+7 passed` ·
`ruff` All checks passed · `lint-imports` **4 kept / 0 broken** · `mypy` **521 files** ·
`contract:check` OK · `tsc -b --noEmit` limpio · vitest `auto-monitor` **4 ficheros / 14 tests** ·
`pnpm window:test` **25/25** · CLI de humo sobre barras selladas ⇒ 20 valores `NOT_MEASURED`, 0 errores,
gate `INCONCLUSIVE`.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **`v2.88.33` no tiene tag propio.** El objeto es `v2.88.34-beta` y su diff base es `v2.88.32-beta`.
   Cualquier cálculo que asuma un `v2.88.33-beta` intermedio es incorrecto.
2. **`NOT_MEASURED` es honestidad, no un bug.** `MIN_VALUE_CYCLES = 5` (`MIN_VALUE_HIT_RATE = 0.5`) se
   **declara** en `limits`; no se relaja para «confirmar». Un valor sin ciclos medidos es `NOT_MEASURED`
   **y el hueco viaja `null`**, nunca `0`.
3. **La detección de divergencia de software es heurística** (pasos deterministas `SIGNAL`/`ORDER`/`FILL`):
   **informa, no sentencia**. `REFUTED` puede venir de `expectancyR <= 0` **o** de una divergencia; la
   precedencia `REFUTED > MIXED` es deliberada.
4. **El «lado ejecutado» sigue `NOT_MEASURED` en días históricos** hasta que la ventana PAPER opere ese
   `D`. El veredicto se **recalcula sin cambiar código** cuando existan ciclos cerrados.
5. **El artefacto del barrido es hermético por CLI, no por HTTP** (ver Trampa nº 3). El artefacto vive en
   `operability_runs/dia-d-auto/*.json`, que es **gitignored**: un tercero lo **regenera**, no lo hereda.
6. **La ruta es fail-closed y respeta el scope de cuenta:** sin cuenta ⇒ `no_account_scope`; sin
   artefacto ⇒ `available=false` + `artifact_not_found`; ventana malformada ⇒ `invalid_window`.
7. **El monitor vivo no se degrada.** Las queries de feedback son **perezosas** (`enabled` sólo al abrir
   la pestaña): montar el modo sandbox **no** dispara llamadas extra.
8. **El veredicto por valor `complementa`** el gate global `window_gate(...)`; **no** lo sustituye.
9. **Este sello mueve el árbol** `apps`/`packages`, así que el runner de la ventana se **re-ancló** a los
   hashes del árbol sellado (`69bd72d8…` / `2c15ecb8…`), **distintos** del `0f9b83cb…` estimado *antes*
   de commitear (`lint-staged` reformatea el frontend en el pre-commit).
10. **Los documentos de auditoría y esta entrega son POST-TAG (en `main`).** El sello es `a98996ed`; la
    cita del CI es `30294546`.

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

**P1.** ¿El barrido es **de verdad** read-only? ¿Existe **algún** camino que escriba un cubo durable
(`insert`/`update`/`commit`) o que **backdatee** `created_at`? El cubo de calendario debe salir del
**reloj de pared** (`sim_fill_finance_context.created_at`); un replay **no** debe fabricarlo.

**P2.** ¿Existe **algún** camino en el que `NOT_MEASURED`/`None` se degrade a `0.0` —en el pliegue, en la
matriz valor × día, en el heatmap, en la curva de R, en la serialización JSON o en la UI—? Señala
cualquier coerción silenciosa.

**P3.** Precedencia y suelos del veredicto: ¿se cumple **siempre** `REFUTED > MIXED`? ¿`CONFIRMED` exige
**las tres** (`expectancyR > 0` **y** `hitRate >= 0.5` **y** cero errores de software)? ¿El suelo
`measuredCycles < 5 ⇒ NOT_MEASURED` no se puede sortear por ningún camino?

**P4.** Determinismo: ¿mismo estado ⇒ payload **byte a byte** idéntico? ¿Hay algún reloj, ULID o
`set`/`dict` sin orden que pueda romper `sort_keys=True`?

**P5.** Taxonomía de errores: ¿cada `code` cae en **una sola** familia (`SOFTWARE`/`OPERATIONAL`/`DATA`)
y **ningún** código desconocido se mapea silenciosamente a un error (o a `None`)?

**P6.** Ruta y scope: ¿la ruta es fail-closed en **todos** los caminos (`no_account_scope`,
`available=false`, `invalid_window`)? ¿Coincide `openapi.json`/`schema.d.ts` con el read model **sin
drift**? ¿Hay algún campo nuevo **sin** consumidor (o viceversa)?

**P7.** `Δ motor = 0`: ¿cómo se inyectan los stores en memoria en el harness? ¿Hay **algún** import del
barrido que **edite** estado del motor real, o algún efecto colateral fuera de los stores en memoria?

**P8.** Freeze: ¿`git rev-parse "HEAD:apps" "HEAD:packages"` devuelve **exactamente** el par pineado, y el
runner **aborta** (`TREE_MOVED`, fail-closed) si el árbol se mueve? ¿Puede el **entorno** reescribir la
configuración de freeze sin `UNSAFE`?

**P9.** UI: ¿las queries de feedback **sólo** se disparan al abrir la pestaña (el monitor «Ventana actual»
no paga llamadas extra)? ¿Hay algún sitio donde `NO MEDIDO` se degrade a `0`, `—` o `null` silencioso?

**P10.** **Orden del siguiente trabajo.** Candidatos: (a) **ventana PAPER real** (`P3-2`/`P3-3`, `≥4
días`/`≥32 ciclos`) con el interruptor `AUTO_ENGINE_SIM_REAL_PRICE=1`; (b) cerrar **`G2`/`OBS-19`** (los
53 ficheros de test que no corren en ningún job); (c) productor durable del «lado ejecutado». ¿Cuál
reduce más riesgo por unidad de esfuerzo, y cuál es **prerrequisito** de cuál?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

- **`P3-2`/`P3-3` (ventana PAPER real) — ABIERTAS.** El **runner** está construido y blindado
  (`v2.88.30`…`v2.88.32`) y el precio real está medido en PG (`v2.88.29`), pero **no hay días reales con
  material**. Aquí el gate se declara `INCONCLUSIVE`.
- **`OBS-19`/`G2` — ABIERTA.** El censo **se deriva** de los workflows (`scripts/ci/test_selection.py` +
  guarda, `maxUndeclared: 0`) y el agujero bajó de **205 a 53** ficheros (**34** `W-G2/2` PG + **19**
  `W-G2/3` red/E2E), pero **53 siguen sin ejecutarse en ningún job**
  ([`evidence/v2.88.18`](./evidence/v2.88.18/README.md)).
- **Compuertas `G1`–`G7` del criterio de salida:** `G6` ✅ (nada peligroso armado: `LIVE_EXECUTION_UNLOCKED`
  off · `PAPER_D_EXECUTE` off · XTB **PARKED** · este sello es read-only) y `G7` ✅ (gobernanza al día);
  **`G1`–`G4` siguen ❌** ([`criterio-salida-beta-2026-10-01.md`](./criterio-salida-beta-2026-10-01.md) §3).
  Este documento **es** el arranque de `G1`; el veredicto externo **aún no existe**.
- **`W5`/`W6` sin sellar** y la **regla direccional duplicada** en 4 módulos (deuda histórica).
- **`OBS-14.b`** (alcance del barrido de arranque) y **`OBS-15`** (techo de 1000 `APPLIED`) siguen
  declaradas en [`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
- **Artefactos locales gitignored:** los `sha256` de `operability_runs/dia-d-auto/*.json` se citan en la
  evidencia; un tercero los **regenera** (comando en `evidence/v2.88.34/README.md` §4), no los hereda.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-34-dia-d-auto-feedback-por-valor-2026-XX-XX.md`, con veredicto
**por pieza** (sandbox por día · bucle por valor · determinismo · taxonomía de errores · fail-closed del
read-only · contrato+UI · freeze) y respuesta a la **pregunta de fondo**: **¿el bucle de realimentación
declara honestamente lo que mide, es de verdad read-only, y falla cerrado cuando no puede demostrar un
hueco?** Hallazgos **nuevos** separados de la deuda **ya declarada** (§5); lo que **no** se pudo medir; y
la **recomendación de siguiente trabajo** (P10).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO: tag anotado v2.88.34-beta -> tag object 1034e4a5 -> commit a98996ed, version 2.11.34-beta,
base del diff v2.88.32-beta (f87425ae), Alembic head 048_journal_entry_dedupe_key (SIN migracion).
Clase: sandbox de investigacion sobre el motor AUTO (DIA-D AUTO por dia v2.88.33, ABSORBIDO, + bucle de
realimentacion POR VALOR sobre una ventana D0..D1). DELTA MOTOR = 0: ningun fichero de motor aparece en
el diff. Advisory y read-only. NO cierra la ventana PAPER real.

PRIMERO lee, en este orden:
  1) docs/engineering/entrega-auditoria-externa-mia-v2.88.34-2026-10-03.md  (trampas §3 y preguntas §4)
  2) docs/engineering/evidence/v2.88.34/README.md   (afirmaciones falsables C1..C9 + limites §3)
  3) docs/engineering/evidence/v2.88.33/README.md   (el sello absorbido, sin tag propio)
  4) docs/engineering/auditoria-externa-v2.88.32-beta-2026-10-03.md  (auditoria del predecesor)

VERIFICA PRIMERO (firma de estado, en el clon):
  git cat-file -t v2.88.34-beta                                       (tag anotado)
  git rev-list -n 1 v2.88.34-beta                                     (a98996ed)
  git diff --name-only v2.88.32-beta v2.88.34-beta \
    -- "*auto_simulation_worker*" "*auto_v2_entry*" "*sim_durable_store*" \
       "*market_operability*" "*replay_oos*"                           (VACIO = delta motor 0)
  git diff --name-only v2.88.32-beta v2.88.34-beta -- "*alembic*" "*versions*"   (VACIO = sin migracion)
  git diff --numstat v2.88.32-beta v2.88.34-beta -- packages apps      (25 ficheros, +6311/-13)
  git rev-parse "HEAD:apps" "HEAD:packages"                            (69bd72d8... / 2c15ecb8...)

QUE QUEREMOS (respuestas concretas a los 10 puntos de §4 de la entrega):
  a) El barrido, ¿es de verdad read-only? ¿algun camino que escriba un cubo durable o backdatee created_at?
  b) ¿Algun camino donde NOT_MEASURED/None se degrade a 0.0 (pliegue, matriz, heatmap, curva, JSON, UI)?
  c) Precedencia REFUTED > MIXED y CONFIRMED con las TRES condiciones; suelo measuredCycles<5 infranqueable.
  d) Determinismo: mismo estado => payload byte a byte identico (sin reloj/ULID/orden no determinista).
  e) Taxonomia de errores: cada code en UNA familia; ningun code desconocido mapeado en silencio.
  f) Ruta fail-closed (no_account_scope / available=false / invalid_window) y contrato sin drift.
  g) Delta motor = 0: como se inyectan los stores en memoria; cero efectos colaterales fuera de ellos.
  h) Freeze: HEAD:apps/HEAD:packages == hashes pineados; TREE_MOVED fail-closed; config no reescribible.
  i) UI: queries perezosas (no degradan el monitor vivo); NO MEDIDO nunca degradado a 0 o guion silencioso.
  j) Orden del siguiente trabajo: ventana PAPER real (P3-2/P3-3), cerrar G2/OBS-19, o productor durable
     del 'lado ejecutado'. Cual es prerrequisito de cual.

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo publico, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (la entrega §5 la lista).
  - NO leas 'NOT_MEASURED' como 0 ni como fallo: es la regla de la casa (un hueco nunca se coacciona a 0).
  - NO leas 'DIA-D AUTO' como 'ventana PAPER operada': es un replay hermetico, no fabrica dias reales.
  - El artefacto del barrido es gitignored: regeneralo con el comando de evidence/v2.88.34 §4.
  - Los documentos de auditoria (esta entrega) estan en MAIN (POST-TAG). El sello es a98996ed; la cita del
    CI es 30294546.
```
