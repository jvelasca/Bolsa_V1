# Handoff sesión 2026-07-31 — cierre operativa DÍA D + CORE-R

> **Estado:** DÍA D **v0.11** y CORE-R **v1.8** operables en producto.  
> Premisas: [`backtesting-dia-d-premises-2026-07-31.md`](./backtesting-dia-d-premises-2026-07-31.md) ·  
> Plan smoke: [`operativa-test-plan-2026-07-31.md`](./operativa-test-plan-2026-07-31.md) ·  
> Lista AUTO / CORE-R: [`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md) ·  
> Handoff previo: [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md).

**As-of Ayuda:** `HELP_CONTENT_AS_OF` = **2026-08-01**.

---

## 1. Qué quedó listo (esta racha)

| Área | Versión | Qué |
|------|---------|-----|
| **Backtesting DÍA D** | v0.11 | Fecha D · embudo ≤ D · Simular D→hoy · película ± full-bleed · Manual/Semi/Auto · gate equity · Evidence · Guardar (local + Fase 2) · Archivo preview/JSON/Importar · Archivo también en Ayuda |
| **FA as-of** | operable | `statementPack` → `pointInTime=reconstructed`; sin pack → `blocked`. Composite corta TA ≤ D |
| **CORE-R** | v1.8 | Juicio post-settle · OOS · PnL DEMO · Encolar · Narrar · cron shell · chip · toast **Abrir Monitor** · **Hecho todos** |
| **Ops** | — | `pnpm test:operativa` · `pnpm test:operativa:smoke` |
| **Ayuda / docs** | sync 2026-07-31 | Guías DÍA D + CORE-R · HELP · research-lifecycle · UI_PREFS · ISSUES |

### Cómo arrancar DÍA D (usuario)

1. Backtesting → Probar → fecha **pasada** en bloque DÍA D → Play hasta Finalistas.  
2. #1 → **Simular D→hoy** → Trading (banner + película).  
3. Semi/Manual: Aceptar/Rechazar; Guardar Evidence; Archivo (JSON / Importar).  
4. **Salir DÍA D** no toca DEMO live.

### Cómo arrancar CORE-R (usuario)

1. Monitor (Probar o Ayuda) → lista con TOP.  
2. **Encolar revisiones** · deep-links · **Hecho** / **Hecho todos**.  
3. Opcional: Narrar · Auto-sync app abierta → chip + toast **Abrir Monitor**.

### Comandos

```bash
pnpm test:operativa          # web + py + smoke API opcional
pnpm test:operativa:smoke    # API live (reinicia api-python tras pulls)
pnpm test:fa                 # batería FA / FIE
pnpm test:coach              # embudo / Lista AUTO
```

---

## 2. Congelado (no reabrir sin decisión)

| Track | Notas |
|-------|--------|
| Auto-paper **D** (`PAPER_D_EXECUTE`) | Off-by-default; ranking TA+FA+perfil |
| Lab UI **P3–P9** / Discovery / Belief UI | Pausa deliberada |
| CORE-R **cron multi-dispositivo** | Requiere report/cola en servidor (shell local hecho) |

---

## 3. Siguiente (prioridad al retomar)

| # | Qué | Notas |
|---|-----|--------|
| 1 | **Smoke UI a fondo** | Checklist D1–D12 + R1–R9 en `operativa-test-plan-2026-07-31.md` |
| 2 | Smoke Lista AUTO frescura live | Reinicio → Play IBEX → mayoritariamente Omitido (histéresis v1.3) |
| 3 | FA operativa / cobertura | `pnpm test:fa` · Yahoo gaps · checklist APP |
| — | CORE-R multi-dispositivo | Solo si producto pide sync cross-device |
| — | CORE-P E2E | Abierto en ISSUES; no bloquea DÍA D |

---

## 4. Docs / Ayuda tocados

| Archivo | Qué |
|---------|-----|
| `docs/HELP.md` | DÍA D v0.11 · CORE-R v1.8 · batería |
| `docs/engineering/operativa-test-plan-2026-07-31.md` | Plan smoke |
| `docs/engineering/backtesting-dia-d-premises-2026-07-31.md` | Premisas v0.11 |
| `docs/engineering/list-auto-ops-2026-07-29.md` | § CORE-R v1.8 |
| `docs/engineering/research-lifecycle.md` | Sync v0.11 / v1.8 |
| `docs/UI_PREFS_LOCALSTORAGE.md` | Claves DÍA D + CORE-R |
| `research/observations/ISSUES.md` | CORE-R v1.8 |
| `apps/web/.../help-content-as-of.ts` | 2026-07-31 |
| `apps/web/.../backtesting-tracker.ts` | Guías + tracking + NEXT |
| `README.md` | Scripts operativa + docs |

**Código clave:**  
`dia-d-*` · `trading-dia-d-*` · `core-r-*` · `strategy-monitor*` · `core_r_review_evidence.py` · `dia_d_session_evidence.py` · `emit_evidence_for_dia_d_session`.

---

## 5. Criterio «listo para pruebas a fondo»

- [x] `pnpm test:operativa` verde (offline)  
- [ ] Smoke API sin WARN de rutas (API reiniciada tras pull)  
- [ ] D1–D12 + R1–R9 manual OK  
- [ ] Ayuda muestra guías + Archivo Evidence + Monitor  

Al retomar: **no** abrir Lab P3–P9 / Belief / auto-paper D sin decisión explícita.
