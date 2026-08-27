# RELEVO — V1.23 UX Consolidation & Operational Cockpit (2026-08-27)

> **AsOf:** 2026-08-28 · **Estado:** **PUBLICACIÓN** — tag `v1.23-beta` → `4bc7426c`. **Release tag CI:** [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33122128224).
> **Padre:** [`traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md`](./traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md) · [ADR-040](../adr/040-user-information-architecture.md) §9 · [diseño Mercado 2.0](./diseno-mercado-2-0-cockpit-2026-08-27.md).
> **Tag relevo:** [`traspaso-relevo-tag-v1-23-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-23-beta-2026-08-28.md).

---

## 0. Qué cierra V1.23

| Pieza                                                            | Estado                                  |
| ---------------------------------------------------------------- | --------------------------------------- |
| Estudio `ok` / `empty` / `unavailable`                           | CÓDIGO + tests (offline `py-operativa`) |
| H2 `target1AchievedAt` en portfolio DTO → cockpit                | CÓDIGO                                  |
| Funnel as-of honesto (null si no hay scan) + 3 relojes           | CÓDIGO                                  |
| Mercado: Listas Estudio-first · overlays · Operaciones filtradas | CÓDIGO                                  |
| `InstrumentOperationalContext` + fase CONFIRMADA                 | CÓDIGO                                  |
| Hoy inbox 4 niveles · Ver detalles · sin pestaña Confirmar       | CÓDIGO                                  |
| Prioridad N/100 · NO ES UNA ORDEN · funnel en castellano         | CÓDIGO                                  |
| Asesor: Journal bridge · estudio_status UI                       | CÓDIGO                                  |

## 1. Freeze heredado

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado · DEX-1…5 · BETA.

## 2. Checklist salida BETA (gate, no epic)

**Backend**

- [x] Tests H1 empty vs unavailable verdes (offline + CI)
- [x] Ninguna ruta Daily Ops amplía Estudio
- [x] Un stop vigente (`currentStop`)
- [x] T1 tocado ≠ gestionado visible en Mercado
- [x] Freshness no miente (as-of null sin scan)
- [x] Trail no escribe stop

**UX**

- [x] Mercado E2E wiring: listas → gráfico con niveles → panel contextual → Confirm sin salir
- [x] Hoy solo atención (inbox)
- [x] Asesor no ejecuta
- [x] Cuenta no es protagonista

## 3. Fuera de V1.23

OpportunityScore · VaR · correlación · batch propose · promover trail · grid Cobertura 180 · thaw/AUTO.

## 4. Verificación (2026-08-28)

```bash
pnpm --filter @bolsa/shared build          # PASS
pnpm --filter @bolsa/web exec tsc --noEmit # PASS
pnpm test:daily-ops:offline                # PASS (6/6)
pnpm test:decision-spine                   # PASS (497)
```

H1: `test_daily_ops_report.py` en `pyOperativaTests` (offline). Digest email/pdf siguen `--with-report`.

**CI tag:** [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33122128224) · tip `4bc7426c`.

## 5. Next

Post-auditoría: un epic. No mezclar OpportunityScore / thaw.
