# RELEVO — P4.1 Consola de Mesa (slice 1) · 2026-08-25

> **Padre:** [`plan-p4-consola-mesa-2026-08-25.md`](./plan-p4-consola-mesa-2026-08-25.md) · ADR-033 §7.
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (P4.1 + P4.2).**

---

## 0. Qué quedó hecho

| Pieza                                                                             | Estado                             |
| --------------------------------------------------------------------------------- | ---------------------------------- |
| Operaciones enriquecido: R, stop, T1/T2, Salida advisory                          | **Hecho** (P4.1)                   |
| CTAs Revisar / Reducir / Salir → cola Confirm (drawer)                            | **Hecho** (P4.1)                   |
| Confirm cierre sin sessionId usa dirección Position persistida                    | **Hecho** (P4.1)                   |
| Barra operativa: caja, posiciones, kill switch, veto entradas                     | **Hecho** (P4.1)                   |
| Cola entradas read-only (Vigilar…Descartado)                                      | **Hecho** (P4.1)                   |
| «No operar hoy» → `POST session-verdict` → Journal                                | **Hecho** (P4.1)                   |
| HELP + tests UI/copy                                                              | **Hecho** (P4.1)                   |
| **Barra estado global completa** (patrimonio, P&L, Confirm, excepciones, régimen) | **Hecho** (P4.2)                   |
| **Filtros cola entradas** (status, gate, símbolo)                                 | **Hecho** (P4.2)                   |
| **Proteger** CTA + preview stop/override en Confirm                               | **Hecho** (P4.2 · enqueue UI-only) |
| Ruta `/console` god page · auto-exit CTA · broker                                 | **No** (fuera)                     |

Spine `pnpm test:decision-spine` — **260 passed** · vitest P4 **21 passed** (ver checklist SEMI).

## 1. Freeze / flags

Igual que P3. Confirm = única firma. CTAs no ejecutan. Kill switch bloquea copy entradas; desriesgo SEMI OK.

## 2. E1 — fork

1. **P4.2:** barra estado global completa, filtros cola, proteger con override stop — **HECHO**.
2. **Operar SEMI** con P4.1+P4.2 — **HECHO** · checklist [`operar-semi-p4-consola-mesa-2026-08-25.md`](./operar-semi-p4-consola-mesa-2026-08-25.md) · spine **260** · vitest P4 **21**.
3. **Commit/tag** `v1.10-beta` — **HECHO** (ver [`traspaso-relevo-tag-v1-10-beta-2026-08-25.md`](./traspaso-relevo-tag-v1-10-beta-2026-08-25.md)).

## 3. Docs clave

- [`plan-p4-consola-mesa-2026-08-25.md`](./plan-p4-consola-mesa-2026-08-25.md)
- [`operar-semi-p4-consola-mesa-2026-08-25.md`](./operar-semi-p4-consola-mesa-2026-08-25.md) ← **Operar SEMI (E1.2)**
- ADR-033 §7 · `CURRENT_SYSTEM.md` · roadmap v1.10
