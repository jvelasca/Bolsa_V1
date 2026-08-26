# RELEVO — tag v1.15-beta (Mesa · Hoy) (2026-08-26)

> **Padre:** [`traspaso-relevo-tag-v1-14-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-14-beta-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — tag `v1.15-beta` pendiente pin SHA post-push.
> **Arranque chat nuevo / auditor:** `CURRENT_SYSTEM.md` + este relevo + ADR-037.

---

## 0. Alcance v1.15-beta (Operational UX, sin core)

| Epic                       | Doc                                                                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Mesa · Hoy (`/mesa`)       | [`plan-mesa-hoy-v115-2026-08-26.md`](./plan-mesa-hoy-v115-2026-08-26.md) · [ADR-037](../adr/037-mesa-hoy-operational-ux.md) |
| Journal tabla simplificada | ADR-037 § UX Journal                                                                                                        |
| Nav daily-first Mesa       | `daily-nav.ts`                                                                                                              |

**Fuera:** refactor `decision_journal_studies.py` · paginación UI · evolución opinión+fuerza (V1.16).

## 1. Freeze intacto

Confirm = firma · TradePlan/Position SoT · DEX-3 incident lifecycle · sin HTTP nuevo en Mesa.

## 2. Verificación pre-tag

```bash
pnpm --filter @bolsa/shared test -- mesa-hoy mesa-status
pnpm --filter @bolsa/web test -- daily-nav mesa-hoy
```

## 3. Release

| Pieza  | Valor                            |
| ------ | -------------------------------- |
| Tag    | `v1.15-beta` → _(pin tras push)_ |
| Previo | `v1.14-beta` → `772a3a73`        |

### Owner: publicado

```bash
git tag v1.15-beta
git push origin main v1.15-beta
```
