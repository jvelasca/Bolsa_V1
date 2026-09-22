# Plan `AUTO-10` — Journal durable por ciclo (`cycleId` + `marketRegime`) — `V2.51` / `1.76.0-beta`

**Estado:** abierto (pasos 1–6 pendientes) · **Fecha:** 2026-09-22 · **Fase anterior:** `V2.50` / `AUTO-9`
(sellada: tag `v2.50-beta` → `e724f19d`, `Release tag CI` `35726585605` **GREEN**).

**Decisiones ratificadas por el usuario (2026-09-22):**

1. **Rótulo** `AUTO-10` / `V2.51` / `1.76.0-beta`.
2. **Punto de escritura:** en la **APERTURA** del ciclo (el régimen que importa para
   `strategy × regime` es el de la decisión, y es el mismo instante en el que ya se crea la reserva de
   entrada: mismo punto, misma transacción lógica).
3. **Sin migración:** `decision_id` **determinista** derivado del `cycle_id` + **dedupe en LECTURA**
   (última gana). Coherente con la promesa de `AUTO-9` de no añadir esquema.

---

## 0. El hueco exacto que cierra esta fase

`AUTO-9` dejó el régimen por ciclo **declarado** (`CycleRisk.regime = None` + nota `regime_not_durable`) y
no inventado: por eso `netExpectancyR` sigue **no medido en producción**. La causa, medida con el código
delante, no es un dato que falte en el esquema: es una **escritura que no existe**.

| Pieza | Ancla | Estado hoy |
| --- | --- | --- |
| Tabla durable del spine | `decision_journal_entries` (ADR-029 F1, `010_decision_journal_entries`) | existe, con índices `account_created`, `decision_id`, `session_id` |
| API de escritura | `SqlAlchemyJournalRepository.append()` (`journal_repository.py:45`: `session.add` + `flush`, **sin** commit) | existe, pero **solo** la usa `api/dependencies.py:517` |
| Régimen por turno | `auto_simulation_worker.py:1299` `_v2_regime()` (override `:1305`, `regime_source` `:1311`) | existe y **ya se usa** en la decisión (`:1584`) |
| Identidad de ciclo | `_v2_cycle_for()` `:2048` (posición abierta → si no, plan del tick) | existe |
| Escritura del régimen | `self._v2_journal.append(entry)` (`:2803`, `:3490`) | **en memoria**: lista del proceso, se pierde al reiniciar |
| Relación `cycleId` ↔ `decision_id` | `auto_v2_entry.py:1744-1768`: mismo `key` ⇒ `dec-<sha256(key)[:12]>` / `cyc-<sha256(key)[:12]>` | **determinista por intercambio de prefijo** |

Mediciones de la sonda de coste (`apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py`, paso 1 de
`AUTO-9`): leer por `decision_id` **derivado** cae en el índice (barato); leer por `payload` obliga a scan
secuencial del JSONB (caro). Y un aviso que esta fase debe respetar: **la forma `cyc-<12 hex>` no prueba
procedencia** (el fallback `uuid4` tiene la misma forma), así que la lectura **confirma** el `cycleId` en
el payload antes de creerse el régimen.

## 1. Invariante que instala `AUTO-10`

> **El régimen por ciclo, o es durable, o se declara.** Ningún consumidor inventa `UNKNOWN`: o lee un
> régimen escrito en el journal durable y confirmado por payload, o el hueco sigue declarado
> (`regime_not_durable`). Es la extensión natural del invariante de `AUTO-9` (*medir o declarar, nunca
> inventar*) al lado de la **escritura**.

## 2. Diseño (lo ratificado, con su porqué)

1. **`decision_id` por intercambio de prefijo.** `cycle_id` es `cyc-<x>`; el `decision_id` que le
   corresponde es `dec-<x>` **con la misma `<x>`**. Vale para los dos casos porque ambas piezas se acuñan
   del mismo `key` (`sha256` cuando hay señal, `uuid4` cuando no). Si el `cycle_id` **no** empieza por
   `cyc-`, no se deriva nada: se escribe con `decision_id` propio y se **declara** que la lectura por
   índice no lo alcanza.
