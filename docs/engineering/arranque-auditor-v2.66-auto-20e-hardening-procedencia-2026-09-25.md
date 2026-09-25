# Arranque del auditor — `v2.66-beta` (`AUTO-20E`)

> **AsOf:** 2026-09-25 · **Tag a auditar:** `v2.66-beta` (`1.91.0-beta`) · **Tag base:** `v2.65-beta` = `a077c1c6`
> **Naturaleza:** fase de **endurecimiento** (cierra las 3 P3 de la auditoría de `v2.65`). Sin producto nuevo.

## Encargo

Verificar, **contra el código sellado**, que las tres P3 quedan realmente cerradas y que la fase **no** ha
movido nada que no debía (freeze, reparto, migración, esquema del artefacto). No creer el audit-pack: medirlo.

## Objeto de auditoría

- Repo: `c:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1`
- Diff: `git diff v2.65-beta v2.66-beta`
- Docs de fase: `plan` / `audit-pack` / `relevo` / este arranque (sufijo
  `v2-66-auto-20e-hardening-procedencia-2026-09-25`).
- Deuda origen: `docs/engineering/deuda-p3-post-auditoria-v2.65-2026-09-25.md`.

## Tesis a verificar

1. **P3-1 real.** El test del frontend **lee** `auto_adaptive_calibration.py` (no un literal). Comprobar que
   **cae** si se renombra una clave (reproducir la rotura o fiarse de **M180**).
2. **La compuerta corre.** `frontend-ci.yml` incluye el fichero Python en `paths` de `push` y `pull_request`.
   Sin esto, el «contrato» no se ejecutaría ante un cambio solo de Python.
3. **Render alineado.** El test Python ata `_CALIBRATION_ROWS` a `_CALIBRATION_QUESTIONS`.
4. **P3-2 fail-safe.** Con orígenes raíz↔material **contradictorios**, la clasificación es
   `PROCEDENCIA DESCONOCIDA` (no `PAPER REAL`) y hay aviso. Verificar por código, no por comentario.
5. **P3-3 simétrico.** Ausente ⇒ `NO MEDIDO` (inconcluso) y vacío ⇒ `(ninguna)`, **en TS y en Python**.
6. **El render de artefactos reales no cambia.** Comprobar que la cadena real siempre declara
   `requestedStrategyVersions`/`observedStrategyVersions` ⇒ la salida es idéntica a `v2.65`.
7. **Freeze y reparto intactos.** `git diff v2.65-beta v2.66-beta -- packages/py/application ...` para los
   ficheros congelados debe estar **vacío**; `auto18-v1`/`auto15-v1` sin cambios.
8. **Sin migración.** Alembic head sigue en `046_fill_reference_mid` (no existe `047_*`).
9. **Mutaciones.** `M179` y `M180` muerden; la matriz completa pasa sin «sin fragmento».

## Sondas sugeridas

- `git diff --stat v2.65-beta v2.66-beta` — ¿la superficie es la declarada (frontend + `auto_evidence_report.py`
  + CI + mutaciones + `package.json`/`CHANGELOG`)?
- Leer `classifyEvidenceSource` y `integrityWarnings` y comprobar que **no hay** rama que asigne `paper_real`
  con orígenes contradictorios.
- Comparar `_version_list` (Python) y `listLabel` (TS): ¿mismo criterio exacto?
- Confirmar que `asStringArrayOrNull` preserva `null` y que ningún consumidor asume `[]`.
- Reproducir la rotura del contrato (renombrar una clave) y confirmar el rojo; restaurar.

## Compuertas a re-ejecutar

| Compuerta | Comando |
|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` (esperado **1323 passed**) |
| Frontend typecheck/lint | `pnpm --filter @bolsa/web typecheck` · `... lint` (0 errores) |
| Frontend build/contrato | `pnpm --filter @bolsa/web build` · `... contract:check` |
| Python analytics | `uv run pytest packages/py/analytics -q` (esperado **1208 passed**) |
| Ruff / import-linter | `uv run ruff check packages/py apps/api-python` · `uv run lint-imports --config packages/py/.importlinter` |
| Mutaciones | `uv run python apps/api-python/scripts/v2_44_mutation_audit.py M179 M180` (y matriz completa si procede) |

## Límite declarado (NO reportar como fallo)

- La **corrida PAPER real** no se ejecuta: bloqueo por **material** del PostgreSQL local (`cycle_id` NULL en
  los fills). Es paso operativo del propietario.
- **P3-2** es **TS**; la matriz de mutaciones (pytest) **no** puede morderlo — su cobertura es **vitest**.
  Declarado en el audit-pack §5 para que no se cuente como hueco.

## Reglas

- **READ-ONLY ESTRICTO**: sin editar, sin commit, sin push, sin tags. Solo lectura, tests y sondas.
- Distinguir **bloqueantes** de **P3**; cada hallazgo con `fichero:línea`.
- Si una afirmación del audit-pack no se sostiene, decirlo con la evidencia.

## Formato de respuesta

1. **Veredicto** (`APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`).
2. **Tabla**: una fila por tesis (1-9), con veredicto y evidencia.
3. **Hallazgos** (bloqueantes y P3) con `fichero:línea`.
4. **Compuertas re-medidas** (comando → resultado).
5. **Confirmación de freeze, reparto y migración**.
6. **Lo que no pudiste verificar** y por qué.
