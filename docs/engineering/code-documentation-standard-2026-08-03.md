# Estándar de documentación de código (2026-08-03)

> **Premisa de proyecto:** [PROJECT_PREMISES.md](../PROJECT_PREMISES.md) §1 — *documentar todo* (producto **y** código).  
> **Qué cubre este doc:** docstrings / JSDoc en código.  
> **Qué no cubre:** docs de producto y auditoría (viven en `docs/` — ver [audit-pack](./audit-pack-post-audits-2026-08-03.md)).  
> **AsOf:** 2026-08-03 · Medición inicial: ~82% defs públicas Python sin docstring (analytics + application + api).

## Separación de responsabilidades

| Capa | Dónde | Para quién |
|------|-------|------------|
| Producto / ADRs / auditoría | `docs/` · HELP · trackers | Humanos, auditores |
| Contrato HTTP | OpenAPI + `bolsa_api/schemas/*` | Clientes API |
| Comportamiento interno | Docstrings en módulos públicos | Devs / reviewers |

No duplicar ADRs dentro del código. El docstring apunta al *qué hace este símbolo*; el ADR al *por qué del sistema*.

## Obligatorio (forward-only)

Al tocar o crear código, añadir:

1. **Módulo** (`"""..."""` al inicio del archivo) si el archivo es API, use-case, dominio o indicador público.  
2. **Función/clase pública** (no `_privada`) con 1–4 líneas: propósito + invariantes no obvios.  
3. **Parámetros / returns** solo si no se entienden por el tipado.  
4. **TS/React:** JSDoc breve en exports de `@bolsa/shared` y en helpers de dominio (no en cada componente UI).

## No obligatorio

- Getters triviales, DTOs Pydantic cuyo nombre + `Field(alias=)` bastan (sí: docstring de **módulo** + clase si el rol no es obvio).  
- Tests (el nombre del test documenta).  
- Reescribir histórico solo para docstrings (misma regla que K: forward-only).

## Prioridad de cobertura (lotes)

| Lote | Ámbito | Criterio de hecho |
|------|--------|-------------------|
| **1** | Schemas/routes auditoría (CORE-R, Mandato, Research, Alerts, Health) + motores Lab (backtest, warm-up, cost v2) | Módulo + símbolos públicos clave · **Hecho 2026-08-03** |
| **2** | Resto `bolsa_api/schemas` + routes trading/listas/Lab | Módulo en cada archivo · **Hecho 2026-08-03** |
| **3** | `bolsa_application` use-cases | Módulo + clases públicas · **Hecho 2026-08-03** |
| **4** | `indicators/` · `signals/` · `optimize/` (+ warmup/backtest/cost v2 surface) | Módulo + símbolos públicos top-level · **Hecho 2026-08-03** |

## Medición

```bash
python scripts/research/docstring_coverage_report.py
```

Reporta defs públicas sin docstring bajo `packages/py/*/src` y `apps/api-python/src`.

## Ejemplo mínimo

```python
"""DTOs HTTP de alertas de precio (API v1)."""

class PriceAlertDto(BaseModel):
    """Alerta de precio persistida; aliases camelCase para el cliente web."""
```

---

*Política viva: actualizar la tabla de lotes al cerrar cada PR de cobertura.*
