# Auditoría externa independiente — `v2.88.169-beta`: cierre del seguimiento técnico

> **Tipo:** acta de **cierre** de una auditoría **independiente**, contrastada por el auditor directamente
> en GitHub (repositorio, workflows, jobs y artefactos publicados), no sobre la narrativa de los documentos.
> **Objeto auditado:** tag anotado **`v2.88.169-beta`** → commit `3ce94048` · **Versión:** `2.11.169-beta` ·
> **AsOf:** 2026-10-28 · **Alembic head:** `058_estudio_daily_proposals` (**sin migración**) ·
> **Tag:** **unsigned** (anotado, sin firma GPG).
> **Veredicto:** **seguimiento técnico CERRADO** con CI verde confirmado; **0 motivo para reabrir el P2 de
> fechas**; **AUTO y rentabilidad NO certificados**.
> **Precisión del veredicto:** un cambio **test-only** y un `replay` reproducido **no** demuestran que AUTO
> produzca operaciones rentables, ni que la validación PAPER esté superada.
> **Naturaleza de este registro:** **docs-only, POST-TAG** — **sin bump, sin mover el tag, sin tocar
> `src`/tests/`package.json`/workflows/migraciones**. No forma parte del árbol publicado por el tag.

---

## 0. Resumen ejecutivo

```text
v2.88.165  último tip certificado antes de este bloque
   ↓ (2.11.166, .167, .168 existen en el árbol, sin tag ni audit pack)
3f25b2b2   fix(auto): fecha ISO imposible se conserva cruda (P2 de fechas)
0b6f68f3   test(auto): la matriz cubre abril también en el instante   (W-169-1)
c04b9e3c   re-anclaje del pin PAPER  →  run 40677571486  ROJO (S5)   [conservado]
1f084f18   test(e2e): el teardown del S5 no confunde carrera con residuo (W-169-2)
3ce94048   re-anclaje del pin PAPER  ← TAG  →  run 40680699713  VERDE (12/12)
c2494c7e   POST-TAG: identidad, run y artefacto citados en el pack
```

El sello presenta **trazabilidad coherente** y un **tratamiento correcto del desvío de CI**: el primer rojo
queda registrado, la causa se atribuye a una **carrera de persistencia en el teardown de pruebas** y el verde
se acredita **sobre el árbol corregido**. El intento fallido **no se borra** ni se reinterpreta como si nunca
hubiera ocurrido.

**Regla de la casa aplicada:** ninguna cifra sin comando; un hueco se declara **`NO MEDIDO`**, jamás un `0`
fingido.

---

## 1. Identidad y CI — contrastados en GitHub

| Elemento | Valor verificado |
| --- | --- |
| Tag (anotado, **unsigned**) | `v2.88.169-beta` |
| Objeto de tag | `d31df9b3f1bfbdae9c5f15d99ddf1280d53f425a` |
| Commit apuntado | `3ce94048b45112d66eb6e3614f2e81676a41be97` |
| CI del tag | [run `40680699713`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40680699713) — **`success`**, `run_attempt: 1`, mismo `headSha` |
| Gates obligatorios | **12/12** en `success` (incluido `playwright (integrated AUTO S5)` y `certify`) |
| Certificación agregada | [artefacto `release-tag-ci-summary`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40680699713/artifacts/12812694195) con `status: GREEN` y los 12 jobs en `success` |
| Primer intento (rojo, **conservado**) | [run `40677571486`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40677571486) — **`failure`** sobre `c04b9e3c` |

- El tag anotado existe y apunta al commit exacto citado; la identidad se comprueba con
  `git rev-parse v2.88.169-beta^{commit}`, **nunca** leyendo un sha escrito en un documento.
- El run verde corresponde al **mismo SHA** que el tag, con `run_attempt: 1` (no hay reintento que oculte un
  rojo).
