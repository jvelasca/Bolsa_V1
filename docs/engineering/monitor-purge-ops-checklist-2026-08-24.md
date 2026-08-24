# Monitor — Purge V2 + ops checklist (living)

> **Padre:** [`plan-r12-pending-delete-v2-purge-2026-08-22.md`](./plan-r12-pending-delete-v2-purge-2026-08-22.md) · [`ops-r1-seguridad-operaciones-2026-08-19.md`](./ops-r1-seguridad-operaciones-2026-08-19.md) · [`pending-delete/README.md`](./pending-delete/README.md).
> **Ciclo:** 3/5 (monitor puro) · **AsOf:** 2026-08-24 · HEAD tag **`v1.7.0-beta` → `e3b943a`**.
> **Regla:** **NO PURGE** sin decisión explícita del propietario + E8 completo. Este doc es read-only salvo actualización de conteos/fechas.

---

## 1. Resumen ejecutivo (T+2 días)

| Área                             | Estado                                                 | Acción                           |
| -------------------------------- | ------------------------------------------------------ | -------------------------------- |
| Purge V2 ventana                 | **MONITOR** (inicio 2026-08-22 · objetivo 4–8 semanas) | Recopilar métricas; **0 purges** |
| E8 riesgo alto                   | **N** (4 ítems + 3 campos workspace)                   | No tocar migradores              |
| Batería protectora T+0           | **19/19** ✅ (re-verificado 2026-08-24)                | Re-ejecutar cada hito            |
| `verify_ledger_balance_chain.py` | **EXIT 0** (2026-08-24)                                | Cadencia §5                      |
| Secret scanning                  | **enabled** vía API (`5100d23`)                        | Propietario: confirmar UI        |
| `TRUSTED_PROXIES` prod           | Runbook listo · valor real **BLOQUEADO**               | Propietario only                 |
| Purga historial git dev          | Opcional · decisión pendiente                          | Propietario only                 |

---

## 2. Purge V2 — ventana y conteos

### 2.1 Ventana

| Campo                 | Valor                                                                     |
| --------------------- | ------------------------------------------------------------------------- |
| Inicio telemetría     | **2026-08-22** (`0763700` + kit persistencia local)                       |
| Duración acordada     | **4–8 semanas**                                                           |
| AsOf monitor          | **2026-08-24** → **T+2 días**                                             |
| Próximo hito sugerido | T+4 semanas (~2026-09-19) — re-ejecutar batería §4 + revisar log métricas |
| Purges ejecutados     | **0** (E8 **N** para todos los ítems de riesgo alto)                      |

### 2.2 Inventario pending-delete (T+0 counts)

| Categoría                      | Count     | Detalle                                                                                                                                          |
| ------------------------------ | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Ítems riesgo alto (E8 **N**)   | **4**     | `readLegacyPendingOrders` · `readLegacyTimeframeFavorites` · `chartDataStrip` · `chartNewTabSeed` + `newChartConfigSource` (agrupados workspace) |
| API viva (no candidato)        | **1**     | `presetRuleGroups` — callers producción                                                                                                          |
| LIVE (no borrar fichero)       | **1**     | `chart-inspector-nav.ts`                                                                                                                         |
| Micro purged (R-13 A2)         | **1**     | `normalizeChartNewTabSeed` ✅                                                                                                                    |
| Ya eliminados (R-8D histórico) | **14+**   | Ver [`pending-delete/README.md`](./pending-delete/README.md) §«Ya eliminado»                                                                     |
| Batería protectora             | **19/19** | 10 + 4 + 5 tests (§4)                                                                                                                            |

**Veredicto R-13 §4.3:** todos los ítems de riesgo alto → **MONITOR**. Ventana T+0 → **19/19 · 0 purges**.

### 2.3 E8 por ítem (sin cambio desde T+0)

| Ítem                                       | E8      | Evidencia clave                                                               |
| ------------------------------------------ | ------- | ----------------------------------------------------------------------------- |
| `readLegacyPendingOrders`                  | **N**   | `use-pending-orders.ts` migrador + `localStorage["bolsa-trading-ui"]`         |
| `readLegacyTimeframeFavorites`             | **N**   | `workspace-store-core.ts` + `localStorage["bolsa-chart-timeframe-favorites"]` |
| `chartDataStrip`                           | **N**   | merge toolbar en `normalizeWorkspace`                                         |
| `chartNewTabSeed` / `newChartConfigSource` | **N**   | campos opcionales en blobs workspace                                          |
| `presetRuleGroups`                         | **N/A** | API viva — **no purgar**                                                      |

### 2.4 Métricas client-side (opt-in)

**Activar (DevTools → consola):**

```javascript
localStorage.setItem("bolsa-legacy-storage-metrics", "1");
location.reload();
```

**Leer log:**

```javascript
JSON.parse(localStorage.getItem("bolsa-legacy-storage-metrics-log") || "[]");
```

**Objetivo antes de flags/purge:** **0 blobs activos** en ventana acordada para cada clave/campo (§2.1 plan R-12).

**Prohibido en monitor:** wipe `localStorage` legacy · quitar migradores · borrar `chart-inspector-nav.ts` / `presetRuleGroups`.

---

## 3. Ops — checklist manual

### 3.1 Secret scanning (commit `5100d23`)

| Check                                           | Estado                       | Quién          |
| ----------------------------------------------- | ---------------------------- | -------------- |
| API `secret_scanning` → enabled                 | ✅ (PATCH 2026-08-24)        | Agente (hecho) |
| API `secret_scanning_push_protection` → enabled | ✅                           | Agente (hecho) |
| CI `.github/workflows/gitleaks.yml` activo      | ✅                           | Repo           |
| **UI confirmación**                             | ⏳ **pendiente propietario** | **Owner**      |

