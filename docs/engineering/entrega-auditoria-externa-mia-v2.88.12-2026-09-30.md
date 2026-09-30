# Entrega a auditoría externa MIA — `v2.88.12-beta` (diseño de granularidad operativa, 2026-09-30)

> **Objeto auditado:** tag anotado **`v2.88.12-beta`** (versión **`2.11.12-beta`**), Alembic head
> **`046_fill_reference_mid`** (**sin migración**). El **SHA del objeto** del tag es **POST-TAG** (no puede
> vivir dentro del propio tag: `Release tag CI` sólo corre al empujar, patrón `OBS-3`/`OBS-4`); se añade a
> `main` como **cita POST-TAG**.
> **Repositorio:** `https://github.com/jvelasca/Bolsa_V1` — **PÚBLICO** (el auditor clona sin credenciales).
> **Punto de entrada del auditor:** [`arranque-auditor-v2-88-12-granularidad-operativa-2026-09-30.md`](./arranque-auditor-v2-88-12-granularidad-operativa-2026-09-30.md)
> (léelo **primero**).
> **Documento a auditar:** [`rethink-granularidad-operativa-auto-2026-09-30.md`](./rethink-granularidad-operativa-auto-2026-09-30.md).
> **Informe/relevo:** el propio documento de diseño, §11.

---

## 0. Qué es y qué NO es esta entrega

**Es** una **revisión de DISEÑO**. El objeto no es código: es un **documento de arquitectura** que repiensa
la cadencia del motor AUTO frente a la granularidad real de los datos. El auditor externo aporta su
**opinión técnica** y ayuda a **consensuar el siguiente trabajo** (§4). Es un `docs`-only: **cero `src`,
cero tests, cero migraciones, cero umbrales.**

**NO es** una auditoría de motor: **no hay cambio de código que auditar**, y un `git diff` vacío sobre
`packages/`/`apps/*/src` **no es un error**, es la naturaleza del objeto (§3.2). **NO** cierra ni mueve
ninguna deuda (§8): `P3-2`/`P3-3` y el resto de la cola siguen **ABIERTAS**.

---

## 1. El objeto y cómo obtenerlo

| | |
| --- | --- |
| Tag (anotado) | `v2.88.12-beta` |
| Versión | `2.11.12-beta` |
| Alembic head | `046_fill_reference_mid` (único head, **sin migración**) |
| Fase | `GRANULARIDAD-OPERATIVA` (diseño) |
| Base del diff | `v2.88.11-beta` |
| Contenido | **1 documento de diseño nuevo** + **2 docs de auditoría** + `CHANGELOG.md` + `package.json` (bump) + registros (`PROJECT_STATE`, `engineering-index`, enlace no normativo en ADR 010) |
| Motor | **INTACTO** (el diff de `packages/py` y `apps/api-python/src` es **vacío**) |

```
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git tag -l "v2.88.12-beta"
git rev-list -n1 v2.88.12-beta         # commit sellado
git show v2.88.12-beta:package.json    # "version": "2.11.12-beta"
```

---

## 2. Firma de estado verificada **antes** de auditar

| # | Comprobación | Comando | Resultado esperado |
| --- | --- | --- | --- |
| 1 | Clon anónimo (repo público) | `git clone https://github.com/jvelasca/Bolsa_V1` | OK |
| 2 | Tag **anotado** (no ligero) | `git cat-file -t v2.88.12-beta` | `tag` |
| 3 | Versión sellada | `git show v2.88.12-beta:package.json` | `2.11.12-beta` |
| 4 | **El motor NO cambia** | `git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src` | **vacío** |
| 5 | **No** se toca config ni CI | `git diff --name-only v2.88.11-beta v2.88.12-beta -- .github pyproject.toml` | **ninguno** |
| 6 | Contenido del tag | `git diff --name-status v2.88.11-beta v2.88.12-beta` | docs + `CHANGELOG.md` + `package.json` |
| 7 | **No** se borra ningún test | `git diff --diff-filter=DR --name-status v2.88.11-beta v2.88.12-beta` | **0** |
| 8 | CI del tag | `Release tag CI` (run **POST-TAG**, citado en `main`) | **SUCCESS** |

