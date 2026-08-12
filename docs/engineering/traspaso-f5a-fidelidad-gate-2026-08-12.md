# Traspaso — F5a fidelidad: gate de contrato BIDIRECCIONAL + sentinelas (2026-08-12)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §5
> (fase F5a §6 fidelidad, deuda registrada en el cierre de
> [traspaso-f5a-contratos-fe-be-2026-08-11.md](./traspaso-f5a-contratos-fe-be-2026-08-11.md) §6 y
> [plan-p2.8-as-unknown-as-2026-08-12.md](./plan-p2.8-as-unknown-as-2026-08-12.md) §8).
> **Rama de ejecución:** `stage/f5a-fidelidad-gate-2026-08-12` (desde base `d892b3f` = tip F5b-drift en
> `stage/f1-integridad-financiera-2026-08-11`).
> **Regla del hilo:** NO tocar código fuera del alcance de la fase. Batería por paso.
> **Estado:** **COMPLETADO 2026-08-12** · `contract:check` verde · typecheck✓ · web typecheck✓ · lint 0
> errores · shared typecheck✓. Working tree limpio.

---

## 1. Deuda que resuelve esta fase (contexto)

En el cierre de [F5a §5](./traspaso-f5a-contratos-fe-be-2026-08-11.md#findings) y de P2.8 queda como deuda
medida: el gate `contract-check.ts` garantiza **solo FE ⊆ contrato** (el FE no declara un campo que el OpenAPI
no emite) para **5 sentinelas**, pero el **drift en el sentido contrario no se detecta**: si el backend añade un
campo a un DTO que el frontend desconoce, el `typecheck` no avisa. Es el drift silencioso más peligroso (campo
nuevo del backbone ignorado por el FE).

La **fidelidad de tipos del valor** (`manifest?: RunManifest` vs `object|null`, `number`↔`integer`, unions
`string`↔enum) **no** es drift TS detectable: `number`↔`integer` son iguales en TS (openapi-typescript emite
ambos como `number`), y degradar `RunManifest`/unions a `object`/`string` empeoraría el tipado del FE.
Permanecen como deuda de fuente de verdad (P2.6), no de esta fase.

## 2. Alcance de esta fase (decisión del usuario)

**D5 cero features, cambio mínimo de gate:**

- Reforzar `apps/web/src/api/contract-check.ts` a **igualdad de claves BIDIRECCIONAL** (FE ⊆ contrato **Y**
  contrato ⊆ FE) sobre un conjunto centinela.
- Ampliar el conjunto centinela de **5 a 11 DTOs** de endpoints de uso intensivo.
- **NO** reescribir `api.ts` ni los ~150 DTOs de wire. **NO** adoptar `openapi-fetch` (fase propia).
- **NO** degradar tipos de valor (`manifest`, unions). **NO** tocar el backend / OpenAPI (contrato ya verde).

## 3. Implementación

| #     | Fichero                                           | Qué                                                                                                                                                                                                                                                                                                     |
| ----- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | `apps/web/src/api/contract-check.ts` (modificado) | Añadir tipo `CoversContract<BE,FE> = MissingInFE<BE,FE> extends never ? true : false` con `MissingInFE<BE,FE> = Exclude<keyof BE, keyof FE>` (dirección contrato→FE). Cada sentinela combina ahora ambos sentidos: `HasNoMissingKeys<FE,BE>` (FE⊆contrato) **Y** `CoversContract<BE,FE>` (contrato⊆FE). |

**Sentinelas (5 → 11):**

| Guarda | DTO-FE `@bolsa/shared`   | Contrato `components["schemas"]`          |
| ------ | ------------------------ | ----------------------------------------- |
| G1     | `BacktestRunDto`         | `BacktestRunDto`                          |
| G2     | `PortfolioSummaryDto`    | `PortfolioSummaryDto`                     |
| G3     | `InvestmentAccountDto`   | `InvestmentAccountDto`                    |
| G4     | `CoreRBundleDto`         | `CoreRBundleDto` (blob, top-level)        |
| G5     | `SupervisedF3BundleDto`  | `SupervisedF3BundleDto` (blob, top-level) |
| G6     | `InstrumentDto`          | `InstrumentDto`                           |
| G7     | `OhlcvBarDto`            | `OhlcvBarDto`                             |
| G8     | `PortfolioDto`           | `PortfolioDto`                            |
| G9     | `PositionDto`            | `PositionDto`                             |
| G10    | `InvestmentPortfolioDto` | `InvestmentPortfolioDto`                  |
| G11    | `AccountSummaryDto`      | `AccountSummaryDto`                       |

**Corrección de gaps (paso C):** al activar `CoversContract`, la batería de typecheck confirmó que **todos los
sentinelas ya tienen igualdad de claves bidireccional** con el contrato → **cero cambios de DTOs**. El gate
queda como **blindaje preventivo**.

## 4. Verificación del gate (probe de drift)

- **FE ⊆ contrato** (comportamiento existente): rompe `TS2322` si el FE declara un campo ausente del OpenAPI.
- **contrato ⊆ FE (NUEVO):** se inyectó temporalmente `driftProbe: number` en `PositionDto` del `schema.d.ts`
  (artefacto generado) → `contract-check.ts(148,7)` falló `TS2322: Type 'true' is not assignable to type
'false'` (G9) → **detectado**. Se restauró sin diff.

## 5. Batería (aplicada)

- `contract:check` (frío, `PYTHONIOENCODING=utf-8`) → **VERDE** ✓ (contrato reproducible, sin diff).
- `pnpm --filter @bolsa/web typecheck` → **✓** (0). Incluye el gate vuelto bidireccional.
- `pnpm --filter @bolsa/web lint` → **0 errores** (2 warnings pre-existentes en `backtests-page.tsx`, no tocados).
- `pnpm --filter @bolsa/shared typecheck` → **✓** (0).
- `pnpm --filter @bolsa/web test` → **714 passed (141 f)** — sin regresiones (ver §4 batería final abajo si procede).
- `git status` → solo `contract-check.ts` modificado (artefactos generados intactos).

## 6. Registro

| Fecha      | Acción                                                                                                                                                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-12 | Diagnóstico: gate `contract-check.ts` unidireccional (solo FE⊆contrato) y con 5 sentinelas; el drift contrato→FE (campo nuevo del BE) no se detecta. `api.ts` usa 162 tipos `@bolsa/shared`; 87 con nombre exacto de esquema. |
| 2026-08-12 | Decisión usuario: nivel **"reforzar el gate"** (fidelidad bidireccional sobre sentinelas); `openapi-fetch` y reconciliación masiva de DTOs → deuda fase propia.                                                               |
| 2026-08-12 | `contract-check.ts`: `CoversContract` + 11 sentinelas (G1–G11), cada uno validado en ambos sentidos. Batería: typecheck✓ · contract:check✓ · lint 0 errores.                                                                  |
| 2026-08-12 | Probe de drift contrato→FE verificado positivo (G9 rompe con `driftProbe`) y restaurado. Cero gaps de claves en los sentinelas (los DTO-FE ya cubren todo lo que el BE emite).                                                |
| 2026-08-12 | Docs: este traspaso + entrada en `engineering-index` §5 (hijo de F5a).                                                                                                                                                        |

## 7. Deuda / fuera de alcance (sin resolver aquí)

- **`openapi-fetch` como cliente completo** (reescribir/reducir `api.ts`, 100 métodos / 2.073 líneas,
  depende aún NO instalado): fase propia grande. El contrato (`operations`/`paths`) ya está disponible y
  `openapi-typescript@^7.13.0` instalado.
- **Reconciliar campo-a-campo los ~87+ DTOs restantes** de wire vs contrato (no sentinela) → requiere acuerdo
  de fuente de verdad (P2.6).
- **Consolidar tipos web-only re-declarados** (`RecommendationV1`, `CoreRVerdict`, `RunManifest`) en
  `packages/shared` → P2.6.
- **Casts residuales** `toF3ItemDto`/`toCoachFactsRecord` son la frontera legítima del blob opaco → no
  eliminables sin cambiar el wire (A2, deuda).
- **Fidelidad de tipos del valor** (`manifest`, `number`↔`integer`, unions) → fuera alcance de claves; no
  es drift TS detectable y degradaría el FE. Depende de P2.6.
- Deuda previa: P1.9 API thin (hilo propio), P1.3 auth full (D4), mypy por fases.

## 8. Cierre — resultado alcanzado y texto de traspaso

F5a §6 fidelidad (gate bidireccional) **COMPLETADO** con cambio mínimo:

- El gate `contract-check.ts` ahora garantiza **igualdad de claves bidireccional** (FE ⊆ contrato Y
  contrato ⊆ FE) sobre **11 sentinelas** (G1–G11) de endpoints de uso intensivo. Si el backend añade un campo
  nuevo a cualquiera de esos DTOs, el `typecheck` rompe en la guarda (antes no se detectaba).
- **Cero cambios de DTOs** (los sentinelas ya estaban alineados en claves). **Cero impactos de wire.**
- `contract:check` verde, verificado reproducible. Artefactos generados sin diff.
- Batería verde: typecheck✓ (web + shared) · lint 0 errores · contract:check✓ · test web 714✓ (141 f).

### Texto de traspaso (pegable en el próximo chat)

> CONTEXTO INMEDIATO: F5a §6 fidelidad (gate de contrato BIDIRECCIONAL) **COMPLETADO** en rama
> `stage/f5a-fidelidad-gate-2026-08-12` (desde base `d892b3f` = tip F5b-drift en
> `stage/f1-integridad-financiera-2026-08-11`).
>
> - **`contract-check.ts` reforzado a bidireccional**: nuevo tipo `CoversContract<BE,FE>`
>   (`Exclude<keyof BE, keyof FE>`) + sentinelas ampliados de **5 a 11**: G1 `BacktestRunDto`, G2
>   `PortfolioSummaryDto`, G3 `InvestmentAccountDto`, G4 `CoreRBundleDto`, G5 `SupervisedF3BundleDto`,
>   G6 `InstrumentDto`, G7 `OhlcvBarDto`, G8 `PortfolioDto`, G9 `PositionDto`, G10 `InvestmentPortfolioDto`,
>   G11 `AccountSummaryDto`. Cada uno valida FE⊆contrato Y contrato⊆FE → si el BE emite un campo nuevo, el
>   typecheck rompe (antes no se detectaba).
> - **Cero cambios de DTOs de shared**: todos los sentinelas ya tenían igualdad de claves con el contrato.
>   Solo `apps/web/src/api/contract-check.ts` modificado. Artefactos generated (`openapi.json`/`schema.d.ts`)
>   intactos.
> - **Probe verificado**: inyectando `driftProbe` en `PositionDto` del contrato rompió G9 (`TS2322`), se
>   restauró sin diff.
> - BATERÍA: contract:check VERDE ✓ (reproducible) · web typecheck✓ · lint **0 errores** (2 warnings
>   pre-existentes `backtests-page.tsx`) · shared typecheck✓ · test web **714✓ (141 f)**.
> - Worktree limpio. Base viva `stage/f1-*` en `d892b3f`.
>
> DEUDA REGISTRADA → fases posteriores (sin resolver):
>
> - **`openapi-fetch` completo** (100 métodos de `api.ts`, aún NO instalado, `openapi-typescript@^7.13.0` ya
>   presente): fase propia grande; el contrato `operations`/`paths` de `schema.d.ts` ya lo soporta.
> - **Reconciliar ~87+ DTOs de wire restantes** vs contrato → acuerdo de fuente de verdad (P2.6).
> - **Consolidar tipos web-only** (`RecommendationV1`/`CoreRVerdict`/`RunManifest`) → P2.6.
> - **Fidelidad de tipos del valor** (`manifest`, `number`↔`integer`, unions) fuera de claves: no es drift TS
>   detectable y degradaría el FE; depende de P2.6.
> - Casts residuales `toF3ItemDto`/`toCoachFactsRecord` (frontera legítima de blob, no se eliminan sin A2) ·
>   deuda previa: P1.9 API thin · P1.3 auth full (D4) · mypy por fases.
>
> Lee PRIMERO: `docs/engineering/traspaso-f5a-fidelidad-gate-2026-08-12.md` y sus fuentes
> (`traspaso-f5a-contratos-fe-be-2026-08-11.md` §5-§6, `plan-p2.8-as-unknown-as-2026-08-12.md` §8).
> NO toques código fuera del alcance de la fase que se declare.
