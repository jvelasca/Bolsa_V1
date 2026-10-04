# Evidencia `v2.88.46.1-beta` — RE-SELLO `DOCS-ONLY` DE `v2.88.46-beta`: **la cita de su CI viaja DENTRO del tag** (patrón `OBS-3`/`OBS-4`, `Δ motor = 0`)

> **Clase: re-sello de auditabilidad. ESTADO: `V2.88.46.1` CERRADO — bump `2.11.46.1-beta` aplicado, tag
> `v2.88.46.1-beta` publicado y su cita POST-TAG escrita en `main` (§6).**
> **AsOf:** 2026-10-04. **Base:** sello `v2.88.46-beta` (objeto `b728fd33`, commit `9658a5cb`).
> **Evidencia del sello funcional:** [`evidence/v2.88.46/README.md`](../v2.88.46/README.md).
> **Entrega a auditoría externa:** [`entrega-auditoria-externa-mia-v2.88.46-2026-10-04.md`](../../entrega-auditoria-externa-mia-v2.88.46-2026-10-04.md).

Este fichero existe por **una sola razón**: el sello `v2.88.46-beta` es **correcto** y su CI está **VERDE**,
pero un auditor que trabaje **sobre el tag aislado** no podía acreditarlo desde el propio objeto sellado.
Este re-sello no cambia el producto: **entrega el MISMO objeto en un formato autocontenido**.

---

## 1. El hueco que cierra (medido, no heredado)

Al auditar `v2.88.46-beta` **desde GitHub**, el objeto sellado (commit `9658a5cb`) declaraba su propia
cita como **pendiente**:

```text
- **Tag:** `v2.88.46-beta` → PENDIENTE.
- **Commits:** PENDIENTE.
```

Y, medido sobre el remoto en ese momento:

| Comprobación | Medición |
| --- | --- |
| Tag `v2.88.46-beta` empujado | **sí** → objeto `b728fd33`, commit `9658a5cb` |
| `Release tag CI` de ese tag | run [`37202334330`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37202334330) **VERDE** (§4) |
| Cita de ese run **dentro** del tag | **NO** — el commit que la escribe (`9ab04e60`) es **POST-TAG** |
| GitHub **Release** publicado | **NO** — el último Release del repo era `v2.88.32-beta` (`2.88.33`–`2.88.46` sólo tenían tag) |
| Dossier de **entrega MIA** | **NO** — la serie `v2.88.40`…`v2.88.45` sí lo tenía; `v2.88.46` no |

⇒ **Tres huecos de auditabilidad** (`OBS-3`/`OBS-4`): el tag **miente por omisión** («PENDIENTE»), la pestaña
*Releases* no lo lista y no hay dossier de entrega para el auditor externo. Los tres se cierran aquí.

---

## 2. Qué es este re-sello (y qué NO es)

**Qué es.** Un cambio **`DOCS-ONLY` + bump de versión**: el único cambio **no** documental respecto de
`v2.88.46-beta` es la cadena `meta.bump` de los CLI `v2_89`–`v2_97` y el `version` del monorepo
(`2.11.46-beta` → `2.11.46.1-beta`), obligados por `test_dia_d_bump_guard.py` (el `meta.bump` de los CLI
DÍA-D **debe** igualar el `version` del monorepo). **Ni una línea de motor, ni de gobernador, ni de
umbrales, ni de costuras.**

**Qué NO es.**

- **NO** re-escribe el tag `v2.88.46-beta`: ese tag **queda intacto** y su CI **VERDE** (patrón declarado en
  `v2.88.17`, `v2.83`; retaguear un objeto publicado está prohibido por `versioning.md` §«Qué no hacer»).
- **NO** arregla el hueco funcional del sello (`v2.88.46` no reconcilia `stopBasisMismatchR`: se **declara**,
  no se arregla). Eso sigue **P3**.
- **NO** añade línea online: el job `python` del tag debe dar el **mismo** recuento que el sello funcional
  (`4503 passed / 45 skipped`), porque lo único que cambia es una cadena de metadatos.

---

## 3. La cadena del objeto (de `v2.88.46` al re-sello)

| Paso | Commit | Qué fija |
| --- | --- | --- |
| Funcional | `20a77ded` | `dia_d_multi_sampling.py` (ledger `-v4`) + `dia_d_thesis_exit.py` (`v2`) + tests + costura inerte (`Δ motor = 0`) |
| Re-anclaje del freeze | `5ebd85aa` | pin del runner de la ventana al árbol de `20a77ded` |
| Docs del sello | `9658a5cb` | evidencia `v2.88.46` + `CURRENT_SYSTEM` + `versioning` + `CHANGELOG` ⇒ **`v2.88.46-beta`** |
| Cita POST-TAG | `9ab04e60` | cita del run `37202334330` en `main` (fuera del tag) |
| Re-sello (bump) | `734fbfbe` | `package.json` `2.11.46.1-beta` + `meta.bump` `v2_89`–`v2_97` |
| Re-anclaje del freeze | `5572399d` | pin del runner al árbol de `734fbfbe` (`apps` `5a3e7080…`, `packages` `519bcdb8…`) |
| Docs del re-sello | *(el propio commit del tag `v2.88.46.1-beta`)* | evidencia `v2.88.46.1` + entrega MIA + punteros ⇒ **`v2.88.46.1-beta`** |

