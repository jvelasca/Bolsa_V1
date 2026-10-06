# Evidencia `v2.88.61-beta` — `DEV/INFRA`: **fix de arranque de la venv bajo Windows Smart App Control** (+ bump `2.11.61-beta`; absorbe la F5 de `v2.88.60`)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial.

**Producto:** `V2.88.61-beta` · **Package:** `2.11.61-beta` · **AsOf:** 2026-10-06 · **Nature:** `DEV/INFRA (tooling de arranque)` · **Fase:** `arranque local (App Control) + absorción de AUTO F5`. **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios respecto a `v2.88.60` (`dia-d-feedback-v2`, `dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **SIN cambio** (se hereda el contrato de `v2.88.60`, que sí añadió `cycles[]`; aquí no se toca `openapi.json`/`schema.d.ts`).

**Padre:** [`v2.88.60`](../v2.88.60/README.md) (F5, **sin tag propio**; se **absorbe** en este sello) → [`v2.88.59`](../v2.88.59/README.md).

**Decisión de alcance (declarada).** Entrada: la incidencia operativa **«no arranca la APP»**. El diagnóstico (registro de *Code Integrity*) mostró que **Windows Smart App Control** bloqueaba el intérprete de la venv que `uv` genera (`.venv/Scripts/python.exe`), y `scripts/run-dev.mjs` moría en `spawn(python, …, { shell:false })` con `spawn UNKNOWN`. Este slice **elimina la causa** (la venv pasa a usar un binario firmado y se **auto-repara**) en vez de depender de configuración de Windows. Como el sello F5 (`v2.88.60`, resolución DÍA-D por `cycleId`) viajaba en **commits locales sin tag**, se **absorbe** aquí para publicar un único pipeline (mismo criterio de absorción que `v2.88.49`→`v2.88.50`).

---

## 0. Qué añade este sello (y qué NO)

**Añade** el arranque robusto frente a *App Control*:

1. **Diagnóstico nativo.** `probePython(exe)` distingue el bloqueo (`error.code === 'UNKNOWN'`, errno `-4094`) de un simple fallo de versión, y expone el detalle (`Python X.Y.Z`).
2. **Reparación de causa.** `repairVenvPython(venvPython)` sustituye **solo** los intérpretes de la venv (`python.exe`/`pythonw.exe`) por una **copia real** generada con `python -m venv --copies` desde el intérprete base, **conservando** `pyvenv.cfg` y `site-packages`. El trampolín bloqueado se respalda en `*.sacbak` (reversible).
3. **Integración.** `resolvePython({ log })` **prioriza la venv del proyecto** y la auto-repara si está bloqueada; `run-dev.mjs` pasa el logger; `dev-doctor` añade el chequeo `Python venv`.
4. **Operación.** `scripts/fix-venv-python.mjs [--check]`, scripts npm `fix:venv`/`venv:test`, tests `scripts/lib/python.test.mjs`.

**NO** cambia el motor (`Δ motor = 0`), **no** cambia el contrato HTTP, **no** añade migración, y **no** cierra las deudas abiertas de `v2.88.60` (`PortfolioDecision` `UI52-02`, barrido `axe` en vivo `F-A2`, `F-S2`/`F-S3`, PIT institucional, Execution Analysis).

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| #   | Afirmación                                                                                                                                                             | Cómo se rompe (falsación)                                                                                       | Evidencia |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------- |
| **1** | El fallo era **App Control** bloqueando `.venv/Scripts/python.exe` (trampolín de `uv`), no un error de Python ni de puertos/DB.                                        | Que `probePython('.venv/Scripts/python.exe')` devuelva `ok:true` (no estaba bloqueado).                        | §3, §4    |
| **2** | `resolvePython()` **prefiere la venv del proyecto** (antes devolvía `"python"`, que ya era la venv activada pero no se validaba).                                       | Que `resolvePython()` devuelva `"python"` con una venv presente y sana.                                        | §3, §5    |
| **3** | Si el intérprete de la venv está bloqueado, se **auto-repara** a una copia real y vuelve a ser ejecutable (`status 0`).                                                | Que tras `repairVenvPython` el `spawn` siga dando `UNKNOWN`.                                                    | §3, §5    |
| **4** | La reparación **no destruye** el entorno: `pyvenv.cfg` y `site-packages` intactos; el binario previo queda en `*.sacbak`.                                              | Que un `import fastapi/sqlalchemy/uvicorn` falle tras reparar, o que no exista el `*.sacbak`.                    | §3, §5    |
| **5** | **Smart App Control no admite exclusiones** (solo on/off; no reversible sin reinstalar Windows) ⇒ la estrategia correcta es eliminar la causa, no excluir.            | Que exista una ruta de exclusión por carpeta documentada que evite el bloqueo.                                   | §5        |
| **6** | `Δ motor = 0` y **contrato HTTP sin cambio**: ningún fichero de motor ni `openapi.json`/`schema.d.ts` tocado.                                                          | Que el diff toque motor, umbrales, `to_dict`, o el contrato.                                                     | §6        |
| **7** | Con la venv reparada, los gates **Python** son ejecutables en local (antes bloqueados): `test_dia_d_bump_guard.py` **1 passed**.                                        | Que `pytest` no arranque o el guard falle.                                                                      | §2        |

---

## 2. Verificación (gates)

| Gate                                                    | Resultado                                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `node --test scripts/lib/python.test.mjs`               | **4 passed** (incluye `readPyvenvHome` de un `pyvenv.cfg` de `uv` y `probePython`)    |
| `node --test scripts/lib/window-forward.test.mjs`       | **25/25 passed**                                                                      |
| `node scripts/fix-venv-python.mjs --check`              | **OK** — `Python 3.12.13` (venv sana)                                                 |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** — `meta.bump == package.json.version` (`2.11.61-beta`) en `v2_89`…`v2_97` |
| `node scripts/run-dev.mjs` (end-to-end)                 | `[dev] Python: …\.venv\Scripts\python.exe` → `[dev] API lista` → `VITE ready` → `[dev] Web lista` |
| `@bolsa/shared` build + `vitest` / `@bolsa/web` `vitest`| heredados de `v2.88.60` (**813** / **1442** passed); **no** se re-corren aquí        |
| `pytest` suite completa / `mypy` / `import-linter` / `contract:check` | **el CI los ejecuta** (localmente ya no bloqueados, pero fuera del alcance de este sello) |

> **Nota de método (declarada).** La reparación de la venv **desbloquea** `python.exe` en esta máquina: el `bump guard` corre y pasa. No se re-ejecuta la matriz completa ni `DÍA-D` (declarado: cifras OOS **heredadas y citadas** de `v2.88.50`/`v2.88.51`).

---

## 3. El cambio, en detalle

- **`scripts/lib/python.mjs`:** nuevo `probePython(exe)` (`ok`/`code`/`detail`), `projectVenvPython()` (venv del proyecto o `VIRTUAL_ENV`), `readPyvenvHome(cfgText)` (función **pura**), `ensureVenvPython({ log })` y **`repairVenvPython(venvPython, { log })`**. `resolvePython({ log })` pasa a: `PYTHON` → **venv del proyecto (reparada si hace falta)** → `PATH` (`python`/`python3`/`py`) → `'python'`.
- **`scripts/fix-venv-python.mjs`:** CLI de diagnóstico/reparación (`--check` no modifica; sin flag, repara si detecta `UNKNOWN`).
- **`scripts/lib/python.test.mjs`:** tests de `readPyvenvHome` (entrada `uv` real, entradas ausentes/no-textuales) y de `probePython` (binario inexistente → `ok:false`; venv/PATH → `Python X.Y.Z`).
- **`scripts/dev-doctor.mjs`:** nuevo chequeo `Python venv` (diagnostica el bloqueo, con pista `node scripts/fix-venv-python.mjs`), sin reparar.
- **`scripts/run-dev.mjs`:** `resolvePython({ log: (m) => logInfo('dev', m) })` para hacer visible la reparación en el arranque.
- **`package.json`:** scripts `fix:venv` y `venv:test` (y `version` → `2.11.61-beta`).

---

## 4. Diagnóstico (registro de Windows)

```
Microsoft-Windows-CodeIntegrity/Operational
Id 3077 (Error): Code Integrity determined that a process (...\nodejs\node.exe) attempted to load
  \Device\HarddiskVolume3\Users\josea\...\Bolsa_V1\.venv\Scripts\python.exe that did not meet the
  Enterprise signing level requirements (Policy ID:{0283ac0f-fff1-49ae-ada1-8a933130cad6}).
Id 3118 (Información): Smart App Control Block Details
```

- Trampolín de `uv`: **45 568 B**, `sha256 61b54f85…` (bloqueado).
- Base firmado: `sha256 d8e3f0ad…` (permitido).
- Venv nueva de `uv`: reproduce el **mismo** `61b54f85…` ⇒ **bloqueado** (recrear no arregla).
- Venv con `python -m venv --copies`: **262 144 B**, `sha256 560b9ef7…` ⇒ **arranca** (`Python 3.12.13`).

---

## 5. Cómo se reproduce

```bash
# 1) Diagnóstico y reparación de la venv.
node scripts/fix-venv-python.mjs --check     # exit 1 si está bloqueado
node scripts/fix-venv-python.mjs             # repara (backup en python.exe.sacbak)

# 2) Repro del escenario (simular que uv reintroduce el trampolín bloqueado):
#    copiar python.exe.sacbak -> python.exe y confirmar que el arranque lo repara solo.
node scripts/run-dev.mjs                     # [dev] Python: ...\.venv\Scripts\python.exe -> API lista

# 3) Gates del sello.
node --test scripts/lib/python.test.mjs
node --test scripts/lib/window-forward.test.mjs
pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
```

**No** se reproduce el pipeline `DÍA-D` (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `scripts/fix-venv-python.mjs`, `scripts/lib/python.test.mjs`, `docs/engineering/evidence/v2.88.61/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.61-2026-10-06.md`.
- **Modificados:** `scripts/lib/python.mjs`, `scripts/dev-doctor.mjs`, `scripts/run-dev.mjs`, `package.json` (`2.11.61-beta` + `fix:venv`/`venv:test`), `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; **no** se toca `replay_oos.RoundTrip.to_dict`. **Contrato HTTP sin cambio.**
- **Absorbe `v2.88.60` (F5, sin tag propio):** su árbol `apps`/`packages` viaja dentro de este sello.

| Rol | Commit | Árboles |
| --- | --- | --- |
| Bump de versión (`chore(release)`) | `52a697e1` | `apps` `286cf716…` / `packages` `b482a276…` |
| Re-anclaje del freeze (`chore(window)`) | `dfc2966a` | pin `commit: 52a697e1` (no mueve árbol) |
| **Commit del sello** (`docs(seal)`) | (este commit) | (mismos árboles que el bump) |
| Tag anotado `v2.88.61-beta` | **creado y empujado** | `Release tag CI` pendiente de cita POST-TAG |

> **Diferencia con `v2.88.60`:** ese sello movía `apps` **y** `packages` y cambiaba el contrato HTTP; este **solo** mueve `apps` (por `meta.bump`) y **no** toca contrato. `packages` conserva `b482a276…`.

---

## 7. Nota de contrato y de pin (declarada)

- `openapi.json` / `schema.d.ts` **no** se tocan en este sello (contrato sin cambio); el `contract:check` del CI sigue validando el contrato heredado de `v2.88.60`.
- El pin del freeze (`WINDOW_CONFIG`) se **re-ancla** al commit `52a697e1` porque el `meta.bump` de los 9 CLI DÍA-D vive en `apps/`; `packages/` no cambia. `freezeCheck` compara `git rev-parse HEAD:apps HEAD:packages` contra el pin, y en `HEAD` coinciden (`286cf716…` / `b482a276…`).
