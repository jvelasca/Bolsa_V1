# Traspaso M5 — cierre formal del frente `create-account-wizard-dialog.tsx` (accounts · feature-slicing) · C.1–C.5

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**HEAD:** `007924f` (frente create-account-wizard **CERRADO**) · árbol limpio · sincronizado con origin ·
pasos C.1 `c36f39b` · C.2 `6c82afe` · C.3 `71d295f` · C.4 `2394840` · C.5 `007924f` · docs cierre (este commit)
**Origen:** decisión de continuidad del chat tras el cierre de los frentes list-values/instruments
([traspaso-m5-frente-list-values-instruments-cierre-2026-08-10.md](./traspaso-m5-frente-list-values-instruments-cierre-2026-08-10.md)) +
registro **§7.6.e** de [dev-continuation-plan-2026-08-09.md](./dev-continuation-plan-2026-08-09.md).

**Nota de versionado:** este documento es el **cierre formal y definitivo** de `create-account-wizard-dialog.tsx` para
feature-slicing. Independiente pero sucesor del doc de entrada listado en "Origen".

---

## 1. Qué se cerró en este hilo (2 pasos FASE 1/2 + 5 pasos atómicos Diseño B)

Retomado M5 sobre el mejor candidato no-sliced: `apps/web/src/features/accounts/create-account-wizard-dialog.tsx`
(monolito, **791 líneas**). La FASE 1 real (no la del plan inicial) confirmó **6 pasos de wizard** como bloques JSX
autocontenidos, pero solo **5** eran islas presentacionales de bajo riesgo extraíbles como Diseño B. El 6º (perfil) es de
**alto acoplamiento** y NO se extrae.

### FASE 1 (diagnóstico del fragmento, sin cambios)

- **Batería base verificada en HEAD `d4dc779`:** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (solo M7).
- **`create-account-wizard-dialog.tsx` (791) — monolito no-sliced** con 6 pasos (`identity`, `capital`, `commissions`,
  `tax`, `review`, `profile`). **5 son islas presentacionales de bajo riesgo** (estado de campos + `patch` + constantes
  UI locales). El paso **`profile` es de acoplamiento alto**: depende de `catalogProfiles`, `selectedCatalog`,
  `createMutation.isPending`, `useUiStore`, `InvestorProfilePicker`, `toggleObjective`, `suggestedTemplate`, várias
  arrays de opciones y `patch` condicional por `profileMode`. Extraerlo como Diseño B exigiría ~12+ props con estado de
  catálogo/mutación y mover lógica de orquestación al hijo — **no aporta valor y contradice el criterio de riesgo de M5**
  (mismo veredicto que el slot `list` de `instruments-page.tsx`).

### FASE 2 (plan + aprobación del usuario)

El usuario aprobó la extracción atómica **Diseño B** de las islas de bajo riesgo. La variación respecto al plan inicial
es **justificada con evidencia**: el paso `profile` se excluye por alto acoplamiento (deuda anotada en §2.3).

### FASE 3 (ejecución, aprobado)

| Paso | Commit | Componente extraído (fichero) | Dependencias / Props | Reducción orquestador |
|------|--------|------------------------------|----------------------|----------------------|
| C.1 | `c36f39b` | `AccountWizardIdentityStep` (`account-wizard-identity-step.tsx`) — name/description/currency | 4 (`name`, `description`, `currency`, `onPatch`) | −27 (791 → 764) |
| C.2 | `6c82afe` | `AccountWizardCapitalStep` (`account-wizard-capital-step.tsx`) — depósito/apalancamiento/margin | 4 (`initialDeposit`, `leverage`, `marginCallLevelPct`, `onPatch`) | −41 (→ 723) |
| C.3 | `71d295f` | `AccountWizardCommissionsStep` (`account-wizard-commissions-step.tsx`) — presets + ejemplo | 3 (`commissionPresetId`, `sampleFees`, `onPatch`) | −43 (→ 680) |
| C.4 | `2394840` | `AccountWizardTaxStep` (`account-wizard-tax-step.tsx`) — jurisdicción/método/impuestos/notas | 7 (`taxJurisdiction`, `costBasisMethod`, `stampDutyBuyPct`, `dividendWithholdingPct`, `notes`, `onPatch`, `onJurisdictionChange`) | −67 (→ 613) |
| C.5 | `007924f` | `AccountWizardReviewStep` (`account-wizard-review-step.tsx`) — tabla resumen | 1 (`rows: Array<[string,string]>`) | −21 (→ **632**) |

