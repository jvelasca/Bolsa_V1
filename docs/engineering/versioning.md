# Versionado — product / tag / package / schema / API

> **AsOf:** 2026-08-31 · **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** política. **No** bump de `package.json` en este slice.

Cinco números distintos. No son intercambiables. Una fila de docs no debe fingir que los cinco coinciden.

| Verdad      | Qué es                                                                | Dónde vive                                | Valor vigente (AsOf)      |
| ----------- | --------------------------------------------------------------------- | ----------------------------------------- | ------------------------- |
| **Product** | Nombre de producto / slice de UX o dominio que lee el auditor         | AsOf de `CURRENT_SYSTEM.md`, relevos      | `V1.42-beta`              |
| **Git tag** | Tip certificado para auditoría / CI-by-tag                            | `git tag` · GitHub Releases               | `v1.42-beta` → `1bb00fd`  |
| **Package** | Semver npm del monorepo (workspaces `@bolsa/*` pueden seguir `0.1.0`) | raíz [`package.json`](../../package.json) | `1.35.0-beta` (congelado) |
| **Schema**  | Migraciones de persistencia                                           | Alembic en `packages/py` / `bolsa_v1`     | revisión Alembic vigente  |
| **API**     | Contrato HTTP / OpenAPI si existe                                     | FastAPI · `apps/web/src/api/schema.d.ts`  | independiente del product |

## Reglas

1. **El tip certificado es el git tag**, no el `version` de npm. Un auditor cita `v1.42-beta` → `1bb00fd`.
2. **Package congelado a propósito** durante la serie UX V1.36–V1.41.3: no bumpir `package.json` en cada parche de proyección. El desfase `1.35.0-beta` vs producto `V1.41.3-beta` **no es un bug de runtime**.
3. **Bump de package** solo al cerrar una **V1.42 estable** (código + Golden Paths + tag), no al publicar este contrato.
4. **Schema / API** cambian con migraciones o `contract:gen`, no con un relevo de UX. No sincronizarlos al product version por costumbre.
5. Apps y packages internos (`apps/web`, `packages/shared`, …) pueden permanecer en `0.1.0` mientras el monorepo raíz sea la verdad de package.

## Qué no hacer

- No retaguear `v1.41.3-beta` para «igualar» package.
- No fingir en CURRENT_SYSTEM que package = product.
- No introducir un sexto número (marketing, build, …) sin fila en esta tabla.