**El árbol `packages` NO se mueve** (`519bcdb8…` idéntico al del sello funcional): el re-sello sólo toca
`apps/` (cadena `meta.bump`) y `docs/`. El árbol `apps` sí se mueve (`ea169f26…` → `5a3e7080…`) y por eso
el pin del runner se re-ancla, exactamente como en el sello funcional.

---

## 4. CI del sello `v2.88.46-beta` — ACREDITADO Y VISIBLE **DESDE ESTE TAG**

`Release tag CI` run **[`37202334330`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37202334330)**
(`ref=refs/tags/v2.88.46-beta`, HEAD `9658a5cb`, `event=push`, `attempt 1`, `2026-10-04T12:30:22Z` →
`12:38:39Z`): **`success`** (`GREEN` en la **primera** pasada).

| Job | Resultado |
| --- | --- |
| `security` (gitleaks) | `success` |
| `shared` (build/typecheck/test) | `success` |
| `decision-spine` | `success` (`610 passed`) |
| `frontend` (typecheck/lint/test/build + `contract:check`) | `success` (`1359 passed`) |
| `python` (ruff/imports/mypy/pytest offline) | `success` |
| `playwright` (mock E2E) | `success` |
| `lifecycle-pg` (Alembic + auth + golden restart) | `success` (todos los pasos PG verdes, **sin skips mudos**) |
| `replay-repro` (regenera el artefacto del sello) | `success` — veredicto `REPRODUCIDO` |
| `dr-verify` (batería DB_DR / TCP CI) | `success` |
| `a7-gate` (A7 C3 chaos `live_a7`, real-PG dedicada) | `success` |
| `playwright` (integrated E2E, opt-in) | `skipped` **por diseño** |
| `certify` (aggregate + artifact) | `success` |

**Job `python` del tag** (los cuatro gates con su salida literal):

```text
ruff    : All checks passed!
imports : Contracts: 4 kept, 0 broken.
mypy    : Success: no issues found in 531 source files
pytest  : 4503 passed, 45 skipped, 7 warnings in 135.74s (0:02:15)
```

**`replay-repro`** (el artefacto congelado **no** se movió ⇒ `Δ motor = 0` **confirmado por el propio job**):

```text
render           LF
bytes            3340728  (sello 3445622 · mismo contenido en LF 3340728)
sha256           1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7
VEREDICTO        REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)
```

⇒ **Cadena verificable desde este tag:** `v2.88.46-beta` → run `37202334330` → **SUCCESS**.

---

## 5. CI del re-sello `v2.88.46.1-beta` (ESTE objeto) — cita POST-TAG

**LÍMITE ESTRUCTURAL (`OBS-3`/`OBS-4`, `v2.74`–`v2.88`):** `Release tag CI` **sólo** corre al **empujar** el
tag; su resultado **no puede preexistir** a ese push. **Ningún tag puede contener su propio resultado de
CI.** Por eso la sección de cita del run del re-sello se escribe en un **commit POST-TAG** en `main`, y la
instancia de este fichero **DENTRO** del tag la lleva como **PLACEHOLDER**.

> **Nota para el auditor (leer ANTES de concluir):** si trabajas **estrictamente sobre el objeto sellado**
> `v2.88.46.1-beta` y lees aquí un «PENDIENTE», **no** concluyas «CI no acreditado». El CI del **producto**
> está acreditado en §4 (run `37202334330`, VERDE) y viaja **dentro** de este tag. El CI del **re-sello**
> (que sólo certifica que el bump de metadatos no rompe nada) se acredita en el commit POST-TAG en `main`
> inmediatamente posterior al sello.

**`Release tag CI` run del re-sello:** PENDIENTE DE TAG (se escribe en el commit POST-TAG).

---

## 6. Cita POST-TAG del re-sello `v2.88.46.1-beta`

PENDIENTE DE TAG — este apartado se completa en `main` tras empujar el tag, con el run del re-sello.

---

## 7. Gates locales del re-sello

| Gate | Resultado |
| --- | --- |
| `test_dia_d_bump_guard.py` | **1 passed** (`meta.bump` `v2_89`…`v2_97` == `package.json` `2.11.46.1-beta`) |
| `pnpm window:test` | **25/25** (freeze re-anclado al árbol `5a3e7080…`/`519bcdb8…`) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `mypy` (gate real, `--follow-imports=silent`) | sin errores (`531` ficheros) |
| `Δ src` | sólo la cadena `meta.bump` (`2.11.46-beta` → `2.11.46.1-beta`) y `package.json`; **cero** ficheros de motor |
| Migración | **SIN migración** (Alembic head `048_journal_entry_dedupe_key`) |

---

## 8. Deuda declarada

- El re-sello **no** arregla el hueco funcional de `v2.88.46` (`stopBasisMismatchR` declarado, no
  reconciliado) ni ninguno de sus límites (§4 de [`evidence/v2.88.46/README.md`](../v2.88.46/README.md)).
- **Cada tag vuelve a abrir el mismo hueco estructural:** su propio CI no puede viajar dentro de él. La
  secuencia honesta es **tag funcional → cita en `main` → (si se exige autocontención) re-sello**. Cerrar
  esto de raíz exige que `Release tag CI` publique un **Release** con el resumen del run (`certify` ya
  emite `release-tag-ci-summary.json` como artefacto): **fase futura**, no de este sello.
