# Evidencia cruda — `v2.88.32-beta` (OPS: `window:unlock` deja de poder borrar un lock vivo)

> **Objeto:** package **`2.11.32-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-02**.
> **Clase:** sello **de operación** sobre el runner de la ventana PAPER `≥4 días`. Cierra el **único hallazgo nuevo** de la auditoría de `v2.88.31-beta` (`window:unlock` borraba cualquier lock, incluido el de un proceso vivo). **`Δ decisión motor = 0`**: no se toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B, UI ni migraciones; **sin cambios de producto Python**.
> **Padre:** [`evidence/v2.88.31/README.md`](../v2.88.31/README.md) (lock diario atómico, config de freeze inmutable, provenance del gate).
> **Nomenclatura:** `AUTO engineering release = v2.88.32-beta` · `application package = 2.11.32-beta`.

---

## 0. Qué corrige este sello

| # | Grieta (auditoría de `v2.88.31`) | Corrección |
|---|---|---|
| **P1/P2 🟠 · unlock** | `cmdUnlock` hacía `readLock` → `rmSync` **sin** aplicar `lockDecision()`: `pnpm window:unlock` borraba el `.run.lock/` de un `run-day` **vivo** ⇒ un tercer `run-day` creaba un lock nuevo y dos corridas concurrentes del mismo día volvían a ser posibles (justo la condición que el lock debía impedir). | `unlockDecision()` (puro): `unlock` aplica la **misma lógica de ownership** que `run-day` y **nunca** borra un PID vivo de este host (ni con `--force`). Reclama sólo lo huérfano: PID muerto en este host, o host ajeno con TTL superado (>12 h). Un host ajeno con TTL **fresco** o un `lock.json` **ilegible** exigen `--force` (escape hatch administrativo). Denegar ⇒ exit `1`. |
| 🟢 · lock | *(no regresión)* `run-day` sigue adquiriendo el `mkdir` atómico antes de la idempotencia y liberando en `finally`; `--force` no salta un lock vivo. | Tests de `lockDecision` intactos. |
| 🟡 · ventana | **No se cierra la ventana PAPER.** | `status` sigue declarando `NO_MEDIDO` (ledger vacío). Este sello endurece el instrumento, no fabrica días. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | `unlock` **deniega** (exit `1`) un lock con PID **vivo** en este host, **incluso con `--force`**. | Volver a `rmSync` sin `unlockDecision` ⇒ borra el lock vivo y `lockStillThere=false`. | `unlock` con `.run.lock/lock.json` de PID vivo ⇒ `DENEGADO (pid_vivo)` · exit `1` · lock presente (con y sin `--force`) |
| **C2** | `unlock` **reclama** un lock con PID **muerto** en este host (sin `--force`). | Tratar todo lock como vivo ⇒ nunca se libera un huérfano por comando. | `unlock` con PID muerto ⇒ `lock … eliminado (pid_muerto)` · exit `0` · lock ausente |
| **C3** | `unlock` **reclama** un lock de otro host con TTL **expirado** (>12 h) sin `--force`; con TTL **fresco** deniega salvo `--force`. | Ignorar el TTL ⇒ se reclama un lock ajeno reciente. | `unlockDecision` (puro): `ttl_expirado` ⇒ reclaim; `host_distinto` ⇒ deny; `host_distinto_force` ⇒ reclaim |
| **C4** | `unlock` **deniega** un `lock.json` **ilegible** (falta/corrupto) y sólo `--force` lo reclama. | Reclamar sin poder probar ownership ⇒ fail-open. | `unlockDecision({lockExists:true, lock:null})` ⇒ `deny/lock_ilegible`; con `--force` ⇒ `reclaim/lock_ilegible_force` |
| **C5** | `unlock --dry-run` **no** toca disco. | Escribir/borrar en dry-run. | `unlock --at <DIA> --dry-run` ⇒ imprime `rm -rf …` y el lock sigue presente |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `node --test scripts/lib/window-forward.test.mjs` (`pnpm window:test`) | **`25` tests, `25` pass, `0` fail** (`19` previos + `6` nuevos de `unlockDecision`) |
| `unlock --at <DIA>` con `.run.lock/lock.json` de **PID vivo** (con y sin `--force`) | `unlock DENEGADO (pid_vivo)` · exit `1` · `.run.lock` **presente** |
| `unlock --at <DIA>` con **PID muerto** | `lock del dia … eliminado (pid_muerto)` · exit `0` · `.run.lock` **ausente** |
| `unlock --at <DIA> --dry-run` (PID muerto) | imprime `rm -rf … (pid_muerto)` · exit `0` · `.run.lock` **intacto** |
| `unlock --at <DIA>` con `.run.lock/` sin `lock.json` | `unlock DENEGADO (lock_ilegible)` · exit `1`; con `--force` ⇒ `eliminado (lock_ilegible_force)` |
| `node scripts/window-forward-runner.mjs --dry-run run-day` | `config FROZEN` · `freeze OK · apps 2237f069… · packages ce0a38b7…` (sin regresión) |
| **CI de tag** — `Release tag CI` run [`37073387310`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37073387310) (`ref=refs/tags/v2.88.32-beta`, HEAD `f87425ae`, `2026-10-02T22:36:24Z → 22:43:50Z`) | **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. El step `shared` **Window runner guards** (`pnpm window:test`) → `# tests 25 · # pass 25 · # fail 0`; `python`: **`4324 passed, 45 skipped`** (**idéntico a `v2.88.31`** ⇒ sin cambios de producto Python); `frontend`: **`235` ficheros / `1355` tests `passed`** · `passed=true · critical=0 · warn=0`; `lifecycle-pg` **VERDE** (Golden Day 2.0 `2 passed`, Crash/Recovery `2 passed`, Concurrent AUTO `3 passed`, crash injection matrix `2 passed`, multiprocess AUTO `1 passed`); `replay-repro`: `REPRODUCIDO` (`1E3ADAC2…`, 2ª corrida IDÉNTICA) ⇒ el árbol no mueve el artefacto OOS |

