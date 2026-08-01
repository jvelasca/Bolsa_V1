# Plan de prueba operativa — DÍA D + CORE-R (2026-07-31)

> Antes de smoke UI a fondo: batería offline + reinicio API.  
> Ayuda: (?) → Backtesting · `BACKTESTING_DIA_D_GUIDE` · `BACKTESTING_CORE_R_GUIDE`.  
> Premisas DÍA D: [backtesting-dia-d-premises-2026-07-31.md](./backtesting-dia-d-premises-2026-07-31.md).  
> CORE-R: [list-auto-ops-2026-07-29.md](./list-auto-ops-2026-07-29.md) · [ISSUES.md](../../research/observations/ISSUES.md).

**AsOf:** 2026-08-01 · DÍA D **v0.11** · CORE-R **v1.8** · frescura Lista AUTO **v1.3** · CORE-B **v0.2**

---

## 0. Preflight

```bash
# Offline (obligatorio)
pnpm test:operativa

# API viva (tras reiniciar api-python)
pnpm test:operativa:smoke
# Forzar fallo si API cae / rutas 404:
OPERATIVA_API_REQUIRED=1 pnpm test:operativa:smoke
```

| Señal smoke | Acción |
|-------------|--------|
| `WARN: … 404` / `FA asOf sin metadata` | Reinicia **api-python** y reintenta |
| `PASS` + `OK Evidence` / `OK CORE-R` / `OK persist` | API al día |
| `SKIP: API unreachable` | Arranca `pnpm dev` / doctor |

---

## 1. Smoke UI — DÍA D (v0.11)

| # | Paso | Esperado |
|---|------|----------|
| D1 | Probar → fecha DÍA D **pasada** → Play → Finalistas | Embudo ≤ D; TOP #1 |
| D2 | #1 → **Simular D→hoy** | Trading + banner MODO DÍA D |
| D3 | Película Auto | HUD + equity; informe lateral |
| D4 | Semi: Aceptar / Rechazar | Pause; equity gated ≠ Auto si hay KO |
| D5 | **Pantalla completa** | Sin watchlist/ops/gráfico live; replay flex-1 |
| D6 | Salir pantalla completa **o recarga** | Docks de nuevo (fullBleed **no** se persiste) |
| D7 | **Narrar con IA** | 3 párrafos (heuristic si no Ollama) |
| D8 | **Guardar Evidence** | «Guardado» · aparece en Archivo |
| D9 | Archivo: preview · **JSON** · × | Preview; descarga; quita fila |
| D10 | **Importar** JSON (mismo valor) | Entra en Archivo; preview |
| D10b | Ayuda → Backtesting → Archivo Evidence | Mismos ítems; JSON / × |
| D11 | Análisis fundamental (D pasado) | badge blocked / reconstructed |
| D12 | **Salir DÍA D** | DEMO live intacta · docks/**Operaciones** restaurados |

---

## 2. Smoke UI — CORE-R / Monitor (v1.8)

| # | Paso | Esperado |
|---|------|----------|
| R1 | Monitor → lista con TOP + DEMO vinculada | Retorno % en fila |
| R2 | **Encolar revisiones** | Ítems open (informe y/o PnL ≤ −5%) |
| R3 | Deep-link Lab / Finalistas | Navega; **Hecho** cierra ítem |
| R4 | **Narrar cola** | Párrafos + band |
| R5 | **Auto-sync app abierta** ON | Prefs `scope=shell` + `listId` |
| R6 | Ir a Trading / otra ruta | Tick shell sigue (intervalo prefs); no pisa TOP |
| R7 | Chip **CORE-R N** en barra (hilos) | Clic → Ayuda · Backtesting scroll Monitor |
| R8 | Tick que añade filas | Toast + **Abrir Monitor** |
| R9 | **Hecho todos** (lista actual) | Abiertas → done; chip desaparece si 0 open |

---

## 3. Mapa de código (referencia rápida)

| Área | Archivos |
|------|----------|
| DÍA D sesión | `dia-d-trading-session-store.ts` · `trading-dia-d-banner.tsx` · `trading-dia-d-replay-panel.tsx` · `trading-layout.tsx` |
| Gate / Evidence UI | `dia-d-gate-equity.ts` · `dia-d-session-evidence.ts` |
| Evidence archivo | `dia-d-evidence-archive-store.ts` · `dia-d-evidence-archive-io.ts` |
| Evidence API | `explain_dia_d_session_evidence.py` · `POST /api/ai/dia-d/session-evidence` · `POST /api/research/dia-d-session-evidence` |
| asOf FA | `fundamentals_as_of.py` · `as_of_cut.py` · `get_instrument_fundamentals.py` |
| CORE-R juicio | `core-r-judgment.ts` |
| CORE-R cola | `core-r-review-queue-store.ts` |
| CORE-R cron | `core-r-scheduler.ts` · `core-r-scheduler-tick.ts` · `core-r-scheduler-host.tsx` |
| CORE-R chip | `core-r-status.ts` · `trading-app-threads.tsx` |
| Monitor | `strategy-monitor.ts` · `strategy-monitor-panel.tsx` |
| Ayuda | `backtesting-tracker.ts` · `backtesting-help-section.tsx` · `docs/HELP.md` |
| Batería | `scripts/research/verify_operativa_battery.mjs` · `verify_dia_d_api_smoke.py` |

---

## 4. No probar (congelado)

- Auto-paper D execute (`PAPER_D_EXECUTE`)
- Lab UI P3–P9 / Discovery / Belief UI
- Cron CORE-R multi-dispositivo (cola servidor)

---

## 5. Criterio «listo para pruebas a fondo»

### Preflight automatizado (2026-08-01)

- [x] `pnpm test:operativa` verde (72 web + 33 py + API smoke)
- [x] `OPERATIVA_API_REQUIRED=1 pnpm test:operativa:smoke` PASS (sin WARN 404)
- [x] `pnpm test:coach` · `pnpm test:fa` verdes
- [x] Ayuda trackers: DÍA D v0.11 · CORE-R v1.8 · frescura v1.3 (`HELP_CONTENT_AS_OF` 2026-08-01)

### Smoke UI humano (pendiente en APP)

- [ ] D1–D12 manual OK en un valor (incl. D6 recarga sin full-bleed · D12 Operaciones)  
- [ ] R1–R9 manual OK en lista con DEMO  
- [ ] Lista AUTO: reinicio → 2º Play → Omitido (histéresis v1.3)  
- [ ] Ayuda → Backtesting: guías DÍA D + CORE-R + Archivo + fila Lab CORE-B  
- [ ] Ayuda → Análisis del valor: checklist CAPM footnote · Composite v1.1  
- [ ] Ayuda → Trading: sección MODO DÍA D  
