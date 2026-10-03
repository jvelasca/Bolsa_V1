# Auditoría externa — `v2.88.32-beta` (OPS: `window:unlock` deja de poder borrar un lock vivo): `APROBADA`

> **Objeto auditado:** tag anotado **`v2.88.32-beta`** → commit `f87425ae` · **Versión:** `2.11.32-beta` ·
> **Clase:** sello **de operación** sobre el runner de la ventana PAPER `≥4 días` · **AsOf:** 2026-10-03 ·
> **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**) · **Auditor:** externo,
> **directamente sobre GitHub** (`github.com/jvelasca/Bolsa_V1`, repo **público**, clon sin credenciales).
> **Cita POST-TAG:** `main` → `769123df` (`docs(release/v2.88.32)`, cita del CI).
> **Veredicto:** **APROBADA — 0 bloqueantes.** El **único** hallazgo nuevo de `v2.88.31` (el `unlock` podía
> eliminar el `.run.lock` de un run-day **vivo**) está **cerrado por código**, no por documentación; y **no**
> se ha encontrado un defecto equivalente nuevo en el runner.
> **Precisión del veredicto:** `v2.88.32` **corrige y certifica** el **escape hatch administrativo del lock**
> del runner; **NO cierra** la ventana PAPER (`≥4 días` / `≥2 episodios` / `≥32 ciclos` sigue **NO MEDIDA**).
> **Naturaleza de este registro:** **docs-only** — **sin bump, sin tag, sin tocar `src`/tests/`package.json`/
> workflows/migraciones**. Patrón de los informes de auditoría `v2.88.3` / addendum `v2.88.18`-`v2.88.19`.

---

## 0. Resumen ejecutivo

```text
v2.88.30  ausencia de lock diario              🔴
v2.88.31  lock + freeze + provenance           🟢 (3 hallazgos cerrados)
          ↓ hallazgo nuevo de la auditoría de v2.88.31:
          window:unlock podía borrar un lock de un run-day VIVO   🟠
v2.88.32  unlock con ownership + staleness      🟢 (corregido por código)
          → 25/25 tests · CI completo verde · AUTO sin regresión
```

El problema detectado en `v2.88.31` —`window:unlock` podía eliminar el `.run.lock` de un run-day que seguía
vivo— está **realmente corregido**: no es una nota de documentación, es un cambio de implementación con
tests que **muerden**. Y, lo más importante, **no aparece** un defecto equivalente nuevo en el runner.

**Regla de la casa aplicada:** ninguna cifra sin comando; un hueco se declara **`NO MEDIDO`**, jamás un `0`
fingido.

---

## 1. Contexto: qué se auditó y contra qué padre

`v2.88.32-beta` es un sello **OPS-only** sobre el runner de la ventana PAPER. Su padre es
[`evidence/v2.88.31/README.md`](./evidence/v2.88.31/README.md) (lock diario atómico, config de freeze
inmutable y provenance del gate). El delta declarado `v2.88.31-beta → v2.88.32-beta` es de **dos commits**
y toca, de forma deliberadamente encapsulada:

- `scripts/lib/window-forward.mjs` (`unlockDecision`)
- `scripts/lib/window-forward.test.mjs` (+6 tests)
- `scripts/window-forward-runner.mjs` (`cmdUnlock` + ayuda)
- `package.json` (bump `2.11.31-beta → 2.11.32-beta`)
- `docs/…` y `CHANGELOG.md`

Y deja constancia de:

| Dato | Valor |
|---|---|
| Alembic head | `048_journal_entry_dedupe_key` (**sin migración**) |
| `application package` | `2.11.32-beta` |
| `AUTO engineering release` | `v2.88.32-beta` |

No hay migración y la nomenclatura de dos niveles (tag de ingeniería ≠ semver del paquete) es correcta.

---

## 2. 🔴 → 🟢 El hallazgo de `v2.88.31` está cerrado

La solución es **mejor** que la propuesta inicial del auditor. Se ha introducido `unlockDecision()`
como **función pura**, y `cmdUnlock()` ya **no** hace simplemente `readLock()` → `rmSync()`: ahora decide
entre tres acciones y sólo borra en una de ellas.

