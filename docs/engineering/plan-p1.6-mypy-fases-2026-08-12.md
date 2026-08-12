# Plan — P1.6 mypy por fases (CIERRE de la deuda de tipado preexistente) (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5.
> **Fuentes de verdad:** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (P1.6) · [traspaso-f4-arquitectura-python-2026-08-11.md](./traspaso-f4-arquitectura-python-2026-08-11.md) (§6 deuda → mypy resto del árbol por fases).
> **Base viva:** `stage/f1-integridad-financiera-2026-08-11` (`f7b2c07`; pendientes PR #42 docs-cierre y PR #43 fix auto-sync 404).
> **Regla del hilo:** NO tocar código fuera del alcance de esta fase (mypy de los 4 paquetes del gate CI).

---

## 1. Objetivo (decisiones tomadas)

Cerrar la deuda de tipado preexistentes para que el paso `Mypy` del CI **deje de ser `continue-on-error`** y se convierta en **gate bloqueante** sobre los 4 árboles que ya gestiona CI.

- Alcance: `packages/py/domain/src` · `packages/py/market/src` · `packages/py/infrastructure/src` · `apps/api-python/src` (el target exacto del paso `Mypy` de `.github/workflows/python-ci.yml`).
- Fuera de alcance (deuda de otra fase / no está en el target de CI): `packages/py/application`, `packages/py/analytics`, `packages/py/ai` (no están en el mypy de CI), y todo el frontend / contrato.
- Reglas: comportamiento idéntico (D5), cero features, NO cambiar el wire ni DTOs, ignorar `# type: ignore[code]` solo cuando no haya anotación limpia posible.

## 2. Medición de referencia (2026-08-12)

`uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src --follow-imports=silent` → **448 errores en 94 ficheros** (checked 243 source files).

| Lote | Paquete / app                | Errores | Ficheros | Rama                                        |
| ---- | ---------------------------- | ------- | -------- | ------------------------------------------- |
| L1   | `packages/py/domain`         | 6       | —        | `stage/p1.6-mypy-domain-2026-08-12`         |
| L2   | `packages/py/market`         | 32      | —        | `stage/p1.6-mypy-market-2026-08-12`         |
| L3   | `packages/py/infrastructure` | 119     | —        | `stage/p1.6-mypy-infrastructure-2026-08-12` |
| L4   | `apps/api-python`            | 291     | —        | `stage/p1.6-mypy-api-python-2026-08-12`     |

Principales hotspots: `database/models/tables.py` (66), `schemas/research.py` (25), `schemas/instruments.py` (25), `market/piotroski.py` (17), `schemas/backtests.py` (17), `market/yahoo_client.py` (12).

## 3. Ejecución y orden

1. 4 subagentes en paralelo (uno por rama/paquete, ficheros disjuntos → merge limpio en cualquier orden).
2. Cada subagente: `git checkout` de su rama → mypy de su paquete = 0 → ruff (CI config) limpio en lo tocado → pytest de su paquete sin regresiones → commit `fix(types, <pkg>)` → push → PR → `stage/f1-integridad-financiera-2026-08-11`.
3. Merge secuencial de los PRs en la base viva.
4. Paso final (un PR dedicado): quitar `continue-on-error` del paso `Mypy` del CI → gate bloqueante full-tree.

## 4. Batería por lote

- `uv run mypy <paquete>/src --follow-imports=silent` → exit 0.
- `uv run ruff check <paquete|app> --config pyproject.toml` → limpio.
- `uv run pytest` de los tests del paquete (criterio exclusión DB igual que CI) → sin regresiones.
- Tras el merge final: `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src --follow-imports=silent` → **0 errores (exit 0)**.

## 5. Cierre

- Actualizar `.github/workflows/python-ci.yml` (paso `Mypy` bloqueante; fusionar/señalar el gate scoped F4+F5b si procede).
- Crear `docs/engineering/traspaso-p1.6-mypy-fases-2026-08-12.md` (padre: engineering-index §5) + entrada en `engineering-index §5`.
- Registrar deuda nueva: `application`/`analytics`/`ai` no cubiertos (si se decide extender el gate a esos árboles en una fase posterior).

## 6. Riesgos / notas

- `tables.py` (SQLAlchemy, plugin mypy activo): anotar columnas JSON/JSONB con `Mapped[dict[str, Any]]` / `Mapped[list[Any]]` sin romper runtime.
- No cambiar el wire (OpenAPI es fuente de verdad): tipar de forma no intrusiva en los endpoints.
- La app `api-python` es el lote más denso; los esquemas Pydantic se anotan campo a campo.