**Regla de la casa:** ninguna cifra sin comando que la reproduzca; un hueco se declara **`NO MEDIDO`**,
jamás un `0` fingido.

---

## 3. Trampas declaradas: lo que el auditor **NO** debe concluir

1. **«El CI del tag no está acreditado.»** La cita **no puede** vivir dentro del tag: `Release tag CI` sólo
   corre **al empujar** ⇒ es **POST-TAG** por construcción (`OBS-3`/`OBS-4`/`OBS-22`). La copia sellada de
   `evidence/` dice «pendiente» **a propósito**; la cita real viaja en `main`.
2. **«El diff del motor está vacío: es un error.»** No: el objeto es un **diseño** (`docs`-only). El diff
   de `src` **debe** estar vacío (§2.4). No hay motor que auditar.
3. **«Este documento cierra `P3-2`/`P3-3`.»** **No.** El propio diseño (§6) declara que sólo la **ventana
   PAPER real** (reloj de pared) puede acreditarlas; un documento **no** mide nada.
4. **«El ADR 010 se ha enmendado.»** **No.** Sólo se añade un enlace **no normativo** en su sección de
   Referencias. Habilitar intradía seguiría exigiendo la **enmienda** del ADR.
5. **«La propuesta ya está implementada.»** **No.** F1–F4 son un **roadmap propuesto**; no hay una sola
   línea de código nueva. Cualquier fase aprobada será un incremento propio, con su bump y su CI.
6. **«Se han cambiado umbrales de evidencia.»** **No.** `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B: **intactos**.

---

## 4. Alcance sugerido: lo que queremos consensuar con el auditor

Por orden de valor (respuestas concretas, no una validación genérica):

1. **¿El diagnóstico (§2 del diseño) es correcto y completo?** ¿Existe alguna superficie donde la
   granularidad entre y que el documento **no** haya inventariado (además de dedupe de señal, régimen/ATR/
   señal, cadencia, protección, fill, ingesta y cubos de evidencia)?
2. **¿`OperativeGranularity` es el seam correcto** o debería residir en el **kernel** (`platform_kernel`),
   dado que ADR 010 ya centraliza `KERNEL_TIMEFRAMES`?
3. **¿La matriz de capacidades y el *capability gate* fail-closed son suficientes** para impedir una
   configuración incoherente (p. ej. protección intra-barra sin barras intra-día)?
4. **Ranking de cadencia (A/B/C).** ¿Conviene **F1 = short-circuit por cambio de barra** como primer
   incremento (mismo comportamiento, menos cómputo), o hay una razón para ir directo al planificador (C)?
5. **Coherencia con `P3-2`/`P3-3` (§6).** ¿Es correcto que el **cubo de evidencia** lo fije la granularidad
   (hoy `day`) y que migrar a `1wk` cambie la lectura del gate?
6. **Riesgos de la nueva cadencia** sobre el **grace window** de reservas y el **settlement** (hoy atados a
   60 s). ¿Qué invariante debería fijar la fase que lo toque?
7. **ADR 010.** ¿`1wk` está ya cubierto sin enmienda? ¿La intradía exige enmienda **y** ingesta intra-día?,
   ¿lo ve igual?

---

## 5. Reproducción en un clon fresco

```
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.88.12-beta            # o main para ver la cita POST-TAG

# Que el motor NO cambió (debe salir vacío)
git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src

# Que es docs-only + bump
git diff --name-status v2.88.11-beta v2.88.12-beta

