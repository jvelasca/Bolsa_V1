# Entrega a auditoría externa (MIA) — `v2.88.94-beta` · `UI`: **UI 7.0 — cierre semántico y de usuario básico (UI-only · Δ motor = 0)**

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.94-beta` · **Package:** `2.11.94-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.93-beta` (tag anotado objeto `544158c8` → commit `68e78ead`; `Release tag CI` [`37815922396`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37815922396) **VERDE**).
> **Unidad de esta auditoría:** que un usuario que no conoce el backend entienda, en cada pantalla, qué está pasando, **qué dinero usa AUTO**, si está haciendo algo, si **necesita** hacer algo y qué significa cada resultado. Se cierra la semántica de producto pendiente **sin falsificar datos** y se hace falsable cada afirmación con tests de copy.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `Precio aplicado ≠ posición materializada` se conservan.
> **`Δ AUTO decision/execution motor = 0`.** Todo el sello es UI/copy y tests en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.94/README.md`](./evidence/v2.88.94/README.md).
> **Cita POST-TAG:** tag anotado `v2.88.94-beta` (objeto `0671ae15` → commit `20fd538c`); `Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `279` ficheros / `1740` passed; `python` `4596 passed / 45 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo en el primer nivel**. No se añaden funciones ni se toca el motor: se elimina la **afirmación falsa** («qué ha elegido AUTO»), se **declara** la deuda durable (`PortfolioDecision`) en vez de inventarla, se separa la **operativa autónoma** de la **firma humana**, se reconcilia la pregunta de **Riesgo** con su read-model, y se reduce la densidad de **Laboratorio/Asesor/Hoy**. AUTO gana una affordance de **primer nivel** (`UI5-21`) **sin** convertirse en sexta puerta L1.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre semántico de usuario básico:

1. **AUTO · Operar (`UI5-12`).** `operar.description` ya **no** afirma una decisión inexistente: «qué oportunidades ha encontrado AUTO y qué operaciones están en curso». Test falsable [`auto-copy.test.ts`](../../apps/web/src/features/auto/auto-copy.test.ts).
2. **AUTO · Decisión (`UI5-12`).** El bloque «Decisión de cartera» de la HOME explica la cadena `oportunidad → ranking → (decisión pendiente) → orden` y **declara el hueco**; no deduce compra del TOP3.
3. **AUTO · Cartera (`UI5-13`/`UI5-17`).** Se separa explícitamente «AUTO continúa su operativa simulada sin tu firma» de «las acciones que **tú** hagas sobre una posición requieren tu confirmación». Un solo término: **dinero virtual** (sin alternar DEMO/PAPER).
4. **AUTO · Riesgo (`UI5-16`/`UI5-18`).** La pregunta pasa a «¿Hay algún problema de riesgo ahora mismo?»; deja de prometer «cuánto puedes perder» mientras el read-model fije `positionRiskAvailable: false`. El veredicto (`Controlado`/`Atención`/`Bloqueado`/`Sin dato todavía`) se conserva.
5. **AUTO · Descubribilidad (`UI5-21`, nuevo).** Chip-enlace de **modo operativo persistente** (`Operativa · AUTO/SEMI/MANUAL`) en el chrome, **fuera** de `nav[aria-label="Principal"]`; informa del modo y enlaza a `/auto` sin cambiar el modo. Contrato enmendado (ADR-040 §13, ADR-044 §2, ADR-045 §1.1, spec Bloque A).
6. **Laboratorio (`UI5-01`/`R-G2`/`RT-01`).** Primer nivel = `h1` + «¿Qué estamos aprendiendo?» + tres caminos (Probar · Aprender · Estrategias); chrome avanzado (universo, DÍA-D, tabs incl. Jobs, ajustes) tras «Más opciones». Rutas y tabs intactas.
7. **Asesor (`UI5-01`/`R-G2`).** Primer nivel responde «¿Por qué?» con accesos a Análisis/Journal/Diario y enlace a Laboratorio; métricas de experimentación tras `Detalle técnico`.
8. **Hoy (`UI5-01`).** El pie refleja el orden real (atención → oportunidades → posiciones) y se añade test de orden de cubos.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y `skipped`. La certificación `axe` de la serie es **con mocks**.
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, read-model de riesgo (máxima pérdida / riesgo por posición / límite diario), traza de materialización SIM, PIT histórico institucional y Execution Analysis.

---

## 2. Cambios verificables (todo con gate)

