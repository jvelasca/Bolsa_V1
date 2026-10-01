# Entrega a auditoría externa MIA — `v2.88.17.1-beta` (proveedor de precio REAL del motor AUTO + bundle direccional del OOS + instrumento OOS, 2026-10-01)

> **Objeto auditado:** tag anotado **`v2.88.17.1-beta`** → **`6221700c`** (versión **`2.11.17.1-beta`**),
> base del diff **`v2.88.16.2-beta`**, Alembic head **`046_fill_reference_mid`** (**sin migración**).
> **Remote:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Punto de entrada del auditor:** [`arranque-auditor-v2-88-17-1-w4-2026-10-01.md`](./arranque-auditor-v2-88-17-1-w4-2026-10-01.md)
> (**léelo primero**). **Audit-pack:** [`audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md`](./audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md).
> **Evidencia cruda:** [`evidence/v2.88.17.1/`](./evidence/v2.88.17.1/README.md) ·
> [`evidence/v2.88.17/`](./evidence/v2.88.17/README.md) · [`evidence/v2.88.16.3/`](./evidence/v2.88.16.3/README.md).

---

## 0. Qué es y qué NO es esta entrega

**Es** la auditoría del **primer tramo con `src` de producto de la serie `W1`…`W6`** que **sí cambia
capacidades** (el motor aprende a decir «no hay precio» y el OOS aprende a medir el lado corto), pero
que está diseñado para **no cambiar un byte de lo sellado** hasta que el propietario accione el
interruptor.

**NO es** una auditoría de diseño (como `v2.88.12`) ni una de `docs`-only: aquí **hay** `src` (8
ficheros, `+728 / −90`) y **hay** tests nuevos. Lo que **no hay** es **migración** ni cambio de
**umbrales**.

**Trampa nº 1 que debe evitarse:** leer «proveedor de precio REAL» como «medido en operación». **Está
apagado por defecto** (`.env.example` lo lleva **comentado**) y **la ventana PAPER real no ha
arrancado** (`P3-2`). Lo que se certifica es que **encenderlo es seguro y honesto**, no que ya haya
producido medidas.

---

## 1. El objeto y cómo obtenerlo

