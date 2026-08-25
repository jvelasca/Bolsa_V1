# RELEVO — operar SEMI (post ExitPermission) · 2026-08-25

> **Padre:** [`traspaso-relevo-exit-permission-2026-08-25.md`](./traspaso-relevo-exit-permission-2026-08-25.md) · roadmap v1.9.
> **AsOf:** 2026-08-25.
> **Estado:** **MODO OPERACIÓN** — no código nuevo. Spine **217**. Thin / F1–F4 / ExitPermission / INFRA **congelados**.
> **Arranque chat nuevo (ops):** este fichero + `CURRENT_SYSTEM.md` + HELP «Hoy en la mesa».

---

## 0. Qué no se toca

- Thin 5.x/8.x · Wyckoff · ActionabilityScore · broker · `PAPER_D_EXECUTE` (sigue **off** salvo opt-in local consciente).
- No wire ExitPermission→Confirm todavía.
- No tag `v1.9-beta` sin decisión owner + Release tag CI GREEN.

## 1. Arranque SEMI (mesa)

```text
pnpm doctor          # opcional: puertos / DB
pnpm dev             # web + api-python
```

- Mesa: `/trading` → tira **Hoy** → Proponer F3 → **Confirmar** (firma humana).
- BUY solo con TradePlan `TRIGGERED` + `check_opening` ALLOW + firma.
- Sin plan → WATCH (nunca BUY). Advisory thin ≠ permiso.

## 2. Checklist del día

1. Ver valor en Trading.
2. Leer recomendación / Proponer F3.
3. Firmar en Confirmar (página o drawer).
4. Si veto: leer reasons (`fit` / freshness / mandate) — no forzar.

## 3. E1 — cuando vuelva el código

1. Tag `v1.9-beta` (owner) · o
2. Wire ExitPermission→ExecutionPlan PAPER (plan D1–D8) · o
3. Seguir operando SEMI.