# Version sellada
git show v2.88.12-beta:package.json
```

El CI del tag (job `python`, `lifecycle-pg`, `replay-repro`, `dr-verify`, `a7-gate`, `certify`) corre
**igual** en un sello docs-only (el workflow certifica sin path-filter), pero su resultado es **POST-TAG**.

---

## 6. Entregable esperado del auditor

Un `docs/engineering/auditoria-v2-88-12-granularidad-operativa-2026-XX-XX.md` con:

- **Veredicto.** Como esto es un **diseño**, el veredicto se formula sobre la **propuesta**:
  `VIABLE` / `VIABLE CON CAMBIOS` / `NO VIABLE`, no sobre «aprobado/rechazado» de código.
- **Respuestas a las 7 preguntas de §4**, cada una con el argumento y, cuando aplique, el comando/fragmento
  del repo que lo respalda.
- **Riesgos y vacíos** del diagnóstico o del modelo, separando **hallazgo nuevo** de **deuda ya declarada**.
- **Recomendación de siguiente paso**: ¿F1 (corte del desperdicio en D1) como primer incremento? ¿Otro orden?
- **Lo que el auditor NO pudo medir** (declarado, no omitido).

---

## 7. Prompt listo para pegar (auditor MIA externo)

```text
Actúa como auditor externo independiente. Auditas un repositorio PÚBLICO de GitHub:
https://github.com/jvelasca/Bolsa_V1

OBJETO: tag anotado v2.88.12-beta -> versión 2.11.12-beta, Alembic head 046_fill_reference_mid (sin migración).
Es un DISEÑO (docs-only): el diff del motor es VACÍO por construcción, no es un error.

PRIMERO lee, en este orden:
  1) docs/engineering/arranque-auditor-v2-88-12-granularidad-operativa-2026-09-30.md
  2) docs/engineering/rethink-granularidad-operativa-auto-2026-09-30.md   (el diseño, §2 diagnostico y §3-§7)
  3) docs/engineering/entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md  (trampas declaradas §3 y preguntas §4)

VERIFICA PRIMERO (no debe haber motor):
  git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src   (vacío)

QUÉ QUEREMOS (respuestas concretas a las 7 preguntas de §4 de la entrega):
  a) ¿El diagnostico es correcto y completo? ¿Falta alguna superficie de granularidad?
  b) ¿OperativeGranularity es el seam correcto, o debe residir en el kernel?
  c) ¿La matriz de capacidades + capability gate fail-closed bastan?
  d) Ranking A/B/C: ¿conviene F1 (short-circuit por cambio de barra) primero?
  e) ¿Es correcto que el cubo de evidencia lo fije la granularidad (día/semana)? Implicación en P3-2/P3-3.
  f) Riesgos de la nueva cadencia en el grace window de reservas y el settlement.
  g) ADR 010: ¿1wk sin enmienda? ¿intradía exige enmienda + ingesta intra-día?

REGLAS:
  - Trabaja sobre un clon fresco desde GitHub (repo público, sin credenciales).
  - NO aceptes ninguna cifra sin comando que la reproduzca.
  - No propongas reescribir el tag (es inmutable). Separa HALLAZGO NUEVO de DEUDA YA DECLARADA.
  - Si algo no lo puedes medir, dilo como NO MEDIDO.

QUÉ ENTREGAR: informe con veredicto VIABLE / VIABLE CON CAMBIOS / NO VIABLE, respuestas a a)-g),
riesgos y vacíos, lo que NO pudiste medir, y la recomendación de SIGUIENTE TRABAJO.
```

---

## 8. Deuda viva que el auditor debe encontrar declarada (no oculta)

| ID | Severidad | Alcance | Estado |
| --- | --- | --- | --- |
| **`P3-2`/`P3-3`** | — | ventana PAPER **real** ≥4 días con material durable (≥32 ciclos, ≥2 episodios) | **ABIERTAS** (este sello no las mide ni las mueve) |
| **`OBS-14.b`** | MEDIUM | motor: el barrido de **arranque** no distingue una huérfana de una reserva viva de otra sesión | **ABIERTA** |
| **`OBS-15`** | MEDIUM | motor: el techo de 1000 filas `APPLIED` puede enganchar `RECONCILIATION_FAILURE` | **ABIERTA** |
| **`OBS-16`** | MEDIUM | proceso: costuras `object.__new__` duplican el estado del worker | **ABIERTA** |
| **`OBS-22`**, `OBS-19`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5` | — | cola de deuda vigente | **ABIERTAS** |

**Límite declarado:** este documento es un **diseño**; no es evidencia de operación y **no sustituye** la
ventana PAPER real.
