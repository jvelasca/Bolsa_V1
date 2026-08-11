# Relevo: CIERRE de la higiene de formato Prettier en apps/web/src (lotes 1-36)

> **Fecha:** 2026-08-11 · **Estado del hilo: CERRADO por finalización del objetivo**
> Documento de cierre/cierre: el objetivo único del hilo (**aplicar prettier por sub-lotes a TODO `apps/web/src`**) está **COMPLETO y CERRADO**.
> Fuente de verdad de ejecución: `traspaso-higiene-formato-legacy-salida-2026-08-11.md`.
> **No queda pendiente de formateo.** Este doc sirve de punto de entrada limpio por si en el futuro se retoma o se extiende a otros dominios.

---

## 1. Estado al cerrar el hilo (verificado y sincronizado)

- Ramas y trabajo: **0 commits ahead**, todo pusheado a `origin/stage/estudio-membership-operativa-2026-08-04`.
- **HEAD = `6112fb2`** (`docs: registro cierre apps/web/src higiene formato Prettier (lotes 32-36, 512 files, HEAD 5b47f60)`).
- Working tree **limpio** (sin untracked ni modificaciones).
- **`prettier --check` amplio** `"apps/web/src/**/*.{ts,tsx}" "!apps/web/src/features/backtests/**"` = **0 files desincronizados**.

### Totales finales
- **512 files con diff real** formateados en **36 commits** propios de formateo:
  - `features/backtests` (lotes 2-18, COMPLETO): **210 files**.
  - Resto de `apps/web/src` (lotes 19-36): **302 files** (incl. los 2 falsos +EOL de trading dentro del conteo de lotes).
- Batería siempre verde por lote: `typecheck` · `lint` 0e · `test` 140/707 · `build` (chunk = M7). `test:coach` 26/186 en lotes de área Coach/TOP (14, 17, 18, 30, 31, 33-35) y 36 de forma conservadora.

### Commits clave de cierre (lotes 32-36)
| Lote | Commit | Dominio | Files | Diff |
|---|---|---|---|---|
| 32 | `7367447` | features/trading sub-batch A (charts-zone ... estudio-process-status.test) | 28 | +878/−648 |
| 33 | `3b92e76` | features/trading sub-batch B (estudio-process-status ... list-recommendation-columns.test) | 29 | +1909/−1471 |
| 34 | `cafba4c` | features/trading sub-batch C (list-recommendation-scores-context ... propose-instrument-supervised.test) | 28 | +1129/−924 |
| 35 | `49c7fac` | features/trading sub-batch D CIERRE trading (propose-instrument-supervised ... use-trade-notional) | 27 | +1169/−938 |
| 36 | `5b47f60` | auxiliares + root app/main CIERRE resto apps/web/src | 19 | +1571/−1077 |
| — | `6112fb2` | registro docs de cierre (3 vistas del índice) | 3 docs | — |

**Dominios cerrados en el hilo:** `accounts` (19), `workspace` (20), `config`+`platform` (21), `research` (22), `settings` (23), `instruments` (24), `stores` (25), `lib` (26-27), `screeners` (28), `charts` (29-31), `trading` (32-35), auxiliares+root (36).

---

## 2. Protocolo estricto (8 pasos) — referencia intacta por si se retoma

1. **Check**: `git status` limpio + `npx prettier --check "<sub-lote glob>"`.
2. **Write**: `npx prettier --write "<sub-lote glob>"` (sub-lote = lista explícita o glob, **sin mezclar dominios**).
3. **EOL check**: `git add <files>` + `git diff --cached --numstat` → si un file no aparece (no listado) es **falso +EOL**: `git reset <file>` y fuera del commit.
4. **Batería**: `pnpm --filter @bolsa/web typecheck` · `lint` · `test` · `build`. Área **Coach/TOP** `test:coach`. Solo desde la raíz.
5. **Commit** `--no-verify` con mensaje largo (ver encodificación abajo).
6. **Push** a origin.
7. **Registro** en los 3 docs (ver §3).
8. **Verificación final**: `git status -sb` sin `[ahead]` (0 ahead).

### Encodificación del mensaje de commit (crítico en PowerShell)
- **NO** usar `Set-Content -Encoding utf8` (añade BOM y corrompe el subject en git).
- Usar **solo ASCII** (reemplazar `—` por `-`, `§` por `sec`, evitar acentos) con `[System.IO.File]::WriteAllText("$PWD\.git\COMMITMSG_<tag>.txt", $msg)`.
- `git add` sobre rutas concretas; `git commit --no-verify -F "$PWD\.git\COMMITMSG_<tag>.txt"`; borrar temporales al final.

### Aviso de auto-review
Los commits `--no-verify` y el `git push` pueden ser **bloqueados por auto-review** pidiendo aprobación nativa (`request_smart_mode_approval=true` + `smart_mode_block_reason` exacto). Es flujo normal de seguridad; usar la tarjeta de aprobación. El push local sí está autorizado por el protocolo.

---

## 3. Docs de registro (los 3, ya actualizados en el hilo)

1. **`docs/engineering/dev-continuation-plan-2026-08-09.md`** — §7.6.i: tabla de lotes (hasta 36) + línea "Siguiente lote" con cierre.
2. **`docs/engineering/traspaso-higiene-formato-legacy-salida-2026-08-11.md`** — tabla de avance (512 files / 36 commits), nota de método de cierre.
3. **`docs/engineering/engineering-index-2026-08-03.md`** — entrada del traspaso-salida marcada COMPLETO.

Este documento (`relevo-higiene-formato-cierre-2026-08-11.md`) es el **ancla de cierre** y debe declararse como hijo del índice.

---

## 4. Cómo leer los docs fuente

- `docs/engineering/traspaso-higiene-formato-legacy-entrada-2026-08-10.md` — ENTRADA original: protocolo 8 pasos + estrategia + hallazgo de falsos EOL.
- `docs/engineering/traspaso-higiene-formato-legacy-salida-2026-08-11.md` — SALIDA: documento vivo con el registro completo 1-36.
- `.gitattributes` (`* text=auto eol=lf`) · `.prettierrc` (vacío = defaults).

---

## 5. Siguientes pasos (opcionales, fuera del alcance del hilo)

La higiene de formato está **cerrada**. Posibles frentes futuros (a coordinar en un hilo nuevo, no en este):
- Otras deudas pendientes fuera de `apps/web/src` (p. ej. `pkg/`, `py/`, `tsconfig` o herramientas) que requieran revisión de alcance.
- Continuar otro hilo de `dev-continuation-plan` o de los `traspaso-m5-*` (M5 en pausa, ver índice).
- No reformatear nada de `apps/web/src` a menos que sea un cambio funcional que lo exija (mantener 0 diffs de formato).
