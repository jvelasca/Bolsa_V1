# ADR-028: R-9 F9 analytics↔market — diferido (estado verificado 2026-08-22)

**Estado:** Aceptado (no acción)  
**Fecha:** 2026-08-22  
**Contexto:** Plan R-9 FASE 9 · informe [R-9 F9 analytics↔market ADR](b9df72c2-faeb-4bb2-9cbf-3118f771d428)

## Contexto

La auditoría original reportó ciclo `bolsa_analytics` ↔ `bolsa_market`. F4 (2026-08-11) movió tipos compartidos a `bolsa_domain` y rompió el ciclo en `src/`.

## Decisión

**Opción A — Diferir F9 a V2.** No abrir B2 (deprecación `legacy_portfolio_id`) mientras motor money esté en freeze (R-13).

### Estado verificado (HEAD `b4efeff`)

| Ítem                           | Estado                                     |
| ------------------------------ | ------------------------------------------ |
| analytics → market en `src/`   | **0 imports**                              |
| market → analytics en `src/`   | **0 imports**                              |
| Tests market → analytics       | **2 ficheros** residuales                  |
| import-linter analytics↔market | **No existe** (3/3 otros contratos verdes) |
| Puente `legacy_portfolio_id`   | **Activo** (~31 ficheros Python + OpenAPI) |

## Consecuencias

- **B1 opcional (futuro):** corregir 2 tests + añadir contrato import-linter — bajo riesgo, sin migración.
- **B2 (V2):** deprecación legacy bridge requiere ADR propio + migración DB + `contract:gen` pactado.
- R-9 permanece **CERRADA** sin F9; deuda documentada en backlog §0.

## Referencias

- `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md` § FASE 9
- `docs/engineering/traspaso-f4-arquitectura-python-2026-08-11.md`
