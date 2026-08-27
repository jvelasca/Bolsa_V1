# Audit pack — estado global v1.20 (Arquitectura de usuario / consolidación UX)

> **AsOf:** 2026-08-27 · **Tag (stamp):** **`v1.20-beta` → `cb849514`** (feature `a28e4a93`). Partida **`v1.19-beta` → `dc9327d`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-040](../adr/040-user-information-architecture.md) · ADR-037 §8 · pack previo [`audit-pack-estado-global-2026-08-27-v119.md`](./audit-pack-estado-global-2026-08-27-v119.md).
> **Para:** auditoría cruzada post-v1.20 · Release tag CI (pin tras GREEN).

---

## 0. Veredicto interno

Ciclo **V1.20** **CERRADO** (arquitectura de información de usuario + cleanup de navegación + Trading terminal + Hoy por vistas + continuidad oportunidad→Mercado). **No** añade motores, scores ni colas. Reorganiza **rutas de acceso** para que el usuario no tenga que conocer Decision Spine, Consola ops, Decision Journal o Libro. DEX-1…DEX-5 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **OFF**. AUTO **off**. LIVE **experimental**. Producto **BETA**. OpportunityScore **aparcado** (explícito).

| Epic     | Nombre                                                               | Estado  |
| -------- | -------------------------------------------------------------------- | ------- |
| UX-IA    | ADR-040 · 5 puertas L1 · mapa módulo→puerta · UX-01…05               | CERRADO |
| NAV-L1   | Header Hoy·Mercado·Cartera·Asesor·Laboratorio · sin Herramientas L1  | CERRADO |
| TRADING  | Sin HoyCommandStrip/MesaOperationalBar · TradingHealthStrip          | CERRADO |
| HOY-VIEW | `?view=` resumen/posiciones/oportunidades/decisiones/journal/confirm | CERRADO |
| CONT     | Opportunity drawer · Ver en Mercado · Preparar orden                 | CERRADO |

**Mensaje clave:** v1.19 separó Opportunity Discovery del Decision Board; v1.20 hace el equivalente en la UI — **arquitectura interna ≠ arquitectura de usuario**.

---

## 1. Scorecard

| Epic        | Cierra                                               | Evidencia                                                       |
| ----------- | ---------------------------------------------------- | --------------------------------------------------------------- |
| **UX-IA**   | 5 conceptos; nombres internos fuera del flujo diario | `040-user-information-architecture.md` · `daily-nav.ts` UX_DOOR |
| **NAV-L1**  | Sin Spine/Consola/Journal/Libro/Señales/Confirm L1   | `app-top-bar.tsx` · `daily-nav.test.ts`                         |
| **TRADING** | Terminal limpio                                      | `trading-layout.tsx` · `trading-health-strip.tsx`               |
| **HOY**     | Vistas + label «Hoy»                                 | `mesa-hoy-page.tsx` · `mesa-hoy-view.ts` · redirects `app.tsx`  |
| **CONT**    | Continuidad símbolo                                  | `opportunity-drawer.tsx` · `openHitInTrading`                   |

---

## 2. Batería (local, 2026-08-27)

| Gate                                          | Resultado                  |
| --------------------------------------------- | -------------------------- |
| Web `tsc --noEmit`                            | OK                         |
| Web daily-nav + mesa-hoy + zone1 + candidates | **35** passed              |
| `pnpm test:decision-spine`                    | **497** (sin cambio spine) |

```bash
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/web test -- daily-nav mesa-zone1 mesa-hoy-view mesa-candidates mesa-hoy
pnpm test:decision-spine
# expect: 497 passed
```

Spine: **497** (v1.19) → **497** (v1.20; UX-only).

---

## 3. Freeze (intacto)

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · BETA · Scenario ≠ permiso · Ranking ≠ BUY · Opportunity ≠ Permission · Stress ≠ permiso · Decision Board ≠ screener · LLM no ejecuta · LAB ≠ TRADING.

---

## 4. Deuda restante (explícita)

| ID          | Limitación                                | Severidad   |
| ----------- | ----------------------------------------- | ----------- |
| OPP-SCORE   | OpportunityScore multiplicativo (backlog) | Producto    |
| OPP-ENGINE  | Análisis TA+FA universo amplio            | Producto    |
| STRESS-FULL | Correlación / VaR                         | Producto    |
| V118-B      | B-read Mesa / backfill legacy             | ADR-038     |
| LAB-B       | Backtest ≠ TradingPolicy                  | Lab         |
| THAW        | Accept estricto 60d/50/70/55              | Deuda larga |
| AUTO-ON     | AUTO on / LIVE producción                 | Freeze      |

---

## 5. Qué **no** entra

OpportunityScore · nueva cola · nuevo motor · thaw · AUTO on · `contract:gen` · cambios Confirm/spine.