```text
readLock()
   ↓
unlockDecision()          // puro: mismo ownership que run-day
   ↓
┌─────────────┬───────────┬──────────┐
│  nothing    │   deny    │ reclaim  │
└─────────────┴───────────┴──────────┘
   ↓                         ↓
 (no toca disco)        rmSync SOLO si reclaim
```

Esto es exactamente lo que buscaba la auditoría. La decisión especialmente valiosa: **`--force` tampoco
puede matar semánticamente un lock de un PID vivo del mismo host**, de modo que el administrador no puede
destruir la exclusión mutua mientras el proceso sigue corriendo.

---

## 3. Comportamiento del nuevo `unlock` (matriz verificada)

| Situación | `unlock` | `unlock --force` | Acción interior |
|---|---|---|---|
| No existe lock | 🟢 nada | 🟢 nada | `nothing` |
| Mismo host + PID vivo | 🔴 DENY | 🔴 DENY | `deny (pid_vivo)` |
| Mismo host + PID muerto | 🟢 RECLAIM | 🟢 RECLAIM | `reclaim (pid_muerto)` |
| Otro host + TTL fresco | 🔴 DENY | 🟠 RECLAIM | `deny (host_distinto)` / `reclaim (host_distinto_force)` |
| Otro host + TTL >12 h | 🟢 RECLAIM | 🟢 RECLAIM | `reclaim (ttl_expirado)` |
| `lock.json` ilegible | 🔴 DENY | 🟠 RECLAIM | `deny (lock_ilegible)` / `reclaim (lock_ilegible_force)` |
| `--dry-run` | 🟢 no toca disco | 🟢 no toca disco | imprime `rm -rf …` |

La matriz coincide, fila por fila, con `unlockDecision()` en
[`scripts/lib/window-forward.mjs`](../../scripts/lib/window-forward.mjs) y con las afirmaciones falsables
`C1`–`C5` de la evidencia. `deny` ⇒ exit `1`.

---

## 4. Decisión arquitectónica: `unlock` **reutiliza** `lockDecision`

Punto arquitectónicamente importante. **No** se ha creado una segunda lógica paralela del tipo
`run-day → lógica A` / `unlock → lógica B`, sino que ambos comandos pasan por el **mismo** núcleo:

```text
                    ┌───────────────┐
                    │ lockDecision  │
                    └───────┬───────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
            run-day                 unlock
         (acquireDayLock)        (unlockDecision)
```

Esto reduce muchísimo el riesgo de que ambos comandos evolucionen de forma divergente: es una **mejora
estructural**, no sólo un parche.

---

## 5. Tests: aquí la corrección sí «muerde»

| Momento | Tests `node:test` |
|---|---|
| `v2.88.31` | `19` |
| `v2.88.32` | **`25`** (`25` pass · `0` fail) |

Los **seis** nuevos cubren específicamente: `sin lock` · PID vivo (con y sin `--force`) · PID muerto ·
host ajeno con TTL fresco/`--force` · host ajeno con TTL expirado · `lock.json` ilegible/`--force`.

Y esto es lo importante de un test de regresión: están diseñados para que **volver al comportamiento
anterior de `rmSync()` haga fallar la suite**. No es «añadimos un test y pasa»; se demuestra que si se
elimina la decisión de ownership, la batería cae.

---

## 6. 🔐 Lock principal: sin regresión

La lógica de `run-day` continúa siendo la misma: `mkdir(.run.lock)` → si `EEXIST` → leer owner →
`lockDecision()`; un **PID vivo** ⇒ `BLOCKED` incluso con `--force`; y el `release` del lock en `finally`
sigue intacto. Por tanto hay **dos barreras** complementarias:

```text
Ejecución            run-day → lock atómico (mkdir) → BLOCKED si PID vivo
Administración       unlock  → ownership check → reclaim sólo si stale
```

La combinación es correcta.

---

## 7. El `race` que preocupaba queda cerrado por construcción

Podría haber aparecido esta carrera:

```text
unlock comprueba PID → PID muerto → otro run intenta adquirir → unlock borra
```

Pero mientras el lock sigue presente, el nuevo `run-day` **no** puede crear otro lock porque `mkdir()`
encuentra `EEXIST`. Así que **no** se abre una ventana de doble ejecución entre la comprobación y el `rm`.
Después de eliminar el lock puede arrancar un proceso nuevo, pero ya **no** existe el proceso antiguo
propietario. Correcto.

