# Relevo: continuación higiene de formato (lotes 19-27, resto de apps/web/src)

> **Fecha:** 2026-08-11 · **Hilo actual cierra en lote 27**
> Documento de mano para el siguiente chat. Fuente de verdad de ejecución: `traspaso-higiene-formato-legacy-salida-2026-08-11.md`.
> Único objetivo pendiente del hilo: **seguir aplicando prettier por sub-lotes al resto de `apps/web/src`** (fuera de `features/backtests`, que está COMPLETO y CERRADO).

---

## 1. Estado al cerrar el hilo (verificado y sincronizado)

- Ramas y trabajo: **0 commits ahead**, todo pusheado a `origin/stage/estudio-membership-operativa-2026-08-04`.
- **HEAD = `e498c68`** (`docs(engineering): registrar lote 27 lib sub-batch B y cierre de dominio`).
- Working tree **limpio** (sin untracked ni modificaciones).

### Commits de este hilo (lotes 19-27)
| Lote | Commit | Dominio | Files | Diff |
|---|---|---|---|---|
| 19 | `689c294` | accounts | 17 | +973/−656 |
| 20 | `1081809` | workspace | 7 | +107/−78 |
| 21 | `75f6595` | config+platform | 14 | +601/−443 |
| 22 | `cbd0fff` | research | 10 | +749/−452 |
| 23 | `4300674` | settings | 25 | +1927/−1433 |
| 24 | `e38be2d` | instruments | 30 | +2128/−1399 |
| 25 | `110667b` | stores (`apps/web/src/stores`) | 31 | +1911/−1207 |
| 26 | `465137a` | lib sub-batch A (18 de 35) | 18 | +1299/−897 |
| 27 | `0b8f04b` | lib sub-batch B (17 de 35) CIERRE lib | 17 | +518/−388 |

**Total acumulado: 379 ficheros** con diff real en 27 commits de formateo (210 de `features/backtests` lotes 1-18 + 169 del resto lotes 19-27). Todos con batería `typecheck · lint 0e · test 140/707 · build` en verde (y `test:coach` en lotes Coach/TOP, que aquí no aplica).

**Pendientes restantes (excl. `features/backtests`): 250 files** (referencia del doc de salida; un glob amplio da ~255 incluyendo 5 de backtests).

---

## 2. Protocolo estricto (8 pasos) — NO VARIAR

1. **Check**: `git status` limpio + `npx prettier --check "<sub-lote glob>"`.
2. **Write**: `npx prettier --write "<sub-lote glob>"` (sub-lote = lista explícita o glob, **sin mezclar dominios**).
3. **EOL check**: `git add <files>` + `git diff --cached --numstat` → si un file no aparece (0 0 / no listado) es **falso +EOL**: `git reset <file>` y fuera del commit. Solo si el file NO aparece en numstat se descarta; todos deben tener diff real.
4. **Batería**: `pnpm --filter @bolsa/web typecheck` · `lint` · `test` · `build`. Si el sub-lote toca área **Coach/TOP**, añadir `test:coach`. Solo métodos desde raíz (cwd = raíz repo).
5. **Commit** `--no-verify` con mensaje largo (ver encodificación abajo).
6. **Push** a origin.
7. **Registro** en los 3 docs (ver §4).
8. **Verificación final**: `git status -sb` sin `[ahead]` (0 ahead).

### Encodificación del mensaje de commit (crítico en PowerShell)
- **NO** usar `Set-Content -Encoding utf8` (añade BOM y corrompe el subject en git).
- Usar **solo ASCII** (reemplazar `—` por `-`, `§` por `sec`, evitar `ê/á/ñ` o acentos) y escribir con:
  `[System.IO.File]::WriteAllText("$PWD\.git\COMMITMSG_<tag>.txt", $msg)` con `$msg` en here-string `@'...'@`.
- `git add` siempre sobre rutas/concretas; `git commit --no-verify -F "$PWD\.git\COMMITMSG_<tag>.txt"`.
- Al terminar, borrar los temporales `COMMITMSG_*.txt` y confirmar `git status -sb` limpio.

