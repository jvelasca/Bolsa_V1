# Arranque del auditor — `v2.69-beta` (`AUTO-22`)

> **AsOf:** 2026-09-25 · **Tag a auditar:** `v2.69-beta` (`1.94.0-beta`) · **Tag base:** `v2.68-beta`
> **Naturaleza:** fase de **instrumentación de la corrida** (runner end-to-end reproducible + UI de
> evidencia en 3 niveles), no de decisión. Sin migración.

## Encargo

Verificar, **contra el código sellado**, que:

1. El RUN de evidencia es **un comando reproducible** que guarda un **bundle con huella**.
2. O se ejecuta **completo** o se declara **BLOQUEADO** (`exit 2`) — **nunca** un bundle parcial, un
   recálculo manual ni un número copiado.
3. La UI publica los **tres niveles** exigidos (Material / Estadística / Contexto) y respeta la regla
   visual: **`null` ⇒ `NO MEDIDO`/`INCONCLUSIVE`, jamás `0`**.
4. La fase **no** mueve nada que no debía (freeze, reparto, migración, esquema del artefacto).

No creer el audit-pack: medirlo. En particular, **intentar** producir un bundle parcial o un número
copiado y comprobar que el sistema lo bloquea.

## Objeto de auditoría

- Repo: `c:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1`
- Diff: `git diff v2.68-beta v2.69-beta`
- Docs de fase: `plan`/`audit-pack`/`relevo`/este arranque (sufijo
  `v2-69-auto-22-real-paper-run-2026-09-25`).

## Tesis a verificar

