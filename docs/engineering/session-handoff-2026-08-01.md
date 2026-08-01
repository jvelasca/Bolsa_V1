# Handoff sesión 2026-08-01 — cierre de racha + sync Ayuda

> **Estado:** producto listo para **GitHub V1** · `git init` hecho · falta commit/push/tag con OK.  
> Checklist: [`github-v1-release.md`](./github-v1-release.md) · `CHANGELOG.md`.  
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

## 3. Siguiente = humano (checklist)

Detalle: [`operativa-test-plan-2026-07-31.md`](./operativa-test-plan-2026-07-31.md) · Ayuda → Backtesting / Análisis del valor / Trading.

| # | Qué | Dónde verificar |
|---|-----|-----------------|
| 1 | Smoke **D1–D12** | DÍA D; D6 recarga sin full-bleed; D12 Operaciones |
| 2 | Smoke **R1–R9** | Monitor CORE-R |
| 3 | Lista AUTO live | Reinicio → Play IBEX → Omitido (v1.3) |
| 4 | Checklist FA APP | Refresh · CAPM footnote · Composite v1.1 · Screener · Paper D dry-run |
| 5 | Ayuda visual | Guías DÍA D / CORE-R / Archivo · fila Lab CORE-B · sección Trading DÍA D |

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
