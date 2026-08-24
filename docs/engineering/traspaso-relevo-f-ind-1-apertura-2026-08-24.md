# RELEVO — F-IND-1 causalidad indicadores (Ciclo 5/5) → coordinador

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** handoff del subagente **Ciclo 5/5** (auditoría AS-IS F-IND-1) al coordinador.
> **AsOf:** 2026-08-24 · HEAD **`e3b943a`** · tag **`v1.7.0-beta`** · **sin commit** (docs-only en working tree).

---

## 1. Veredicto

| Campo                             | Valor                                                          |
| --------------------------------- | -------------------------------------------------------------- |
| **F-IND-1**                       | **CLOSED** — merge `79fa155`, ancestro de HEAD                 |
| **F-IND-2**                       | **CLOSED** — merge `09fb06b`, ancestro de HEAD                 |
| **Trabajo de código pendiente**   | **Ninguno**                                                    |
| **«Residual» en relevos previos** | **Deriva documental** (nota obsoleta F2 en `PROJECT_STATE.md`) |

Audit pack: [`audit-f-ind-1-causalidad-indicadores-2026-08-24.md`](./audit-f-ind-1-causalidad-indicadores-2026-08-24.md)

---

## 2. Qué se hizo en Ciclo 5 (read-first + verify + docs)

| Ítem                                                                     | Resultado                                               |
| ------------------------------------------------------------------------ | ------------------------------------------------------- |
| Lectura backlog §0/§3, `PROJECT_STATE` F2/F-IND rows, relevos tag/D3/ops | Completada                                              |
| Búsqueda `causal*` en repo                                               | 6 ficheros productivos + tests                          |
| Verificación git ancestry `79fa155` / `09fb06b`                          | Ambos en HEAD                                           |
| Batería pytest causality                                                 | **39/39** passed                                        |
| Batería vitest metadata                                                  | **5/5** passed                                          |
| Audit AS-IS                                                              | `audit-f-ind-1-causalidad-indicadores-2026-08-24.md`    |
| Plan residual                                                            | **No creado** — ítem CLOSED                             |
| Higiene doc trivial                                                      | `PROJECT_STATE.md` §2 F2 + §3 intro + §4 «Aún vigentes» |
| Código productivo                                                        | **0 cambios**                                           |

---

## 3. Evidencia clave (una línea cada guardia)

- **Metadata:** `indicator-universe.ts:156-185`, `IND-FR` `:972-974`, `IND-ICH` `:1008-1011`
- **Runtime guard:** `rules_engine.py:53-55`, `:71-79`
- **Validator:** `strategy_definition_validator.py:67-76`
- **Tests:** `test_causality_layer.py`, `test_causality_battery_ind_2.py`, `indicator-causality.test.ts`

---

## 4. Follow-ups opcionales (decisión propietario — no abrir sin plan)

1. **Recalcular trials** que usaran `chikou` pre-merge (impacto en resultados históricos; «no recalcular aún» pactado 2026-08-19).
2. **ADR-014** causal profundo (grafo/discovery) — fase distinta, diferida en ADR-013/017.

---

## 5. TEXTOS DE PASO

### 5.1 Coordinador — post-commit docs (si aprueba)

> Ciclo 5/5 F-IND-1 **CERRADO (AS-IS)**. Audit: `audit-f-ind-1-causalidad-indicadores-2026-08-24.md`. F-IND-1/2 ya estaban mergeados; el «residual» era doc stale. Batería: pytest causality 39/39 · vitest 5/5. Sin código productivo. Siguiente ciclo: decisión propietario (OrderProposal/Journal Ciclo 1 sigue activo en working tree).

### 5.2 Brief subagente (patrón — no reabrir F-IND-1)

> **NO reabrir F-IND-1** salvo nuevo indicador no causal sin metadata/guardia. Al añadir indicadores implemented/production: declarar `causal`/`confirmationLag` en `indicator-universe.ts` + extender batería F-IND-2 si aplica.

---

## 6. Enlaces

- Audit: [`audit-f-ind-1-causalidad-indicadores-2026-08-24.md`](./audit-f-ind-1-causalidad-indicadores-2026-08-24.md)
- Backlog: [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) §0
- Estado vivo: [`PROJECT_STATE.md`](./PROJECT_STATE.md) §3 F-IND-1/2
- Cierre ola hardening: [`traspaso-ola-hardening-cierre-2026-08-19.md`](./traspaso-ola-hardening-cierre-2026-08-19.md)
