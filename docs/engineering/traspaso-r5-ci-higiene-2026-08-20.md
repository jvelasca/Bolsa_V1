# Traspaso R-5 — CI/higiene: Node.js 22 + actions Node-24 + 2 warnings lint + gitignore artefactos locales

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-5 del plan de refactor 2026-08-19 (CI Node.js 20 deprecado + opcional `.prettierrc`), ampliada a la **re-auditoría de deuda abierta/operativa** pactada en el hilo de re-auditoría 2026-08-20.
> **Estado:** **COMPLETADO en `main`** (2 commits directos `3b9c139` + `da8a10c`, árbol limpio, `local main = origin/main = da8a10c`).
> **AsOf:** 2026-08-20.

---

## 1. Resumen

R-5 cierra la deuda operativa/pendiente del relevo `relevo-para-reauditoria-2026-08-19.md`. El alcance pactado con el usuario fue **deuda abierta/operativa** (no superficie completa), ejecutado por fases acotadas con aprobación por commit.

**Hallazgo clave:** la deprecación de Node 20 en CI **NO venía de nuestro `node-version`** (que ya era `'22'` en `frontend-ci.yml` y `fase2-scientific.yml`), sino de **las propias acciones** corriendo internamente sobre Node 20 (`actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, `pnpm/action-setup@v4`). GitHub migró el runner a Node 24 por defecto el 2026-06-16 (EOL Node 20 abr 2026); la anotación es un aviso no-bloqueante pero se eliminó por higiene.

## 2. Commit 1 — `3b9c139` `chore(ci): R-5 fondo deuda operativa ...`

- **`.github/workflows/optimize-lab.yml`**: `setup-node` `node-version: '20'` → `'22'` — única runtime Node 20 restante; alinea con `frontend-ci`/`fase2-scientific`.
- **`apps/web/src/features/backtests/backtests-page.tsx`** (líneas 1226-1239): suprimir **puntualmente** 2 warnings `react-hooks/exhaustive-deps` en el `useEffect` de cleanup de unmount (`batchAbortRef`/`exploreAbortRef`). El autofix sugerido por ESLint (snapshot del ref a una variable local **dentro del effect**) **REGRESIONARÍA**: los refs nacen como `null` en el primer render y solo se asignan al iniciar un batch; en unmount queremos abortar el `AbortController` vigente (leer `ref.current` en cleanup es deliberado). Fix = `// eslint-disable-line react-hooks/exhaustive-deps` en las 2 líneas concretas con comentario justificando por qué.
- **`.gitignore`**: añadir `.import_linter_cache/` y `.venv_backup_*/`. Hallazgo real de auditoría: `.venv_backup_20260811/` (backup venv local no versionado, **661 MB**) y `packages/py/.import_linter_cache/` eran artefactos locales no rastreados NI gitignoreados que inflaban `pnpm format:check` (~446 files de ruido). Se **borró** `.venv_backup_20260811` del disco (661 MB liberados).
- **`.prettierrc`: NO se toca.** La nota del relevo ("opcional .prettierrc para quitar churn de comillas dobles") quedó **OBSOLETA**: la hygiene M0/§6.2 ya convirtió `apps/web/src` a comillas dobles prettier-default (512 files / 36 commits). Añadir `singleQuote: true` ahora **revertiría 500+ archivos** → churn masivo no deseado. Decisión con aval del usuario.

**Batería commit 1:** web `typecheck` 0 ✓ · `lint` **0 errores / 0 warnings** (los 2 históricos resueltos) ✓ · `build` OK ✓ · `git check-ignore` verifica `.venv_backup_*` y `.import_linter_cache/` ✓.

## 3. Commit 2 — `da8a10c` `chore(ci): R-5 bump actions a majors Node-24 ...`

Descubierto en la verificación CI del commit 1: la anotación de deprecación seguía apareciendo en el run de Optimize lab a pesar de `node-version: '22'`, porque **las acciones** corren internamente en Node 20. Bump de las 4 afectadas a sus majors Node-24:

| Acción                 | v4/v5 →       | Workflows                                             |
| ---------------------- | ------------- | ----------------------------------------------------- |
| `actions/checkout`     | `@v4` → `@v5` | frontend-ci, optimize-lab, python-ci, fase2, gitleaks |
| `actions/setup-node`   | `@v4` → `@v5` | frontend-ci, optimize-lab, fase2                      |
| `actions/setup-python` | `@v5` → `@v6` | optimize-lab, fase2                                   |
| `pnpm/action-setup`    | `@v4` → `@v5` | frontend-ci, optimize-lab, fase2                      |

**Notas:**

- `actions/setup-node@v5` tiene un breaking change (auto-cache si hay `packageManager` en `package.json`). Se **mantiene `cache: 'pnpm'` explícito** que tiene precedencia y evita colisión con el auto-detect.
- Se dejan sin tocar: `astral-sh/setup-uv@v5` (binario Rust, no action JS Node) y `gitleaks/gitleaks-action@v2` (no aparece en la anotación de deprecación).

## 4. Batería CI (verificada en `origin/main` tras `da8a10c`)

Tras el push, los 4 workflows que dispara el cambio (path-filter) quedaron **VERDES** y la anotación de deprecación de Node 20 **desapareció**:

| Workflow                                                                           | Resultado                                                                                        |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Frontend CI (quality: shared build/typecheck/test + web typecheck/lint/test/build) | ✅ verde, sin anotación                                                                          |
| Optimize lab (battery + Walk-forward DTO contract)                                 | ✅ verde, sin anotación (`checkout@v5`/`pnpm/action-setup@v5`/`setup-node@v5`/`setup-python@v6`) |
| Fase 2 scientific (fase2-battery)                                                  | ✅ verde                                                                                         |
| Gitleaks                                                                           | ✅ verde                                                                                         |

(Python CI no disparó: el cambio de actions no toca packages/py ni apps/api-python — correcto por path-filter.)

## 5. Checklist operativo manual pendiente (fuera de repo, no bloquea)

Del relevo R-1/2026-08-19 + F-WORKER-1, **siguen pendientes** (acciones manuales, no código):

- Activar GitHub **secret scanning** nativo (UI → Settings → Code security; configurar GHL + gitleaks).
- Definir **`TRUSTED_PROXIES` prod** con las IPs del proxy de borde (bloqueado por valores reales del usuario; `config.py:28` ya expone el setting, default vacío).
- Corregir registro en BD `yahoo_symbol='BP/.L'` → `'BP.L'` si se quiere dato real (F-WORKER-1; actualmente fallo permanente no reintentable, sin impacto).
- Limpiar `logs/dev/*.log` antiguos en disco si se desea (~150 MB históricos; `pruneStampedLogs()` ya conserva las 10 sesiones recientes).
- Opcional: purga de valores dev del historial git público (filter-repo/BFG, decisión explícita informada).

## 6. Deuda futura / fuera de alcance de R-5 (no abrir sin decisión explícita)

- `MandateTenure`/`MandateTradeLink` del web conservan shape localStorage (NO el `*Dto` wire) — no consolidado por D5.
- Inner `data` de los endpoints AI shape-abierto NO tipado (por diseño; tiparlo dropearía claves condicionales).
- Alias semántico del wrapper `AiEffectivenessResponseDto` → `OpenPayloadResponseDto` (cosmético).
- Transferencias entre carteras / dividendos (P2.3 README, deuda feature).
- **Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4).