- `playwright (integrated E2E, opt-in)` figura como **`skipped`**, tal como declara el
  [audit pack](./audit-pack-v2.88.169-beta-2026-10-28.md); **no** es uno de los 12 gates obligatorios.
  `playwright (live AUTO daily chain)` corrió en el workflow y terminó en `success`, pero **no** está en el
  `needs` de `certify`: su verde es **informativo**.
- El primer run figura **realmente** como `failure` y corresponde al **SHA anterior** `c04b9e3c`: **12** jobs
  en `success`, `playwright (integrated AUTO S5)` en **`failure`** y `certify` arrastrando el fallo. No se ha
  ocultado el rojo ni se ha presentado ese intento como verde.

**Conclusión §1:** integridad del release **correcta** — identidad del tag, commit, pin y CI verde
corresponden al **mismo árbol publicado**.

---

## 2. Revisión de las dos correcciones

### 2.1 `W-169-1` — fechas ISO imposibles: **cerrado**

La prueba añadida en
[`auto-hold-declarations.test.ts`](../../apps/web/src/features/auto/auto-hold-declarations.test.ts) cubre
abril en `formatHoldInstant`, **con y sin hora**, y comprueba con control negativo que `2026-04-31` **no** se
presente como una fecha normalizada de mayo. La implementación compartida
([`auto-hold-declarations.ts`](../../apps/web/src/features/auto/auto-hold-declarations.ts), `hasIsoDayPrefix`
+ `isoDay`) **no se modifica** en este sello: el hueco era de **matriz de regresión**, no de comportamiento.

### 2.2 `W-169-2` — teardown de AUTO S5: **corrección aceptada; CI verde**

El fixture E2E incorpora `probeAccountUntilGone`, con **sondeos acotados** de seis intentos separados por
250 ms. El cambio permite **observar el borrado tras el commit de la sesión**, en lugar de declarar un
residuo por una única lectura inmediata.

La distinción importante es que **no se elimina el fallo por residuo real**: si la cuenta sigue existiendo al
agotarse los intentos, el teardown **conserva la posibilidad de fallar**. El job S5 verde en el nuevo run
confirma que la suite pasó sobre el árbol corregido; **no** demuestra por sí solo que todos los escenarios
posibles de carrera estén cubiertos.

**Conclusión §2:** los sondeos adicionales resuelven una **carrera legítima** sin rebajar el criterio de fallo
por residuos reales.

---

## 3. El rojo y Yahoo Finance

La explicación del rojo es **técnicamente plausible** y queda documentada con la secuencia medida en el
artefacto de timings:

```text
DELETE /api/accounts/{id} → 204 No Content
GET    /api/accounts/{id} → 200 OK            (4 ms después)
```

La dependencia con `yield` —la sesión de la API comitea al **salir** de la dependencia— puede retrasar el
commit hasta **después** de la respuesta, de modo que un `204` no prueba por sí solo que la fila ya no exista
en una lectura inmediata.

También es correcto **mantener separado** el problema de **Yahoo Finance**: un `sync` con **cero barras** es
una **precondición de datos externos**, no evidencia automática de un defecto del motor. Debe seguir visible
como **limitación** y **no** convertirse silenciosamente en un test omitido.

---

## 4. Alcance real del sello

El diff entre `3f25b2b2` y el commit del tag muestra cambios en:

- la **prueba unitaria** (`auto-hold-declarations.test.ts`),
- el **fixture E2E** (`gp-v288-s5-auto-dia-d-bridge-integrated.spec.ts`),
- los **bump de versión** (`package.json` + `meta.bump`),
- los **documentos** (`CHANGELOG.md`, `PROJECT_STATE.md`, audit pack, evidence),
- el **re-anclaje del pin PAPER** (`scripts/lib/window-forward.mjs`).

Por tanto, la expresión **test-only** es **correcta respecto al comportamiento funcional de la aplicación**,
pero **no** significa que todo el diff se limite a un único fichero de pruebas.

