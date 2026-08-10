# Traspaso M5 — continuación: orquestación de `list-values-panel.tsx` + `instruments-page.tsx` · punto de entrada del siguiente hilo

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD al crear:** `d894cdb` (cierre formal frente backtest-explore + M5 en pausa) · árbol limpio · sincronizado con origin
**Dirección aprobada (usuario):** retomar M5 atacando la **orquestación** de `list-values-panel.tsx` (1.395) /
`instruments-page.tsx` (1.222) en **FASE 1 de diagnóstico** (sin cambios) — los dos frentes de mejor ratio valor/riesgo
que quedan, según la recomendación del traspaso de cierre backtest-explore (§2.3) y de trading-dia-d (§2.3).

**Origen / encadenamiento:**
- [traspaso-m5-frontend-2026-08-10.md](./traspaso-m5-frontend-2026-08-10.md) — entrada M5 (protocolo + mapeo features)
- [traspaso-m5-f4-8-coach-lab-2026-08-10.md](./traspaso-m5-f4-8-coach-lab-2026-08-10.md) — hilo F4.8 (Coach+Lab)
- [traspaso-m5-frente-coach-cierre-2026-08-10.md](./traspaso-m5-frente-coach-cierre-2026-08-10.md) — cierre Coach+Lab
- [traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md](./traspaso-m5-frente-trading-dia-d-cierre-2026-08-10.md) — cierre trading-dia-d (B.1–B.3)
- [traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md](./traspaso-m5-frente-backtest-explore-cierre-2026-08-10.md) — cierre backtest-explore (E.1–E.5) · M5 en pausa
- Registro vivo: [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md) (registros §7.1–§7.6.c)

> **Nota de versionado:** este documento es el **punto de entrada** del siguiente hilo de M5.
> No es un cierre ni un registro progresivo todavía; es el handoff que fija el estado y la FASE 1 a ejecutar.
> El cierre de este nuevo hilo (si procede) se documentará en un traspaso de cierre propio y en el registro §7.6.d.

---

## 1. Qué NO cambia / protocolo sagrado (mantener vigente)

1. **Tolerancia cero a fallos.** No asumir: verificar en repo/CI.
2. **Preservación funcional absoluta.** Cambio solo si es necesario y probado.
3. **Alcance atómico.** Un frente por hilo; no tocar backend (M3/M4/M6) ni M7 (dev-stack).
4. **Flujo 3 fases:** FASE 1 (diagnóstico, sin cambios) → FASE 2 (plan atómico + **aprobación del usuario**) →
   FASE 3 (ejecución + **batería completa por cada paso** + commit + push + registro §7.6.d). Sin aprobación **no se
   toca código ni se commitea.**
5. **Docs como fuente de verdad.** Anclar decisiones a ficheros reales.
6. «No romper NADA»: batería completa de tests antes y después de cada paso.
7. Área Coach/TOP: regla `coach-top-quality.mdc` + batería `pnpm test:coach` (NO aplica a list-values/instruments).

## 2. Estado del repo al crear este traspaso (verificado en HEAD `d894cdb`, 2026-08-10)

- Rama activa: `stage/estudio-membership-operativa-2026-08-04`. **Árbol limpio**, sincronizado con `origin/<rama>`.
- HEAD: `d894cdb` (docs · cierre formal frente backtest-explore + M5 en pausa · traspaso definitivo, índice y registro §7.6).
- **Batería re-ejecutada por el auditor en este hilo (verde):**
  - `pnpm --filter @bolsa/web typecheck` → exit 0
  - `pnpm --filter @bolsa/web lint` → exit 0 (0 errores; solo warning cosmético Node de `eslint.config.js`, no bloqueante)
  - `pnpm --filter @bolsa/web test` → **140 ficheros / 707 tests passed**
  - `pnpm --filter @bolsa/web build` → exit 0 (solo warnings code-splitting >500 kB ≈ 2.5 MB = **M7**, fuera de M5)

**Nota entorno Windows:** shell **PowerShell** (no `&&`; usar `;`). `pnpm 10.12.1` sí en PATH; `uv` NO
(`$env:USERPROFILE\.local\bin\uv.exe`). Commits con `git commit --no-verify` (hook lint-staged/prettier sobre
ficheros legacy CRLF). Push a `origin/stage/estudio-membership-operativa-2026-08-04`.