| # | Tensión de origen | Regla | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| 1 | AUTO afirmaba una decisión inexistente | `UI5-12` | `auto-copy.ts`, `auto-copy.test.ts` | Copy honesto + test falsable (`no contiene "ha elegido"`). |
| 2 | Decisión sin explicar la cadena | `UI5-12` | `auto-home-page.tsx` | «Decisión de cartera» declara el hueco; no deduce del TOP3. |
| 3 | AUTO autónomo ≠ firma humana | `UI5-13` | `auto-copy.ts`, `auto-cartera-page.tsx` | Separa autonomía de firma; unifica «dinero virtual». |
| 4 | Riesgo prometía cifra no medida | `UI5-16`,`UI5-18` | `auto-copy.ts`, `auto-riesgo-page.tsx` | Pregunta por problemas actuales; veredicto conservado. |
| 5 | AUTO poco descubrible | `UI5-21` | `operative-mode-chip.tsx`, `app-top-bar.tsx`, spec/ADR-040/044/045 | Chip-enlace de modo operativo fuera de la nav Principal. |
| 6 | Laboratorio denso | `RT-01`,`R-G2` | `backtests-page.tsx` | Tres caminos; avanzado tras «Más opciones». |
| 7 | Asesor reexponía experimentación | `R-G2` | `research-page.tsx` | Primer nivel «¿Por qué?»; métricas tras `Detalle técnico`. |
| 8 | Copy de Hoy no reflejaba el orden | `UI5-01` | `mesa-hoy-page.tsx`, `daily-desk-inbox.test.tsx` | Pie alineado + test de orden. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.94-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en el commit post-tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); **279 ficheros / 1740 tests verdes** (+13 tests respecto a `2.11.93-beta`).
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.94-beta`).
- **`Δ motor = 0` local:** `git diff --name-only -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`UI52-02` — `PortfolioDecision` durable:** el bloque «Decisión de cartera» declara «Sin dato todavía» porque el read-model todavía no traza la decisión. **Remediación (fuera de este ciclo):** exponer la traza durable en el read-model; entonces el bloque la mostrará sin cambiar la UI.
- **Read-model de riesgo:** máxima pérdida / riesgo por posición / límite diario no medidos; `positionRiskAvailable: false`. La copy ya no los promete.
- **`F-A2` — barrido `axe` en vivo.** Este sello certifica **con mocks**; la variante en vivo (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **Traza de materialización SIM**, **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **279 ficheros / 1740 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.94-beta`) |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** (`Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE**) |

---

## 6. Sello

- **Producto:** `V2.88.94-beta`. **Package:** `2.11.94-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `apps/web/src/components/layout/operative-mode-chip.tsx` (+ test), `apps/web/src/features/auto/auto-copy.test.ts`, `docs/engineering/evidence/v2.88.94/README.md`, este documento.
- **Modificados:** `apps/web/src/**` (auto, backtests, research, mesa, layout, components), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/domain-language.md`, `docs/engineering/spec-ui-contract-5-0-2026-10-08.md`, `docs/adr/040-user-information-architecture.md`, `docs/adr/044-auto-workspace-information-architecture.md`, `docs/adr/045-ui-contract-5-0.md`.
- **Tag anotado `v2.88.94-beta`** — objeto `0671ae15` → commit `20fd538c`; mensaje `UI 7.0 semantic and basic-user closure (AUTO copy honesty, operative mode chip, lab/asesor/hoy density) - Delta motor = 0`. **`Release tag CI`** [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.94/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` (Bloque A `UI5-21` + §5) y `docs/adr/040-user-information-architecture.md` §13.
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.93-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad semántica (`UI5-12`/`UI5-16`).** Comprobar que `auto-copy.test.ts` falla si `operar.description` vuelve a decir «ha elegido», si `riesgo.description` promete «cuánto puedes perder», o si reaparece DEMO/PAPER en primer nivel.
7. **Descubribilidad sin sexta puerta (`UI5-21`).** Comprobar que el chip `operative-mode-chip` enlaza a `/auto` y que **no** vive dentro de `nav[aria-label="Principal"]` (`app-top-bar.test.tsx`).
8. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que AUTO vuelva a afirmar una decisión de cartera sin traza durable · que el chip de modo entre en la nav Principal o cambie el modo · que Riesgo vuelva a prometer una cifra no medida · que el diff toque `packages/py/**`/motor/contrato/migraciones · que `replay-repro` no reproduzca `1E3ADAC2…`.
