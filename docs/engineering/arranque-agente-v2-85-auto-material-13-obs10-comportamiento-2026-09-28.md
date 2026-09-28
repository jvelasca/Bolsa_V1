# Arranque del agente siguiente — post `v2.85` / `AUTO-MATERIAL-13` (rama `OBS-10`)

> **Punto de entrada** para el siguiente chat/agente. **AsOf:** 2026-09-28 · **Estado:** rama
> **`feat/v2.85-obs10-comportamiento`** con **código + docs + bump**; **NO** mergeada a `main`;
> `OBS-10` **cerrada en la rama**; `OBS-11` **abierta**; tag `v2.85-beta` **PENDIENTE**.
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 1. Qué acaba de pasar

Fase de **código** (worktree aislado sobre `63696d0c`, **`main` intacto**) que cierra `OBS-10` y endurece
un anexo de operación. **No** se tocó el motor congelado, el gobernador, `operability_window.py`,
`v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B ni la UI.

- `stateCounts` de `window_totals` **ahora itera `measured_rows`** (coherente con `counts`/`coverage`/`rSum`/`funnel`).
- `unresolvedRate` queda **etiquetado** como indicador (sin renombrar la clave, sin mover la aritmética).
- `ops_seed_window_pair.py` **ya no acuña** una cuenta nueva en silencio (nuevo `--allow-create`).
- **`OBS-11` (LOW)** nueva: la aritmética de `unresolvedRate` es indicador, no proporción — registrada.

Detalle en el [relevo](./traspaso-relevo-post-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md) y
el [audit-pack](./audit-pack-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md).

## 2. Estado de la deuda

| Deuda | Estado |
|---|---|
| `OBS-10` (LOW, `stateCounts`) | CERRADA **en la rama** (código + test + `M233`); pendiente de merge a `main` |
| `OBS-11` (LOW, aritmética de `unresolvedRate`) | ABIERTA y declarada |
| `P3-2` / `P3-3` | ABIERTAS — exigen ventana PAPER ≥4 días **real** |
| `H-4` (LOW) | ABIERTO — visible vía `warnings: reason_contract` |
| `OBS-9`, `P3-5`, `OBS-5` | declaradas |
| `OBS-6` / `OBS-7` / `OBS-8` | CERRADAS en `v2.84` |

**Ninguna deuda se cierra por documentación.** Primero el dato, después la evidencia.

## 3. Camino natural (en este orden)

1. **OPERACIÓN (bloqueante real, no se puede fabricar):** completar la **ventana PAPER D1..D4** por el
   [runbook](./runbook-ventana-forward-v2.78-2026-09-27.md) §3.1 (preflight → forward → ventana →
   auditoría) y por el [protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md).
   **Cuenta y versión fijas** los cuatro días (`--account-id 1484e253d2d54645945a6b1d7`, `--version-a
   v283-window-a`). **Docker Desktop debe permanecer arriba todo el tiempo** (ver §5).
   > **ANTES DE INVERTIR 4 DÍAS, LEE ESTO:** la cuenta de la ventana tiene **0 fills, 0 reservas y 0
   > entradas de journal** en los últimos 5 días, y el capturador construye los días **sólo** con material
   > durable (`v2_80_market_window.py:210`); el `--forward` **no crea días**, sólo los enriquece. Con el
   > eje en `BEAR_TREND` la ventana **está vacía y no acumulará nada**: hoy `v2_80` sale con **exit 2**
   > (`# BLOQUEADO: no hay ningún día de operabilidad que leer en la ventana`). Correr D2..D4 **no cambia
   > el veredicto**: `NO MEDIDO` por veto legítimo de régimen. **No** se fuerza nada; ver el relevo §(d).
2. **Merge a `main`** de esta rama **cuando la ventana cierre** (hoy `main` no puede moverse).
3. **Sello `v2.85-beta`** en `main` (tag anotado + cita del CI **POST-TAG**, autocontenida patrón
   `OBS-3`/`OBS-4`). **No** hay re-sello intermedio.
4. Después: `AUTO-22`/`AUTO-23` y cierre de `P3-2`/`P3-3` con el material real; `H-4` **sólo** si
   `otherCount > 0`; `OBS-11` cuando se decida la semántica de la clave.

## 4. Reglas duras

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales `32/3/8/4/2` intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia.

## 5. Recordatorios operativos de esta fase

- El forward D1 se lanzó **detached** (`Start-Process -PassThru`) y su PID quedó en `logs/dev/forward-d1.pid`.
- **Docker Desktop debe seguir arriba**: si se para, PostgreSQL (`bolsa-postgres`) queda inalcanzable y el
  forward muere con `psycopg.errors.ConnectionTimeout` (eso mató a D1 al inicio de esta fase).
- Preflight read-only **exit 2** (agregado `BEAR_TREND`, LONG vetadas por `regime_invalid`): **declarado,
  no forzado** ⇒ D1 acumulará `cycles=0/0` y el veredicto honesto esperado es `INCONCLUSIVE`/`NO MEDIDO`.
- **La ventana está VACÍA** (medido, no deducido): `0` fills / `0` reservas / `0` entradas de journal para
  `1484e253d2d54645945a6b1d7` en los últimos 5 días ⇒ `v2_80` sale con **exit 2**. El `--forward` **no**
  crea días. Detalle y consecuencias en el relevo §(d).

## 6. Comandos de verificación rápida

```powershell
pytest packages/py/application/tests/test_operability_audit.py -q          # 19 passed
python apps/api-python/scripts/v2_44_mutation_audit.py M233               # muerde
git rev-parse "HEAD:apps" "HEAD:packages"                                  # 980c7b6e… / ffe36fd2… (freeze de main)
Select-String -Path package.json -Pattern version                          # 2.10.0-beta
```
