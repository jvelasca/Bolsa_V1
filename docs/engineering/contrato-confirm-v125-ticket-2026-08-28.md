# Contrato — Confirm ticket V1.25 (Operational safety)

> **AsOf:** 2026-08-28 · **Estado:** **IMPLEMENTADO** (V1.25 operational safety).
> **Padre:** [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md) · [`traspaso-relevo-v1-24-honesty-2026-08-28.md`](./traspaso-relevo-v1-24-honesty-2026-08-28.md) · [ADR-040 §10](../adr/040-user-information-architecture.md).
> **Superficie:** drawer Confirm + `/confirm` → `SupervisedF3Panel` (`apps/web/src/features/settings/supervised-f3-panel.tsx`).
> **Freeze:** Confirm = firma · Ranking ≠ BUY · AUTO off · `PAPER_D_EXECUTE` off · sin nuevas puertas L1 · drag gráfico solo B-γ stop→Confirm (V1.34) · sin móvil.

---

## 0. Objetivo

Una sola autoridad de sizing desde TradePlan hasta la firma. El usuario puede editar cantidad / entrada / stop; la app **debe** recalcular, revalidar y (si excede el plan) exigir override con motivo. Ningún número del ticket default puede contradecir el plan sin declararlo.

Hoy (V1.24) **no** cumple esto: `riskPct={null}` / `target1={null}` en el bloque risk-first; `suggestQuantityFromCash` paralelo; what-if solo en Mesa.

---

## 1. Autoridad de sizing

| Caso                                                                         | Autoridad de `quantity`                                                                       | UI                                                                                                         |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| TradePlan status **TRIGGERED** (o equivalente operable con geometría válida) | `compute_risk_size` / campos `TradePlanV1.quantity`, `riskPct`, `riskAmount`, `initialRiskR`  | Default qty = plan qty; max sugerido = plan qty                                                            |
| Sin plan TRIGGERED                                                           | **No inventar** tamaño de riesgo                                                              | Modo `no_plan`: no prefill con `% caja` como si fuera mandato; qty manual o vacío; sin R firmado inventado |
| Propose paths (`propose-instrument-supervised`, alarms, finalists)           | Misma regla: si hay TradePlan TRIGGERED → plan qty; **no** `suggestQuantityFromCash` como SoT | Alinear o eliminar sizer paralelo en openings supervisados                                                 |

**Fórmula canónica (intacta):**  
`(equity × risk_pct/100) / |entry − stop|` → quantity (solo cuando el plan está TRIGGERED).

Fuentes: `packages/py/analytics/.../trade_plan.py` · `packages/shared/src/cognitive/trade-plan.ts` · `evaluateRiskSignature`.

---

## 2. Vista default del ticket (Nivel 1 — humano)

Visible **sin** expandir «Ajustes avanzados». Una sola columna, acción de firma prominente.

| Campo                       | Fuente                                       | Regla de honestidad                                                         |
| --------------------------- | -------------------------------------------- | --------------------------------------------------------------------------- | ------------------- | ----------------------------------------------------- |
| **Instrumento + lado**      | intent / TradePlan                           | —                                                                           |
| **Entrada**                 | plan entry o precio firmado                  | Editable → dispara recálculo                                                |
| **Stop**                    | plan stop / stop técnico                     | Editable → dispara recálculo; ≠ trailing sugerido                           |
| **Cantidad**                | plan qty (TRIGGERED)                         | Editable → dispara recálculo                                                |
| **Riesgo / acción**         | `                                            | entry − stop                                                                | `                   | Mostrar siempre si hay geometría                      |
| **Riesgo total €**          | `quantity ×                                  | entry − stop                                                                | ` (pérdida al stop) | **No** usar `cashImpact`/notional como «pérdida máx.» |
| **Riesgo % cartera**        | `riskAmount`/equity o firma recalculada      | **Nunca** `riskPct={null}` si hay TradePlan con `riskPct`                   |
| **R firmado**               | `evaluateRiskSignature`                      | Visible en default                                                          |
| **Exposición / notional**   | qty × price                                  | —                                                                           |
| **Cash after** (orden)      | ticket preview existente                     | Opcional en default si cabe; si no, en what-if                              |
| **What-if Antes → Después** | `buildPortfolioScenario` (misma fn que Mesa) | Capital / cash % / open risk R / sector / fit / veredicto                   |
| **CTA firma**               | Confirm                                      | Única acción primaria; copy «Firmar» / equivalente — nunca «BUY» de ranking |

### 2.1 What-if en ticket

- Reutilizar `buildPortfolioScenario` / proyección Mesa — **un solo modelo**, no un segundo calculador en Confirm.
- Mostrar al menos: riesgo abierto R, % sector (si conocido), cash %, veredicto fit (dentro / concentración / excede).
- Si datos insuficientes: estado honesto (`INSUFFICIENT_DATA`), no ceros inventados.

### 2.2 Copy de producto

- «Calidad» / ranking **no** aparecen como CTA de compra.
- Trailing propuesto, si se menciona: etiqueta **PROPUESTA — NO APLICADO** (vocabulario V1.24).

