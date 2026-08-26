# RELEVO — tag v1.14-beta (candidato post-P1) (2026-08-26)

> **Padre:** [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-13-beta-2026-08-26.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PRE-TAG** — código local post-`v1.13-beta`; pin SHA al publicar.
> **Arranque chat nuevo:** `CURRENT_SYSTEM.md` + este relevo + pack v113.

---

## 0. Alcance v1.14-beta (UI / Journal, sin DEX)

Epics P1 post-tag **v1.13-beta** cerrados en código:

| Epic                                  | Relevo                                                                                                     |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Evolución tesis (Journal 3ª pestaña)  | [`traspaso-relevo-journal-evolucion-2026-08-26.md`](./traspaso-relevo-journal-evolucion-2026-08-26.md)     |
| Mesa incident UI (DEX-3)              | [`traspaso-relevo-mesa-incident-ui-2026-08-26.md`](./traspaso-relevo-mesa-incident-ui-2026-08-26.md)       |
| Operational Console                   | [`traspaso-relevo-operational-console-2026-08-26.md`](./traspaso-relevo-operational-console-2026-08-26.md) |
| Journal hub UI (Tesis ≈ Instrumentos) | [`traspaso-relevo-journal-hub-ui-2026-08-26.md`](./traspaso-relevo-journal-hub-ui-2026-08-26.md)           |

**Fuera:** Accept estricto · thaw · Redis multi-worker · mass sim · broker producción.

## 1. Freeze intacto

LAB ≠ TRADING · Confirm = firma · `PAPER_D_EXECUTE` default off · AUTO off · Journal/Consola **solo lectura** donde aplique.

## 2. Verificación pre-tag

```bash
pnpm test:decision-spine   # expect 483
pnpm --filter @bolsa/web test -- src/features/decision-journal
```

## 3. Publicación (owner)

```bash
git tag v1.14-beta
git push origin v1.14-beta
# Actions GREEN → pin SHA en este doc + CURRENT_SYSTEM.md
```

## 4. Auditoría rápida — sin refactors pendientes obligatorios

- Decision Journal Tesis alineado con patrón Instrumentos (split, grid, autofit).
- No quedan TODOs bloqueantes en P1 Journal/Mesa/Consola.
- OC3 recon-detail sigue **skipped** (YAGNI).
- Próximas candidatas: OperationalPolicy · mass sim · thaw (solo con palabra explícita).