---

## 5. Dictamen por área

| Área | Dictamen |
| --- | --- |
| Corrección de fechas en UI | **Cerrada** |
| Carrera del teardown E2E | **Corrección aceptada; CI verde** |
| Motor y reglas de decisión | **Sin cambios funcionales declarados** |
| Contrato HTTP | **Sin delta declarado**; `contract:check` verde |
| Migraciones | **Sin migración nueva**; head `058_estudio_daily_proposals` |
| Firma del tag | **Sin firma GPG**; objeto anotado `unsigned` |
| AUTO y rentabilidad | **No certificados** por este sello |

---

## 6. Una precisión documental (PRE-TAG / POST-TAG)

El **tag** contiene la versión del audit pack **anterior** a la incorporación de la identidad y el resultado
definitivo del propio tag. La rama `ui/auto-hold-provenance-2026-10-28`, en `c2494c7e`, contiene la versión
**POST-TAG** completada.

Es una distinción **válida**, siempre que al auditar se use:

| Para | Fuente |
| --- | --- |
| Datos **posteriores** al tag (identidad, run, artefacto, recuentos del CI) | el documento de la **rama** |
| El **código publicado** | el **SHA fijado** `3ce94048b45112d66eb6e3614f2e81676a41be97` |

---

## 7. Límites del dictamen

- La revisión se apoya en el **repositorio, los workflows y los artefactos publicados**; las cifras de jobs y
  el contenido de los documentos son **evidencia del sello**, verificada contra GitHub.
- **No** demuestra que AUTO produzca operaciones rentables ni que PAPER haya superado la validación.
- Según los límites del propio sello: **AUTO continúa OFF**, **PAPER es virtual**, la ventana permanece
  **`INCONCLUSIVE`** (`0/2` episodios, `0/32` ciclos) y los días anteriores al reanclaje siguen **`STALE`**.
- Los días previos al reanclaje del pin **no** son medición válida: la ventana arranca en el primer día de
  sesión posterior al tag.
- **No se ha demostrado rentabilidad** ni se autoriza inferir que la aplicación esté lista para operar con
  dinero real.

---

## 8. Dictamen final y siguiente paso

**Se da por cerrado el seguimiento técnico de `v2.88.169-beta` con CI verde confirmado.** La evidencia
independiente concuerda con la identidad publicada, los gates obligatorios y la conservación del intento
fallido. **No** hay, en lo revisado, motivo para reabrir el P2 de fechas.

**Siguiente paso recomendado:** **conservar este sello sin más cambios** y, cuando se retome la validación
PAPER, **ejecutar la ventana sobre el pin vigente** y reunir evidencia suficiente para los **dos episodios** y
los **32 ciclos** requeridos.

---

## 9. Fuentes

| # | Fuente | Qué responde |
| --- | --- | --- |
| 1 | [`audit-pack-v2.88.169-beta-2026-10-28.md`](./audit-pack-v2.88.169-beta-2026-10-28.md) | Identidad, CI, deltas, límites y falsabilidad del sello (versión POST-TAG en la rama) |
| 2 | [`evidence/v2.88.169/README.md`](./evidence/v2.88.169/README.md) | Qué publica el sello, hallazgo cerrado, corrección del teardown y verificación medida |
| 3 | [Run `40680699713`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40680699713) | CI verde del tag, 12/12 gates, artefacto `GREEN` |
| 4 | [Run `40677571486`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40677571486) | El rojo previo, sobre `c04b9e3c`, conservado |
| 5 | [`CHANGELOG.md` §`2.11.169-beta`](../../CHANGELOG.md) | Nota de release: naturaleza, deltas y verificación |
| 6 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) | Estado vivo y qué queda abierto |

> **Nota:** este acta **registra** el dictamen del auditor independiente; **no** lo sustituye ni amplía su
> alcance, y **no** modifica el tag, el código ni el audit pack del sello.
