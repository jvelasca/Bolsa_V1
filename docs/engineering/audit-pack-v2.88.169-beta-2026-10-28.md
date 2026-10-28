# Audit pack — `v2.88.169-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-28 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.169-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** sello de **seguimiento**. **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **SIN migración nueva** · cambio de código **test-only**. Tag **unsigned** (anotado, sin firma GPG).
>
> **Estado (PRE-TAG → POST-TAG):** este documento se escribe **antes** del tag y su §1/§4 se completan en el commit **POST-TAG**, porque un tag no puede citar su propio objeto ni el resultado de su propio CI. La identidad real se verifica siempre con `git rev-parse v2.88.169-beta^{commit}`, **nunca** leyendo un sha escrito en un documento.

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.169-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout <SHA_DEL_SELLO>
```

> El `<SHA_DEL_SELLO>` exacto se cita en §1 (commit **POST-TAG**).

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.169-beta` — **unsigned** |
| **Objeto de tag** | se cita en el commit POST-TAG |
| **Commit apuntado** | se cita en el commit POST-TAG (**re-anclaje del pin** PAPER) |
| **Commit del sello** | se cita en el commit POST-TAG (prueba + bump + docs) |
| **Base (tag anterior)** | `v2.88.165-beta` → `00f321bb6e05332b677e7c880ba23442af9486cf` |
| **Punto de partida de la rama** | `a982f45c` (**3 commits** de distancia: `778c00a0`, `f47d548b`, `3f25b2b2`; **18 ficheros**) |
| **Versión monorepo** | `2.11.169-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `058_estudio_daily_proposals` (**sin migración nueva**) |
| **Firma** | **unsigned** (anotado, sin GPG) |
| **Rama** | `ui/auto-hold-provenance-2026-10-28` |

> **Nota de continuidad (léela antes de auditar).** Las versiones `2.11.166-beta`, `2.11.167-beta` y
> `2.11.168-beta` **existen en el árbol** con su `CHANGELOG`, su evidencia y sus commits
> (`2b9cbfd9`, `3676d644`, `778c00a0`, `f47d548b`, `a982f45c`), pero **no se publicaron como tag ni
> como audit pack**: el último tip certificado antes de este sello es `v2.88.165-beta`. Este pack
> **no** retrocertifica `.166`–`.168`; declara que este sello es el primer tag desde `.165` y que su
> árbol **incluye** el trabajo de ese bloque, con sus pruebas, su `CHANGELOG` y su evidencia. Un
> auditor que quiera el tip intermedio puede fijar `a982f45c`, pero **no** encontrará un run de CI de
> tag para él.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.169-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | ver §1 (commit POST-TAG) |
| Ver el árbol en la web | [tree/v2.88.169-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.169-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.169/README.md`](./evidence/v2.88.169/README.md) | Qué publica el sello, el hallazgo que cierra, la prueba añadida, verificación medida y límites |
| 2 | [`CHANGELOG.md` §`2.11.169-beta`](../../CHANGELOG.md) | Nota de release: naturaleza, deltas, verificación |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.169-beta`) | Estado vivo y qué queda abierto |
| 4 | [`auto-hold-declarations.test.ts`](../../apps/web/src/features/auto/auto-hold-declarations.test.ts) | La matriz de regresión: febrero **y** abril, con hora y sin hora, en las dos funciones |
| 5 | [`auto-hold-declarations.ts`](../../apps/web/src/features/auto/auto-hold-declarations.ts) | `hasIsoDayPrefix` + `isoDay`: la regla compartida que **no** se tocó |
| 6 | [`evidence/v2.88.168/README.md`](./evidence/v2.88.168/README.md) | Contexto inmediato: el bloque `.166`–`.168` cuyo árbol entra aquí |

---

## 4. CI público (citable)

**`Release tag CI` del tag:** se cita en el commit **POST-TAG** (run id, `headSha`, duración,
`run_attempt` y artefacto `release-tag-ci-summary` con `status: GREEN`).

**Qué bloquea el sello.** `certify` agrega exactamente **12** jobs
(`[release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml), `needs` de `certify`):
`security`, `shared`, `spine`, `frontend`, `python`, `playwright-mock`,
`playwright-integrated-auto-s5`, `playwright-integrated-axe`, `lifecycle-pg`, `replay-repro`,
`dr-verify`, `a7-gate`. Los **12** deben estar en `success`. `playwright (integrated E2E, opt-in)`
queda `skipped` **por diseño** y **no** certifica; `playwright (live AUTO daily chain)` corre en el
workflow pero **no** está en `needs`: su verde es informativo.

**Qué se espera de este run en concreto.** El sello es test-only: los jobs que **deben** moverse
son `frontend` (una prueba más en `auto-hold-declarations.test.ts`) y `shared`
(`window:freeze` ⇒ `freeze OK (<commit del tag>)` tras el re-anclaje). El resto debe seguir verde
sin cambios de comportamiento; `replay-repro` debe seguir dando **`REPRODUCIDO`** con el mismo
`sha256` (`Δ decisión = 0` medido por el CI).

---

## 5. Qué **certifica** esta versión

1. **El defecto de normalización de fechas ISO imposibles está cerrado** (hallazgo **P2 de fechas**,
   commit `3f25b2b2`): `2026-02-31` y `2026-04-31` se conservan como **texto original**, no se
   presentan como días normalizados; el parseo alternativo se mantiene para formatos no ISO
   (`2026/09/30`); el filtro por día usa **exclusivamente** `barTimestamp` validado; `withoutBarDay`
   conserva su alcance (sólo se calcula cuando se solicita un día).