2. **Sin migración.** No se añade índice único ni columna: el dump de la entrada lleva `cycleId` y
   `marketRegime` en el `payload` (JSONB ya existente). Los duplicados de reintento se resuelven en
   **lectura** (última gana, ordenado por `created_at`), y se **declaran** (nota medida), no se silencian.
3. **Escritura en la apertura, fail-closed declarado.** La entrada se emite donde nace el ciclo
   (`_v2_track_entry`, `:3537`) / se crea la reserva de entrada (`:3826`). Si el sink durable falta o
   falla, **el turno no se tumba** (mismo patrón que `_journal_position_event`, `:3501`) pero el fallo
   **no** se convierte en éxito: queda declarado para que el hueco no mienta.
4. **Seam inyectable, no acoplamiento.** El worker recibe un escritor de journal por constructor,
   exactamente como `reservation_store` (`:574`) y `regime_source` (`:562`): inyectable en tests, `None`
   en el camino hermético. El runner con `session_factory` (`:4548`) es quien lo construye.

## 3. Pasos, con su gate

| # | Paso | Gate |
| --- | --- | --- |
| 1 | **Constructor puro** `build_auto_cycle_regime_entry(...)`: deriva `decision_id` por prefijo, arma `payload` con `cycleId` + `marketRegime` + `strategyVersion`, y devuelve `None` (no-op declarado) si falta `cycle_id` | tests de borde: sin `cycle_id` ⇒ `None`; `cycle_id` sin prefijo `cyc-` ⇒ `decision_id` propio y declarado; régimen `None` ⇒ `UNKNOWN` **declarado**, nunca inventado; `payload` estable (golden) |
| 2 | **Puerto de escritura en el worker** en la **apertura** + inyección del seam | test de seam: con sink ⇒ una entrada por ciclo; sin sink ⇒ turno intacto y hueco declarado; sink que revienta ⇒ turno intacto, fallo declarado |
| 3 | **Lector**: el productor de `AUTO-9` (`cycle_risk`) recibe `regime_by_cycle` desde el journal durable (por `decision_id` derivado **y** confirmación de `payload['cycleId']`) y el hueco pasa de `regime_not_durable` a `COMPLETE` | sonda de coste con números antes/después (`a9_cycle_regime_read_cost_probe.py`); test de que sin confirmación de payload **no** se cierra el hueco |
| 4 | **Dedupe en lectura** (última gana) + nota declarada por duplicados | test con dos entradas del mismo ciclo: gana la más nueva; la nota dice cuántas |
| 5 | **Mutaciones** `M34–M39` sobre constructor, puerto y lector (`v2_44_mutation_audit.py`) | todas **muerden** con el árbol intacto |
| 6 | **Verificación y sello**: `ruff` + `mypy` + `import-linter` + suites (delta **simétrico**), docs (`PROJECT_STATE`, `CHANGELOG`, índice, pack, relevo), bump `1.76.0-beta`, tag `v2.51-beta` | árbol limpio y CI verde |

## 4. Límites declarados de `AUTO-10` (no silenciosos)

- **Solo ciclos del worker `AUTO`**: ciclos históricos ya cerrados sin entrada durable siguen declarando
  su hueco; `AUTO-10` **no** reescribe el pasado.
- **`netExpectancyR` sigue necesitando su propia cadena**: que el régimen sea durable cierra el eje
  `strategy × regime`, pero la expectativa neta en R depende además de que existan ciclos medidos con
  coste; `AUTO-10` no promete que el número aparezca, promete que el **insumo** deja de faltar.
- **La UI sigue sin exponer `AUTO-7`/`AUTO-8`/`AUTO-9`** (deuda ya declarada en `V2.50`); esta fase no
  la toca.
- **`governor.json` sigue sin trackear**: se mantiene tal cual.

## 5. Freeze / no tocar

- **No** se reabre el sello de `V2.50` (tag `v2.50-beta` quieto en `e724f19d`).
- **No** se toca `prettier` para `*.md` (decisión del tramo de tooling: `*.md` fuera de `prettier` +
  `tools/fix_md_spacing.py` como reparador determinista).
- **No** se cambia el contrato de `expectancy_r` / `net_expectancy_r` ni la política `auto9-v1`: si el
  contrato de evidencia cambia, sube `adaptivePolicyVersion` (sería `auto10-v1`) y eso es una decisión
  aparte, no un efecto colateral.