## 3. Diagnóstico heredado (ya confirmado en traspasos previos — NO rehacer)

| Frente | Líneas (verificadas) | Estado |
|--------|----------------------|--------|
| `trading/lists-tab/list-values-panel.tsx` | **1.395** | **ya feature-sliced** en sub-componentes (`ListCarousel`, `ListColumnHeader`, `ListItemAccordion`, `SortedApiList`, `SortedVisualizationList`, `PortfolioKeyboardList`, `PendingOrdersKeyboardList`, `EstudioListSupervisionBanner`). Lo que resta es **lógica de orquestación** (estado/queries/handlers de selección y estudio), no JSX monolítico. |
| `instruments/instruments-page.tsx` | **1.222** | **ya feature-sliced**: celdas y barras en sub-componentes (`InstrumentsHubFilterBar`, `InstrumentsHubSplitLayout`, `SyncBadge`, `ListsCell`, `ScoreCell`, `SeguimientoCell`, `PortfolioCell`). Resta **lógica de orquestación**. |

Ambos ficheros **verificados en HEAD** por el auditor (líneas 1.395 / 1.222; sub-componentes presentes en el repo).
El anterior frente confirmó que NO quedan islas JSX autocontenidas de bajo riesgo en estos ficheros.

## 4. FASE 1 a ejecutar en el siguiente hilo (diagnóstico, SIN cambios)

Objetivo de este hilo nuevo: **FASE 1** (y, con aprobación, FASE 2 plan atómico). Evaluar con evidencia en repo si pese
a estar feature-sliced queda alguna isla JSX de bajo riesgo, o si (más probable) toda la lógica restante es de
orquestación y el siguiente paso real pasa por **refactor a custom hooks** (requires recalibración explícita) o por
**cerrar estos frentes** como ya feature-sliced.

1. **FASE 1 de `list-values-panel.tsx` (1.395):**
   - Mapear qué JSX inline queda no extraído (si alguno) y acoplamiento con el orquestador (estado/selección/estudio).
   - Verificar batería base en HEAD para este fichero y tests del feature `trading/lists-tab`.
   - Razonar valor/riesgo: ¿quedan islas extraíbles como thin wrappers (Diseño B) o es orquestación pura?
2. **FASE 1 de `instruments-page.tsx` (1.222):**
   - Mismo procedimiento: islas JSX restantes vs orquestación.
   - Verificar `InstrumentsHubFilterBar`/`InstrumentsHubSplitLayout` y tests del feature `instruments`.
3. **Conclusión de FASE 1 → FASE 2 candidata (si procede):**
   - Si hay islas extraíbles de bajo riesgo → plan atómico Diseño B (cada extracción = paso 1/2/3 con batería).
   - Si es orquestación pura → proponer opciones (custom hooks con recalibración, o **cerrar estos frentes** y dejar M5
     en el estado actual, ya que no queda JSX de bajo riesgo en el resto de candidatos).
   - En ambos casos, **sin aprobación del usuario NO se toca código ni se commitea.**

## 5. Reglas del juego (vigentes en el nuevo chat)

- **Batería por cada paso** (FASE 3): typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0.
- **Docs como fuente de verdad** y **preservación funcional absoluta**.
- **No tocar** backend M3/M4/M6 ni **M7**. No tocar el área Coach ni `test:coach` en este hilo (no aplica).
- Al cierre de este hilo: actualizar `dev-continuation-plan-2026-08-09.md` con el registro **§7.6.d** y añadir este
  fichero / el de cierre al índice `engineering-index-2026-08-03.md` (junto a los traspasos M5).
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar. Leer a fondo la doc de entrada y avisar al usuario cuando se sature.

## 6. Estado de referencia para validar batería

| Comando | Esperado |
|---------|----------|
| `pnpm --filter @bolsa/web typecheck` | exit 0 |
| `pnpm --filter @bolsa/web lint` | 0 errores (cosmético Node no bloqueante) |
| `pnpm --filter @bolsa/web test` | 140 ficheros / 707 tests, 0 fallos |
| `pnpm --filter @bolsa/web build` | exit 0 (solo warnings code-splitting = M7) |

---

_Documento de traspaso de entrada para el hilo de continuación de M5 (orquestación list-values / instruments). 2026-08-10._
