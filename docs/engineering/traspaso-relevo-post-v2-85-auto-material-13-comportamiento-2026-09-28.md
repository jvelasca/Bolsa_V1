# Traspaso / relevo — tras `AUTO-MATERIAL-13`: AUDITORÍA DE COMPORTAMIENTO y `OBS-10`

> **[SUPERSEDED — NO ES EL RELEVO VIGENTE]** Marca de fecha: 2026-09-28. Este documento es la entrega
> **docs-only** **previa** a la ejecución de la fase. El relevo vigente es
> [`traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md`](./traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md),
> que **sí ejecuta** la fase (cierra `OBS-10` con **código + test + `M233`**), mergea a `main` y sella
> `v2.85-beta` (más su re-sello docs-only `v2.85.1-beta`). Se conserva por **trazabilidad histórica** y
> **no** se borra. A continuación el texto **original, verbatim**: el `HEAD` `d7a4924d`, el freeze
> `980c7b6e…`/`ffe36fd2…` y la etiqueta «SIN bump y SIN tag» eran ciertos **al autorar este documento** y
> **ya no** describen `main` (ver [`PROJECT_STATE.md`](./PROJECT_STATE.md)). **No leas este documento como
> el estado vigente.**

> **AsOf:** 2026-09-28 · **Etiqueta de entrega:** **SIN bump y SIN tag** (docs-only) · **Base:**
> `v2.84-beta` (`2.09.0-beta`, tag `e6d921a8` → commit `fd3859e3`) · **HEAD de `main`:** `d7a4924d`
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze intacto:** `apps` =
> `980c7b6e782296dda50be99385a2350b2cb4b83e`, `packages` = `ffe36fd2fbcf3c12ea26b7523c334f6399a6b716`.
> **Lectura:** fase **DOCS-ONLY**. Convierte la auditoría de instrumentación/CI en **auditoría de
> COMPORTAMIENTO**, registra `OBS-10` y **no toca una línea** de `packages/` ni `apps/` (la ventana
> PAPER en curso no puede ver moverse el árbol de código).

## Qué quedó hecho

1. **Protocolo de auditoría de COMPORTAMIENTO** (nuevo)
   [`protocolo-auditoria-comportamiento-auto-2026-09-28.md`](./protocolo-auditoria-comportamiento-auto-2026-09-28.md):
   los **10** escalones del funnel con su `source` declarado, la **tabla de patrones de atasco** (el
   escalón donde el caudal pasa a `0` **es** el diagnóstico), qué responde cada bloque de `window_audit`
   (`totals` / `funnel` / `rates` / `gate` / `warnings`), las **reglas de lectura** (`n/d` nunca es `0`;
   todo TOTAL con su `coverage.partial`; `unresolvedRate` es tasa de **días**, no de propuestas), los
   comandos PowerShell y el **veredicto honesto** `READY` / `INCONCLUSIVE` / `NO MEDIDO`.
2. **`OBS-10` (LOW) registrada y APLAZADA** en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md):
   `stateCounts` de `window_totals` recorre **`rows`** mientras `counts`/`coverage`/`rSum`/`funnel` usan
   **`measured_rows`**. **Semántica decidida:** `stateCounts` sobre **`measured_rows`**. **Matiz medido
   propio** (no lo tenía el auditor): su escenario (`measured=False` **y** `state="unresolved"`) **no es
   alcanzable por los productores** (`operability_state` es fail-closed ⇒ `unknown`; `build_window_row`
   pasa `"measured": day_measured`), así que hoy solo se contamina el bucket `unknown`; **pero**
   `window_totals` es **pura sobre filas arbitrarias** (el CLI consume JSON/JSONL) ⇒ el endurecimiento
   **es válido**.
3. **Cita del CI de `v2.84` cerrada formalmente**: punto 12 del
   [arranque del auditor](./arranque-auditor-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md)
   reescrito (en `v2.84` el tag **no** lleva la cita de su propio CI; lleva un placeholder declarado) y
   [audit-pack](./audit-pack-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md) §5 con la
   cita acreditada POST-TAG `1f2638aa`/`434f058d` (`Release tag CI` `36353503867` **SUCCESS**, `python`
   `3022/37`, `quality` `3011/40`) y el límite del placeholder.
4. **Plan de la fase de código** [`plan-v2-85-…`](./plan-v2-85-auto-material-13-statecounts-y-auditoria-comportamiento-2026-09-28.md):
   fix de `OBS-10` + test + **`M233`** (matriz **232 → 233**), etiqueta de `unresolvedRate` (**sin
   renombrar la clave**) y **endurecimiento** de `ops_seed_window_pair.py`.