1. **Lector único.** ¿`read_paper_material` es la **única** implementación de la lectura PG y
   `paper_cycles_export.py` es un **envoltorio** que la importa (no una copia)? ¿Comparte el paginador
   (`paper_cycles_export._read_all_reservations is read_paper_material`'s default)? Una segunda ruta
   divergente del denominador de R sería el defecto que `AUTO-20` cerró.
2. **Completitud fail-closed.** ¿Una lectura de reservas que no completa (página llena sin ids nuevos)
   **bloquea** (`MaterialIncompleteError` → `exit 2`) en vez de devolver material sesgado? ¿La venue ≠
   `paper` bloquea (`NonPaperVenueError`)?
3. **Composición pura y aditiva.** ¿`build_evidence_run_bundle` **compone** los productores auditados
   (`AUTO-19A/19B`, `AUTO-20C`, `AUTO-21`) sin una segunda aritmética? ¿El artefacto conserva el esquema
   `auto20c_evidence_artifact_v1` y las claves aditivas?
4. **Fail-closed del run.** ¿Sin ciclos con R medible lanza `EvidenceRunBlockedError` y el script sale
   `exit 2` **sin escribir ningún fichero** (ni la carpeta de la corrida)? Probar con `--cycles`
   inexistente y con un JSON de ciclos sin `riskAmount`. **M190** debe morder.
5. **Bundle con huella y procedencia.** ¿`run.json` lleva `schema`, `materialOrigin`, `fingerprint`,
   `source`, los args y los **tres niveles**? ¿El artefacto viaja **verbatim** (sin recálculo del
   cliente)? ¿El origen lo declara el material (manifest) y no lo adivina el script? **M188**/**M189**
   deben morder.
6. **Corrida inmutable.** ¿Repetir la misma corrida (misma huella/instante) **bloquea** en vez de
   sobrescribir una medición?
7. **UI en 3 niveles.** ¿`buildEvidenceView` expone `global` (`P(R>0)`, `P(R>0)` OOS, `WFE`), `currentRegime`,
   `regimeEvidence`, `crossStrategy` y `allocation`? ¿`P(R>0)` sale de
   `meanDeclaredProbability` y `P(R>0) OOS` de `aggregate.probabilityPositiveOos` (claves existentes, sin
   cambio de esquema)?
8. **Regla visual dura.** ¿Un par de correlación `null` se muestra `NO MEDIDO` y **nunca** `0.0000`? ¿Un
   veredicto de régimen ausente es `INCONCLUSIVE` (una estrategia sin celda **no** puede fingir
   `SUPPORTED`)? Verificar el mapeo de `edgeConfidence` (`HIGH` ⇒ `SUPPORTED`, `MEDIUM`/`UNKNOWN` ⇒
   `INCONCLUSIVE`, `LOW` ⇒ `NOT_SUPPORTED`).
9. **`ALLOCATION` congelado.** ¿La vista y el render declaran `FROZEN — auto18-v1` y la fase **no**
   conecta nada de la evidencia al reparto? `git diff` de `portfolio_optimizer.py` /
   `portfolio_reservation.py` → **vacío**.
10. **Sin regresión.** Compuertas en verde y matriz completa sin huecos. **Freeze y reparto intactos**;
    **sin migración** (head `046_fill_reference_mid`).

## Sondas sugeridas

- `git diff v2.68-beta v2.69-beta --stat`: ¿la superficie es la declarada?
- Correr el runner en seco con el fixture (`--cycles packages/py/analytics/tests/fixtures/auto_calibration_cycles.json`)
  y comprobar los **cuatro** ficheros del bundle y el `materialOrigin = synthetic_fixture`.
- Correr con `AUTO20B_EXPORT_PG_REQUIRED=1` y material PG sembrado (reutilizar el fixture de
  `test_auto_v63_auto20b_export_e2e_pg.py`): ¿`source = paper_real`, `fingerprint` no vacío?
- **Intento de bundle parcial**: que `--cycles` apunte a un fichero ilegible ⇒ ¿`exit 2` y **cero**
  ficheros escritos, ni la carpeta?
- **Intento de número copiado**: manipular el artefacto del bundle a mano y comprobar que la UI lo
  clasificaría como procedencia desconocida/incoherente (no lo "arregla").
- Sonda del contrato TS: el test de paridad lee el `.py` del instrumento; ¿sigue leyéndolo?
- `git diff v2.68-beta v2.69-beta -- <freeze>` → **vacío**.
- Re-ejecutar la matriz (`M188 M189 M190`) y la completa.

## Compuertas a re-ejecutar

| Compuerta | Comando |
|---|---|
| Frontend test | `pnpm --filter @bolsa/web test` |
| Frontend typecheck/lint | `pnpm --filter @bolsa/web typecheck` · `... lint` |
| Frontend build/contrato | `pnpm --filter @bolsa/web build` · `... contract:check` |
| Python (application + analytics) | `uv run pytest packages/py/application packages/py/analytics -q` |
| Runner (puros + PG) | `uv run pytest apps/api-python/tests/test_auto_v69_auto22_evidence_run.py -q` |
| Ruff / import-linter / mypy | `uv run ruff check packages/py apps/api-python --config pyproject.toml` · `uv run lint-imports --config packages/py/.importlinter` · `uv run mypy … --follow-imports=silent` |
| Mutaciones | `.../v2_44_mutation_audit.py M188 M189 M190` y la completa |

## Límites declarados (NO reportar como fallo)

- **La corrida PAPER real NO se ejecuta** (bloqueo por **material**, decisión del propietario). El RUN
  queda listo y probado; la evidencia de mercado sigue sin existir y la UI mostrará `NO MEDIDO` hasta que
  haya material. **No es un defecto de la fase.**
- El modo `--cycles` es un **fixture declarado** (`synthetic_fixture`): mide el instrumento, no el mercado.
- Las correlaciones y `P(R>0)` siguen siendo **evidencia publicada**: no reparten. Que no muevan el
  reparto es el **objetivo**.
- Deudas **P3-2**/**P3-3** (validación empírica de la correlación por cubos y `P(R>0)` vs muestra) siguen
  **abiertas** por falta del primer dataset real.

## Reglas

- **READ-ONLY ESTRICTO**: sin editar, sin commit, sin push, sin tags. Si editas algo para una sonda,
  RESTÁURALO y deja el árbol limpio (byte a byte).
- Distinguir **bloqueantes** de **P3**; cada hallazgo con `fichero:línea`.

## Formato de respuesta

1. **Veredicto** (`APROBADO` / `APROBADO CON OBSERVACIONES` / `NO APROBADO`).
2. **Tabla**: una fila por tesis (1-10), con veredicto y evidencia.
3. **Hallazgos** (bloqueantes y P3) con `fichero:línea`.
4. **Compuertas re-medidas** (comando → resultado).
5. **Confirmación de freeze, reparto y migración**; y del **BLOQUEO** correcto sin material.
6. **Lo que no pudiste verificar** y por qué.
