# BETA1 — runbook de simulaciones (post GitHub V1)

> **Repo:** https://github.com/jvelasca/Bolsa_V1 · release [v1.0.0](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.0.0)  
> **Regla:** si algo falla → issue corta en [`ISSUES.md`](../../research/observations/ISSUES.md). **No** reabrir tracks congelados (Belief, Lab P3–P9, `PAPER_D_EXECUTE`, CORE-R multi-device, broker live).

Smoke UI detallado: [`operativa-test-plan-2026-07-31.md`](./operativa-test-plan-2026-07-31.md).  
Credenciales GitHub: [`github-credentials-and-ops.md`](./github-credentials-and-ops.md).

---

## 0. Preflight (cada sesión BETA1)

```powershell
pnpm db:ensure   # si hace falta
pnpm dev
pnpm health      # api + web OK (ignorar crash libuv Windows tras los OK)
pnpm test:coach:smoke   # CORE-P live (API arriba)
OPERATIVA_API_REQUIRED=1 pnpm test:operativa:smoke
```

---

## 1. Orden recomendado de simulaciones

Haz **un bloque por sesión**; marca al terminar.

### Bloque A — Embudo + perfiles (CORE-P)
| # | Simulación | OK si… |
|---|------------|--------|
| A1 | Cuenta con perfil **low** · Play 1 valor débil | No fuerza Lab si check no manda; techo DD 18% |
| A2 | Cambiar a perfil **high** · mismo valor | Rail/perfil; aviso mismatch Finalistas si TOP era de low |
| A3 | Lab con high vs low | Hint espacio más ancho/estrecho; familia preferida coherente |
| A4 | Lista AUTO IBEX (subset) tras cambio perfil | Frescura no salta a ciegas; fingerprint perfil |

### Bloque B — DÍA D (D1–D12)
Seguir tabla D1–D12 del plan operativa. Críticos: **D6** (recarga sin full-bleed), **D12** (Operaciones restauradas).

### Bloque C — CORE-R (R1–R9)
Monitor + cola + narrar + chip. Crítico: **no pisa TOP**.

### Bloque D — FA APP
| # | Qué | OK si… |
|---|-----|--------|
| D-FA1 | Tarjeta valor refresh | Score + footnote CAPM `ke = rf + β×ERP` |
| D-FA2 | Composite | `ver=composite_score_v1_1` |
| D-FA3 | Screener FA | Hits sin crash |
| D-FA4 | Paper D propose | `dry_run` (execute off) |

### Bloque E — Lista AUTO live (frescura v1.3)
Reinicio app → Play IBEX → filas **Omitido** cuando stamp fresco; histéresis `lastBarDate` en `1d`.

---

## 2. Plantilla de issue corta (copiar)

```markdown
### BETA1 · <área> · <síntoma en 1 línea>
| Campo | Valor |
|-------|--------|
| Estado | Open |
| Severidad | Baja / Media / Alta |
| Bloque | A/B/C/D/E |
| Repro | 1) … 2) … 3) … |
| Esperado | … |
| Obtenido | … |
| Congelado? | No tocar Belief / P3–P9 / PAPER_D / multi-device |
```

---

## 3. Fuera de BETA1 (siguiente producto)

Solo con decisión explícita: Indicadores DSL/Pine · Predictions binarios · F5 Backtest-by-IA · descongelar un track.

---

---

## 4. Sesión 2026-08-01 (auto + UI pendiente)

| Capacidad | Auto | UI humano |
|-----------|------|-----------|
| **A** CORE-P multi-perfil | PASS (`test:coach:api` + smoke live) | A1–A4 en app |
| **B** DÍA D | PASS (`test:operativa` + smoke asOf/Evidence) | D1–D12 en app |
| Health API/Web/DB | OK | — |

**UI ahora (orden corto A→B):**

1. Config → Perfil **low** → Backtesting → Play 1 valor → mirar Lab/rail  
2. Cambiar perfil **high** → aviso mismatch si había Finalistas · hint Lab espacio  
3. Probar → fecha DÍA D pasada → Play → **Simular D→hoy**  
4. Pantalla completa → recarga (D6) → **Salir DÍA D** (D12 Operaciones)

*As-of: 2026-08-01 · V1.0.0 en GitHub.*