5. **Registro**: `PROJECT_STATE.md` (AsOf 2026-09-28) y `engineering-index-2026-08-03.md` (entrada **174**).
6. **Declaración de la SUSPENSIÓN de D1**: el registro de la ventana
   [`arranque-ventana-paper-operativa-2026-09-27.md`](./arranque-ventana-paper-operativa-2026-09-27.md)
   §4.bis declara que el equipo **se suspendió** ≈6 h 58 min durante D1 (salto del tick 20 al tick 30) y
   corrige la predicción de fin.

## El hallazgo, en una línea

La auditoría de `v2.84-beta` propone **4 acciones** y **3 ya estaban hechas** (el auditor trabajó sobre el
**tag aislado** y no podía verlas): la **evidencia CI** (cerrada POST-TAG), la **cuenta PAPER fija**
(`.env` ya la fija) y la **ventana real** (**en curso**). La única **real** era `stateCounts` = **`OBS-10`**,
y su corrección **no se hace ahora** porque una ventana PAPER viva prohíbe mover `packages/`.

## Estado de la deuda

| Deuda | Estado |
|---|---|
| `OBS-10` (LOW, `stateCounts`) | 🟡 **ABIERTA y APLAZADA** a `v2.85` — semántica **decidida** (`measured_rows`) |
| `P3-2` / `P3-3` | 🔴 **ABIERTAS** — exigen ventana PAPER ≥4 días **real** |
| `H-4` (LOW) | 🟡 ABIERTO — visible vía `warnings: reason_contract` |
| `OBS-9` (doc-only, frase `1 = uso incorrecto` replicada en CLIs) | 🟡 ABIERTA y declarada |
| `P3-5`, `OBS-5` | 🟡 declaradas |
| `OBS-6` / `OBS-7` / `OBS-8` | 🟢 CERRADAS en `v2.84` |

**Ninguna deuda se cierra por documentación.** Primero datos, después evidencia.

## La ventana D1..D4 (lo pendiente, es OPERACIÓN en tiempo real)

**(a) D1 — EN CURSO, y con incidente declarado.**

| Dato | Valor |
|---|---|
| PID del forward | `34492` (proceso `uv`, lanzado **2026-09-28 00:02:32** local) |
| Comando | `v2_76_forward_market_material.py --account-id 1484e253d2d54645945a6b1d7 --version-a v283-window-a --interval-seconds 60 --max-ticks 400 --stop-when-ready --level evidence --json --out operability_runs/forward-market-20260928.json` |
| Log | `logs/dev/forward-d1.out.log` (a las 05:41:23 iba por `ticks=40`, `prices=20/20`, `cycles=0/0`, `verdict=BLOCKED`) |
| Freeze | **intacto** (`980c7b6e…` / `ffe36fd2…`) |
| Salida | `operability_runs/forward-market-20260928.json` (**se escribe al terminar**, no antes) |

> **La máquina se suspendió durante D1** (≈6 h 58 min entre el tick 20 y el tick 30). A ~60 s/tick le
> restan ~**360** ticks ⇒ **fin ≈11:40 local** (estimación, puede moverse). **No** se reinicia D1 por esto:
> la suspensión **no** cambia el árbol de código ni fabrica ni pierde material. **Recomendación:**
> mantener el equipo **sin suspensión** durante D1..D4 (o declarar cada salto).
>
> **Lectura honesta de D1:** sirve precio de los **20** símbolos y **no** acumula ciclos
> (`cycles=0/0`, `verdict=BLOCKED`) porque el eje sigue en **`BEAR_TREND`** y el motor **veta** las
> entradas LONG. Es el **veto legítimo de régimen**, **no** un fallo de AUTO: `signals=0`/`fills=0`
> **no** se maquilla ni se fuerza.

**(b) D2, D3, D4 — pendientes.** Con **cuenta y versión FIJAS** en los cuatro días (advertencia del
auditor: sin cuenta fija la muestra se rompe): `--account-id 1484e253d2d54645945a6b1d7` y
`--version-a v283-window-a`. Chequeo de freeze **cada día**.

**(c) Cierre de la ventana** (después de D4, o de D1 si se decide cerrar con 1 día):

```powershell
$ACCOUNT   = "1484e253d2d54645945a6b1d7"
$VERSION_A = "v283-window-a"
$env:BROKER_VENUE = "paper"

uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render `
    --forward 'operability_runs/forward-market-*.json' `
    --out "operability_runs/operability-window.json" `
    --html "operability_runs/operability-window.html"

uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py `
    --window "operability_runs/operability-window.json" `
    --forward 'operability_runs/forward-market-*.json' --render `
    --out "operability_runs/operability-audit.json"

# Gate (NO debe bajar umbrales):
uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py `
    --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --level evidence
