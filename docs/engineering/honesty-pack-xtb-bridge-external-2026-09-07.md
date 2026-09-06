# Honesty pack — XTB bridge externo (fuera del monorepo)

> **AsOf:** 2026-09-07 · **Padre:** [audit LIVE venue](./audit-pack-live-venue-thaw-design-2026-09-06.md) · [roadmap LIVE Execution](./roadmap-live-execution-core-2026-09-07.md).  
> **Alcance:** lo que este repositorio **no** puede auditar línea a línea.

---

## 1. Separación

| Capa              | Vive en                             | Responsabilidad                                                                         |
| ----------------- | ----------------------------------- | --------------------------------------------------------------------------------------- |
| Monorepo Bolsa_V1 | este repo                           | HTTP client `XtbBridgeClient` · adapter fail-closed · VIRTUAL sandbox · OR-6            |
| **Bridge XTB**    | servicio externo (`XTB_BRIDGE_URL`) | Protocolo/credenciales XTB · flags `XTB_BRIDGE_ALLOW_ORDERS` / `XTB_BRIDGE_FILL_ORDERS` |

El mock local [`scripts/xtb-bridge-mock.mjs`](../../scripts/xtb-bridge-mock.mjs) documenta el contrato fail-closed del mock; **no** sustituye una auditoría del bridge de producción.

---

## 2. Cadena de confianza

```text
Confirm / adapter
  → (LIVE_EXECUTION_UNLOCKED? kill?)
  → POST {bridge}/orders
  → bridge (ALLOW / FILL — fuera de alcance)
  → respuesta submitted|filled|rejected
```

La disciplina «nunca asumas éxito» del monorepo es tan fuerte como el eslabón externo. Timeout/error en el cliente → `unknown` (sin ledger). Sin unlock → `live_virtual_sandbox` (sin HTTP).

---

## 3. Qué NO afirmar desde este pack

- Que el bridge externo esté auditado en este zip/repo.
- Que `XTB_BRIDGE_FILL_ORDERS=1` = capital XTB real (puede ser mock/DEMO).
- Que disponer de URL cableada = thaw.

---

## 4. Recomendación de proceso

Mantener un documento de honesty equivalente **en el repo del bridge** (fail-closed defaults, no retry ciego, idempotencia). Hasta entonces, tratar el bridge como **trust boundary** explícita en todo scorecard L1–L10.