## 7. Texto de traspaso (para el próximo chat)

> CONTEXTO (2026-08-20): **R-5 (CI/higiene deuda operativa) COMPLETADO en `main`** — 2 commits directos (`3b9c139` fondo deuda: Node 22 en optimize-lab + 2 warnings lint + gitignore; `da8a10c` bump actions a majors Node-24), árbol limpio, `local main = origin/main = da8a10c`, CI verde.
>
> **Hallazgo clave R-5:** la deprecación de Node 20 en CI NO era nuestro `node-version` (ya 22 en casi todo) sino **las acciones** corriendo internamente en Node 20. Se subieron a majors Node-24 (`checkout@v5`, `setup-node@v5`, `setup-python@v6`, `pnpm/action-setup@v5`) → **anotación eliminada**, CI verde en los 4 workflows. **`.prettierrc` NO se tocó** (obsoleto: la hygiene ya convirtió a comillas dobles; añadir singleQuote revertiría 500+ archivos).
>
> **Hallazgo de auditoría adicional:** `.venv_backup_*/` y `.import_linter_cache/` eran artefactos locales no rastreados ni gitignoreados que inflaban `pnpm format:check` (~446 files). Fix: `.gitignore` + borrado del venv backup (661 MB).
>
> Estado vivo y deuda: `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO, §3 deuda · §6 texto · §7 registro) · `docs/engineering/engineering-index-2026-08-03.md` §5 · relevo de re-auditoría: `docs/engineering/relevo-para-reauditoria-2026-08-19.md` · este traspaso.
> SIGUIENTES (checklist operativo manual, fuera de repo): secret scanning UI · `TRUSTED_PROXIES` prod · `BP/.L`→`BP.L` en BD · limpiar logs dev. **Plan de refactor 2026-08-19 (R-1..R-5) COMPLETADO.**
>
> Regla: una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Freeze vigente: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. Auth JWT diferida (D4).
