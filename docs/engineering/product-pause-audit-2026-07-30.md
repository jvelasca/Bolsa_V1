# Pausa de producto — auditoría profunda (2026-07-30)

> Tras cerrar el embudo Finalistas (ACS OK), paramos a **auditar eficacia** antes del tramo de **Análisis Fundamental (FA)** y el control de versiones en **GitHub**.  
> App `0.1.0` · **no elevar versión** hasta cerrar esta pausa + backup + repo.

## 1. Veredicto en una frase

El embudo técnico **ya funciona** (Universo → Coach → Lab → Coach² → Finalistas), pero **aún no es óptimo ni “APP TOP de bolsa”**: frescura demasiado agresiva ante 1 vela, listas ops confusas, y borrar “favoritos” ≠ borrar Finalistas.

## 2. Hallazgos concretos (hoy)

### 2.1 Lista «IBEX35 SIN TOP» — no la creaste tú a mano

| Qué es | Lista **operativa efímera** creada en sesión de ops (audit missing), ID `4225247e9c004bd396c17a521` |
| Por qué aparece | `pnpm audit:ibex35:missing` + docs de handoff la usaban como atajo para Play solo sobre gaps |
| ¿Hace falta? | **No** como lista de producto. Confunde. Usa catálogo **IBEX 35** + frescura v1.2 |
| Acción usuario | **Eliminar** esa lista en UI de listas si sigue ahí |
| Acción código/docs | Dejar de empujarla como camino principal; el script `audit:ibex35:missing` queda como herramienta ops |

### 2.2 ACS «OMITIDO» tras borrar favoritos — bug de modelo mental + frescura

| Lo que hiciste | Borrar 3 estrategias en **Biblioteca / favoritos** |
| Lo que el sistema usaba | **InstrumentStrategyTop** (Finalistas) + huella en `localStorage` / sesión |
| Resultado | Lista AUTO → **Omitido** aunque “ya no hubiera TOP útil” en tu cabeza |

**Fix v1.2 (esta pausa):**

- `shouldSkipFinalistsSearch` solo omite si **`hasSlots === true`** (Finalistas reales) **y** huella igual.
- Sin slots → `no_finalists_slots` → **analizar**.
- UI **Eliminar Finalistas** en el panel TOP + `clearLocalFreshnessFingerprint`.
- Borrar en Biblioteca **no** borra el TOP; hay que usar Eliminar Finalistas (o DELETE API).

### 2.3 Una vela nueva ≠ “NUEVO TOP” de inversión (5y+)

| Hoy | `lastBarDate` entra en la huella → 1 barra nueva → **no Omitido** → re-embudo completo |
| Reescritura TOP | Sigue exigiendo mejora Lab / política de save (no pisa a ciegas) |
| Problema | CPU/tiempo y sensación de “todo cambió” cuando la tesis no cambió |
| Deuda (cerrada v1.3 · 2026-08-01) | **Histéresis lastBar:** en `1d` hasta 5 días calendario desde el stamp → Omitido (`bar_hysteresis`); stamp **no** se desliza; «Reevaluar resto» fuerza |

Conclusión: el diseño es **conservador en contenido TOP** y, desde v1.3, **menos agresivo en coste** ante 1–pocas barras nuevas.

## 3. ¿Son eficaces las herramientas locales y de IA?

| Capa | Estado | Notas |
|------|--------|--------|
| Motor backtest local | Útil | Genéricas + Lab OOS son el núcleo cuantitativo |
| Coach / perfil (local) | Operativo | Une preferencias a ranking; no es “alpha” |
| Dual-audit / LLM | Apoyo | Narrativa y contraste; **no** sustituye FA ni riesgo real |
| CORE-R Monitor | v1.8 | Cola · OOS · PnL · Narrar · cron shell · chip · toast→Monitor · Hecho todos · multi-dispositivo pendiente |
| Finalistas | Cierre embudo | Fuente #1 para paper |
| FA / FIE | Cerrado en código | F0–F2.8 + F3/F4 + Paper D (execute off) · Beneish→distress · densificación UI |

**Eficacia relativa hoy:** buen **laboratorio de TA** + FA operable + orquestación. Frescura Lista AUTO v1.3 con histéresis lastBar.

## 4. Mapa de producto (dónde estamos)

```text
[Hecho · embudo AT]     1 Genéricas → 2 Coach¹ → 3 Lab → 4 Coach² → 5 Finalistas
[Hecho · operativa]     DÍA D v0.11 · CORE-R v1.8 · Lista AUTO frescura v1.3 (histéresis)
[Hecho · FA]            FIE F0–F2.8 + F3/F4 · Beneish distress · Tarjeta densificada
[Deuda]                 Cobertura Yahoo nulls · calibrar ADV/mcap
[Congelado]             Auto-paper D · Lab P3–P9 · Belief · CORE-R multi-dispositivo
```

Diseño listas: [`lists-universes-design-2026-07-30.md`](./lists-universes-design-2026-07-30.md).

**Congelado (no tocar en esta pausa):** Auto-paper D · Lab UI P3–P9 deep · Discovery · Belief deep.

## 5. Copias de seguridad (antes de elevar versión)

Copias en `docs/engineering/backups/2026-07-30/`:

- `session-handoff-2026-07-30.md`
- `list-auto-ops-2026-07-29.md`
- `assistant-play-funnel-design-2026-07-29.md`
- `backtesting-funnel-handoff-2026-07-29.md`
- `research-lifecycle.md`

Código crítico tocado en esta pausa (revisar en diff):

- `backtest-finalists-freshness.ts` (+ tests)
- `instrument-strategy-top-panel.tsx`
- `backtests-page.tsx` (rama error TOP)

## 6. Plan GitHub (cuenta del usuario)

El workspace **aún no es un repo git** (`fatal: not a git repository`). Plan propuesto:

1. `git init` + `.gitignore` sólido (node_modules, `.env*`, `logs/`, dist, secrets).
2. Primer commit baseline (sin secrets) · tag `v0.1.0-pause` **solo cuando digas**.
3. Crear repo privado en GitHub (`gh repo create`) · `main` protegida.
4. Flujo: `feature/*` → PR → review → merge; Issues para FA / histéresis / paper.
5. Opcional: Actions (test coach + lint web) antes de merge.
6. **No** `force push` a main; no subir `.env` ni dumps con datos personales.

## 7. Criterios para “cerrar pausa” y empezar FA

- [x] Política Omitido solo con Finalistas reales  
- [x] Eliminar Finalistas en UI + clear huella  
- [x] Documentar lista IBEX sin TOP como ops (borrar en UI)  
- [ ] Usuario elimina lista «IBEX… SIN TOP» si molesta  
- [ ] Smoke: borrar Finalistas ACS → Play Lista IBEX → ACS **no** Omitido  
- [ ] Repo GitHub + primer tag (cuando lo pidas)  
- [ ] Histéresis 1-barra (ticket FA/tech, no bloqueante absoluto de FA)

## 8. Referencias

- [`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md) — frescura v1.2  
- [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md)  
- [`research-lifecycle.md`](./research-lifecycle.md)  
