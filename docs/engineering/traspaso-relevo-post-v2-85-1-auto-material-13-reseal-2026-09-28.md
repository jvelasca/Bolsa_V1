# Traspaso / relevo — post `v2.85.1` / `AUTO-MATERIAL-13`: re-sello docs-only (objeto autocontenido) + `OBS-12`

> **AsOf:** 2026-09-28 · **Etiqueta de entrega:** **bump a `2.10.1-beta`** + tag anotado **`v2.85.1-beta`**
> (**re-sello DOCS-ONLY**; código **byte-idéntico** a `v2.85`) · **Base (diff):** `v2.85-beta`
> (`2.10.0-beta`, commit `481cf168`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) ·
> **Reparto:** `auto18-v1` / `auto15-v1` (`ALLOCATION = none`).
> **Freeze de `main`:** `apps` `ddcf636f39054e29cf9013e0273da2b773c1fd76` / `packages`
> `ba90ccf233bce9bada4e41cf81eb0b69312fd0d1` (**movido por `v2.85`**, no por este re-sello).

## 1. Qué acaba de pasar

1. **`v2.85-beta` se selló** (commits `e69d3b60` feat + `481cf168` docs; tag anotado objeto `0582799b`):
   cierra **`OBS-10`** (`stateCounts` sobre `measured_rows`) con **test** + **`M233`** (matriz 232 → **233**),
   etiqueta **`unresolvedRate`** sin renombrar la clave, registra **`OBS-11`** (LOW) y **endurece**
   `ops_seed_window_pair.py` (`--allow-create`). CI del tag: `Release tag CI` **`36392052899` SUCCESS** en la
   primera pasada (`python` `3023/37` = `3022 + 1`; `quality` `3012/40` = `3011 + 1`; `mypy 507 = 507`).
2. **La ventana PAPER D1..D4 se cerró como `NO MEDIDO`** (decisión del propietario, no una rendición): con el
   eje en `BEAR_TREND` el motor veta LONG por `regime_invalid`, y el censo de días de `v2_80_market_window.py`
   se construye **solo** con material durable ⇒ corriendo D2..D4 no cambiaría nada. Evidencia cruda en
   [`ventana-paper-cierre-no-medido-2026-09-28.md`](./ventana-paper-cierre-no-medido-2026-09-28.md).
   **No** se bajaron umbrales ni se forzaron entradas.
3. **El propietario fue a auditar externamente desde GitHub y apareció un defecto REAL del objeto sellado**
   (no un fallo del código): el tag `v2.85-beta` contenía **dos sets documentales paralelos** de la misma fase
   y `PROJECT_STATE.md` llamaba **«Relevo vivo»** al set **docs-only** — que dice «SIN bump y SIN tag» y cita
   `HEAD` `d7a4924d`. Un auditor que siguiera el punto de entrada aterrizaba en un documento que **negaba la
   existencia del tag**. Se registró como **`OBS-12` (LOW, higiene documental)** y se corrigió.
4. **Este re-sello** (`v2.85.1-beta`) deja el objeto **autocontenido** y **coherente**: la cita del CI de
   `v2.85` viaja **dentro** del tag y la duplicidad queda **declarada** en vez de oculta.

## 2. Qué cambia exactamente (alcance verificable)

`git diff --stat v2.85-beta v2.85.1-beta` debe dar **exactamente** `package.json` (`2.10.0-beta → 2.10.1-beta`)
+ `docs/engineering/*` (+ `CHANGELOG.md`). **Ningún** fichero de `packages/` ni `apps/`; en particular
`git diff v2.85-beta v2.85.1-beta -- packages apps` debe ser **vacío**. Si no lo es, **este re-sello es falso**.

- **NUEVO** [`evidencia-ci-tag-v2.85.1-2026-09-28.txt`](./evidencia-ci-tag-v2.85.1-2026-09-28.txt) — viaja
  **dentro** del tag: acredita el CI de `v2.85` y declara el de este tag (post-tag por construcción).
- **NUEVO** [`arranque-auditor-v2-85-1-auto-material-13-obs10-comportamiento-2026-09-28.md`](./arranque-auditor-v2-85-1-auto-material-13-obs10-comportamiento-2026-09-28.md)
  — punto de entrada del auditor, autocontenido.
- **NUEVO** este relevo.
- **[SUPERSEDED]** en los dos documentos del set docs-only (`…-auto-material-13-comportamiento-…`):
  **conservados**, no borrados; se declara que son **anteriores** a la ejecución.
- `PROJECT_STATE.md`: **«Relevo vivo»** pasa a apuntar al relevo real (`…-obs10-comportamiento-…`), el set
  docs-only queda marcado como **[SUPERSEDED]** y se declara el re-sello y `OBS-12`.
- `audit-pack-v2-85-…-obs10-comportamiento-…`: bloque **«LEER ESTO PRIMERO»** con el re-sello, la duplicidad y
  los puntos donde el texto sellado decía «NO mergeada a `main`» / «Tag PENDIENTE».
