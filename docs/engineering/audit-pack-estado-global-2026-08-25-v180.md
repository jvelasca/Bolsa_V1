# Paquete de auditoría — ESTADO GLOBAL post-tag v1.8.0-beta (2026-08-25)

> **Propósito:** documento **único** para auditoría externa general tras el tag **`v1.8.0-beta`**. Consolida identidad, freeze, arcos cerrados desde `v1.7.0-beta`, verificación y riesgos ops.
> **AsOf:** 2026-08-25 · tag **`v1.8.0-beta` → `8c8b789`** · previo **`v1.7.0-beta` → `e3b943a`**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`
> **Fuentes vivas:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [`CHANGELOG.md`](../../CHANGELOG.md) · ADR-023 · ADR-031 · relevo A3-wire.
> **Histórico pack:** [`audit-pack-estado-global-2026-08-24e.md`](./audit-pack-estado-global-2026-08-24e.md) (pre-1.8).

---

## 0. Resumen ejecutivo

| Pieza                                                   | Estado                                                                                               |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Rama / tag**                                          | `origin/main` tip ≥ `8c8b789` · **`v1.8.0-beta` → `8c8b789`** · previo **`v1.7.0-beta` → `e3b943a`** |
| **Identidad**                                           | QROS + Investment OS + Decision Spine · Lab/Radar fuera (D3) · LLM no ejecuta                        |
| **R-1..R-13 + Track B + U0–U6 + DS-05/03**              | ✅ heredados de v1.7                                                                                 |
| **TradePlan 4.x–4.9 + 5.x thin + 6 + 7 + 8.0–8.2 thin** | ✅ CERRADOS                                                                                          |
| **Integridad I1–I3 + RX1**                              | ✅ CERRADOS                                                                                          |
| **ADR-023 BETA-D + A3-wire**                            | ✅ Accepted parcial · UI arm `ACTIVAR AUTO` · execute opt-in                                         |
| **Thaw estricto 60/50/70/55**                           | ❌ deuda abierta (W2–W4) — runbook                                                                   |
| **Broker live**                                         | ❌ no                                                                                                |
| **Batería spine**                                       | `pnpm test:decision-spine` **159**                                                                   |
| **Alembic**                                             | `010` en `bolsa_v1`                                                                                  |

**Mensaje clave:** núcleo financiero + spine + mesa + honesty execute + thaw **parcial** BETA-D están tagged en **`v1.8.0-beta`**. Estricto y broker siguen fuera. **BETA / no producción.**

---

## 1. Arcos nuevos desde v1.7.0-beta

| Arco                        | Anclas típicas                                             |
| --------------------------- | ---------------------------------------------------------- |
| TradePlan / Wyckoff / Board | 4.0–4.9 · 5.0–5.3 · 6 · 7 · 8.0–8.2                        |
| Integridad                  | I1 `2bd5cd8` · I2 `e31840d` · I3 `26901aa` · RX1 `9289b53` |
| Thaw BETA-D                 | `cb58962` · A3-wire `d704263`                              |
| Deuda estricto              | runbook + snapshot helper                                  |

Detalle file:line del camino: [`decision-spine-cadena-2026-08-24.md`](./decision-spine-cadena-2026-08-24.md) · SoT [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).

---

## 2. Freeze (auditoría)

- Ranking / TOP / dictamen **≠ BUY**.
- `PAPER_D_EXECUTE` default **off** (opt-in local).
- Arm UI ≠ permiso server.
- Sin broker live · sin Accept estricto hasta P1–P5 verdes + palabra owner.
- F9-B · expectancy/trail/bracket **plena** · Wyckoff Alembic/`wyckoffPhase` · **PARKED**.

---

## 3. Open risks (ops, no código)

| Riesgo                   | Estado                                         |
| ------------------------ | ---------------------------------------------- |
| `TRUSTED_PROXIES` prod   | BLOCKED_ON_OWNER (IPs exactas; matcher ≠ CIDR) |
| Thaw estricto P1–P5      | FAIL baseline · tracking semanal               |
| Redis / worker_arq local | degraded tipico en DEMO local                  |
| Purge pending-delete E8  | N (sin purge)                                  |

---

## 4. Cómo verificar rápido

```bash
pnpm test:decision-spine   # 159
node scripts/thaw_estricto_snapshot.mjs   # read-only; P1–P5 esperados FAIL
# API up:
# GET /api/health → components.risk.details.paperDExecuteEnv
```

UI armado: Cuentas → Operativa → Auto → frase `ACTIVAR AUTO`.
