# Evidencia `v2.88.171-beta` — el expediente se publica para auditoría externa

## 1. Qué publica este sello

**Acto nuevo de publicación documental.** No es un sello de corrección ni de funcionalidad: no
cambia motor, decisión, contrato HTTP, UI ni migraciones. Su único propósito es que un **auditor
externo** tenga un **objeto publicado** (`v2.88.171-beta`), unas **notas de Release** y un **punto
de entrada** al expediente de `.170`, sin tener que conocer de antemano el nombre de la rama.

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ código = 0`** salvo los literales `meta.bump`.
- **Contrato HTTP sin cambio** · **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Tag `v2.88.171-beta`** (anotado, unsigned) sobre el commit del re-anclaje del pin.
- **No enmienda el acta de `.170`**: la deja válida para su fecha y su objeto y añade encima otro
  acto, con otro propósito. `v2.88.169-beta` (`d31df9b3` → `3ce94048`) y `v2.88.170-beta`
  (`3e794841` → `babfe228`) quedan **intactos**.
- **Bump** `2.11.170-beta` → `2.11.171-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

## 2. Qué NO publica ni certifica

| No certifica | Por qué |
| --- | --- |
| **Rentabilidad** | Publicar el expediente no añade evidencia operativa. AUTO sigue **OFF** y PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`). |
| **Exactitud del P&L neto** | `P2-03` sigue **abierto**: el P&L no realizado es bruto de comisiones. |
| **Valoración multidivisa completa** | `P2-11` sigue **abierto**: los totales suman importes sin conversión. |
| **Reproducibilidad del typecheck en clon limpio** | `R-170-1` sigue **abierto**: `pnpm typecheck` no es reproducible sin generar Prisma. |
| **Alineación de `main`** | `origin/main` = `26250187` con `package.json` en `2.11.160-beta`. Este acto **no** abre PR ni fusiona. |

Tampoco re-certifica `.169` ni `.170`: sus CI, sus dictámenes y sus actas se citan, no se rehacen.

## 3. Cómo obtiene el objeto un auditor externo

El repositorio es **público**. Un clon por defecto entrega `main`, que **no** contiene este
expediente ni los sellos `.161`–`.170`.

```bash
# Opción A — el objeto certificado, exacto y sin rama
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git fetch --tags
git checkout v2.88.171-beta

# Opción B — el expediente completo, nombrando la rama
git clone --branch ui/auto-hold-provenance-2026-10-28 https://github.com/jvelasca/Bolsa_V1.git
```

Punto de entrada único: [`entrega-auditoria-externa-v2.88.171-beta-2026-10-28.md`](../../entrega-auditoria-externa-v2.88.171-beta-2026-10-28.md).

## 4. Ficheros

| Capa | Ficheros |
| --- | --- |
| Bump | `package.json` (raíz) + `meta.bump` de `v2_87`, `v2_89`…`v2_100` (el literal congelado `2.11.0-beta` de `v2_87` **no** se toca) |
| Pin | `scripts/lib/window-forward.mjs` (`WINDOW_CONFIG`) |
| Docs | `CHANGELOG.md`, `PROJECT_STATE.md`, este README, `entrega-auditoria-externa-v2.88.171-beta-2026-10-28.md` |

Ningún fichero bajo `apps/web`, `packages/`, `.github/` ni `migrations/` cambia por motivo funcional:
la única diferencia en `apps/` son los `meta.bump` de los CLIs de evidencia.

## 5. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:test` | **50 passed** |
| `pnpm window:freeze` | **`freeze OK`** tras el re-anclaje |
| `pnpm typecheck` | ejecutado en local sobre este árbol (con Prisma generado); `R-170-1` sigue abierto para el clon limpio |
| `prettier --check` sobre los ficheros tocados | sin diferencias |
| `Release tag CI` | ver §7 (identidad del run) |

Las suites completas (`web`, `shared`, `pytest`) las ejecuta el `Release tag CI` del tag; este
documento **no** adelanta cifras que no se hayan medido.

## 6. Límites declarados

- **AUTO OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`**: este sello **no la mueve**.
- El bump mueve `apps`, así que el pin PAPER se re-ancla **después** del commit del sello; los días
  anteriores al re-anclaje quedan **`STALE`** y no se reinterpretan.
- Este acto **no** cierra hallazgos: `R-170-1`, `P2-03`, `P2-11`, `P2-05…P2-12` y los `P3` siguen
  abiertos.
- Publicar el expediente **no** eleva la calidad de la evidencia: la coherencia interna del corpus
  `.170` se aceptó en su acta y **no** se re-audita aquí.

## 7. Publicación (POST-TAG)

| Dato | Valor |
| --- | --- |
| Tag anotado | `v2.88.171-beta` |
| Objeto de tag | _pendiente de medición POST-TAG_ |
| Commit | _pendiente de medición POST-TAG_ |
| `Release tag CI` | _pendiente de medición POST-TAG_ |
| GitHub Release | _pendiente de medición POST-TAG_ |

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El sello no cambia el producto | `git diff --stat v2.88.170-beta^{} v2.88.171-beta^{}` solo contiene `package.json`, los 13 scripts, `CHANGELOG`, `docs/` y `scripts/lib/window-forward.mjs` |
| 2 | Los sellos anteriores no se mueven | `git rev-parse 'v2.88.169-beta^{}'` = `3ce94048…` y `'v2.88.170-beta^{}'` = `babfe228…` |
| 3 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 4 | El pin casa con el árbol del tag | `pnpm window:freeze` ⇒ `freeze OK`; en otro caso el job `shared` del CI del tag falla |
| 5 | `main` no está alineado | `git show origin/main:package.json` sigue en `2.11.160-beta` |
| 6 | El expediente no está en `main` | `git ls-tree -r --name-only origin/main docs/engineering \| grep entrega-auditoria-externa` sin salida |
