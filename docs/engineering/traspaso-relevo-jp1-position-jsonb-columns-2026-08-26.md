# RELEVO — JP-1 PositionState JSONB → columnas · 2026-08-26

> **Padre:** [`plan-jp1-position-jsonb-columns-2026-08-26.md`](./plan-jp1-position-jsonb-columns-2026-08-26.md) · ADR-034 · relevo VS-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código).** Alembic `012` + dual-write; JSONB SoT.

---

## Qué quedó hecho

| Pieza                                        | Estado           |
| -------------------------------------------- | ---------------- |
| Alembic **`012`** hot columns                | **Hecho**        |
| Dual-write `insert` + `update_state`         | **Hecho**        |
| JSONB `position_state` SoT (nested/advisory) | **Hecho**        |
| Backfill desde JSONB camelCase               | **Hecho**        |
| Tablas `paper_orders` / `execution_records`  | **No**           |
| Thaw `PAPER_D_EXECUTE` · Redis venue         | **Chats aparte** |

## Siguiente chat

1. Per-account venue (opcional).
2. Thaw **estricto** P1–P5 (deuda) — chat aparte.
3. Revisions child / DDL paper_orders (parked).

## Sesión 2026-08-26 (cadena)

- **VS-1** / **RV-1** venue path.
- **JP-1** columnas hot (este chat).
- **Thaw stamp** (misma sesión).

## Docs

- Plan JP-1 · roadmap v1.11 · CURRENT_SYSTEM · ADR-034
- Relevo thaw: [`traspaso-relevo-thaw-paper-d-execute-2026-08-26.md`](./traspaso-relevo-thaw-paper-d-execute-2026-08-26.md)