---

## 3. Vista avanzada (colapsada por defecto)

Tras «Ajustes avanzados» / equivalente:

| Bloque                                           | Hoy (V1.24)                  | V1.25                                                  |
| ------------------------------------------------ | ---------------------------- | ------------------------------------------------------ |
| Assessment checkboxes + `AssessmentBlock`s       | Siempre visibles             | **Dentro** de avanzado                                 |
| Protect / trailing / conflictos entre finalistas | Mezclados en el panel        | Avanzado                                               |
| Fees / margen detallado                          | `F3TicketPreviewBlock`       | Puede quedar bajo avanzado o segundo nivel del default |
| Override textarea                                | Ya en `F3RiskSignatureBlock` | Sigue; obligatorio cuando `overrideRequired`           |

Patrón: thinkorswim «ticket mínimo + Analyze bajo demanda» — sin crecer hacia TWS (Order Type / TIF / OCA / routing).

---

## 4. Recálculo y override (obligatorio)

### 4.1 Disparadores

Cualquier cambio de usuario a:

- cantidad
- precio de entrada
- stop

**obliga** a:

1. Recalcular pérdida al stop €, riesgo %, R, exposición, escenario what-if.
2. Re-ejecutar `evaluateRiskSignature` (y gate de apertura si aplica).
3. Si qty o pérdida firmada **>** plan (`riskAmount` / plan qty): `overrideRequired = true` + motivo no vacío para firmar.
4. Marcar inputs stale hasta que la firma se actualice (ya existe `inputsStale` — conservar).

### 4.2 Qué **no** hace el edit

- No reescribe silenciosamente el TradePlan persistido como si el usuario no hubiera cambiado nada.
- No presenta trailing sugerido como stop vigente.
- No usa `% caja` para «corregir» un plan TRIGGERED.

### 4.3 Bajar cantidad

Permitido sin override si la pérdida firmada ≤ plan. What-if y R se actualizan igual.

---

## 5. Sector limits / portfolio fit (P1 dentro de V1.25)

| Pieza          | Contrato                                                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Límite sector  | Visible en what-if del ticket; fuente única (hoy Mesa hardcodea `maxSectorExposurePct: 40` — V1.25 debe leer mandato/config, no un segundo literal en Confirm) |
| Fit            | Mismo veredicto que Mesa scenario                                                                                                                              |
| Excede mandato | Firma bloqueada **o** override explícito con motivo (producto: preferir bloqueo claro + override consciente; no silenciar)                                     |

Si el epic debe partirse: **P0** = sizing + €/%/R + recálculo + slim ticket; **P1** = what-if + sector limits en el mismo ticket. Ambos siguen siendo V1.25; no mezclar con V1.26 posición.

---

## 6. Tests de contrato (DoD)

Sin estos tests, V1.25 **no** se cierra.

| ID        | Afirmación                                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------------------ |
| T-SIZE-01 | Con TradePlan TRIGGERED, qty default = `plan.quantity`                                                                   |
| T-SIZE-02 | Con TradePlan TRIGGERED, `riskPct` mostrado = plan (nunca null en UI default)                                            |
| T-SIZE-03 | «Pérdida máx.» / riesgo € = pérdida al stop, no notional/`cashImpact`                                                    |
| T-SIZE-04 | Editar qty por encima del plan → `overrideRequired` y firma rechazada sin motivo                                         |
| T-SIZE-05 | Editar entry o stop → R y riesgo € cambian; what-if se invalida/recalcula                                                |
| T-SIZE-06 | Sin plan TRIGGERED, `suggestQuantityFromCash` **no** se presenta como sizing de mandato                                  |
| T-SIZE-07 | What-if ticket y Mesa what-if usan la misma función pura (`buildPortfolioScenario`) para el mismo input → mismos números |
| T-SIZE-08 | Assessments no están en el DOM visible default (colapsados / no montados hasta expandir)                                 |
| T-SIZE-09 | Ranking / Calidad nunca renderizan CTA de ejecución en el ticket                                                         |

Ubicación sugerida: tests junto a `f3-risk-signature-block.test.tsx`, `supervised-f3-panel` (si hay harness), y shared `risk-signature` / `portfolio-scenario`.

---

## 7. Fuera de alcance de este contrato

- Drag de niveles en gráfico
- Móvil / Capacitor / Web Notifications
- Command palette / hotkeys / layouts
- Colapsar puerta Hoy / nuevas puertas L1
- AUTO / `PAPER_D_EXECUTE` / thaw
- Promover trail a autoridad
- Position lifecycle durable (V1.26)
- Trocear `supervised-f3-panel.tsx` por mantenibilidad (deseable, no DoD)

---

## 8. Arranque del epic (checklist)

1. Leer este contrato + análisis Operative Flow + relevo V1.24.
2. Cablear `riskPct` / `target1` / pérdida al stop en el bloque default.
3. Colapsar assessments.
4. Montar what-if con `buildPortfolioScenario`.
5. Cerrar sizer paralelo en openings supervisados.
6. Añadir T-SIZE-01…09.
7. **No** tocar nav ni Mercado shell.