```

> **Glob:** `operability_runs/forward-market-*.json` **excluye** los fixtures del repo
> (`forward-20260926.json`, `…-operated-fixture.json`, `…-truncado.json`). No mezclarlos con el material
> real.

## Lo que hereda el siguiente (dos caminos, en ESTE orden)

### Fase B — OPERACIÓN (bloqueante real; no es código, no se puede fabricar)

1. **Esperar/cerrar D1** (PID `34492`; fin ≈11:40) y correr el **cierre** de arriba.
2. **D2, D3, D4** por el [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md) §3.1: preflight →
   forward → ventana → auditoría. **Cuenta y versión fijas** los cuatro días.
3. **Freeze cada día:** `git rev-parse "HEAD:apps" "HEAD:packages"` debe seguir en `980c7b6e…` /
   `ffe36fd2…`. Si se mueve, **declararlo** y decidir si se reinicia el día (como ya ocurrió una vez en D1).
4. **Auditoría de comportamiento** con el [protocolo](./protocolo-auditoria-comportamiento-auto-2026-09-28.md):
   localizar el escalón del atasco y emitir el veredicto honesto. **Nada se cierra con 1 día degenerado.**

### Fase C — CÓDIGO `v2.85` / `AUTO-MATERIAL-13` (**solo DESPUÉS** de cerrar la ventana)

> **Decisión de sellado (2026-09-28, propietario): `v2.85-beta` es la SIGUIENTE auditoría externa y NO
> hay re-sello intermedio.** Se descarta `v2.84.1-beta` (un re-sello docs-only tendría **código cero
> nuevo**: el mismo instrumento que el auditor ya aprobó). El sello `v2.85-beta` debe ser **autocontenido**
> (cita del CI + rango en el commit de sello, patrón `OBS-3`/`OBS-4`) e incorporar los docs acumulados en
> `main` (protocolo, `OBS-10`, correcciones **H-1**/**H-2**), para que su auditor **no** reencuentre H-1/H-2.

5. **`OBS-10`**: `stateCounts` sobre `measured_rows`; test
   `test_window_totals_state_counts_ignores_unmeasured_rows`; mutación **`M233`** (matriz **232 → 233**).
6. **Etiqueta de `unresolvedRate`**: aclarar render/docstring (**sin** renombrar la clave).
7. **Endurecer `ops_seed_window_pair.py`**: exigir `--account-id` (o un `--allow-create` explícito) para
   que **no** pueda acuñar una cuenta nueva en silencio.
8. **Compuertas completas + re-sellado** (**bump** `2.09.0-beta → 2.10.0-beta`, tag **`v2.85-beta`**) y
   **auditoría de comportamiento sobre el material real**.

> **Restricción dura que ordena todo:** `v2.85` **toca `packages/`** ⇒ **jamás** con la ventana viva.
> Primero se cierra la ventana, después se mueve el árbol de código.

## Reglas duras que siguen vigentes

- **No** se toca el motor (`auto_simulation_worker.py`), el gobernador (`aggregate_trial_regime`),
  `operability_window.py`, `v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI ni
  migraciones (`046_fill_reference_mid`).
- **No** se cierra deuda por documentación: `P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5`/`OBS-10` **ABIERTAS**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **Forward, no replay:** no se inyecta ni se backdatea `created_at`.
- **No** se añade ninguna capa nueva de observabilidad (es lo que pide el auditor).
- El **capturador y el auditor son read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana
  está degenerada.

## Comandos de verificación rápida

```powershell
git log -1 --oneline                                  # d7a4924d
git rev-parse "HEAD:apps" "HEAD:packages"             # 980c7b6e… / ffe36fd2…  (ventana intacta)
Get-Content logs/dev/forward-d1.out.log -Tail 4       # progreso de D1
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 18 passed (19 en v2.85)
```

## Ficheros de la fase

- [Protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md) ·
  [Plan `v2.85`](./plan-v2-85-auto-material-13-statecounts-y-auditoria-comportamiento-2026-09-28.md)
- [Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) (`OBS-10`) ·
  [Audit-pack `v2.84`](./audit-pack-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md) ·
  [Arranque del auditor `v2.84`](./arranque-auditor-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md)
- Registro de la ventana: [arranque operativo PAPER](./arranque-ventana-paper-operativa-2026-09-27.md) ·
  [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md)
- Auditoría externa de la base: [auditoría `v2.84`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md)
  (`APROBADO`, 0 bloqueantes; H-1/H-2 LOW documentales, corregidos/registrados)
- Contexto previo: [relevo `v2.84`](./traspaso-relevo-post-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md)
