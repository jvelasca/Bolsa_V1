# Traspaso — F5a Contratos FE/BE: OpenAPI como fuente de verdad + drift gate (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (hallazgo **P1.5** + D0/D5) · [ADR-003](../adr/003-python-backend-ai-platform.md) §2 (contrato objetivo `openapi.json → openapi-typescript + openapi-fetch → apps/web`) · [traspaso-f3b-alembic-data-epoch-2026-08-11.md](./traspaso-f3b-alembic-data-epoch-2026-08-11.md) (§9: siguiente fase).
> **Rama de ejecución:** `stage/f5a-contratos-fe-be-2026-08-11` (desgajada desde `stage/f1-*`, tras merge de PR #31).
> **Regla del hilo:** NO tocar código fuera del alcance F5a. Cambios validados con la batería antes del commit.
> **Estado:** F5a **en ejecución** — piloto scoped: contrato OpenAPI versionado + tipos TS generados + gate de tipos + gate de spec. Ver §7.

---

## 1. Objetivo de F5a

Resolver el **hallazgo P1.5 (drift silencioso FE/BE)**: los DTOs TypeScript se escriben a mano en `packages/shared` y en `apps/web/src/lib/api.ts` (~2.073 líneas de cliente manual con `request<T>` + `import("@bolsa/shared").XxxDto`), sin cliente generado desde el OpenAPI de FastAPI. El resultado es que el contrato FE puede divergir del BE sin que el `typecheck` lo detecte (drift silencioso). ADR-003 §2 fija como contrato objetivo: `FastAPI → openapi.json → openapi-typescript + openapi-fetch → apps/web`, con "No duplicar modelos a mano; CI debe fallar si OpenAPI y cliente TS divergen".

**Alcance pactado (incremental, decisión del usuario — D5 cero features):** piloto scoped:

1. Volcar el OpenAPI de FastAPI a un fichero **versionable** (`apps/web/api/openapi.json`) que sea la **fuente de verdad** (diffable, revisable en PR).
2. Generar el **contrato TS** (`apps/web/src/api/schema.d.ts`) con `openapi-typescript` (componentes + paths).
3. **Cablear regeneración**: `contract:gen` (dump + gen) y `contract:check` (gate de spec: regenera y falla si hay diff).
4. **Gate de tipos** (`apps/web/src/api/contract-check.ts`): para DTOs centinela de endpoints de uso intensivo, garantiza en compilación que el FE **nunca declara un campo que el OpenAPI no emite**.

**NO forma parte de esta fase:** reescribir `api.ts` entero con `openapi-fetch` (cliente completo); sustituir todos los DTOs manuales; alinear campo-a-campo la fidelidad de tipos (fase posterior). Queda como deuda (§6).

## 2. Diagnóstico confirmado en código (P1.5)

- `apps/web/src/lib/api.ts`: **2.073 líneas** de cliente manual; cada método usa `request<{...}>` y referencia DTOs manuales (`import("@bolsa/shared").XxxDto`) escritos a mano en `packages/shared/src/*`.
- `packages/shared` (~110 fuentes) mezcla DTOs de API con lógica pura FE (charts/cognitive/indicators...). Sin verificación frente al OpenAPI.
- FastAPI expone el OpenAPI en `/api/openapi.json` (`openapi_url` en `apps/api-python/src/bolsa_api/main.py:180`), `response_model` Pydantic por ruta → 367 schemas / 180 paths.
- No existía ningún artefacto de contrato generado ni gate; cualquier cambio en Pydantic sin reflejo en TS pasaba `typecheck` sin aviso.

## 3. Decisiones pactadas (no renegociar)

- **D0** orden F1 → F2 → F3b → F5a → (F3a+F4+F5b); F5a es la fase ejecutada.
- **D5** solo F1–F5, cero features (piloto scoped, sin reescribir el cliente).
- **F5a alcance incremental (usuario):** contrato versionado + tipos generados + gates (spec + tipos) + muestra centinela; NO reescribir `api.ts` entero ni sustituir todos los DTOs (deuda).

## 4. Implementación

| #     | Fichero(s)                                   | Qué                                                                                                                                                                                                                                                                                                  |
| ----- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | `apps/api-python/scripts/dump_openapi.py`    | Vuelca `app.openapi()` (FastAPI, `create_app()`) a `apps/web/api/openapi.json` — **offline, sin servir ni tocar BD** (el `lifespan`/`ensure_migrated` NO se ejecuta al llamar `openapi()`). UTF-8, `sort_keys`, indent 2. `# type: ignore[import-untyped]` por `bolsa_api` edictable sin `py.typed`. |
| **B** | `apps/web/api/openapi.json` (nuevo)          | **Fuente de verdad versionada**: 180 paths · 367 schemas. Diffable en PR.                                                                                                                                                                                                                            |
| **C** | `apps/web/src/api/schema.d.ts` (nuevo)       | Contrato TS generado con `openapi-typescript@7.13.0` (7.13.0): `paths`, `components["schemas"]`, `operations`, `responses`. Commitado para diff determinista.                                                                                                                                        |
| **D** | `apps/web/scripts/sync-contract.mjs` (nuevo) | Orquestación: `contract:gen` (dump via `uv` + gen `openapi-typescript`) y `contract:check` (regenera y compara → falla si hay diff; gate CI). Sin uv: `--check` termina en verde con aviso.                                                                                                          |
| **E** | `apps/web/package.json`                      | scripts `contract:gen` y `contract:check`; devDependency `openapi-typescript@^7.13.0`.                                                                                                                                                                                                               |
| **F** | `apps/web/src/api/contract-check.ts` (nuevo) | **Gate de tipos**: `HasNoMissingKeys<FE, Contract[BE]>` — para DTOs centinela (`BacktestRunDto`, `PortfolioSummaryDto`, `InvestmentAccountDto`) garantiza que ninguna clave del DTO-FE falte en el contrato. `const _guard: G = true` materializa TS2322 si hay drift.                               |

## 5. Batería (aplicada)

- **ruff** `apps/api-python/scripts/dump_openapi.py`: **0 errores**.
- **mypy** `apps/api-python/scripts/dump_openapi.py`: **0 errores** (`ignore[import-untyped]` documentado en la línea del import; `bolsa_api` edictable sin `py.typed`).
- **pytest**: aplic por `<root> apps/api-python/tests --ignore=integration` **11✓** · analytics **323✓** · application **222✓** → **556✓ · 0 fallos** (no se tocó infraestructura/repos/BD ni analytics/app; fase frontend-tooling + un script offline).
- **web**: `typecheck` **✓** (incluye el gate `contract-check.ts`) · `lint` **✓** · `test` **707✓** (140 ficheros).
- **contract:check** gate: **✓ verde** cuando coinciden, y **verificado que FALLA** al inyectar drift en `openapi.json` (mensaje "el contrato ha cambiado", exit≠0) → restaurado sin diff.

### Hallazgos medidos (P1.5 con evidencia)

- Fidelidad de tipos: `BacktestRunDto.manifest` — FE declara `manifest?: RunManifest` (de `research-platform.ts`), el contrato emite `manifest: object|null`. `RunManifest` no es asignable a `object` → **drift real** del FE (declara más de lo que el BE garantiza).
- Normalizaciones que rompen la igualdad estricta pero son benignas en valor: `number`↔`integer`, opcionalidad `?`/`undefined`↔`| null`, campos `XxxDto` con prefijo de módulo FastAPI (p. ej. `bolsa_api__schemas__lists__InstrumentListResponseDto`).
- Gate de claves (FE no declara campo ausente del contrato) **verde** para los sentineles muestreados.

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **Sustituir/reconciliar TODOS los DTOs manuales de `packages/shared`** contra el contrato (fidelidad campo-a-campo + igualdad estricta bidireccional): fase posterior (F3a/F5a-follow). El gate de claves es una primera capa; la **fidelidad de tipos** (p. ej. `manifest`, `number`↔`integer`) queda medida y documentada.
- **Adoptar `openapi-fetch` como cliente** completo (reescribir/reducir `api.ts`): NO en esta fase.
- **`packages/shared` como propietario del contrato** en vez de `apps/web`: el piloto lo sitúa en `apps/web` (consumidor mejor acoplado y typecheck inmediato). Mover a `.consumo-compartido/` compartido queda como mejora.
- **Algunos nombres de component** quedan con prefijo FastAPI (`bolsa_api__schemas__*`) si el `response_model` usa alias de namespace; revisar en la fase de fidelidad.
- Sin `openapi-fetch` todavía, el `api.ts` sigue siendo la capa de transporte (el contrato valida _tipos_; el enrutado real queda como está).

## 7. Registro

| Fecha      | Acción                                                                                                                                                                     |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Merge PR #31 (F3b) en `stage/f1-*` (GitHub merge commit `014a207`; local fast-forward a `014a207`). Rama `stage/f5a-contratos-fe-be-2026-08-11` creada desde `stage/f1-*`. |
| 2026-08-11 | A: `dump_openapi.py` offline. Volcado `openapi.json` (180 paths, 367 schemas) → `apps/web/api/openapi.json`.                                                               |
| 2026-08-11 | C: `schema.d.ts` generado con `openapi-typescript@7.13.0` (paths + components + operations). Commitado.                                                                    |
| 2026-08-11 | D–E: `sync-contract.mjs` + scripts `contract:gen`/`contract:check` en `apps/web`. Gate `contract:check` verificado (verde; falla ante drift → restaurado).                 |
| 2026-08-11 | F: `contract-check.ts` gate de tipos (claves FE ⊆ contrato) para sentinelas `BacktestRunDto`/`PortfolioSummaryDto`/`InvestmentAccountDto`. Verificado `typecheck` verde.   |
| 2026-08-11 | Batería: ruff✓ · mypy✓ · pytest api 11✓ + analytics 323✓ + app 222✓ = 556✓ · web typecheck✓ lint✓ test 707✓ · contract:check✓.                                             |
| 2026-08-11 | **(en curso)** commits atómicos C1–C4 + push + PR hacia `stage/f1-*`.                                                                                                      |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto (traspasos F1 §8 / F2 §8 / F3b §8). Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo (tras F5a)

> (Se rellena al CERRAR F5a — es el texto que va en el chat.)
