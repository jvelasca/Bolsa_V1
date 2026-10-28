# Acta de cierre documental — `v2.88.170-beta` (dictamen final)

> **AsOf:** 2026-10-28 · **Rama:** `ui/auto-hold-provenance-2026-10-28` (**no** `main`) · **Commit del corpus:**
> `bf1433e7` · **Objeto certificado:** tag anotado `v2.88.170-beta` (objeto `3e7948417c22bf9e767848331fe0d57fc2154e98`
> → commit `babfe228f9d81eb2b18be787465af588b5ff170b`), **intacto**.
> **Naturaleza:** **acto de aceptación documental** POST-TAG, read-only sobre el sello. No es una re-auditoría, no
> reabre `v2.88.169-beta` (`d31df9b3` → `3ce94048`), no modifica código, CI, migraciones, `package.json`, tags ni el
> pin PAPER, y **no abre PR ni merge a `main`**.
> **Veredicto:** **cierre documental aceptado**, sin certificación financiera. Se aceptan `P2-01` y `P2-02` en el
> alcance de representación y control de datos; `R-170-1`, `P2-03` y `P2-11` quedan **abiertos**.

---

## 0. Procedencia de la aceptación (atribución)

Esta acta **no** es una auditoría independiente. Quien firma **acepta sobre la evidencia aportada** en la entrega
del agente y **no ha repetido ahora, por su cuenta, las consultas a GitHub**. La distinción se declara por escrito
porque el valor probatorio de cada afirmación no es el mismo, y confundirlos convertiría una cita en una medición.

| Afirmación | Procedencia | ¿Re-verificada al firmar? |
| --- | --- | --- |
| `bf1433e7` = **4 ficheros**, `+269/−17` | Medido en esta rama (`git show --stat bf1433e7`) | **Sí** |
| El diff es **solo `docs/`** (sin `apps/`, `packages/`, `.github/`, `package.json`, `CHANGELOG`) | Medido en esta rama | **Sí** |
| Identidad del tag: objeto `3e794841…` → commit `babfe228…` | Medido en esta rama (`git rev-parse 'v2.88.170-beta^{tag}'` / `^{}`) | **Sí** |
| `v2.88.169-beta` inmóvil (`d31df9b3` → `3ce94048`) | Medido en esta rama | **Sí** |
| El commit documental **no** dispara CI (filtro de `paths`) | Leído en `.github/workflows/`: `frontend-ci`, `python-ci`, `fase2-scientific` y `optimize-lab` filtran por código; `release-tag-ci` dispara **solo** por push de tag `v*`. Las dos únicas rutas `docs/` del filtro son ficheros concretos (`docs/engineering/research-lifecycle.md`, `docs/adr/018-fase2-evidence-store-v0.md`) | **Sí** (ficheros, no runs) |
| El dictamen técnico está publicado y enlazado desde **tres** puntos | Medido en esta rama (`git grep dictamen-tecnico-v2.88.170`) | **Sí** |
| `Release tag CI` [`40727162474`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40727162474) **verde**, 14 jobs `success`, `certify` `GREEN` | **Evidencia aportada** en la entrega | **No** |
| `replay-repro` ⇒ **`REPRODUCIDO`** | **Evidencia aportada** | **No** |
| **823** enlaces relativos comprobados, **0** rotos | **Evidencia aportada** (comunicada; no consta como artefacto en el árbol) | **No** |
| Recuentos de suites citados (`web` 2539, `shared` 861, `typecheck` 4/4, `window:freeze` OK, …) | **Evidencia aportada** en la entrega y en [`evidence/v2.88.170`](./evidence/v2.88.170/README.md) | **No** |

Consecuencia práctica: lo aceptado aquí es la **coherencia interna del expediente** y la **identidad del objeto**
—ambas comprobables con los comandos de §6—; lo relativo a los **runs de GitHub** se acepta **como evidencia
aportada**, no como medición propia de esta firma.

---

## 1. Resultado por ámbito

