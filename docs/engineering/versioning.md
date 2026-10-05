# Versionado — product / tag / package / schema / API

> **AsOf:** 2026-10-04 · **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** política. **No** bump de `package.json` en este slice.

Cinco números distintos. No son intercambiables. Una fila de docs no debe fingir que los cinco coinciden.

| Verdad      | Qué es                                                                | Dónde vive                                | Valor vigente (AsOf)                            |
| ----------- | --------------------------------------------------------------------- | ----------------------------------------- | ----------------------------------------------- |
| **Product** | Nombre de producto / slice de UX o dominio que lee el auditor         | AsOf de `CURRENT_SYSTEM.md`, relevos      | `V2.88.50-beta` (`DÍA-D-3h` + cierre PIT por día + proyección de mediciones en reservas + AUTO UI 1.0 piloto). **Absorbe `v2.88.49-beta`** (`DÍA-D-3h`: A/C `THESIS_EXIT` vs `STOP`) |
| **Git tag** | Tip certificado para auditoría / CI-by-tag                            | `git tag` · GitHub Releases               | `v2.88.50-beta` → **PENDIENTE** de sellar (implementación local; re-pipeline PostgreSQL + `replay-repro` pendientes). Anterior `v2.88.48-beta` → tag object `1e344391`, commit `149d5886` (producto funcional `814c9392`, freeze `ba8ee8e7`); **`Release tag CI` run [`37221439959`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37221439959) VERDE**; **GitHub Release** publicado. **Nota de absorción:** `v2.88.49-beta` se commiteó (`e70b23fa`) **sin tag ni medición**; se absorbe en `v2.88.50-beta` para no correr dos veces el pipeline, re-midiendo A/C sobre el universo PIT corregido |
| **Package** | Semver npm del monorepo (workspaces `@bolsa/*` pueden seguir `0.1.0`) | raíz [`package.json`](../../package.json) | `2.11.50-beta`                                  |
| **Schema**  | Migraciones de persistencia                                           | Alembic en `packages/py` / `bolsa_v1`     | head `048_journal_entry_dedupe_key` (sin pendiente) |
| **API**     | Contrato HTTP / OpenAPI si existe                                     | FastAPI · `apps/web/src/api/schema.d.ts`  | `contract:gen` al día (independiente del product) |

> **Nota de higiene (2026-10-03).** Las reglas 2–3 (abajo) se escribieron en la serie `V1.36`–`V1.48`,
> cuando el `package.json` iba **congelado** a propósito. En la práctica el monorepo lleva desde `2.11.x`
> **bumpeando el package en cada sello** (`2.11.34-beta` acompaña a `v2.88.34-beta`), de modo que la
> afirmación «package congelado hasta una versión estable» describe un régimen que **ya no aplica** (no
> es un bug de runtime, pero **sí** una política desactualizada). La **enmienda de la regla 3** es trabajo
> del **commit de promoción** (§4/§5 del [criterio de salida](./criterio-salida-beta-2026-10-01.md), `G7`).

## Reglas

1. **El tip certificado es el git tag**, no el `version` de npm. Un auditor cita `v1.47-beta` → `77f96ead`.
2. **Package congelado a propósito** durante la serie UX V1.36–V1.48: no bumpir `package.json` en cada parche. El desfase `1.35.0-beta` vs producto `V1.48-beta` **no es un bug de runtime**.
3. **Bump de package** solo al cerrar una **versión estable**. V1.46 es Paper Desk foundation. V1.47 es Runtime Truth. V1.48 es Event Continuity. Ninguno es estable.
4. **Schema / API** cambian con migraciones o `contract:gen`, no con un relevo de UX. No sincronizarlos al product version por costumbre.
5. Apps y packages internos (`apps/web`, `packages/shared`, …) pueden permanecer en `0.1.0` mientras el monorepo raíz sea la verdad de package.

## Qué no hacer

- No retaguear `v1.41.3-beta` para «igualar» package.
- No fingir en CURRENT_SYSTEM que package = product.
- No introducir un sexto número (marketing, build, …) sin fila en esta tabla.
