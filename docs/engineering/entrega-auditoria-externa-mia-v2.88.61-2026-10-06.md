# Entrega a auditoría externa (MIA) — `v2.88.61-beta` · `DEV/INFRA`: **fix de arranque de la venv bajo Windows Smart App Control** (+ bump `2.11.61-beta`; absorbe la F5 de `v2.88.60`)

> **Fecha:** 2026-10-06 · **Producto:** `V2.88.61-beta` · **Package:** `2.11.61-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.60-beta` (F5, **sin tag propio**; **absorbido** aquí) → `v2.88.59-beta` (tag → `a970b2e0`, `Release tag CI` [`37423991541`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37423991541) **VERDE**).
> **Unidad de esta auditoría:** el bloqueo de arranque reportado («no arranca la APP»). Causa medida: **Windows Smart App Control** bloqueaba el intérprete de la venv que genera `uv`.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia.
> **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor tocado; **no** se toca `replay_oos.RoundTrip.to_dict`. **El contrato HTTP NO cambia** en este sello (se hereda el de `v2.88.60`).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.61/README.md`](./evidence/v2.88.61/README.md) (`§0`–`§7`).
> **Nota de auditabilidad.** A diferencia de `v2.88.60` (commits locales, sin push ni tag), este sello **se publica**: `main` empujado y **tag anotado `v2.88.61-beta`** creado, de modo que el `Release tag CI` certifica el árbol en GitHub. La **cita del CI** viaja en el `Release` y en la evidencia §7 (POST-TAG).

**Sello dirigido (declarado).** Mandato: **la APP debe arrancar**. La decisión de diseño es **no depender de la configuración de Windows** (SAC no admite exclusiones) y **eliminar la causa**: la venv usa un binario firmado y **se auto-repara** si `uv` reintroduce el trampolín bloqueado. Se **absorbe** la F5 de `v2.88.60` para no correr dos pipelines (criterio `v2.88.49`→`v2.88.50`).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el arranque robusto frente a *App Control*:

1. **Diagnóstico nativo.** `probePython(exe)` distingue el bloqueo (`UNKNOWN`/`-4094`) de un fallo de versión.
2. **Reparación de causa.** `repairVenvPython()` sustituye **solo** los intérpretes de la venv por una **copia real** del base (`python -m venv --copies`), conservando `pyvenv.cfg`/`site-packages`; backup en `*.sacbak`.
3. **Integración.** `resolvePython({ log })` prioriza la venv del proyecto y la auto-repara; `run-dev.mjs` loguea la reparación; `dev-doctor` chequea `Python venv`.
4. **Operación.** `scripts/fix-venv-python.mjs [--check]`, scripts npm `fix:venv`/`venv:test`, `scripts/lib/python.test.mjs`.

**Se entrega, además (absorbido),** la **F5 de `v2.88.60`** — resolución DÍA-D por `cycleId` (`dia-d-feedback-v2`, `cycles[]`, `resolveExplanationForCycle`), tal y como se documenta en [`entrega-auditoria-externa-mia-v2.88.60-2026-10-06.md`](./entrega-auditoria-externa-mia-v2.88.60-2026-10-06.md) y [`evidence/v2.88.60`](./evidence/v2.88.60/README.md).

**NO se entrega**, y se declara:

- **NO** se toca el motor ni el contrato HTTP ni el esquema/migraciones (`Δ motor = 0`; Alembic head intacto).
- **NO** se cierran las deudas abiertas de `v2.88.60`: `PortfolioDecision` durable (`UI52-02`), barrido `axe` en vivo (`F-A2`), `F-S2`/`F-S3`, PIT histórico institucional y Execution Analysis.
- **NO** se re-mide `DÍA-D`: las cifras OOS de `v2.88.50`/`v2.88.51` se **heredan y citan**.

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| Diagnóstico/guardias | `scripts/lib/python.mjs` | `probePython`, `projectVenvPython`, `readPyvenvHome`, `ensureVenvPython`, `repairVenvPython`; `resolvePython({ log })` prioriza la venv. |
| CLI de reparación | `scripts/fix-venv-python.mjs` | `node scripts/fix-venv-python.mjs [--check]`. |
| Doctor | `scripts/dev-doctor.mjs` | Chequeo `Python venv` (diagnóstica el bloqueo, con pista de arreglo). |
| Arranque | `scripts/run-dev.mjs` | Pasa el logger a `resolvePython` (reparación visible). |
| Tests | `scripts/lib/python.test.mjs` | `readPyvenvHome` (entrada `uv`) + `probePython` (**4 passed**). |
| Bump | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.61-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |
| Freeze | `scripts/lib/window-forward.mjs` | Re-ancla el pin al commit `52a697e1` (`apps` `286cf716…`). |

---

## 3. Medición

- **Motor:** sin cambio. No se re-corre `DÍA-D`; se **citan** las cifras vigentes de [`v2.88.50`](./evidence/v2.88.50/README.md) (idénticas a las que cita `v2.88.60`, porque la F5 no altera el veredicto agregado por instrumento).
- **Arranque (medido en esta máquina):** `node scripts/run-dev.mjs` → `[dev] Python: …\.venv\Scripts\python.exe` → `[dev] API lista` → `VITE ready` → `[dev] Web lista -> http://localhost:5173`. Reproducción del escenario de bloqueo: el arranque detecta `UNKNOWN` y **repara solo**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`F-A2` — barrido `axe` en vivo de `/auto/*` no ejecutado.** Remediation: spec `axe` propio para `/auto/*` en el siguiente sello de UI.
- **`F-S2`/`F-S3` (P3):** densidad tipográfica (`text-[11px]`) e `h1` crudo de ausencia.
- **`PortfolioDecision` durable (`UI52-02`)**, **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): pre-existentes.
- **Método local.** La reparación de la venv **desbloquea** `python.exe`: el `bump guard` corre y pasa (**1 passed**), a diferencia de `v2.88.60`, donde figuraba como no ejecutable. La matriz Python completa/`mypy`/`import-linter`/`contract:check` las ejecuta el **CI** (fuera del alcance de este sello).

