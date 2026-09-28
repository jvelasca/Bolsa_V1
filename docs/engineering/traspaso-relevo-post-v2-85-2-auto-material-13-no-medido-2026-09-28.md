# Traspaso / relevo — post `v2.85.2-beta` / `AUTO-MATERIAL-13` (RE-SELLO: cierre D1 + evidencia cruda)

> **AsOf:** 2026-09-28 · **Objeto vivo:** tag **`v2.85.2-beta`** (`2.10.2-beta`, docs-only) ·
> **Base:** `v2.85.1-beta` (`3ce8b85e`) · **Alembic head:** `046_fill_reference_mid` (SIN migración) ·
> **Freeze:** `apps` `ddcf636f39054e29cf9013e0273da2b773c1fd76` / `packages`
> `ba90ccf233bce9bada4e41cf81eb0b69312fd0d1` (sin mover).
> **Punto de entrada del auditor:** [`arranque-auditor-v2-85-2-auto-material-13-no-medido-2026-09-28.md`](./arranque-auditor-v2-85-2-auto-material-13-no-medido-2026-09-28.md).

## 1. Qué se ha hecho (re-sello docs-only)

`v2.85.2-beta` **no** cambia código: el diff contra `v2.85.1-beta` es `package.json` + `docs/engineering/*`
(+ `CHANGELOG.md` + `.prettierignore`). Entrega cuatro cosas, todas nacidas de la **operación real del 2026-09-28**:

1. **Evidencia cruda D1 dentro del tag** — [`evidence/v2.85.2/`](./evidence/v2.85.2/README.md): el `--out`
   del forward `v2_76` (`400 ticks`, `stopReason=completed`), su cronología (`out.log`), su `stderr` y la
   fila de `v2_77` del día, copiados **verbatim** con SHA-256 (los originales, gitignoreados, no se tocaron).
2. **Cierre `NO MEDIDO` documentado** — [`ventana-paper-d1-cierre-no-medido-v2.85.2-2026-09-28.md`](./ventana-paper-d1-cierre-no-medido-v2.85.2-2026-09-28.md):
   el funnel medido, la causa (régimen `BEAR_TREND` ⇒ `regime_invalid`/`top_n_excluded`, 0 fills) y la
   razón por la que `v2_80` no puede leer la ventana (censo **solo** durable).
3. **Por qué tardó ~7h38m** — cronología recomputable: `60 s × 400 ticks = 6h40m` por construcción, el
   `--stop-when-ready` no puede cortar (0 ciclos medibles) y **+58 min** de suspensión del equipo.
4. **`OBS-13` (LOW, instrumento/diagnóstico), nueva y ABIERTA** — `vetoes=8000` (par A+B) frente a
   `vetoCounted=4000` (solo versión A: `regime_invalid:2000` + `top_n_excluded:2000`);
   `contractViolation=false` no la marca (solo mide `other>0`).

## 2. Estado de la ventana PAPER

- **D1..D4: `NO MEDIDO`.** El eje es `BEAR_TREND` ⇒ LONG vetadas. **No** se rebajaron umbrales ni se
  forzaron entradas. `P3-2`/`P3-3` **ABIERTAS**.
- **Bloqueante real medido (para el próximo intento):** las **barras** de `ohlcv_bars` estaban **estancadas
  en `2026-09-26`**; sin barras frescas el eje no sale de `BEAR_TREND`. **Antes de gastar más días hay que
  refrescar el material** (scheduler/EOD), no alargar la cadencia.

## 3. Siguiente paso recomendado (operación, no código)

1. **Arreglar el dato**: verificar que `scheduler_worker`/`auto_sync_worker` refresca `ohlcv_bars` con `DATABASE_URL`
   heredado y que el EOD de Yahoo entra en `data_sync_log`; confirmar barras posteriores a `2026-09-26`.
2. **Preflight** (`v2_76 --preflight-only`): confirmar que el eje deja de ser `BEAR_TREND` (`entriesAllowedLong`).
3. **Solo entonces** lanzar la **ventana ≥4 días** por el runbook, con `--forward` válido, y cerrar con
   `v2_80 --days 4` + `v2_83_window_audit`.
4. **`OBS-13`**: si se quiere censo del **par** completo (no solo A), tocar el seam
   (`_journal_reasons` sobre el journal del **par**, no solo `runtime.worker`). Fuera del alcance docs-only.

## 4. Deuda declarada (NINGUNA cerrada por este re-sello)

`P3-2`/`P3-3` (ventana PAPER real ≥4 días **con material**), `OBS-11` (LOW), `H-4` (LOW), `OBS-9`,
`P3-5`, `OBS-5` y **`OBS-13`** (LOW, nueva) siguen **ABIERTAS**. `OBS-10` **CERRADA** (código + test +
`M233`). `OBS-12` **CERRADA** (defecto documental, en `v2.85.1`). Regla vigente: **ninguna deuda se cierra
por documentación**.

## 5. Punteros

- Auditor: [`arranque-auditor-v2-85-2-…`](./arranque-auditor-v2-85-2-auto-material-13-no-medido-2026-09-28.md).
- Evidencia cruda: [`evidence/v2.85.2/`](./evidence/v2.85.2/README.md).
- Cierre de ventana: [`ventana-paper-d1-cierre-no-medido-v2.85.2-2026-09-28.md`](./ventana-paper-d1-cierre-no-medido-v2.85.2-2026-09-28.md).
- CI: [`evidencia-ci-tag-v2.85.2-2026-09-28.txt`](./evidencia-ci-tag-v2.85.2-2026-09-28.txt).
- Estado / deuda: [`PROJECT_STATE.md`](./PROJECT_STATE.md) · [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
