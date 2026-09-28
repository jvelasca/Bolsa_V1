# Auditoría externa — `v2.84-beta` / `AUTO-MATERIAL-12` (INSTRUMENT FUNNEL CONTRACT): `APROBADO CON OBSERVACIONES`

> **Objeto auditado:** tag anotado **`v2.84-beta`** (objeto `e6d921a8` → commit `fd3859e3`) ·
> **Versión:** `2.09.0-beta` · **Base (diff):** `v2.83.1-beta` (`2.08.1-beta`) · **AsOf:** 2026-09-28 ·
> **Alembic head:** `046_fill_reference_mid` (SIN migración) · **Auditor:** externo, **desde un clon
> fresco de GitHub** (`github.com/jvelasca/Bolsa_V1.git`), **nunca** sobre el árbol local (la ventana PAPER
> forward estaba en curso).
> **Veredicto:** **APROBADO CON OBSERVACIONES — 0 bloqueantes** (14 puntos; sin hallazgos ALTA ni MEDIA).

## 0. Alcance y método

El auditor clonó el repositorio en un directorio temporal, hizo `checkout` del tag `v2.84-beta` y trabajó
**solo** contra ese snapshot. **Prueba de la Regla de Oro:** `git status --porcelain` **vacío** en el clon
al inicio, tras cada sonda con escritura potencial (CLI sin `--out`, matriz de mutaciones, 5 mutaciones
dirigidas) y al final; las sondas que escriben lo hacen **dentro de `scratch/`** del clon.

## 1. Identidad verificada del objeto

| Comprobación | Comando | Resultado |
|---|---|---|
| Tipo de objeto | `git cat-file -t v2.84-beta` | `tag` (**anotado**) |
| Objeto tag | `git rev-parse v2.84-beta` | `e6d921a8e8bcca3ff80238e6ab5735491dcae065` |
| Commit del sello | `git rev-parse 'v2.84-beta^{commit}'` | `fd3859e305b7ef68f85f8c813b34fa434fb0a73f` |
| Base del diff | `git rev-parse 'v2.83.1-beta^{commit}'` | `42c97bab…`, versión `2.08.1-beta` |
| Sello en 3 commits | `a0f03017` feat · `bad2866c` chore(ops) · `fd3859e3` docs | presentes en el log del tag |
| Versión | `package.json` | `2.09.0-beta` |
| `operability_audit.py` byte-idéntico en `v2.83.1` | `git diff v2.83-beta..v2.83.1-beta -- …` | vacío |

## 2. Tabla de los 14 puntos

| # | Punto | Veredicto |
|---|---|---|
| 1 | Identidad del objeto | **PASS** |
| 2 | Diff acotado y sin ficheros prohibidos (23 ficheros) | **PASS** |
| 3 | `OBS-6` cerrado de verdad (refutación intentada y fallida) | **PASS** |
| 4 | `OBS-7` cerrado de verdad (`funnel` sobre `measured_rows`) | **PASS** |
| 5 | `OBS-8` (`argparse` = `2`, doc ya no promete `1`) | **PASS** |
| 6 | Invariantes del instrumento intactos (`rate=None` nunca `0.0`; forma sin cambio; determinismo cross-proceso) | **PASS** |
| 7 | READ-ONLY de verdad (único escritor = `--out`) | **PASS** |
| 8 | Tests (`18 passed`; los nuevos fallan contra `v2.83`) | **PASS** |
| 9 | Matriz adversarial (`232/232`, byte a byte; `M231`/`M232` muerden exacto) | **PASS** (obs. H-1) |
| 10 | Compuertas (`ruff` OK, `import-linter` 4/0, `mypy` 507, `alembic 046`, app `2084 passed, 5 skipped`) | **PASS** (lim. PG) |
| 11 | Registro en CI (test explícito en ambos workflows) | **PASS** |
| 12 | Cita del CI dentro del tag + `OBS-3`/`OBS-4` (placeholder pre-tag; cita acreditada POST-TAG) | **PASS** |
| 13 | Anexo operativo DECLARADO (`ops_seed_window_pair.py`, fuera del instrumento, no CI) | **PASS** (obs. H-2/H-3) |
| 14 | Honestidad de la deuda (ninguna abierta se declara cerrada por prosa) | **PASS** |

**CI remoto verificado con `gh`:** `Release tag CI` `36353503867` (`fd3859e3`) → **success**, job `python`
**`3022 passed, 37 skipped`**; `Python CI` `36353503833` → `quality` **`3011 passed, 40 skipped`**;
`Frontend CI` `36353503843`, `Optimize lab` `36353503832`, `Fase 2 scientific` `36353503849` → **success**;
en `main` (`fd3859e3`) `Python CI` `36353481118` (`quality 3011/40` + jobs PG verdes), `Frontend CI`
`36353481072`, `Optimize lab` `36353481116`, `Fase 2 scientific` `36353481110`, `Gitleaks` `36353481089`
→ **success**.

## 3. Hallazgos

### H-1 — BAJA (documental). «5 huecos locales preexistentes que no muerden» **no se reproduce**.

`plan-v2-84`, `audit-pack-v2-84`, `PROJECT_STATE` (entrada `v2.84`) y `engineering-index` (173) afirmaban
que `M117`/`M118`/`M170`/`M176`/`M197` «no muerden en este entorno». En un clon fresco **sí muerden 5/5**:

```text
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M117 M118 M170 M176 M197
→ M117 rojo en: test_a_failed_write_cleans_the_tick_session_and_lets_the_error_up
→ M118 idem · M170 rojo en: test_a_cycle_query_can_be_paginated_without_gaps_or_repeats
→ M176 rojo en: test_the_manifest_declares_the_perimeter_of_the_dump
→ M197 rojo en: test_the_cell_payload_is_json_shaped_and_rounded, test_the_regime_coverage_key_...
→ medidas: 5/5 · restaurado byte a byte: si
```

Los 5 labels **son preexistentes** (están en `v2.83.1-beta`, no en esta fase) y la frase «idénticos a la
evidencia `v2.81-230`» es cierta; lo **inexacto/obsoleto** es el «no muerden en este entorno».
**No bloquea** (la declaración era **conservadora**: declaraba más deuda de la que hay).

**Corrección (docs-only, POST-TAG, `2026-09-28`):** la frase se sustituye por «**preexistentes y
dependientes del entorno**» en `plan-v2-84`, `audit-pack-v2-84`, `arranque-auditor-v2-84`, `PROJECT_STATE`
y `engineering-index` (173). **No** se modifica la evidencia cruda
(`evidencia-matriz-mutaciones-v2.84-232-2026-09-27.txt`), que es un artefacto observado y queda como está.

### H-2 — BAJA (documental). `OBS-9` **se replica** en el nuevo `ops_seed_window_pair.py`.

El tag declara `OBS-9` para «otros CLIs», pero **introduce una instancia nueva** del mismo defecto en
`apps/api-python/scripts/ops_seed_window_pair.py:44` («`1` uso incorrecto»), mientras `argparse` sale con
**`2`** en el uso incorrecto de argv. La **validación manual** del script sí devuelve `1` (coherente
consigo misma), pero el nivel argv es `2`. Mismo patrón que `OBS-8` ⇒ **engrosa** `OBS-9`.

**Corrección (docs-only, `2026-09-28`):** `OBS-9` (en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md))
incorpora `ops_seed_window_pair.py` a su barrido declarado con nota de instancia nueva. **No** se corrige
el fichero en esta entrega (vive en `apps/`, prohibido tocar con la ventana PAPER viva); entra en el
barrido docs-only de `OBS-9` o en el endurecimiento de `v2.85`.

### H-3 — INFO (aceptable, declarado). `ops_seed_window_pair.py` sin test unitario ni mypy.

Consistente con la convención preexistente (todo `apps/api-python/scripts/` queda fuera del target mypy
`apps/api-python/src`), **declarado fuera del instrumento** y **no corre en CI**; es un camino de
**escritura a PostgreSQL** ejecutado por el operador. **Aceptable**; registrado en el audit-pack.

### H-4 — INFO. El filtro de «medido» solo excluye `measured is False`.

`measured=0` (int) y `measured=null` **cuentan como medidos**. Coincide con el contrato declarado
(`measured != False`) y con el builder canónico (`"measured": measured_days > 0`, bool real); no es
defecto, es un borde a mantener documentado.

## 4. Límites declarados (honestidad del auditor)

- **Sin PostgreSQL local:** los 5 tests PG-gated no se reproducen; midió **`2084 passed, 5 skipped`** (el
  `2089` declarado es la medición con PG).
- **`operability_runs/` gitignoreado:** sin material PAPER real en el repo; la ventana ≥4 días **no** se
  certifica con fixtures.
- **`lint-imports`** abortó por Control de aplicaciones de Windows (os error 4551) y lo invocó vía
  `python` → `4 kept, 0 broken`.
- **Cita del CI** verificada contra el **remoto** con `gh`; el fichero **dentro** del tag es el placeholder
  pre-tag **esperado**.
- **Fuera de alcance:** compuertas de frontend/web y `apps/web/**` (el diff no los toca).

## 5. Veredicto global

**APROBADO CON OBSERVACIONES — 0 bloqueantes.** El objeto sellado es **coherente y honesto**: diff
**acotado** (0 ficheros prohibidos), `OBS-6`/`OBS-7`/`OBS-8` **realmente cerradas** (refutaciones
intentadas y fallidas), instrumento **READ-ONLY y determinista cross-proceso**, matriz **232/232 byte a
byte** y CI del tag **acreditado** POST-TAG. Quedan **dos hallazgos BAJA documentales** (H-1, H-2) y dos
INFO, **ninguno bloqueante** — y **ambos corregidos/registrados** en esta entrega docs-only.

## 6. Relación con la fase en curso

Esta auditoría **no** mueve ningún árbol: es **documental** y se registra en `main` sin bump y sin tag
(patrón docs-only `80b18061` / `1f2638aa` / `434f058d`).

El **mismo tag** `v2.84-beta` recibió además la observación **`OBS-10` (LOW)** —`stateCounts` del `TOTAL`
recorre `rows` en vez de `measured_rows`— y dos recomendaciones operativas (cuenta PAPER fija, cierre de la
cita del CI); su registro, su semántica de cierre y su **aplazamiento declarado** a `v2.85` viven en la
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) y en el
[protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md). Este documento
registra el **informe de 14 puntos** con los hallazgos **H-1**…**H-4** (todos LOW/INFO, 0 bloqueantes); los
dos primeros quedan **corregidos/registrados** aquí mismo.

**`OBS-10` sigue ABIERTA y APLAZADA** a `v2.85`; el **freeze** (`980c7b6e…` / `ffe36fd2…`) queda **intacto**.