---

## 8. Provenance sigue intacta

No se ha tocado negativamente la solución de `v2.88.31`. La cadena continúa existiendo:

```text
ledger → manifest → window.json del run → SHA-256 → window header → freeze → gate
```

y `status` sigue **sin** utilizar directamente el `operability_runs/operability-window.json` como fuente
autoritativa (evita que un `window.json` antiguo contamine una medición nueva).

---

## 9. Freeze sigue correctamente congelado

La configuración continúa siendo `FROZEN` por defecto. Los overrides `WINDOW_APPS_HASH`,
`WINDOW_PACKAGES_HASH`, `WINDOW_ACCOUNT`, `WINDOW_VERSION_A`, `WINDOW_VERSION_B` y `WINDOW_WATCH_SIZE`
siguen requiriendo explícitamente `UNSAFE`, y el material `UNSAFE` **no** puede convertirse en gate
certificado. Sin regresión.

---

## 10. PAPER sigue honestamente NO MEDIDO

`v2.88.32` **no** intenta declarar cerrada la ventana PAPER. La propia evidencia declara que
`≥4 días` · `≥2 episodios` · `≥32 ciclos` continúan **pendientes** (`status` honesto `NO_MEDIDO`, ledger
vacío) y `BEAR_TREND` puede seguir vetando LONG. Es la lectura correcta: el sello **endurece el
instrumento, no fabrica días**.

---

## 11. CI real de `v2.88.32`

| Dato | Valor |
|---|---|
| Run | `Release tag CI` [`37073387310`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37073387310) |
| `ref` | `refs/tags/v2.88.32-beta` (HEAD `f87425ae`) |
| Ventana | `2026-10-02T22:36:24Z → 22:43:50Z` |
| Resultado | **`SUCCESS`** |

Jobs principales, todos verdes:

| Área | Resultado |
|---|---|
| Security / Gitleaks | 🟢 |
| Shared (`Window runner guards`) | 🟢 |
| Window guards | 🟢 |
| Decision Spine | 🟢 |
| Python | 🟢 |
| Frontend | 🟢 |
| Mock E2E | 🟢 |
| Lifecycle PostgreSQL | 🟢 |
| Replay reproducibility | 🟢 |
| DR verify | 🟢 |
| A7 gate | 🟢 |
| Certify | 🟢 |
| Integrated Playwright | ⚪ `skipped` por diseño |

El job `shared` ejecutó específicamente **Window runner guards** (`pnpm window:test`) →
`# tests 25 · # pass 25 · # fail 0`, y pasó. `python` dio **`4324 passed, 45 skipped`** (**idéntico a
`v2.88.31`** ⇒ sin cambios de producto Python); `frontend` **`235` ficheros / `1355` tests `passed`**
(`critical=0 · warn=0`); `lifecycle-pg` volvió a correr **Golden Day 2.0** (`2 passed`),
**Crash/Recovery** (`2 passed`), **Concurrent AUTO** (`3 passed`), crash injection matrix (`2 passed`) y
**multiprocess AUTO** (`1 passed`), y el job completo está verde; `replay-repro` reprodujo el artefacto
`1E3ADAC2…` de forma determinista (**2ª corrida IDÉNTICA**).

---

## 12. AUTO no ha sufrido regresión

El `lifecycle-pg` de esta versión vuelve a ejecutar Golden Day 2.0, Crash/Recovery, Concurrent AUTO,
HardKill recovery, crash injection y Multiprocess AUTO, y el job completo está **verde**; el
`replay-repro` vuelve a reproducir el artefacto **determinísticamente**. Por tanto:

```text
Δ decisión motor = 0
```

se mantiene, que es exactamente lo que se buscaba con una versión **OPS-only**.

---

## 13. No hay contaminación del producto

El diff es extremadamente sano para este tipo de release. **No** se ha tocado: Decision Engine ·
Governor · `TOP_N` · thresholds · allocation · strategy weights · Python product code · database schema ·
migrations · frontend operativo. El cambio queda prácticamente encapsulado en: **runner · tests · docs ·
versión**. No se ha mezclado una reparación de infraestructura de medición con modificaciones del
algoritmo de trading.

---

## 14. Observación P3 declarada (no corregida; mejora futura)

