# Paquete de auditoría — v1.8.1 Operational Consolidation (2026-08-25)

> **Propósito:** stamp documental de consolidación **post-auditoría** `v1.8.0-beta`. No es un tag.
> **AsOf:** 2026-08-25 · código consolidado en `main` local (C1–C5 + ADR-032 + C6 stamp). Tag vigente **`v1.8.0-beta` → `8c8b789`**. Tag **`v1.8.1-beta` parked** (palabra del dueño). **No push** salvo petición.
> **Padre pack:** [`audit-pack-estado-global-2026-08-25-v180.md`](./audit-pack-estado-global-2026-08-25-v180.md).
> **Fuentes vivas:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [`CHANGELOG.md`](../../CHANGELOG.md) · ADR-031 · ADR-032 · [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md).

---

## 0. Resumen ejecutivo

| Pieza                      | Estado                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------- |
| **Tag vigente**            | `v1.8.0-beta` → `8c8b789` · **`v1.8.1-beta` no creado**                                 |
| **C1 Hoy honesty + HELP**  | CERRADO `659e6c4` — sin TradePlan → WATCH; `whyNot: legacy_projection`; HELP 2026-08-25 |
| **C2 Alembic-only**        | CERRADO `952b115` — Prisma público fail-closed; bootstrap `ensure_migrated`             |
| **C3 ActionQueue**         | CERRADO `420ad37` — cola completa ordenada; Hoy = slice top-8                           |
| **C4 shape canónico**      | CERRADO `96d1148` — `readCanonicalTradePlan` + `planSource`; **sin** `contract:gen`     |
| **C5 métricas honesty**    | CERRADO `4e245f7` — MFE `source`; expectancy `sampleQuality`                            |
| **ADR-032**                | docs-only `b532933` — Operational Core v1.9 **no implementado**                         |
| **Thin 5.x / 8.x**         | congelados (no un mapper más)                                                           |
| **Thaw estricto / broker** | ❌ deuda · ❌ no                                                                        |
| **Batería spine**          | `pnpm test:decision-spine` **161** (2026-08-25, C6)                                     |
| **@bolsa/shared vitest**   | **84**                                                                                  |
| **Prisma fail-closed**     | `node scripts/research/verify_prisma_not_authoritative.mjs` OK                          |

**Mensaje clave:** consolidación operativa **código listo** en living SoT. No más módulos thin. Siguiente fase = **v1.9 Operational Core** (ADR-032) **o** operar SEMI. **No** optimizar el modelo con demo. **BETA / no producción.**

---

## 1. Qué se consolidó (vs v1.8.0-beta)

| Slice   | Qué deja de mentir / de competir                                     |
| ------- | -------------------------------------------------------------------- |
| C1      | Hoy no inventa BUY/ARMED sin TradePlan vivo                          |
| C2      | Prisma no es autoridad de schema                                     |
| C3      | ActionQueue ≠ recorte UI; prioridad determinista                     |
| C4      | Un reader canónico; fallbacks legacy explícitos                      |
| C5      | Proxy MFE ≠ bars; `ready` ≠ muestra útil                             |
| ADR-032 | Contrato v1.9 escrito; **sin** PositionState/ExecutionPlan en código |

Autoridad normativa:

```text
CURRENT_SYSTEM → ADR → código → tests
```

Planes `plan-ciclo-*` = contexto histórico.

---

## 2. Freeze (sigue vigente)

- Ranking / TOP / dictamen **≠ BUY**.
- `PAPER_D_EXECUTE` default **off**.
- LAB ≠ TRADING · LLM no ejecuta.
- Sin broker live · sin thaw estricto · sin `contract:gen`.
- Thin 5.x/8.x **parked**. No TargetPlan / PositionPlan / LiquidityPlan.

---

## 3. Verificación C6 (2026-08-25)

```bash
pnpm test:decision-spine
# 161 passed

pnpm --filter @bolsa/shared test
# 84 passed

node scripts/research/verify_prisma_not_authoritative.mjs
# OK: exit 1; message present
```

---

## 4. Siguiente (D5)

1. **v1.9 Operational Core** bajo ADR-032 (TradePlan v1 · PositionState · ExitPlan / ExecutionPlan) — fase propia, no un mapper thin.
2. **O** operar SEMI con el modelo actual (no reabrir crecimiento advisory).
3. Tag `v1.8.1-beta` + push **solo** con palabra explícita del dueño.
