# M5/§M0.6.2 — Higiene de formato legacy (prettier) por lotes aislados — ENTRADA

**Fecha:** 2026-08-10 · **Rama:** `stage/estudio-membership-operativa-2026-08-04`
**Cabecera previa (cierre M5):** `2c7cf3a`

---

## 1. Objetivo

Normalizar el formato Prettier de ficheros legacy de `apps/web` que están desincronizados con la configuración
actual, de forma **incremental y en lotes aislados** (por directorio/feature), cada uno como **commit propio de
formateo único** (sin mezclar con cambios editoriales). Esto ataca la causa raíz de por qué el proyecto commitea con
`git commit --no-verify` para evitar que el hook `lint-staged/prettier --write` formatee masivamente archivos legacy
con estilo antiguo (hallazgo M0/§6.2, `dev-continuation-plan-2026-08-09.md`).

## 2. Aclaración de alcance (relevante al nombrarla "CRLF")

**La "higiene CRLF" como deuda commiteada NO existe** y queda descartada como línea: el repo tiene `.gitattributes`
con la regla global `* text=auto eol=lf`, por lo que **git ya almacena el código en LF en el índice** y normaliza el
working copy en checkout Windows sin inflar diffs. Los 1.677 ficheros que el working copy local reporta como CRLF no
son deuda de git; son solo el checkout local.

**El problema real de M0/§6.2 es el FORMATO Prettier**, no los EOL: `prettier --check "apps/web/src/**/*.{ts,tsx,css,json}"`
reporta **643 archivos desincronizados** con la configuración actual (`.prettierrc` vacío = defaults). Prettier
reformatea el *contenido* de esos ficheros legacy (indentación 2→semantics actual, saltos de línea, quitar `'`→`"` en
props JSX, etc.), lo que infla el diff editorial: por eso se usa `--no-verify`. El formateo masivo de prettier sobre
docs/legacy debe hacerse **en commits propios de formateo único** (premisa M0/§6.2).

## 3. Estrategia: lotes aislados + commit de formateo propio

- **Regla de oro:** cada lote = solo formateo Prettier, sin cambio funcional; verificar batería tras cada lote;
  commit Y push; pasar al siguiente lote.
- **Criterio de orden** (mejor ratio valor/riesgo primero):
  1. `components/ui` + `components/layout` — reuso alto, poca lógica de negocio. (LOTE 1, hecho `d39bbbb`.)
  2. `features/backtests` **subdividido por dominio funcional** (directorio plano enorme): `optimize`→`explore`→`result`→
     `wizard` (hechos) → siguientes: `library`/`strategy-matrix`/`core-r`/`dia-d`… Cada sub-lote ≤ ~30 archivos.
  3. El resto de `apps/web/src` por sub-lotes.
- **Riesgo controlado:** cada lote es pequeño y aislado; si algo falla en batería, se revierte el commit de ese lote
  sin afectar a los demás.

## 4. Protocolo por lote (FASE 3)

1. `git status` limpio.
2. `npx prettier --check` sobre el subconjunto → confirmar recuento de desincronizados (≤ ~30 por lote).
3. `npx prettier --write` sobre SOLO ese subconjunto.
4. **Detectar falsos positivos EOL:** `git add` TODO el subconjunto y leer `git diff --cached --numstat`. Los que no
   aparezcan (numstat vacío) son **falsos positivos EOL** (contenido idéntico a HEAD; git ya los normaliza a LF) y se
   **resetean** (`git reset -- <file>`), quedando fuera del commit. Solo se commitean los ficheros con diff de contenido
   real. (Verificado en lotes 3, 4 y 5.)
5. Batería : `pnpm --filter @bolsa/web typecheck` · `lint` · `test` · `build` (exit 0).
6. `git diff --cached --stat` para confirmar que es solo formato (sin borrados funcionales).
7. Commit `--no-verify` (por el propio hook lint-staged que ya está formateado) + push.
8. Registrar en `dev-continuation-plan-2026-08-09.md` (§7.6.i) y anclar en `engineering-index`.

## 5. Estado de avance

| Lote | Commit | Dominio | Ficheros con contenido real |
|------|--------|---------|-----------------------------|
| 1 | `d39bbbb` | components/ui + layout | 15 |
| 2 | `0ceeb5b` | backtests/optimize | 8 |
| 3 | `7c174c7` | backtests/explore | 7 (bh = falso +EOL) |
| 4 | `d96123d` | backtests/result | 5 (detail/finalists/ranking = falso +EOL) |
| 5 | `9fa403a` | backtests/wizard | 2 (mass-compare/probe-list = falso +EOL) |
| 6 | `68c9dac` | backtests/library + strategy-matrix | 5 |
| 7 | `f241872` | backtests/core-r | 13 |

**Estado del hilo (2026-08-10):** lotes 1-7 ejecutados bajo+verde. El siguiente hilo retoma por dominio
(`dia-d`/`assistant`/`lab`…) siguiendo el protocolo que incluye el check de falsos positivos EOL (paso 4).

## 6. Documentos fuente de verdad / índices

- `docs/engineering/dev-continuation-plan-2026-08-09.md` (M0/§6.2 nota de higiene; registro §7.6.i pendiente).
- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/traspaso-m5-frontend-2026-08-10.md` (§7 nota de cierre M5).
- `.gitattributes` · `.prettierrc` (vacío = defaults).
