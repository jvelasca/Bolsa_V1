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
  1. `components/ui` + `components/layout` — **15 ficheros** (todos `.tsx` de producción, ninguno de test); reuso alto,
     poca lógica de negocio. (PRIMER LOTE, en ejecución en este hilo.)
  2. Un feature aislado completo (p. ej. `features/backtests`).
  3. El resto de `apps/web/src` por sub-lotes.
- **Riesgo controlado:** cada lote es pequeño y aislado; si algo falla en batería, se revierte el commit de ese lote
  sin afectar a los demás.

## 4. Protocolo por lote (FASE 3)

1. `git status` limpio.
2. `npx prettier --check` sobre el subconjunto → confirmar recuento de desincronizados (≤ ~30 por lote).
3. `npx prettier --write` sobre SOLO ese subconjunto.
4. Batería reducida : `pnpm --filter @bolsa/web typecheck` · `lint` · `test` · `build` (exit 0).
5. `git diff --stat` para confirmar que es solo formato (sin borrados funcionales ≠ suma de líneas de código).
6. Commit `--no-verify` (por el propio hook lint-staged que ya está formateado) + push.
7. Registrar en `dev-continuation-plan-2026-08-09.md` (§7.6.i) y anclar en `engineering-index`.

## 5. Estado del primer lote (components/ui + components/layout)

Confirmado con `npx prettier --check`:

- **Desincronizados: 15** (listados a continuación), todos `.tsx` de producción.
  `button.tsx` · `card.tsx` · `dialog.tsx` · `expiry-datetime-field.tsx` · `icon-button.tsx` · `info-tip.tsx` ·
  `key-value-list.tsx` · `opaque-menu-panel.tsx` · `app-error-boundary.tsx` · `app-top-bar.tsx` · `chart-tab-bar.tsx` ·
  `dock-zone.tsx` · `panel-resize-handle.tsx` · `platform-shell.tsx` · `trading-layout.tsx`.

## 6. Documentos fuente de verdad / índices

- `docs/engineering/dev-continuation-plan-2026-08-09.md` (M0/§6.2 nota de higiene; registro §7.6.i pendiente).
- `docs/engineering/engineering-index-2026-08-03.md`
- `docs/engineering/traspaso-m5-frontend-2026-08-10.md` (§7 nota de cierre M5).
- `.gitattributes` · `.prettierrc` (vacío = defaults).