2. **La matriz de regresión es simétrica**: febrero y abril, sello **con hora** y sello **de sólo
   día**, en `formatHoldInstant` **y** en `formatHoldBarDay`. El caso de abril en `formatHoldInstant`
   es el que añade este sello, con control negativo (`not.toContain("may")`).
3. **No hay cambio de comportamiento**: la implementación (`hasIsoDayPrefix`, `isoDay`) es
   **idéntica** a la de `3f25b2b2`. El sello es **test-only** en código de producto.
4. **Bump coherente**: `2.11.169-beta` en `package.json` y en los **13** `meta.bump`
   (`v2_87`, `v2_89`…`v2_100`), con el literal congelado `2.11.0-beta` del replay de `v2_87`
   **intacto** (`test_dia_d_bump_guard`, **2 passed**).
5. **Contrato HTTP sin delta**: `contract:check` verde.
6. **Sin migración**: `head` sigue `058_estudio_daily_proposals`.
7. **Freeze re-anclado**: el pin PAPER se re-ancla al árbol del sello **antes** del tag, de modo que
   `window:freeze` del job `shared` corre **fail-closed** sobre el árbol correcto.

**Deltas:** `Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
2. **La ventana PAPER sigue `INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`). El re-anclaje del pin
   deja **`STALE`** los días anteriores: la medición válida arranca en el primer día de sesión
   posterior al tag. Este sello **no** mueve la ventana ni **demuestra rentabilidad**.
3. **Evidencia E1** (hermética): la prueba fija el **formato**, no la fuente. Que un `barTimestamp`
   llegue imposible es un defecto del **productor**; aquí se garantiza que la UI **no lo maquilla**.
4. **La verificación local es dirigida** (vitest del módulo, `typecheck`, `lint`, guardián de bump,
   `window:test`, `contract:check`). Las suites completas las ejecuta el CI del tag; este pack cita
   **lo que el run diga**, no una estimación.
5. **`.166`–`.168` no se retrocertifican**: entran como árbol dentro de este sello (ver §1). Si el
   auditor quiere un tip intermedio, `a982f45c` es auditable por código y pruebas, pero **sin** run
   de CI de tag.
6. **Un CI verde no certifica una versión de producto**: certifica **este árbol** con estas pruebas.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | El tag apunta al commit citado y desciende de `v2.88.165-beta` (`00f321bb`). | `git cat-file -p v2.88.169-beta` / `git rev-parse` da otro commit o linaje. |
| 2 | `2.11.169-beta` es la versión del árbol y los **13** `meta.bump` coinciden. | `package.json` muestra otra versión o `test_dia_d_bump_guard` falla. |
| 3 | Abril no se normaliza al 1 de mayo en `formatHoldInstant`. | el caso `un mes de 30 días no se desborda al mes siguiente` falla si la función vuelve a formatear `new Date(...)`. |
| 4 | El sello `2026-04-31` (sin hora) se conserva crudo. | el mismo caso falla si se pinta `01 may 2026`. |
| 5 | La regla es compartida, no duplicada. | `hasIsoDayPrefix`/`isoDay` desaparecen o divergen entre las dos funciones de formato. |
| 6 | El cambio es **test-only**. | `git diff 3f25b2b2 <commit-del-tag> -- apps/web/src/features/auto/auto-hold-declarations.ts` sale **vacío**. |
| 7 | Sin migración: head `058_estudio_daily_proposals`. | `alembic heads` (desde `packages/py/infrastructure`) da otro head. |
| 8 | `Δ contrato HTTP = 0`. | `pnpm --filter @bolsa/web contract:check` falla. |
| 9 | El freeze del tag es OK. | `node scripts/window-pin.mjs --check` sobre el commit del tag da `TREE_MOVED`. |
| 10 | El CI del tag es verde. | el run citado tiene algún job obligatorio en `failure`, o `certify` rojo, o el artefacto no dice `GREEN`. |
| 11 | `.166`–`.168` no están retrocertificados. | aparece un tag `v2.88.166/167/168` en `origin` sin pack ni run citado por este documento. |

---

## 8. Reproducir la verificación (local, opcional)

```bash
# La prueba del sello (la matriz simétrica)
pnpm --filter @bolsa/web exec vitest run auto-hold-declarations

# No-delta de comportamiento: la implementación no cambió en este sello
git diff 3f25b2b2 v2.88.169-beta -- apps/web/src/features/auto/auto-hold-declarations.ts

# Bump y contrato
uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm contract:check

# Gates de ventana
pnpm window:test
node scripts/window-pin.mjs --check

# Typecheck y lint del árbol
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
```

**Resultados de referencia medidos en este árbol (verificación dirigida):**
`vitest auto-hold-declarations` **49 passed / 2 ficheros** (`auto-hold-declarations.test.ts` **35**,
`auto-hold-declarations-panel.test.tsx` **14**) · `typecheck` **OK** · `lint` **0 errores / 23
avisos** (preexistentes) · `test_dia_d_bump_guard` **2 passed** · `window:test` **50 passed** ·
`contract:check` **OK**. Las cifras de las suites completas las publica el run del tag (§4).
