# Traspaso — F5a Contratos FE/BE: OpenAPI como fuente de verdad + drift gate (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5 (sub-entrada de la Auditoría consolidada, junto a F1/F2/F3b).
> **Fuentes de verdad (leer primero):** [audit-consolidado-internas-externas-2026-08-11.md](./audit-consolidado-internas-externas-2026-08-11.md) (hallazgo **P1.5** + D0/D5) · [ADR-003](../adr/003-python-backend-ai-platform.md) §2 (contrato objetivo `openapi.json → openapi-typescript + openapi-fetch → apps/web`) · [traspaso-f3b-alembic-data-epoch-2026-08-11.md](./traspaso-f3b-alembic-data-epoch-2026-08-11.md) (§9: siguiente fase).
> **Rama de ejecución:** `stage/f5a-contratos-fe-be-2026-08-11` (desgajada desde `stage/f1-*`, tras merge de PR #31).
> **Regla del hilo:** NO tocar código fuera del alcance F5a. Cambios validados con la batería antes del commit.
> **Estado:** F5a **COMMITEADO (6 commits C1–C6, HEAD `dde9c32`)**. Batería **py + web ✓ · gates contract ✓**. Working tree limpio. Pendiente de **merge** del PR (fast-forward) en `stage/f1-*`. Ver §7/§8.

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

| **G** | `.prettierignore` (nuevo) · `dump_openapi.py` (LF) · `sync-contract.mjs` (norm. CRLF) | **Corrección tras cierre (C5–C6):** el `openapi.json`/`schema.d.ts` commitado en C1/C2 tenía una serialización distinta a la del generador (array compacto/CRLF vs `json.dumps(indent=2)`+LF), por lo que el tree quedaba `M` y `contract:check` fallaba pese a estar commitado. `lint-staged` re-aplicaba `prettier --write` sobre `openapi.json` deshaciendo la forma canónica. Se añade `.prettierignore` (excluye los dos artefactos generados) y se fuerzan LF; ahora `contract:gen` regenera **byte-idéntico** (verif.) y el árbol queda limpio. |

## 5. Batería (aplicada)

- **ruff** `apps/api-python/scripts/dump_openapi.py`: **0 errores**.
- **mypy** `apps/api-python/scripts/dump_openapi.py`: **0 errores** (`ignore[import-untyped]` documentado; `bolsa_api` edictable sin `py.typed`).
- **pytest `apps/api-python/tests`**: **27✓ · 0 fallos** (no se tocó infraestructura/repos/BD; fase frontend-tooling + un script offline).
- **web**: `typecheck` **✓** (incluye el gate `contract-check.ts`) · `lint` **✓** · `test` **707✓** (140 ficheros).
- **contract:check** gate: **✓ verde** cuando coinciden, y **verificado que FALLA** al inyectar drift en `openapi.json` (mensaje "el contrato ha cambiado", exit≠0) → restaurado sin diff.
- **Regresión del gate (post-corrección C5–C6):** tras `contract:gen` en frío, `git status` queda **sin cambios** y `contract:check` **verde** → el contrato commitado es **reproducible byte-a-byte** por el generador.

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

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                                                                    |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Merge PR #31 (F3b) en `stage/f1-*` (GitHub merge commit `014a207`; local fast-forward a `014a207`). Rama `stage/f5a-contratos-fe-be-2026-08-11` creada desde `stage/f1-*`.                                                                                                                                                                                                |
| 2026-08-11 | A: `dump_openapi.py` offline. Volcado `openapi.json` (180 paths, 367 schemas) → `apps/web/api/openapi.json`.                                                                                                                                                                                                                                                              |
| 2026-08-11 | C: `schema.d.ts` generado con `openapi-typescript@7.13.0` (paths + components + operations). Commitado.                                                                                                                                                                                                                                                                   |
| 2026-08-11 | D–E: `sync-contract.mjs` + scripts `contract:gen`/`contract:check` en `apps/web`. Gate `contract:check` verificado (verde; falla ante drift → restaurado).                                                                                                                                                                                                                |
| 2026-08-11 | F: `contract-check.ts` gate de tipos (claves FE ⊆ contrato) para sentinelas `BacktestRunDto`/`PortfolioSummaryDto`/`InvestmentAccountDto`. Verificado `typecheck` verde.                                                                                                                                                                                                  |
| 2026-08-11 | Batería: ruff✓ · mypy✓ · pytest api 27✓ · web typecheck✓ lint✓ test 707✓ · contract:check✓.                                                                                                                                                                                                                                                                               |
| 2026-08-11 | **CORRECCIÓN tras cierre (C5–C6)**: contrato commitado no era reproducible por el generador (serialización prettier/CRLF vs `json.dumps(indent=2)`+LF) → tree `M` + `contract:check` rojo. Añadido `.prettierignore` (excluye `openapi.json`/`schema.d.ts`), LF en dump, norm. CRLF en `--check`. Ahora `contract:gen` en frío deja tree limpio y `contract:check` verde. |
| 2026-08-11 | **COMMITS + PR**: 6 commits atómicos C1–C6 en `stage/f5a-contratos-fe-be-2026-08-11` (C6 `dde9c32`) · C5 `d8fb5e2` (LF fixes) · C6 (`.prettierignore` + contrato canónico). **PR abierto** → base `stage/f1-*`. Working tree limpio.                                                                                                                                      |

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto (traspasos F1 §8 / F2 §8 / F3b §8). Al cerrar: preparar el siguiente con su `traspaso-*`, entrada única en `engineering-index`, y entregar en el chat el **texto exacto** para pegar en el próximo.

## 9. Texto exacto de traspaso — siguiente hilo (tras F5a)

```text
Texto de traspaso → nuevo chat (F5a completado — siguiente fase tras F5a)

CONTEXTO INMEDIATO: F5a (Contratos FE/BE — OpenAPI fuente de verdad + gates de drift,
hallazgo P1.5 / ADR-003) está COMPLETADO con 6 commits en rama
stage/f5a-contratos-fe-be-2026-08-11 y PR #32 ABIERTO:
  - 4 commits atómicos C1..C4 (C4 `164f692`): dump_openapi.py + openapi.json versionado
    (fuente de verdad, 180 paths / 367 schemas) + schema.d.ts generado
    (openapi-typescript@7.13.0) + sync-contract.mjs (contract:gen/contract:check) +
    contract-check.ts (gate de tipos: claves FE ⊆ contrato).
  - CORRECCIÓN tras cierre C5–C6 (C5 `d8fb5e2`, C6 HEAD `dde9c32`): el contrato commitado
    en C1/C2 NO era reproducible por el generador (serialización prettier/CRLF vs
    `json.dumps(indent=2)`+LF) → `lint-staged` re-aplicaba prettier sobre openapi.json.
    Añadido `.prettierignore` (excluye openapi.json y schema.d.ts: artefactos generados),
    LF en dump, normalización CRLF en --check. Ahora `contract:gen` en frío deja el árbol
    limpio y `contract:check` verde (reproducible byte-a-byte).
  - PR #32 (https://github.com/jvelasca/Bolsa_V1/pull/32) → base stage/f1-integridad-financiera-2026-08-11.
  - Gates: `pnpm --filter @bolsa/web contract:check` (regenera openapi.json desde FastAPI via uv
    y falla si hay diff) ✓ · `contract:gen` regenera en sitio ✓ · `contract-check.ts`
    (compilación tipo: rompe typecheck si un DTO-FE centinela declara un campo ausente del OpenAPI).
  - Drift medido P1.5: BacktestRunDto.manifest FE (`manifest?: RunManifest`) no cabe en
    `manifest: object|null` del contrato; normalizaciones number↔integer / ?↔null.
  - Batería: ruff✓ · mypy✓ (dump_openapi.py) · pytest api-python 27✓ ·
    web typecheck✓ (incl. contract-check) + lint✓ + test 707✓.

ESTADO GIT (VERIFICADO, OJO): origin/stage/f1-* = `014a207` (F3b mergeado, PR #31). PR #32
PENDIENTE DE MERGE. La rama LOCAL stage/f5a-* está adelantada respecto a origin/stage/f1-*;
merge fast-forward posible (base es ancestro). NO hacer reset --hard salvo aprobación explícita.
Checkpoint de retroceso global: tag audit-checkpoint-2026-08-11 (2683c49).

Lee PRIMERO: docs/engineering/traspaso-f5a-contratos-fe-be-2026-08-11.md (§4 A–F, §5 batería
+ drift medido, §6 deuda) y su fuente: audit-consolidado-internas-externas-2026-08-11.md (P1.5 + D0–D5).
Para la fase siguiente usa engineering-index-2026-08-03.md y el plan de la fase declarada.
NO toques código fuera del alcance de la fase que se declare.

SIGUIENTE FASE (orden pactado D0, NO renegociar): F5a → (F3a+F4+F5b). Tras F5a, la siguiente es
CONJUNTA: F3a (arquitectura de procesos y DB) + F4 (arquitectura Python) + F5b (auth), o bien
F3a en primer lugar. Las deudas registradas en F5a §6 para esas fases:
  - Deuda F5a: reconciliar DTOs manuales de packages/shared campo-a-campo contra el contrato
    (fidelidad de tipos: manifest, number↔integer, ?↔null) y adoptar openapi-fetch como cliente
    completo (reescribir/reducir api.ts). Mover el contrato de apps/web a un home compartido.
  - Deuda heredada F3b §6: portar TODO el DDL Prisma a Alembic (→F3a/F4) · account_repository.
    ensure_migrated por-request no retirado (→F3a) · workers en lifespan de FastAPI (→F3a).
  - Deuda consolidada auditoría: P0.6 ciclo analytics↔market y mypy gate (→F4) · auth HttpOnly
    cookie/TTL (→F5b) · P1.2/P1.4/P1.9 (→F3a).

Decisiones pactadas (NO renegociar): D0 orden F1→F2→F3b→F5a→(F3a+F4+F5b); D1 next_open inmutable
1D (MOC fuera); D2 Alembic única autoridad BD; D3 extraer workers de FastAPI (F3a); D4 auth local
diferida (F5b); D5 Solo F1–F5, CERO FEATURES. F5a fue un piloto scoped (no reescribió api.ts).

NOTA OPERATIVA: al tocar scripts que imprimen caracteres Unicode ('→') en Windows, ejecutar con
$env:PYTHONIOENCODING="utf-8"; (consola cp1252 lanza UnicodeEncodeError). Para regenerar el
contrato OpenAPI se necesita el venv Python de apps/api-python (uv): `pnpm --filter @bolsa/web contract:gen`.

BATERÍA OBLIGATORIA: ruff check + mypy (ficheros tocados) + pytest (analytics/application/api-python,
+ infraestructura si se tocan DB/repos) + pnpm test / CI si toca web. Al cerrar cualquiera: preparar el
siguiente traspaso-* + entrada única en engineering-index + texto exacto en el chat (norma permanente).

FLUJO DE COMMITS (patrón proyecto): trabajo en rama stage/fX-*-fecha; commits atómicos por cambio; push +
PR hacia la base activa (stage/f1-* actualmente); merge fast-forward tras aprobación del usuario.
```