### Aviso de auto-review (novedad en lotes 26-27)
Los commits `--no-verify` y el `git push` pueden ser **bloqueados por auto-review** y pedir aprobación nativa (`request_smart_mode_approval=true` + `smart_mode_block_reason` exacto). Es el flujo normal de seguridad; usa la tarjeta de aprobación cuando ocurra. El push local sí es autorizado por el protocolo; en caso de rechazo manual, reportar al usuario.

---

## 3. Dominios pendientes por hacer (orden sugerido)

Dado que el límite es **≤ ~30 files por sub-lote** y no mezclar dominios:

- **`features/screeners` — 27 files** → cabe en **1 lote** completo (próximo natural). Verificar con check.
- **`features/charts` — ~86 files** → dividir en **3 sub-lotes** (~29 / ~29 / ~28) por prefijo de nombre alfabético. *CUIDADO: puede haber área Coach/TOP (charts del dominio `hub`/`chart`/`misc` forma parte del backtesting de gráficos) → revisar si toca `test:coach`.*
- **`features/trading` — ~96 files** → dividir en **4 sub-lotes** (~24 cada uno). Incluye subdirectorio `lists-tab/` (gestionar el glob para `*.{ts,tsx}` dentro). *Revisar Coach/TOP.*
- **Auxiliares (opcional, por tamaño): `features/alerts`, `features/auth`, `features/ai`, `features/help`** → juntos ~12 files, pueden ir en 1-2 lotes.
- Otros posibles: `components/ui`, `layout`, `utils`, `hooks`, `pages` si los tiene (verificar con glob por dominio fuera de features).

**Regla de oro:** medir SIEMPRE con `prettier --check` qué files están realmente desincronizados (no asumir el count del plan); los globs pueden no coincidir con la realidad (ej: `stores` estaba en `apps/web/src/stores`, no `features/stores`).

---

## 4. Docs a actualizar tras cada lote (los 3, commit `docs(engineering)`)

1. **`docs/engineering/dev-continuation-plan-2026-08-09.md`** — §7.6.i: añadir fila a la tabla de lotes (con commit, dominio, files, diff), y actualizar la línea "Siguiente lote" con HEAD y el nuevo conteo pendiente.
2. **`docs/engineering/traspaso-higiene-formato-legacy-salida-2026-08-11.md`** — tabla de avance (fila + total de files), entrada en la lista de sub-lotes (tachar dominio al cerrarlo), y la "Nota de método (relevo)" con los lotes hechos y el conteo pendiente.
3. **`docs/engineering/engineering-index-2026-08-03.md`** — línea del documento de salida: avance (lotes/files), HEAD y dominios hechos.

Conteo de referencia para la nota de relevo: al cierre del hilo, **250 files pendientes** (excl. backtests), **379 files formateados** en **27 commits**.

---

## 5. Cómo leer los docs fuente

- `docs/engineering/traspaso-higiene-formato-legacy-entrada-2026-08-10.md` — ENTRADA original: protocolo 8 pasos + estrategia por dominios + halazgo de falsos EOL.
- `docs/engineering/traspaso-higiene-formato-legacy-salida-2026-08-11.md` — SALIDA actualizada: es el **documento vivo** donde registrar avance (este fichero es el anclado por `engineering-index`).
- `.gitattributes` (`* text=auto eol=lf`) · `.prettierrc` (vacío = defaults).

---

## 6. Recomendaciones operativas para el siguiente chat

1. Empezar por **`features/screeners` (1 lote, 27 files)** para cerrar otro dominio entero y ganar empuje.
2. Mantener el ritmo de 1 lote por mensaje, confirmando batería verde y 0 ahead al final de cada uno.
3. No reformatear por encima de la lista/glob elegida; verificar con numstat que NO hay files fuera del sub-lote staged.
4. Los tests (707) y build deben seguir verdes en cada lote; si algún diff de formato tocara lógica por accidente, revertir ese file antes de commitear.
5. Al acabar cada dominio "grande" (charts, trading), marcar el CIERRE en la lista de sub-lotes del traspaso-salida, igual que se hizo con `lib` (lotes 26-27).
