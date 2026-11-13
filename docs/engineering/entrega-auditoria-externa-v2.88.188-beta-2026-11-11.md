# Entrega para auditoría externa — `v2.88.188-beta`

> **Objeto entregado:** tag anotado `v2.88.188-beta` sobre `main`.
> **Naturaleza:** **sello funcional** de UI, de modelo compartido de lectura y de diagnóstico del entorno
> de desarrollo. **No** es una auditoría y **no** reabre `.187`.
> **Para quién:** auditor externo que llega sin la historia del repositorio y necesita un punto de entrada
> único, verificable y con sus límites escritos.

---

## 0. Qué recibe el auditor (y qué no)

| Afirmación | Procedencia | ¿Re-verificada al escribir esto? |
| --- | --- | --- |
| `main` estaba en `2.11.187-beta` (`b6adc871`) al abrir este acto | `git show HEAD:package.json` | **Sí** |
| El último tag publicado era `v2.88.187-beta` | `git tag --list`, `gh release list` | **Sí** |
| El árbol del sello es `apps` `5310f21d…` / `packages` `7c31fca3…` | `git rev-parse HEAD:apps HEAD:packages` + `window-pin --check` | **Sí** |
| `Δ motor = 0` y `Δ decisión = 0` en reglas | Diff completo: no hay cambios en motores, umbrales, sizing ni replay | **Sí** (diff) |
| Sin migración | `head` sigue `066_account_evidence_policy` | **Sí** |
| Contrato HTTP sin cambio | `openapi.json`/`schema.d.ts` fuera del diff; `contract:check` | **Sí** |
| CI del tag | `Release tag CI` `42983709708` **GREEN**; cita POST-TAG en `CHANGELOG.md` | **Sí**, POST-TAG (§6) |

---

## 1. Índice del expediente (todo dentro del árbol del tag)

| Documento | Qué es |
| --- | --- |
| [`evidence/v2.88.188/README.md`](./evidence/v2.88.188/README.md) | Evidencia, verificaciones medidas y falsabilidad |
| [`CHANGELOG.md`](../../CHANGELOG.md) §`2.11.188-beta` | Declaración del acto y alcance por área |
| [`PROJECT_STATE.md`](./PROJECT_STATE.md) bloque `AsOf (V2.88.188-beta)` | Estado vivo al sellar |
| [`analisis-diario-operativa-mercado-2026-11-10.md`](./analisis-diario-operativa-mercado-2026-11-10.md) | Arquitectura de la proyección de análisis diario |
| [`dev-logs.md`](./dev-logs.md) | Vocabulario `api-exit:` y receta de diagnóstico |
| [`DEV_STARTUP.md`](../DEV_STARTUP.md) | Arranque del stack y qué hacer si la API se cae |

---

## 2. Cómo obtener el objeto

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git
cd Bolsa_V1
git fetch --tags
git checkout v2.88.188-beta
```

Un clon por defecto entrega `main`, que **contiene** este expediente. El tag es el objeto certificado;
`main` puede haber avanzado después.

---

## 3. Qué certifica este acto

1. **DECISIÓN con un asunto por bloque:** dos bloques fijos (*Análisis diario*, *Decisión*) y cinco
   plegables (*Seguimiento Lab*, *Mandato*, *Evidencia*, *Aprendizaje*, *AUTO*), con **una sola puerta de
   acción** y sin atajos duplicados.
2. **DECISIÓN maximizable** a área completa, con exclusión mutua frente a Listas y Operaciones y reparto
   por el **ancho real del panel** (container queries), no por el viewport.
3. **Análisis diario del valor** como **proyección única de lectura** (`InstrumentDailyAnalysisV1`): no
   calcula motores ni rellena huecos; declara `gaps` y **`UNKNOWN` ≠ `0`**.
4. **Entradas bloqueadas sin impedir cierres:** el aviso aparece y **Confirm sigue disponible**.
5. **Caída de la API diagnosticable:** `api-exit:<code>` / `api-exit:signal:<SIG>` /
   `api-exit:spawn-error` con rol, pid, señal, uptime y últimas líneas del stderr, en consola,
   `logs/agent/events.log` y `logs/agent/dev.json`.

---

## 4. Qué certifica y qué no

**Certifica** que el árbol publicado hace lo anterior y que las verificaciones de
[`evidence/v2.88.188`](./evidence/v2.88.188/README.md) §4 se ejecutaron **en local** sobre ese árbol.

**No certifica:**

- Rentabilidad, eficacia de AUTO ni calidad de la operativa: AUTO **OFF**, PAPER **`INCONCLUSIVE`**,
  operativa **100 % SIM**, sin órdenes reales.
- Que la banda de análisis diario mejore una decisión: **proyecta** artefactos existentes y declara lo que
  no mide.
- Comportamiento de los E2E live/integrated: exigen API + PostgreSQL + barras; un `skipped` no certifica.
- Que las cifras locales de suites equivalgan a las del CI: el certificador es el job del tag.

---

## 5. Alcance del diff y límites

**57 ficheros, +4.046/−459** contra `v2.88.187-beta` (40 y +2.828/−434 sin `docs/` ni `CHANGELOG`), en
cuatro áreas y sin salir de ellas: `apps/web`
(DECISIÓN, banda, aviso), `packages/shared` (modelo de análisis diario y proyección de indicadores),
`scripts/` (api-exit y su test) y `docs/`. **Sin migración**, **sin cambio de contrato HTTP**, **sin
tocar motores**. La cifra anterior de este párrafo (**41 ficheros, +3.723/−441**) era la del commit
funcional `b6adc871`, previo al bump y al re-anclaje del pin; se corrige `POST-TAG` tras la auditoría
independiente del `2026-11-11`.

Límites abiertos y declarados:

- `main` no se reescribe: los commits anteriores al tag conservan su identidad.
- El pin de la ventana PAPER se re-ancla a este árbol; los días medidos con árboles anteriores quedan
  **`STALE`** y no se reinterpretan.
- La UI no eleva la evidencia operativa: la ventana sigue **`INCONCLUSIVE`**.

---

## 6. Publicación

| Campo | Valor |
| --- | --- |
| Commit del sello | `53285f18` |
| Objeto del tag | `2cc673dc…` |
| `Release tag CI` | [`42983709708`](https://github.com/jvelasca/Bolsa_V1/actions/runs/42983709708) — **GREEN** (`success`, `12` jobs + `certify`) |
| Artefacto | `release-tag-ci-summary`: `status: GREEN`, `sha 53285f18`, `asOf 2026-11-11T08:13:49Z` |
| GitHub Release | [v2.88.188-beta](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.188-beta) |

Medido en el run: `python` **6515 passed, 111 skipped** · `mypy` **599 ficheros** · `playwright (mock)`
**136 passed** · `replay-repro` **`REPRODUCIDO`** (`sha256 E9B7376B…F5625`) ⇒ **`Δ motor = 0` confirmado
por el CI**. Único `skipped`: el E2E integrado opt-in, que no es requisito de GREEN.

**Nota de lectura:** la cita del CI es **POST-TAG** (commit posterior en `main`). El expediente que viaja
**dentro** del tag declara el run como pendiente porque un commit no se certifica a sí mismo; el tag y su
objeto **no se mueven**.