---

## 5. Gates

| Gate | Resultado |
| --- | --- |
| `node --test scripts/lib/python.test.mjs` | **4 passed** |
| `node --test scripts/lib/window-forward.test.mjs` | **25/25 passed** |
| `node scripts/fix-venv-python.mjs --check` | **OK** (`Python 3.12.13`) |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.61-beta`) |
| `node scripts/run-dev.mjs` (E2E arranque) | **OK** (API lista + Web lista) |
| `@bolsa/shared` / `@bolsa/web` | heredados de `v2.88.60` (`813` / `1442` passed) |
| `pytest` matriz / `mypy` / `import-linter` / `contract:check` | **los ejecuta el CI** (contrato sin cambio) |

---

## 6. Sello

- **Producto:** `V2.88.61-beta`. **Package:** `2.11.61-beta`. **Sin migración** (Alembic head `048_journal_entry_dedupe_key`). **Contrato HTTP sin cambio.**
- **Añadidos:** `scripts/fix-venv-python.mjs`, `scripts/lib/python.test.mjs`, `docs/engineering/evidence/v2.88.61/README.md`, este documento.
- **Modificados:** `scripts/lib/python.mjs`, `scripts/dev-doctor.mjs`, `scripts/run-dev.mjs`, `package.json` (`2.11.61-beta`), `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).

| Rol | Commit | Árboles |
| --- | --- | --- |
| Bump de versión (`chore(release)`) | `52a697e1` | `apps` `286cf716…` / `packages` `b482a276…` |
| Re-anclaje del freeze (`chore(window)`) | `dfc2966a` | pin `commit: 52a697e1` (no mueve árbol) |
| **Commit del sello** (`docs(seal)`) | (tip) | (mismos árboles que el bump) |
| Tag anotado `v2.88.61-beta` | **creado y empujado** | `Release tag CI` pendiente de cita POST-TAG |

- **Absorción:** este sello **incluye** la F5 de `v2.88.60` (sin tag propio); el `Release tag CI` de `v2.88.61-beta` certificará conjuntamente ambos cambios.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.61/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Base.** `docs/engineering/evidence/v2.88.60/README.md` + `entrega-auditoria-externa-mia-v2.88.60-2026-10-06.md` (F5, absorbida) y `…/v2.88.59/…`.
4. **Freeze.** `git rev-parse "52a697e1:apps" "52a697e1:packages"` debe devolver **exactamente** `286cf716…` / `b482a276…` (el pin `scripts/lib/window-forward.mjs` los cita).
5. **Reproducción local.**
   ```bash
   node scripts/fix-venv-python.mjs --check
   node --test scripts/lib/python.test.mjs
   node --test scripts/lib/window-forward.test.mjs
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   node scripts/run-dev.mjs   # API lista + Web lista
   ```
6. **Qué falsaría el sello:** que `probePython` no detecte el bloqueo · que `resolvePython` no priorice la venv · que la reparación deje la venv inejecutable o rompa `site-packages` · que el diff toque motor/contrato/`to_dict` · que `freezeCheck` no cuadre con `HEAD` · que el `Release tag CI` no reproduzca `replay-repro` (`Δ motor = 0`).