- `deuda-p3-post-auditoria-v2.70-2026-09-26.md`: registra **`OBS-12`** y su cierre; **`OBS-11`** sigue abierta.
- `engineering-index` (entrada del re-sello) · `CHANGELOG.md` (`[2.10.1-beta]`) · `package.json`.

**CI del re-sello (POST-TAG):** `Release tag CI` **`36395524355` SUCCESS** en la **primera** pasada (~8m19s;
10 jobs + `certify`; `playwright` integrado `skipped` por diseño); cita escrita en el POST-TAG
**`57631636`**. Job `python` del tag
**`3023 passed / 37 skipped`** y `quality` **`3012 passed / 40 skipped`** = **idénticos a `v2.85`**, como se
predijo **antes** de sellar. En `main` **no** corrieron `Python CI` ni `Fase 2 scientific` (triggers por
rutas: el diff no lleva ficheros Python) — declarado, no un fallo. Cita completa (y el run del objeto
auditado, dentro del tag) en
[`evidencia-ci-tag-v2.85.1-2026-09-28.txt`](./evidencia-ci-tag-v2.85.1-2026-09-28.txt).

## 3. `OBS-12` (LOW, higiene documental) — registrada y CERRADA

**Hallazgo (del propietario, no del CI):** en el objeto sellado `v2.85-beta` coexistían (a) dos sets de
traspaso/arranque para la misma fase, sin declarar cuál regía, y (b) un puntero **«Relevo vivo»** que apuntaba
al set **obsoleto**. Riesgo real: un auditor externo trabajando sobre el tag lee «SIN bump y SIN tag» y
concluye un hallazgo **falso** («no hay tag / los docs se contradicen»).

**Cierre:** cabeceras **[SUPERSEDED]** + puntero corregido + declaración explícita en tres sitios (este relevo,
el `audit-pack` y la evidencia del CI dentro del tag). **Por qué esta deuda sí se cierra con documentación:**
es un defecto **documental**; la regla «ninguna deuda se cierra por documentación» rige para **deuda de
datos** (`P3-2`/`P3-3` exigen ventana PAPER real; `H-4` exige `otherCount > 0`; `OBS-11` exige decidir una
semántica). No se usa como precedente para cerrar ninguna de ellas.

## 4. Lo que hereda el siguiente

1. **Auditoría externa del propietario** sobre el tag **`v2.85.1-beta`** (autocontenido). Punto de entrada:
   [`arranque-auditor-v2-85-1-…`](./arranque-auditor-v2-85-1-auto-material-13-obs10-comportamiento-2026-09-28.md).
   **Es lo que toca ahora.**
2. **`OBS-11` (LOW, ABIERTA):** decidir si `unresolvedRate` debe ser un **indicador** declarado (hoy) o una
   **fracción real**; la clave **no** se renombra sin decisión y ningún número publicado se mueve.
3. **`P3-2`/`P3-3` (ABIERTAS):** exigen una ventana PAPER **real** ≥4 días **con material** (≥2 episodios,
   ≥32 ciclos medibles/estrategia). Antes de invertir días: comprobar que la cuenta tiene material durable
   (`fills`/`reservations`/`decision_journal_entries`) y, muy importante, **Docker Desktop arriba** (un Docker
   parado mató al D1 anterior en silencio).
4. **`AUTO-22`/`AUTO-23`** y, sólo si `otherCount > 0`, `H-4` (LOW, hoy visible vía `warnings: reason_contract`).

## 5. Reglas duras que siguen vigentes

- **No** se toca el motor (`auto_simulation_worker.py`), el gobernador (`aggregate_trial_regime`),
  `operability_window.py`, `v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI ni
  migraciones (`046_fill_reference_mid`).
- **No** se cierra deuda por documentación: `OBS-11`/`P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5` **ABIERTAS**.
- **No** se baja `min cycles` / `min R` / `folds` / `min_episodes` para forzar una corrida.
- **Forward, no replay:** no se inyecta ni se backdatea `created_at`.
- El **capturador y el auditor son read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana
  está degenerada.
- El objeto sellado **no** se reescribe: los defectos se **declaran** (patrón `OBS-3`/`OBS-4`), y se corrigen
  en un **re-sello** nuevo.

## 6. Comandos de verificación rápida

```powershell
git rev-parse v2.85.1-beta^{commit}                    # commit del sello
Select-String -Path package.json -Pattern version      # 2.10.1-beta
git diff --stat v2.85-beta v2.85.1-beta                # SOLO package.json + docs/engineering + CHANGELOG
git diff v2.85-beta v2.85.1-beta -- packages apps      # DEBE estar vacio (si no: re-sello FALSO)
git grep -l "SUPERSEDED" -- docs/engineering           # los 2 docs del set docs-only
pytest packages/py/application/tests/test_operability_audit.py -q   # 19 passed
python apps/api-python/scripts/v2_44_mutation_audit.py # medidas: 233/233
gh run list --branch v2.85.1-beta                      # Release tag CI del re-sello
```