| Ámbito | Dictamen |
| --- | --- |
| **Diff documental** | **Correctamente delimitado**: 4 ficheros, `+269/−17`, todos bajo `docs/engineering/` |
| **Enlaces relativos** | Verificación **remota comunicada**: 823 comprobados, 0 rotos (evidencia aportada, §0) |
| **Dictamen técnico** | **Publicado y enlazado** desde los tres puntos declarados: [`PROJECT_STATE.md`](./PROJECT_STATE.md) (bloque del sello), [`audit-pack`](./audit-pack-v2.88.170-beta-2026-10-28.md) (§2, fila 7) y [`evidence/v2.88.170/README.md`](./evidence/v2.88.170/README.md) |
| **CI del commit documental** | **Sin ejecución**, conforme al filtro de rutas: los workflows filtran por `apps/**`, `packages/**`, `package.json`, `pnpm-lock.yaml`, etc.; las **dos** únicas rutas `docs/` que aparecen en un filtro son ficheros concretos —`docs/engineering/research-lifecycle.md` y `docs/adr/018-fase2-evidence-store-v0.md`— y **ninguna** cubre este corpus; `release-tag-ci` dispara **solo** por push de tag `v*` |
| **Identidad del tag `.170`** | Se mantiene `babfe228…` (objeto `3e794841…`), con CI verde **reportado** |
| **`P2-01` y `P2-02`** | **Aceptados** en el alcance de representación y control de datos (un P&L no medido no se colorea como ganancia; «Controlado» exige sus tres componentes medidos) |
| **`R-170-1`** | **Abierto** — `pnpm typecheck` no reproducible en un clon limpio sin generar Prisma |
| **`P2-03` y `P2-11`** | **Abiertos** — bases financieras mezcladas y ausencia de conversión de divisa en los totales |

Los cuatro límites de §4 del [dictamen técnico](./dictamen-tecnico-v2.88.170-beta-2026-10-28.md) se conservan sin
rebaja: esta acta **no** los reduce, **no** los absorbe en el CI verde y **no** los convierte en aceptados por
omisión.

---

## 2. Dos límites que quedan fijados

### 2.1 La evidencia no está en `main`

El corpus documental —este acta, el dictamen técnico, el audit pack, la respuesta a la auditoría y la auditoría
independiente— vive **solo** en `ui/auto-hold-provenance-2026-10-28`. Un clon por defecto del repositorio **no**
obtiene este corpus.

- La decisión es **válida como estrategia de trabajo en una rama**, y ese es su alcance declarado.
- El dictamen **no** debe describirse como disponible en la rama principal, ni como accesible desde el flujo
  ordinario de clonación (`git clone https://github.com/jvelasca/Bolsa_V1.git` ⇒ `main`, sin este material).
- Obtenerlo exige nombrar la rama de forma explícita:

```bash
git clone --branch ui/auto-hold-provenance-2026-10-28 https://github.com/jvelasca/Bolsa_V1.git
```

- Que la evidencia no esté en `main` **no invalida** el dictamen técnico del sello: el objeto certificado
  (`babfe228`) y su CI son independientes de dónde se publique la documentación. Lo que **no** puede afirmarse es
  que el cierre documental forme parte del flujo ordinario.

### 2.2 El sello no certifica la operativa financiera

`Release tag CI` verde y `replay-repro` ⇒ `REPRODUCIDO` **no** demuestran:

- **rentabilidad** — `replay-repro` mide reproducibilidad de la **decisión**, no resultado económico;
- **exactitud del P&L neto** — el P&L no realizado es **bruto** de comisiones (`P2-03`, abierto);
- **valoración multidivisa completa** — los totales suman importes sin conversión (`P2-11`, abierto).

Lo aceptado es la **honestidad de la representación** sobre lo medido y lo ejecutado. El **contenido** de las
cifras y la **evidencia operativa** siguen sin cerrarse con este acto.

---

## 3. Estado de cierre

**Cierre documental aceptado.** El commit `bf1433e7` documenta el dictamen **sin alterar el código ni el sello
`.170`**, según el diff aportado y comprobado en §0.

> **Sin re-sello · Sin modificación del pin PAPER · Sin merge a `main` · AUTO OFF · PAPER `INCONCLUSIVE`
> (0/2 episodios, 0/32 ciclos).**

Esos cinco invariantes no son una descripción de intención: son el estado verificado del árbol y del remoto al
firmar, y cualquiera de ellos que cambiara exigiría **un acto nuevo**, no una enmienda de esta acta.

