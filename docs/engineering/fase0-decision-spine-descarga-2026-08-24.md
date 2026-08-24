# F0.4 — Descargue de decisión: orden de gates y autorización (docs-only)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Ciclo:** Fase 0 Decision Spine · rebanada **F0.4** (docs-only).
> **AsOf:** 2026-08-24 · HEAD `f69a7b0` == `origin/main`.
> **Depende de:** [AS-IS F0.1](./fase0-decision-spine-asis-2026-08-24.md) + [TO-BE F0.2](./fase0-decision-spine-tobe-2026-08-24.md) + [Mapping F0.3](./fase0-decision-spine-mapping-2026-08-24.md).
> **Alcance:** cómo las colas convergen en un Decision Package y qué orden de gates/autorización garantiza «el mismo motor, otra policy». **Solo documento; el código de spine requiere plan + aprobación (premisa E1).**
> **Nota de método:** cita `file:line` sobre los EXISTS ya validados; no inventa.

---

## 1. El descargue (dónde convergen las tres colas)

El TO-BE pone UN punto de integración antes de `ExecuteTrade`:

```text
cola SEMI  ─┐        run_decision_runtime       policy_gate.py:57       accounts/trade.py:17
cola AUTO  ─┴──▶  decision_runtime.py:256  ──▶  risk (check_opening)  ──▶ ConfirmRecommendationIntent (SEMI)
cola Dictan ┘          │ DecisionPackage          risk_engine.py:55   │     O  ExecutionRouter (AUTO)
                    decision-package.ts:39       ("cesta" único)       └──▶ ExecuteTrade
```

- SEMI (`confirm_recommendation.py:87`) y AUTO (`execution_router.py:638`) **ya llaman** a `ExecuteTrade`. El cambio es insertar **antes** de ese fill el DecisionPackage + gate/risk **común**, no dos autores distintos.
- El Runtime (`decision_runtime.py:256`) es el **único** que construye `Recommendation` (`recommendation.py:23`) — no hay dos rutas de decisión.

## 2. Orden de gates del spine (único pre-fill)

1. **Assessment/Evidencia** — las colas emiten evidencia tipada (Opportunity, Dictamen, Composites). Cero decisión aquí.
2. **DecisionRuntime** (`decision_runtime.py:256`) — fusiona evidencias, **no vota**: produce **DecisionPackage** (`decision-package.ts:39`).
3. **Policy Gate** (`policy_gate.py:57`) — PASS/VETO; propose es pasivo, `paper_auto`/live es veto duro (AS-IS §6).
4. **Risk de cesta** (`check_opening`, `risk_engine.py:55`) — **aplica a SEMI y AUTO por igual** (cierra el gap de F0.2 §7: hoy SEMI lo salta).
5. **Fill** — `ExecuteTrade` (`accounts/trade.py:17`), único puerto.

**Diferencia SEMI vs AUTO = autorización, no arquitectura** (AS-IS §4): SEMI pasa por el override humano en `/confirm`; AUTO pasa por la policy `paper_auto`/scan/Paper-D.

## 3. Decisión del propietario (bloqueante — no decido yo)

| #      | Pregunta                                                                                           | Opciones                                                                               | Estado                                                                                                                                                                                                                                                                                                                                         |
| ------ | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | Si `check_opening` de cesta falla en SEMI, ¿puede el humano **overridear** o el risk aplica igual? | (a) override humano con aviso · (b) risk siempre bloquea el fill en papel como en AUTO | ✅ **ACEPTADA (b) — risk de cesta idéntico en SEMI y AUTO, sin override** (decisión propietario, 2026-08-24). SEMI deja que `check_opening` bloquee igual que AUTO; así SEMI no es «otra caja». Override solo como caso futuro con policy explícita.                                                                                           |
| **D2** | ¿Quién se considera **autoridad** entre `DecisionPackage` y `Recommendation`?                      | (a) package = contrato, Recom = cara operativa · (b) Recom = contrato                  | ⏳ recomendada **(a)** (RFC-008 §14) — pendiente confirmación                                                                                                                                                                                                                                                                                  |
| **D3** | ¿El Lab/Radar quedan **fuera** del spine?                                                          | (a) fuera (laboratorio, `ADR-019`) · (b) el diario puede proponer a la mesa            | ✅ **ACEPTADA (a) — Lab/Radar FUERA del spine (laboratorio, ADR-019)** (decisión propietario, 2026-08-24). El spine gobierna SOLO el universo TRADING; Lab/Radar son universo paralelo que **recomiendan** (evidencia/oportunidad) y no entran en la columna autoritativa de decisión (AS-IS `/backtests`=`BacktestsRouteSlot` «Laboratorio»). |

> **D1 CERRADA por el propietario.** D2 (cerrada con código `f7b1f6c`: DecisionPackage = contrato) y **D3 (cerrada 2026-08-24: Lab/Radar fuera del spine)** ya no bloquean. Con D1, el descargue queda definido: **mismo gate + mismo risk en SEMI y AUTO**; el único parámetro que difiere es la **autorización** (humano `/confirm` vs policy `paper_auto`). F0.5 (Fit) y F0.6 (Daily vista) CERRADAS con código (F0.5b `3670a09` · F0.6b `8df8a65` · F0.6-UI `672e88f`).

---

## 4. Lo que el descargue NO cambia

- Motor money / `ExecuteTrade` internals (congelado).
- Policy Gate / Risk **existentes**: se **convierten en destino común**, no se reescriben.
- `contract:gen` NO se toca en Fase 0 docs.
- Daily es **vista**, no orquestador (no-op en F0.3).

---

## 5. Fuera de alcance F0.4

F0.5 (Fit code) · F0.6 (Daily vista code) · motor money · Belief · gobernanza IA · Track B. **Solo documento.** Implementación de spine requiere plan de fase + aprobación (premisa E1).
