# Plan de cierre de la operativa AUTO (FASE 3) — con motor

> **ESTADO: PARKED (2026-10-08).** **No vigente.** Reordenado por las [prioridades de producto `P1`–`P4`](../PROJECT_PREMISES.md)
> (§6): el foco pasa a claridad de entrada/salida, estrategia/indicadores y evaluación DÍA-D.
> **Dueño del disparador:** propietario. **Disparador de reactivación:** que un pilar `P1`–`P4` **exija**
> decisión durable de cartera o materialización de posición para sostener una operativa diaria ganadora.
> Hasta entonces, este plan **no** se ejecuta.

> **AsOf:** 2026-10-08 · **Base:** `v2.88.94-beta` · **Origen:** [`auditoria-operativa-auto-fase-2-2026-10-08.md`](./auditoria-operativa-auto-fase-2-2026-10-08.md) §5.
> **Naturaleza:** este plan **SÍ toca motor** — `Δ motor ≠ 0` es un resultado explícito y esperado (a diferencia de UI 6.x/7.0).
> **Objetivo:** cerrar `F2-1` (posición por operación), `F2-2` (`PortfolioDecision` durable), `F2-3` (resultado realizado agregado a primer nivel) y `F2-5`/`F2-6` (vocabulario de dinero virtual), sin romper `UI5-12` (`ranking ≠ decisión`), `UNKNOWN ≠ 0` ni la separación SIM/XTB.

## 0. Invariantes que el plan no puede romper

1. **`UNKNOWN ≠ 0`**: ningún eslabón nuevo se rellena; sin medición ⇒ «Sin dato todavía».
2. **`ranking ≠ decisión`** (`UI5-12`): `SELECTION`/`TOP_N` sigue siendo ranking; la decisión es otro objeto.
3. **Nada se fabrica**: `DECISION`/`POSITION` solo se materializan cuando el motor registra el hecho, con `measurement: COMPLETE`.
4. **Escalera que no salta peldaños** (`UI5-09`): «Posición creada» exige traza de materialización, no un fill.
5. **SIM/XTB**: AUTO sigue sin camino de dinero real; los eslabones nuevos no introducen cifras reales.
6. **No sexta puerta L1** (`UI5-02`): el chip de modo operativo (`UI5-21`) no cambia.

## 1. Slices

### `S0` — Gate de contrato y ADR (semántica antes que código)
- **Contrato:** enmendar `spec-ui-contract-5-0-2026-10-08.md` (§ decisiones durables y traza de posición) y añadir la regla falsable del **resultado realizado** en primer nivel.
- **ADR:** `docs/adr/044-auto-workspace-information-architecture.md` — AUTO **lee** decisión y posición durables (no las infiere).
- **Tests falsables (UI, sin motor):** el bloque «Decisión de cartera» deja de ser hueco **solo** si existe traza; la cifra «Resultado realizado» es «Sin dato todavía» cuando el read-model no la publica.

### `S1` — `F2-2` `PortfolioDecision` durable
- **Motor (`packages/py/**`):** registrar la decisión de cartera por tick/ciclo (activo, tamaño, asignación, motivo, sello, medición) en un registro durable. **Migración Alembic** nueva (head pasa de `052_top3_opportunities`).
- **Contrato:** exponer la decisión en el read-model del monitor (`AutoMonitorCycleV1`/paso `DECISION`) con `measurement`; `contract:gen` regenera `schema.d.ts`.
- **UI:** HOME «Decisión de cartera» y etapa `DECISION` de la historia pasan a dato real; si el motor no la materializa, siguen «Sin dato todavía».
- **Guard:** la decisión **no** se deduce de `TOP_N`/`TOP3`.

