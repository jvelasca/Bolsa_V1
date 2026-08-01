# Handoff sesión 2026-08-01 — cierre de racha + sync Ayuda

> **Estado:** **GitHub V1 publicado** — https://github.com/jvelasca/Bolsa_V1 · release [v1.0.0](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.0.0).  
> Siguiente: BETA1 (simulaciones; issues cortas).  
> Handoff previo: [`session-handoff-2026-07-31.md`](./session-handoff-2026-07-31.md).

**As-of Ayuda:** `HELP_CONTENT_AS_OF` = **2026-08-01**.

---

## 1. Qué quedó listo (esta racha)

| Área | Versión | Qué |
|------|---------|-----|
| **Lista AUTO frescura** | v1.3 | Histéresis `lastBarDate` (`1d` ≤5d → `bar_hysteresis`; stamp no desliza) |
| **FA Score_FUND** | — | Beneish M > −1.78 → distress |
| **Tarjeta Valor** | — | Secciones · «Más métricas» · nulls bancos · **CAPM footnote** |
| **Yahoo timeseries** | — | Income vacío → replace · ROIC debt/cash desde balance |
| **Cobertura Yahoo** | audit | `pnpm audit:fa:coverage` |
| **Composite liquidez** | v1.1 | Buckets ADV/mcap · etiquetas UI · `composite_score_v1_1` |
| **CAPM Tarjeta** | v0 | Snapshot `capmRf`/`capmErp` · `ke = rf + β×ERP` (no live) |
| **CORE-B** | v0.2 | Meseta→espacio · `resolveDefaultLabFamily` |
| **Trading DÍA D** | fix | `fullBleedMovie` **no** se persiste · Salir restaura Operaciones |
| **CORE-P** | closed | Soft-bias + E2E live `test:coach:smoke` · Ayuda IA done |
| **CORE-R / DÍA D** | — | Ya cerrados; sin reabrir congelados |
| **Ayuda sync** | 08-01 | Trackers + `HELP.md` + Trading MODO DÍA D + plan smoke + IA NEXT/FROZEN |

### Comandos (baterías)

```bash
pnpm test:operativa
OPERATIVA_API_REQUIRED=1 pnpm test:operativa:smoke
pnpm test:fa
pnpm test:coach
CORE_P_API_REQUIRED=1 pnpm test:coach:smoke
pnpm test:coach:api          # ASGI (DB) + smoke live
```

---

## 2. Congelado (sin cambio)

| Track | Notas |
|-------|--------|
| Auto-paper **D** execute | Off-by-default |
| Lab UI **P3–P9** / Discovery / Belief | Pausa |
| CORE-R **multi-dispositivo** | Servidor |
| Moat / Management / **rf·ERP live** | Opcional (CAPM v0 ya visible) |

---

## 3. Siguiente = BETA1 (humano)

Runbook: [`beta1-simulation-runbook.md`](./beta1-simulation-runbook.md) · detalle UI: [`operativa-test-plan-2026-07-31.md`](./operativa-test-plan-2026-07-31.md).

| Bloque | Qué |
|--------|-----|
| A | Embudo + multi-perfil CORE-P |
| B | Smoke **D1–D12** DÍA D |
| C | Smoke **R1–R9** CORE-R |
| D | FA APP (CAPM · Composite v1.1 · Screener · Paper D dry-run) |
| E | Lista AUTO live (frescura v1.3) |

Si falla: issue corta en `research/observations/ISSUES.md` — no reabrir congelados.

---

## 4. Criterio «listo para pruebas a fondo»

- [x] Preflight auto (operativa + smoke required + coach + fa)  
- [x] Composite live `ver=composite_score_v1_1`  
- [x] CORE-B v0.2 + CAPM Tarjeta + fix Trading DÍA D  
- [x] Ayuda / trackers / HELP.md / plan smoke sincronizados  
- [ ] D1–D12 + R1–R9 manual  
- [ ] Checklist FA APP + Lista AUTO live  

**Al retomar código:** solo bugs del smoke o decisión explícita de producto.