**`unlock --force` sobre otro host.** Actualmente, `otro host` + `TTL fresco` + `--force` ⇒ `RECLAIM`.
Es deliberado y está documentado. Existe un escenario **teórico**:

```text
Host A  run-day vivo
Host B  no puede comprobar correctamente el PID de A
        ↓
unlock --force
        ↓
borra lock  ⇒ podría volver a permitir dos procesos
```

**No** se considera un bug: el comportamiento está diseñado como *escape hatch administrativo explícito*.
Para una versión posterior, si se quiere llevar a nivel muy alto de producción, podría sustituirse ese
`--force` por una operación más explícita:

```text
--force-reclaim-foreign-lock
    → registrar: operator · reason · timestamp · previous owner · previous host · age
```

Sería **P3 de auditabilidad**, no una corrección necesaria ahora. Se declara para no perderla.

---

## 15. Estado de AUTO después de esta versión

| Componente | Estado |
|---|---|
| Decision Spine | 🟢 |
| Risk / Allocation | 🟢 |
| Reservation | 🟢 |
| Order durability | 🟢 |
| Fill durability | 🟢 |
| Protection exactly-once | 🟢 |
| Settlement | 🟢 |
| Crash recovery | 🟢 |
| HardKill | 🟢 |
| Concurrent AUTO | 🟢 |
| Multiprocess | 🟢 |
| Replay | 🟢 |
| Operational Monitor | 🟢 |
| PAPER runner | 🟢 |
| Lock | 🟢 |
| Freeze | 🟢 |
| Provenance | 🟢 |
| PAPER ≥4 días | 🔴 PENDIENTE |

---

## 16. Veredicto y valoración

```text
v2.88.30  problema: ausencia de lock
   ↓
v2.88.31  lock + freeze + provenance
   ↓
          problema descubierto: unlock podía destruir un lock vivo
   ↓
v2.88.32  unlock con ownership + staleness
   ↓
          25/25 tests · CI completo verde · AUTO sin regresión
```

**Veredicto de la auditoría:** `v2.88.32-beta` — 🟢 **APROBADA**.

| Área | Valoración |
|---|---|
| AUTO CORE | 9.7/10 |
| Durable integrity | 9.8/10 |
| Crash/recovery | 10.0/10 |
| Concurrency | 10.0/10 |
| Operational Monitor | 9.9/10 |
| PAPER Runner | 10.0/10 |
| Provenance | 9.8/10 |
| **GLOBAL AUTO** | **~9.8/10** |

**Recomendación del auditor:** **no** emitir una `v2.88.33` para seguir refinando este runner. El `unlock`
ya está suficientemente protegido y la suite lo demuestra. El siguiente paso es el que queda pendiente
desde hace varias versiones: **ejecutar la ventana PAPER real ≥4 días** con `≥2` episodios de régimen y
`≥32` ciclos medibles, y analizar después los resultados. Ahí se obtendrá por primera vez evidencia
**longitudinal real** del AUTO, en lugar de seguir aumentando únicamente la robustez de la infraestructura.

---

## 17. Relación con la fase en curso y deuda documental

Este registro es **documental**: se añade a `main` **sin bump, sin tag y sin tocar `packages/`/`apps/`**
(patrón docs-only de los informes `v2.88.3` y del addendum `v2.88.18`-`v2.88.19`). **No** mueve ningún
árbol.

**Deuda documental declarada (no oculta).** El SoT corto [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) y el
historial [`PROJECT_STATE.md`](./PROJECT_STATE.md) siguen anclados en **`v2.88.19`** (2026-10-01), y
`engineering-index` termina en la entrada **199**; las versiones **`v2.88.20`…`v2.88.32`** se sellaron el
2026-10-02 y **no** se reflejaron allí. Este informe **no** «rellena» ese hueco: lo **declara** como deuda
documental, pendiente de una puesta al día específica.

**Punto de entrada del objeto auditado:** [`evidence/v2.88.32/README.md`](./evidence/v2.88.32/README.md) ·
[`evidence/v2.88.31/README.md`](./evidence/v2.88.31/README.md) (padre) ·
[`arranque-ventana-paper-operativa-2026-09-27.md`](./arranque-ventana-paper-operativa-2026-09-27.md) ·
[`runbook-ventana-forward-v2.78-2026-09-27.md`](./runbook-ventana-forward-v2.78-2026-09-27.md).