### `S2` — `F2-1` Posición por operación
- **Motor:** materializar un paso `POSITION` por ciclo desde `PositionState` **solo** cuando la posición esté realmente trazada (`measurement: COMPLETE`).
- **Contrato:** `steps[].id === "POSITION"` en el read-model.
- **UI:** `auto-operation-ladder.ts` puede alcanzar «Posición creada» con traza; `auto-operation-story.ts` despliega `POSITION` como fila propia (`foldedInto: null`).
- **Guard:** sin traza, la escalera sigue deteniéndose en «Ejecución completada» (comportamiento actual preservado).

### `S3` — `F2-3` Resultado realizado agregado
- **Motor:** publicar el P&L **realizado** (y, si procede, total) de la cuenta en el read-model de resumen que consume AUTO (hoy solo `totalUnrealizedPnl`; el realizado existe en dominio: `lifecycle`/`_sim_realized_pnl`).
- **Contrato:** nuevos campos en el resumen (`contract:gen`).
- **UI:** `auto-account-figures.ts` añade la cifra «Resultado realizado»; ausente ⇒ «Sin dato todavía» (nunca `0`). HOME y Cartera la muestran a primer nivel.
- **Guard:** no se mezcla realizado y no realizado bajo un único «Resultado».

### `S4` — `F2-5`/`F2-6` vocabulario de dinero virtual
- **Copy/UI:** unificar «CARTERA DEMO»/«Cuenta demo» con la frase oficial de dinero virtual (`AUTO_VIRTUAL_MONEY_PHRASE`); declarar la correspondencia explícita entre `DINERO VIRTUAL` (AUTO) y `LIVE VIRTUAL · SIMULADO` (camino manual/XTB) para que no se lean como dos cosas distintas.
- **Tests falsables:** primer nivel sin alternancia DEMO/PAPER/SIMULADO; la etiqueta de cuenta no contradice la frase oficial.

### `S5` — Verificación, evidencia y sello
- `typecheck` + `lint` + `vitest` + `pytest` (incluye `test_dia_d_bump_guard`) + `axe` E2E; `contract:check` verde con el contrato regenerado.
- **Bump**: monorepo + los 9 CLIs DÍA-D (`v2_89`…`v2_97`) a la nueva versión.
- **Evidencia**: `docs/engineering/evidence/<nueva-versión>/README.md` + `entrega-auditoria-externa-mia-…`.
- **Sello**: commit → tag anotado → `Release tag CI` (**`replay-repro` debe seguir `REPRODUCIDO`**; aquí `Δ motor ≠ 0` es esperado y se documenta, no se oculta).

## 2. Orden y dependencias

```
S0 (contrato/ADR)
  ├── S1 (PortfolioDecision durable)   ─┐
  ├── S2 (Posición por operación)       ├──> S5 (verificación + sello)
  ├── S3 (Resultado realizado)         ─┤
  └── S4 (copy dinero virtual)         ─┘
```

`S1` y `S2` tocan migraciones/contrato → se cierran antes de `S5`. `S3` depende del read-model que introduce `S1` (mismo esquema de medición). `S4` es independiente.

## 3. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La decisión o la posición se infieren del ranking/fill | Guard falsable por test: sin traza durable, el eslabón es «Sin dato todavía». |
| `contract:gen` rompe `contract:check` | Regenerar y versionar el contrato en el mismo slice. |
| Replay deja de reproducir por cambio de motor | `Δ motor ≠ 0` se documenta; `replay-repro` valida el **nuevo** artefacto esperado. |
| Migración rompe `lifecycle-pg`/`a7-gate` | Migración aditiva; `golden restart` y `dr-verify` cubren el arranque. |
| Se reintroduce vocabulario DEMO/PAPER a primer nivel | Test de copy (ya existente en `auto-copy.test.ts`) extendido a las nuevas cifras. |

## 4. Fuera de alcance (declarado)

`F2-4` (motivo de ranking durable por ciclo) y el read-model de riesgo por posición quedan **fuera** de este plan; se mantienen declarados como deuda en la auditoría FASE 2.