**Paso UI (propietario):**

1. Abrir `https://github.com/jvelasca/Bolsa_V1/settings/security_analysis`
2. Confirmar **Secret scanning** = **Enabled**
3. Confirmar **Push protection** = **Enabled**
4. (Opcional) marcar este ítem ✅ en este doc tras confirmar

### 3.2 `TRUSTED_PROXIES` prod

| Check                                         | Estado                                                                                                  | Quién          |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------- |
| Código + tests (`config.py`, `get_client_ip`) | ✅                                                                                                      | Repo           |
| Runbook                                       | ✅ [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md) | Agente (hecho) |
| Valor real IP/CIDR edge proxy                 | ⏳ **BLOQUEADO propietario**                                                                            | **Owner**      |
| Verificación rate-limit post-deploy           | ⏳ tras valor real                                                                                      | **Owner**      |

Default vacío = **seguro** en dev/local/CI sin reverse proxy.

### 3.3 Ops cerrados (no reabrir)

| Ítem                               | Estado                   |
| ---------------------------------- | ------------------------ |
| BP/.L → BP.L (9 LSE)               | ✅ HECHO 2026-08-24      |
| Re-sync vivo `idx-ftse100` sin 404 | ✅ HECHO 2026-08-24      |
| `_backup_instruments_corrupt`      | ✅ DROPPED               |
| Logs locales `logs/**`             | ✅ purgados (gitignored) |

### 3.4 Opcional — purga historial git dev

Valores dev (`bolsa:bolsa_dev` / `bolsa-dev-secret`) en historial público. **No urgente.** Requiere filter-repo/BFG + coordinación CI. **Decisión explícita propietario.**

---

## 4. Verificación read-only — batería Purge V2

```bash
pnpm --filter @bolsa/web exec vitest run \
  src/lib/legacy-storage-metrics.test.ts \
  src/features/trading/use-pending-orders.migration.test.ts \
  src/stores/workspace-legacy-timeframe-favorites.test.ts
```

| Suite                                          | Tests  | 2026-08-22 T+0 | 2026-08-24 Ciclo 3 |
| ---------------------------------------------- | ------ | -------------- | ------------------ |
| `legacy-storage-metrics.test.ts`               | 10     | ✅             | ✅                 |
| `use-pending-orders.migration.test.ts`         | 4      | ✅             | ✅                 |
| `workspace-legacy-timeframe-favorites.test.ts` | 5      | ✅             | ✅                 |
| **Total**                                      | **19** | **19/19**      | **19/19**          |

---

## 5. Cadencia de verificación

| Script / check                                         | Cuándo                                          | Quién              | EXIT esperado        |
| ------------------------------------------------------ | ----------------------------------------------- | ------------------ | -------------------- |
| `python scripts/verify/verify_ledger_balance_chain.py` | Tras limpieza dev · cada hito monitor · pre-tag | Agente (read-only) | **0**                |
| Batería §4 (19 tests)                                  | T+0 · T+4 sem · T+8 sem · pre-purge             | Agente             | **19/19**            |
| Log `bolsa-legacy-storage-metrics-log`                 | Semanal si opt-in activo                        | Agente / owner dev | 0 blobs objetivo     |
| Secret scanning UI                                     | Una vez (confirmación)                          | **Owner**          | Enabled ×2           |
| `TRUSTED_PROXIES` prod                                 | Cuando exista deploy con proxy                  | **Owner**          | rate-limit coherente |

**Última ejecución verify (2026-08-24):** `verify_ledger_balance_chain.py` → **EXIT 0** — todas las cuentas cumplen A (cash-ledger) y B (cadena balance_after).

---

## 6. Owner-only vs agent actions

### Propietario (owner-only)

- Confirmar secret scanning + push protection en GitHub UI
- Aportar IP/CIDR reales y configurar `TRUSTED_PROXIES` en prod
- Decidir purga historial git dev (opcional)
- **Decidir apertura de fase purge** tras ventana 4–8 sem + métricas en 0
- Activar opt-in métricas en sesiones reales de uso (si se quiere telemetría representativa)

### Agente (read-only en monitor)

- Re-ejecutar `verify_ledger_balance_chain.py` y batería §4
- Leer inventario / README pending-delete (sin borrar)
- Actualizar conteos y fechas en este doc
- **NO** purge código · **NO** wipe storage · **NO** prod env · **NO** commit salvo update-last docs acordado

---

## 7. Próximo paso (post-ventana)

1. Revisar métricas §2.4 — objetivo **0 blobs** sostenido
2. Propietario aprueba flags (`PENDING_ORDERS_LEGACY_MIGRATION_COMPLETE`, etc.)
3. Subagente purge V2 con [`plan-r12-pending-delete-v2-purge-2026-08-22.md`](./plan-r12-pending-delete-v2-purge-2026-08-22.md) como checklist
4. Hasta entonces: **MONITOR ONLY**

---

## 8. Historial de monitor

| Fecha      | Ciclo | verify EXIT | Batería 19 | Notas                                  |
| ---------- | ----- | ----------- | ---------- | -------------------------------------- |
| 2026-08-22 | T+0   | —           | 19/19      | Ventana abierta; E8 N                  |
| 2026-08-24 | 3/5   | **0**       | **19/19**  | Monitor puro; 0 purges; ops UI pending |