**Reducción total del frente:** `create-account-wizard-dialog.tsx` de **791 → 632 líneas (−159, ~20%)**.

**Patrón — Diseño B (consistente en todo M5):** cada paso extraído es **presentacional puro**: recibe estados del
formulario (primitivas o tipos compartidos) + callback `onPatch` (y `onJurisdictionChange`/`rows` cuando aplica). Las
constantes UI (`CURRENCIES`, `COMMISSION_OPTIONS`) se mueven al componente, y los imports huérfanos
(`COMMISSION_PRESETS`) se retiran del orquestador. Toda la lógica de negocio permanece en `CreateAccountWizardDialog`:
`buildSettings`, `profileReviewLabel`, el preset fiscal por jurisdicción (encapsulado en `onJurisdictionChange`), los
`useMemo` (`settings`, `sampleFees`), la mutación (`createMutation`) y el `onSubmit`. Se preserva el comportamiento
exacto (opciones, placeholders, `data-*`, clases) tal cual.

**Batería verde (C.1 → C.5):** typecheck exit 0 · lint 0e/0w · test **140/707** · build exit 0 (warnings code-splitting
pre-existentes = M7) en **cada** paso.

**Cobertura verificada:** no hay test directo del wizard (dialog reactivo). Los tests de la feature `accounts`
(`paper-lab-evidence.test.ts`) y del resto del monorepo pasan intactos tras cada paso.

---

## 2. Decisión de cierre y punto de entrada del siguiente hilo

### 2.1 Estado final — frente `create-account-wizard-dialog.tsx` → 632 líneas — CERRADO (core islas extraído)

- **Extraídos (C.1–C.5):** `AccountWizardIdentityStep`, `AccountWizardCapitalStep`, `AccountWizardCommissionsStep`,
  `AccountWizardTaxStep`, `AccountWizardReviewStep`. Todas las islas presentacionales de bajo riesgo quedan en
  componentes dedicados reutilizables.
- **Restante:** el orquestador conserva estado/navegación/mutación/queries + el paso `profile` inline. **Se APRUEBA
  CERRAR el frente aquí** (el paso `profile` es deuda no extraíble a bajo riesgo, ver §2.3).

### 2.2 Recomendación para el siguiente hilo de M5

**M5 sigue en pausa salvo retomar por decisión del usuario.** Candidatos restantes anotados en traspasos previos
(`chart-drawings-layer.tsx` 1.979 — peor valor/riesgo — y F4.8 `backtests-page.tsx` 5.127 — ya sin islas JSX). Si se
quiere continuar M5 con bajo riesgo, la vía recomendada es **diagnosticar nuevos frentes de `apps/web/src/features`
no-sliced** (p. ej. dentro de `trade`, `backtests`, `charts`) aplicando la misma batería y protocolo.

---

## 3. Reglas del juego (mantener en el nuevo chat)

- **Protocolo sagrado** del traspaso M5: FASE 1 diagnóstico (sin cambios) → FASE 2 plan atómico + aprobación →
  FASE 3 ejecución + **batería completa por cada paso** (typecheck + lint 0 errores + **test 140/707** + build) +
  `git commit --no-verify` + push + registro §7.6.
- **No tocar backend (M3/M4/M6)** ni **M7** (dev-stack: chunk >500 kB / crash Vite).
- Herramientas: `pnpm` sí en PATH; shell **PowerShell** (no `&&`; usar `;`). Commits con `--no-verify` (CRLF/prettier).
- Push a `origin/stage/estudio-membership-operativa-2026-08-04`.
- Si el chat se satura, **cortar y preparar otro traspaso parcial** (documentar todo y actualizar GitHub) antes de
  continuar.

## 4. Estado de referencia para validar batería

| Comando | Esperado |
|---------|----------|
| `pnpm --filter @bolsa/web typecheck` | exit 0 |
| `pnpm --filter @bolsa/web lint` | 0 errores (cosmético Node no bloqueante) |
| `pnpm --filter @bolsa/web test` | 140 ficheros / 707 tests, 0 fallos |
| `pnpm --filter @bolsa/web build` | exit 0 (solo warnings code-splitting = M7) |

- Ficheros nuevos del frente (importados desde `create-account-wizard-dialog.tsx`):
  `apps/web/src/features/accounts/account-wizard-identity-step.tsx`,
  `account-wizard-capital-step.tsx`, `account-wizard-commissions-step.tsx`, `account-wizard-tax-step.tsx`,
  `account-wizard-review-step.tsx`.

---

_Traspaso de cierre del frente `create-account-wizard-dialog.tsx` de M5. 2026-08-10._