> **Dónde vive qué.** El **producto** auditado está **dentro del tag**; esta **entrega** (y el
> audit-pack, el arranque y el criterio de salida) viaja **POST-TAG en `main`**, porque el tag es
> inmutable y se selló antes de escribirse. Clona `main` para **leer**, y haz `checkout` del tag para
> **verificar**. Dentro del tag **no** encontrarás los `docs/engineering/*auditor*`: es el diseño, no
> un fichero perdido.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
# (A) leer la entrega  -> rama main (default tras el clon)
# (B) verificar el producto -> el tag
git checkout v2.88.17.1-beta
git log --oneline -1                       # 6221700c (fix W4.1)
```

| Verdad | Valor |
| --- | --- |
| Tag anotado | `v2.88.17.1-beta` → `6221700c` |
| Versión (`package.json`) | `2.11.17.1-beta` |
| Base del diff | `v2.88.16.2-beta` |
| Alembic head | `046_fill_reference_mid` — **SIN migración** |
| `src` de producto | **8 ficheros, `+728 / −90`** |
| Tags del tramo | `v2.88.16.3-beta` (W3.3) · `v2.88.17-beta` (**ROJO en `lifecycle-pg`**, superseded) · **`v2.88.17.1-beta`** (verde) |

---

## 2. Firma de estado verificada **antes** de auditar

Idéntica a la del arranque §2, y **corrida por el auditor en el clon**, no heredada: tag anotado,
versión, árbol limpio, **sin migración**, **umbrales intactos**, **hotfix test-only**, **interruptor
comentado en `.env.example`**, CI del tag **verde**.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **El tag `v2.88.17-beta` está ROJO y es CORRECTO que lo esté.** Fue **público** con
   `lifecycle-pg` en rojo por un **sorteo del arnés** (`uuid4()` del instrumento del certifier `A11`),
   **no** por el producto: en ese mismo run `python` (`3 219 passed`) y `replay-repro` fueron verdes.
   El tag rojo **no se reescribe**; se **supersede** con `v2.88.17.1-beta`. Auditar el rojo es
   auditar un **arnés de test**, no el motor.
2. **`Δ = 0` NO significa «no se tocó el motor».** El motor **sí** se tocó (8 ficheros): significa que
   **el resultado observable con el interruptor apagado es byte a byte el de antes**. La prueba es el
   job `replay-repro` (regenera el artefacto OOS y lo `asserta` por SHA-256), **no** una narración.
3. **El hash local `697526ED…C298967` / `3 448 185 B` NO es el sello.** Es el render **LOCAL en
   Windows** y **tampoco coincidía antes** de este tramo (drift de plataforma/seed local, declarado en
   `evidence/v2.88.17` §1.3 «Nota OBS»). La **autoridad** es el par del `assert-artifact`:
   **`1E3ADAC2…929A37E7` / `3 340 728 B`** (LF) y **`240662250347A2AA…6D9F54F0` / `3 445 622 B`** (CRLF).
4. **`point_citable = False` es una CONCLUSIÓN, no una carencia.** `W3.3` **mide** que el replay es un
   sorteo del venue y que la banda `K = 12` **cruza el cero**; por eso el propio repo **prohíbe** citar
   un punto del OOS como mérito. Un auditor que pida «un número de rendimiento del OOS» está pidiendo
   exactamente lo que el sello declara no citable.
5. **El bundle direccional no cambia resultados hoy.** AUTO es **long-only**
   (`auto_v2_entry._ENTRY_DIRECTION == "long"`); el valor del fix es dejar de **descartar en silencio**
   las cortas y unificar la regla. No es una mejora de rendimiento.
6. **La protección no está unificada (a propósito).** Cinco lecturas de precio pasan al tick de barra;
   la **sexta** (protección legacy) se queda en el minuto. Es el incremento **`W5`**, no un olvido.
7. **Dentro del tag, `docs/CURRENT_SYSTEM.md` es la foto VIEJA** (`AsOf V2.15`, `1.44.0-beta`).
   El tag es **inmutable** y el documento se puso al día **después**, en `main` (`AsOf V2.88.17.1`).
   No es un defecto del producto: es el precio de no reescribir un sello. La fuente al día es `main`.

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

Las **7 preguntas**:

**P1.** Con el interruptor apagado, ¿se sostiene el `Δ = 0` **por construcción** (no sólo por
observación)? Es decir: ¿existe algún camino en el que la mera **presencia** del seam altere el
comportamiento (orden de evaluación, `async`, cacheo de la foto del tick, excepciones nuevas)?

**P2.** ¿Es correcta la **frontera mixta**? — `mid(...)` = `close` de la última barra **cerrada**
(`<= B-1`, decisión) y `execution(...)` = barra **corriente** (fill y marca). ¿Hay **algún** consumidor
del precio leyendo la frontera equivocada? ¿El `open` de la barra corriente es de verdad **conocido**
(sin lookahead) en el instante en que el worker lo lee?

**P3.** **Fail-closed:** ¿existe un camino donde la ausencia de precio se degrade a una constante
(100.0/0.0)? ¿Y en la **composición** del `PriceSource` (si el proveedor real falla a mitad de turno,
qué ve el motor)?

**P4.** Dejar la **sexta** lectura (protección) en el minuto mientras decisión/fill/marca van al tick de
barra: ¿es una **incoherencia** que puede producir un comportamiento observable (p. ej. proteger con un
precio de la barra y evaluar la salida con otro), o es inocuo hasta `W5`?

**P5.** El bundle direccional: al delegar en `directional_geometry` **conservando** cada llamante su
`_round4`, ¿es imposible introducir un cambio de decimal? ¿Algún llamante perdió su redondeo?

**P6.** `W3.3` concluye `point_citable = False`. ¿Hay alguna lectura **legítima** del OOS que sí sea
citable (p. ej. **comparar dos políticas bajo el mismo sorteo**, o usar el sorteo como control
pareado)? Si la hay, ¿cómo debería declararse?

**P7.** **Orden del siguiente trabajo.** Candidatos: (a) cerrar el **test PG invisible** (ver §5) y su
alta en CI — peaje `OBS-19`; (b) **`W5`** (ProtectionClock); (c) la **ventana PAPER real** (`P3-2`) con
el interruptor **encendido**. ¿Cuál reduce más riesgo por unidad de esfuerzo, y **encender el
interruptor** antes de (b) es prudente?

---

## 5. Deuda viva que el auditor debe encontrar declarada (no oculta)

* **`OBS-19`** — causa **estructural** abierta: las listas de pytest se mantienen **a mano**.
* **Test PG invisible (hallazgo propio, 2026-10-01)** —
  `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py` asertaba
  `measuredCycles == len(_SPECS)` ⇒ **`17 != 26`**, y **falla** cuando corre contra PG. **El `17` es
  correcto** (ciclos **con R medible**: 9 de la familia A + 8 de la B); el `26` es el **total** del
  fixture. **Ningún job lo ejecuta** (offline ⇒ `pytest.skip`; jobs PG ⇒ listas explícitas donde no
  figura; `v70` aparece **0** veces en `.github/workflows/`). **No arreglado en este sello.**
* Regla direccional aún **duplicada** en `risk_allocator` / `trade_plan` /
  `portfolio_decision_engine` / `exit_plan`.
* `W5` (ProtectionClock) y `W6` (planificador de barra cerrada) **pendientes**.
* `P3-2`/`P3-3` (ventana PAPER real), `P3-5`, `H-4`, `OBS-15`, `OBS-16`, `OBS-22` — **abiertas**.

---

## 6. Entregable esperado del auditor

`docs/engineering/auditoria-v2-88-17-1-w4-bundle-direccional-2026-XX-XX.md`, con veredicto **por pieza**
(instrumento OOS / bundle direccional / proveedor de precio real) y respuesta a la **pregunta de fondo**:
**¿es seguro y honesto encender `AUTO_ENGINE_SIM_REAL_PRICE` en PAPER con lo sellado?** Hallazgos
**nuevos** separados de la deuda **ya declarada**; lo que **no** se pudo medir; y la **recomendación de
siguiente trabajo** (P7).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO: tag anotado v2.88.17.1-beta -> version 2.11.17.1-beta, base del diff v2.88.16.2-beta,
Alembic head 046_fill_reference_mid (SIN migracion).
OJO: aqui SI hay src de producto (8 ficheros, +728/-90), pero el comportamiento nuevo esta
tras un interruptor APAGADO por defecto (AUTO_ENGINE_SIM_REAL_PRICE, comentado en .env.example).

PRIMERO lee, en este orden:
  1) docs/engineering/arranque-auditor-v2-88-17-1-w4-2026-10-01.md
  2) docs/engineering/audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md  (tesis T1-T8 + limites §5)
  3) docs/engineering/entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md  (trampas §3 y preguntas §4)
  4) docs/engineering/evidence/v2.88.17/README.md y evidence/v2.88.17.1/README.md

VERIFICA PRIMERO (firma de estado, en el clon):
  git cat-file -t v2.88.17.1-beta                                     (tag anotado)
  git diff --name-only v2.88.16.2-beta v2.88.17.1-beta -- "*alembic*" "*versions*"   (vacio)
  git diff --name-only v2.88.17-beta v2.88.17.1-beta -- packages/py apps/api-python/src  (vacio = test-only)
  git show v2.88.17.1-beta:.env.example | grep -A1 AUTO_ENGINE_SIM_REAL_PRICE  (comentado = default OFF)

QUÉ QUEREMOS (respuestas concretas a las 7 preguntas de §4 de la entrega):
  a) El delta=0 con el interruptor apagado, ¿es POR CONSTRUCCION o solo observado?
  b) ¿Es correcta la frontera mixta (mid = ultima barra CERRADA; execution = barra CORRIENTE)?
  c) Fail-closed: ¿hay algun camino donde la ausencia de precio se vuelva una constante 100.0/0.0?
  d) La sexta lectura (proteccion legacy) sigue en el MINUTO: ¿incoherencia observable o inocua?
  e) El bundle direccional con _round4 por llamante: ¿es imposible mover un decimal?
  f) point_citable=False: ¿hay alguna lectura del OOS que SI sea citable (control pareado)?
  g) Orden del siguiente trabajo: cerrar el test PG invisible + OBS-19, W5 (ProtectionClock), o la
     ventana PAPER real (P3-2) con el interruptor encendido.

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo público, sin credenciales).
  - Cita fichero:linea. Distingue HALLAZGO NUEVO de DEUDA YA DECLARADA (el audit-pack §5 la lista).
  - El tag v2.88.17-beta ESTA ROJO A PROPOSITO (sorteo del arnes de test, superseded): no lo
    cuenta como defecto del producto; auditar el arnes si quieres, pero dilo aparte.
  - No pidas un "numero de rendimiento" del OOS: W3.3 certifica que su banda cruza el cero.
  - Los documentos de auditoria (arranque, audit-pack, entrega) estan en MAIN (POST-TAG),
    no dentro del tag: el tag solo lleva el producto. Si ves docs/CURRENT_SYSTEM.md con
    AsOf V2.15 dentro del tag, es la foto vieja e inmutable, no un fallo del producto.
```
