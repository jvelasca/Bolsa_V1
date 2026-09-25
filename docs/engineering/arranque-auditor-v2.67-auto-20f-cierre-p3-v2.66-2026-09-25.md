# Arranque del auditor — `v2.67-beta` (`AUTO-20F`)

> **AsOf:** 2026-09-25 · **Tag a auditar:** `v2.67-beta` (`1.92.0-beta`) · **Tag base:** `v2.66-beta` = `6fe7faa8`
> **Naturaleza:** fase corta de **precisión** (cierra las 2 P3 de la auditoría de `v2.66`). Sin producto nuevo.

## Encargo

Verificar, **contra el código sellado**, que las dos P3 quedan cerradas y que la fase **no** ha movido nada que
no debía (freeze, reparto, migración, esquema del artefacto). No creer el audit-pack: medirlo.

## Objeto de auditoría

- Repo: `c:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1`
- Diff: `git diff v2.66-beta v2.67-beta`
- Docs de fase: `plan`/`audit-pack`/`relevo`/este arranque (sufijo `v2-67-auto-20f-cierre-p3-v2.66-2026-09-25`).
- Deuda origen: `docs/engineering/deuda-p3-post-auditoria-v2.66-2026-09-25.md`.

## Tesis a verificar

1. **P3-1 corregida**: ¿los documentos de `v2.66` (`plan`/`audit-pack`) ya **no** atribuyen a M180 el contrato
   TS-vs-Python? ¿Se distingue claramente lo que cubre M180 (render Python) de lo que cubre vitest?
2. **M180 no cubre el contrato**: la salida de la matriz debe mostrar que M180 enrojece **tests Python**.
3. **P3-2 Python**: un valor no-lista ⇒ `NO MEDIDO` (no se itera la cadena). Comprobar por código, no por
   comentario; **M181** debe morder.
4. **P3-2 TS (espejo)**: mismo criterio en `listLabel`/`isMeasuredList`; comprobar que `buildEvidenceView` no
   revienta ni itera un escalar.
5. **Sin regresión**: el render de artefactos reales (listas siempre presentes) es **idéntico** a `v2.66`.
6. **Freeze y reparto intactos**; **sin migración** (head `046_fill_reference_mid`).
7. **Mutaciones**: M179/M180/M181 muerden; matriz completa sin «sin fragmento».

## Sondas sugeridas

- Leer `_version_list` (Python) y `listLabel`/`isMeasuredList` (TS): ¿el criterio es idéntico para `None`,
  `[]`, escalar y dict?
- `git diff --stat v2.66-beta v2.67-beta`: ¿la superficie es la declarada?
- `git diff v2.66-beta v2.67-beta -- packages/py/applications ...` para los ficheros congelados → **vacío**.
- Re-ejecutar la matriz (`M179 M180 M181`) y, opcionalmente, la completa.

## Compuertas a re-ejecutar

| Compuerta | Comando |
|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` (esperado **1324 passed**) |
| Frontend typecheck/lint | `pnpm --filter @bolsa/web typecheck` · `... lint` (0 errores) |
| Frontend build/contrato | `pnpm --filter @bolsa/web build` · `... contract:check` |
| Python analytics | `uv run pytest packages/py/analytics -q` (esperado **1209 passed**) |
| Ruff / import-linter | `uv run ruff check packages/py apps/api-python` · `uv run lint-imports --config packages/py/.importlinter` |
| Mutaciones | `.../v2_44_mutation_audit.py M179 M180 M181` |

## Límites declarados (NO reportar como fallo)

- **P3-1 es documental**: su verificación es la lectura de los documentos; no hay compuerta ejecutable. Además,
  el tag `v2.66` es inmutable: sus documentos conservan el texto original y la corrección vive en `main`.
- **P3-2 en TS** es **vitest** (no la matriz pytest); el espejo Python **sí** entra (**M181**).
- La **corrida PAPER real** no se ejecuta (bloqueo por material); `AUTO-21` fuera de alcance.

## Reglas

- **READ-ONLY ESTRICTO**: sin editar, sin commit, sin push, sin tags. Si editas algo para una sonda,
  RESTÁURALO y deja el árbol limpio.
- Distinguir **bloqueantes** de **P3**; cada hallazgo con `fichero:línea`.

## Formato de respuesta

1. **Veredicto** (`APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`).
2. **Tabla**: una fila por tesis (1-7), con veredicto y evidencia.
3. **Hallazgos** (bloqueantes y P3) con `fichero:línea`.
4. **Compuertas re-medidas** (comando → resultado).
5. **Confirmación de freeze, reparto y migración**.
6. **Lo que no pudiste verificar** y por qué.