> El step `Window runner guards` (`pnpm window:test`) del job `shared` del `Release tag CI` ya existía desde
> `v2.88.31`: este sello sólo añade `6` tests al mismo fichero, sin tocar el workflow.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No cierra la ventana PAPER.** `≥4 días` / `≥2 episodios` / `≥32 ciclos` sigue **abierta**; el `status`
   honesto es `NO_MEDIDO` (ledger vacío).
2. **Cuenta fija supeditada a la BD alcanzable** (bloqueante declarado en `v2.88.29` §0.1): el runner no la
   crea ni la siembra.
3. **`--force` no salta un PID vivo del mismo host** por diseño: el escape hatch es **matar** el proceso;
   sólo un lock de otro host o un lock ilegible admiten `--force`. Es una decisión consciente (favorece la
   exclusión mutua sobre la conveniencia administrativa).
4. **Sin migración / sin backfill** (head `048`).
5. **Provenance sólo en el runner (Node)** (misma decisión que `v2.88.31`): no se modifica
   `v2_80_market_window.py`.

---

## 4. Comandos (reproducir)

```bash
pnpm window:test
node scripts/window-forward-runner.mjs unlock
node scripts/window-forward-runner.mjs unlock --force
node scripts/window-forward-runner.mjs --dry-run run-day
node scripts/window-forward-runner.mjs status
```

---

## 5. Sello

- **Versión:** `2.11.32-beta` (base `2.11.31-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros de operación:** `scripts/lib/window-forward.mjs` (`unlockDecision`), `scripts/window-forward-runner.mjs` (`cmdUnlock` + ayuda), `scripts/lib/window-forward.test.mjs` (+6 tests), `package.json` (bump), docs de runbook.
- **RELEASE (GitHub):** `v2.88.32-beta` — *pre-release* sobre el tag anotado.
- **CITA REAL DEL CI (POST-TAG, 2026-10-02):** `Release tag CI` run [`37073387310`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37073387310) (`ref=refs/tags/v2.88.32-beta`, HEAD `f87425ae`, `2026-10-02T22:36:24Z → 22:43:50Z`) → **`SUCCESS`**: **11 jobs `success`** (`security`, `shared`, `decision-spine`, `python`, `replay-repro`, `dr-verify`, `a7-gate`, `frontend`, `lifecycle-pg`, `playwright (mock E2E)`, `certify`) + `playwright (integrated E2E, opt-in)` `skipped` por diseño. El step `shared` **Window runner guards** (`pnpm window:test`) → `# tests 25 · # pass 25 · # fail 0`. Job `python`: **`4324 passed, 45 skipped`** (**idéntico a `v2.88.31`** ⇒ sin cambios de producto Python, como se declara). Job `frontend`: **`235` ficheros / `1355` tests `passed`** · `passed=true · critical=0 · warn=0`. `lifecycle-pg` **VERDE** con gates *fail-if-skipped*: **Golden Day 2.0 `2 passed`** · **Crash/Recovery Day `2 passed`** · **Concurrent AUTO `3 passed`** · crash injection matrix `2 passed` · multiprocess AUTO `1 passed`. `replay-repro` → `VEREDICTO REPRODUCIDO` con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (**idéntico a `v2.88.25`–`v2.88.31`**), **2ª corrida IDÉNTICA** ⇒ el árbol no mueve el artefacto OOS.
- **`Δ motor = 0`:** ningún fichero de motor/producto Python tocado; sin cambios de contrato.