---

## 4. Trabajos separados

`R-170-1`, `P2-03` y `P2-11` se abordan **como trabajos separados**, sin reabrir el tag por defecto y sin
reinterpretar este cierre como su resolución.

| Hallazgo | Qué exige | Qué **no** exige |
| --- | --- | --- |
| **`R-170-1`** | Reproducibilidad del entorno de instalación: generar Prisma en el camino de `typecheck` o documentar el paso como precondición explícita | No exige mover el tag ni re-certificar `babfe228` |
| **`P2-03`** | Decidir y ejecutar la etiqueta de base financiera (bruto/neto de comisiones) en el P&L no realizado | No exige cambiar el motor |
| **`P2-11`** | Conversión de divisa en `marginUsed` y en los totales de cartera | No exige cambiar el motor |

**A fecha de esta acta no se ha abierto ningún issue** para estos tres hallazgos: la decisión es mantener **solo
registro documental**. Si más adelante se abren, deberán enlazar a esta acta y al §4 del dictamen técnico, no
sustituirlos.

---

## 5. Alcance y no-cambios

- **No** modifica `apps/`, `packages/`, `.github/`, `package.json`, `pnpm-lock.yaml`, `CHANGELOG`, migraciones ni
  `operability_runs/`.
- **No** crea, mueve, anota ni re-firma tags: `v2.88.170-beta` y `v2.88.169-beta` quedan **byte-idénticos**.
- **No** mueve el pin PAPER; los días previos siguen `STALE`.
- **No** reescribe el [dictamen técnico](./dictamen-tecnico-v2.88.170-beta-2026-10-28.md), el
  [audit pack](./audit-pack-v2.88.170-beta-2026-10-28.md), el
  [acta de auditoría](./auditoria-ui-operativa-profunda-2026-10-28.md), la
  [respuesta](./respuesta-auditoria-ui-operativa-2026-10-28.md) ni la
  [auditoría independiente](./auditoria-independiente-v2.88.170-beta-2026-10-28.md): se **añade encima**.
- **No** abre ni cierra `R-170-1`, `P2-03`, `P2-11`, `P2-05…P2-12` ni los `P3`.
- **No** abre PR ni fusiona a `main`.

---

## 6. Cómo se falsa esta acta

Cada afirmación de §0–§3 se puede **romper** con un comando:

```bash
# §1 — el diff es de 4 ficheros, +269/−17 y solo docs/
git show --stat bf1433e7

# §1 — el diff no toca código ni CI
git diff --name-only bf1433e7~1 bf1433e7 | grep -v '^docs/'   # sin salida

# §1/§2 — el tag no se ha movido (sello intacto)
git rev-parse 'v2.88.170-beta^{tag}'    # 3e7948417c22bf9e767848331fe0d57fc2154e98
git rev-parse 'v2.88.170-beta^{}'       # babfe228f9d81eb2b18be787465af588b5ff170b
git rev-parse 'v2.88.169-beta^{}'       # 3ce94048b45112d66eb6e3614f2e81676a41be97

# §1 — el dictamen está enlazado desde los tres puntos declarados
git grep -l 'dictamen-tecnico-v2.88.170' -- docs | wc -l   # >= 3

# §2.1 — esta acta no está en main
git ls-tree -r --name-only origin/main docs/engineering | grep acta-cierre-documental   # sin salida

# §2.1 — el corpus sí está en la rama (y solo nombrándola)
git ls-tree -r --name-only origin/ui/auto-hold-provenance-2026-10-28 \
  docs/engineering/acta-cierre-documental-v2.88.170-beta-2026-10-28.md

# §1 — no hay PR abierta para esta rama
gh pr list --head ui/auto-hold-provenance-2026-10-28 --state all
```

Si alguno de estos comandos discrepa, **esta acta es falsa en ese punto** y debe corregirse con un acto nuevo,
no reescribiendo el pasado.

---

## 7. Recomendación

Mantener `ui/auto-hold-provenance-2026-10-28` como **expediente documental trazable** y abordar `R-170-1`,
`P2-03` y `P2-11` como trabajos separados, **sin reabrir el tag por defecto** y **sin confundir cierre documental
con certificación financiera**.
