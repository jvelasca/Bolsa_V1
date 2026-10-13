# Auditoría externa — ventana `v2.88.118-beta` → `v2.88.120-beta` (re-verificación independiente)

> **Tipo:** auditoría **independiente** (re-verificación con subagentes sobre el árbol, los artefactos, los tests y `git`).
> **Objeto:** los sellos `v2.88.118-beta` (`H1.1` sin muestra), `v2.88.119-beta` (`R-ev`, evidencia) y `v2.88.120-beta` (`A1-trace-por-valor`).
> **Resultado:** **0 hallazgos bloqueantes**; **1 fallo de corrección real** (`H1`) + **3 huecos de trazabilidad** (`H2`–`H4`) + **1 errata cosmética** (`H5`), remediados en el sello **`v2.88.121-beta`**.
> **Fecha:** 2026-10-13.

---

## 1. Alcance y método

Se re-verificaron cuatro áreas en paralelo, cada una contra el código, los artefactos de evidencia y `git` (sin confiar en la narrativa de los README):

1. **`v2.88.119` (R-ev):** artefacto K=12, esquema `oos-finance-band-v4`, agregados, sellos LF, «sin cambio de lógica».
2. **`v2.88.120` (A1):** `_cycles_for_symbol`, `cycles[]`, helpers de UI, deep-link, filtrado del backend, contrato.
3. **`v2.88.118` (H1.1):** guarda `no_effective_sample`, precedencia, cobertura de tests.
4. **Abiertos:** AUTO diario, PAPER longitudinal (P3-2/P3-3), traza DÍA-D, aislamiento de ejecución, auditoría UI.

**Método:** lectura de fuentes + `git diff/log/show`, ejecución de baterías focales y de la suite de aplicación; para UI, render de componentes con React Testing Library.

---

## 2. Veredictos por claim

### 2.1 `v2.88.119-beta` (R-ev) — 6/6 CONFIRMADO

| Claim | Veredicto | Evidencia |
| --- | --- | --- |
| Artefacto + informe existen, esquema `oos-finance-band-v4` | CONFIRMADO | [`evidence/v2.88.119/finance-band-w32-k12.json`](./evidence/v2.88.119/finance-band-w32-k12.json) (`schemaVersion` L1396); `SCHEMA_VERSION` en [`oos_finance_band.py`](../../packages/py/application/src/bolsa_application/oos_finance_band.py#L62) |
| Agregados declarados | CONFIRMADO | `n:12, min:-3.398126, median:-0.7028965, max:0.515323, mean:-0.8613163, stdev:1.0195998` |
| `statisticalConfidence=NOT_MEASURED`, `pointCitable=false` | CONFIRMADO | presentes en el agregado y en los 10 grupos |
| `Δ medición` vs `v2.88.114` = 0 y 12 sellos LF coinciden | CONFIRMADO | 10 bandas y 12 `sha256Lf` idénticos; `k=0 = 1E3ADAC2…929A37E7` |
| Sin cambio de lógica (`Δ motor = 0`) | CONFIRMADO | `git diff v2.88.118..v2.88.119`: solo `meta.bump`, docs y artefactos |
| Origen único del string de esquema | CONFIRMADO | una sola aparición en `*.py` (`oos_finance_band.py:62`) |

**No verificable localmente:** las 12 corridas requieren PostgreSQL sembrado; los `run-id` de CI son atestaciones del markdown.

### 2.2 `v2.88.120-beta` (A1) — claims CONFIRMADO, con huecos

Backend `_cycles_for_symbol` ([`estudio_audit.py`](../../packages/py/application/src/bolsa_application/estudio_audit.py)), DTO, UI, ruta y contrato presentes y correctos. **Huecos** en §3 (`H2`–`H4`).

### 2.3 `v2.88.118-beta` (H1.1) — CONFIRMADO el caso `draws=[]`; **borde `n=1` ABIERTO**

La guarda `no_effective_sample` tiene máxima precedencia y `draws=[]` ⇒ `NOT_MEASURED`. **Pero** con **1 sorteo** (`stats` no-`None` pero `< MIN_DRAWS_FOR_BAND`) + `independent_sample` + procedencia completa, seguía emitiendo `MEASURED` / `established=False`: el mismo medio-estado que el sello decía eliminar. Ver `H1`.

### 2.4 Áreas abiertas — estado real

| Área | Estado |
| --- | --- |
| AUTO diario por valor ESTUDIO | **PARCIAL** — el orquestador existe y recorre el universo ESTUDIO, pero `AUTO_ORCHESTRATOR_ENABLED` / `AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only); no hay cron diario por valor |
| P3-2/P3-3 PAPER longitudinal | **INSTRUMENTO IMPLEMENTADO / VALIDACIÓN ABIERTA** (ADR-046); cierra solo operando días reales |
| Traza DÍA-D (señal→ciclo→cierre→P&L) | **IMPLEMENTADO** (`auto_operational_monitor.py`) |
| Aislamiento de ejecución (SIM vs XTB) | **IMPLEMENTADO, default seguro** (`broker_venue="paper"`, doble barrera LIVE OFF, `live_auto` dry-run) |
| Auditoría UI | **PARCIAL/PENDIENTE** (ola 1 sellada; olas 2..6 abiertas) |

**Aviso de etiquetas:** no confundir el **P3-2/P3-3 abierto** (ventana PAPER) con los **P3-2/P3-3 de `v2.65`** (`materialOrigin` / perímetro), **cerrados en `v2.66`**.

---

## 3. Hallazgos y remediación (sello `v2.88.121-beta`)

| ID | Severidad | Hallazgo | Remediación |
| --- | --- | --- | --- |
| **H1** | **Corrección (alta)** | `band_validity` sólo guardaba `stats is None`; con `n=1` + `independent_sample` + procedencia completa ⇒ `MEASURED`/`established=False` | Guarda a **muestra efectiva** (`stats["n"] < MIN_DRAWS_FOR_BAND`), antes de `venue_seeded`/procedencia; mismo motivo `no_effective_sample`. Tests de `n=1` en ambas bandas |
| **H2** | Trazabilidad | `signal.cycles`/`measuredCycles` contaban no-enlazados mientras `cycles[]` los excluía ⇒ recuentos que no cuadran | `signal` expone `linkedCycles` / `unlinkedCycles` / `duplicateCycles`; invariante `linkedCycles == len(cycles[])` |
| **H3** | Trazabilidad | Orden lexicográfico (`cyc-10` < `cyc-2`) y sin dedup (claves React repetidas) | Orden **natural** + dedup determinista por `cycleId` (desempate por firma; invariante bajo permutación); `key` React con índice |
| **H4** | Cobertura | Sin test del caso mixto enlazado/no-enlazado ni de navegación; el hueco no distinguía «cargando» de «fuera de ventana» | Tests de caso mixto, dedup y orden; `AutoOperacionPage` distingue **cargando** vs **no-encontrado** (declara el id y la ventana); tests de render |
| **H5** | Cosmética | [`evidence/v2.88.119/README.md`](./evidence/v2.88.119/README.md) atribuía `v1→v4` a los sellos 115–118; `v4` llegó en `v2.88.117` y 118 no cambió esquema | Texto corregido (115→v2, 116→v3, 117→v4; 118 sin cambio de esquema) |

La errata del doc del sello `v2.88.118` se registra como **Errata** en [`plan-v2-88-118-h1-1-sin-muestra-no-measured-2026-10-13.md`](./plan-v2-88-118-h1-1-sin-muestra-no-measured-2026-10-13.md).

---

## 4. Naturaleza del sello de remediación

- **`Δ motor ≠ 0` acotado** al **dominio puro de informe/banda** (`dia_d_multi_uncertainty`, `estudio_audit`) y a la **UI**; **`Δ decisión = 0`** (no toca umbrales, reparto, `TOP_N`, régimen ni protección).
- **SIN cambio de forma de artefacto:** `SCHEMA_VERSION` no sube (`dia-d-multi-band-v3`, `oos-finance-band-v4`); sólo se endurece una rama semántica (`H1`) y se **amplía** el DTO de señal (`H2`).
- **Contrato HTTP ampliado** (campos aditivos en `EstudioAuditSignalDto`) ⇒ contrato regenerado.
- **SIN migración** (head `053_dia_d_cycle_verifications`).

---

## 5. Agenda de la siguiente auditoría funcional

No cerrada por este sello (se mantiene abierta y explícita):

1. **AUTO diario por valor ESTUDIO:** verificar la activación real (`AUTO_ORCHESTRATOR_ENABLED`), que el universo sea **todos** los valores de ESTUDIO y que entrada/salida no dependan del reloj de la máquina; hoy nace **OFF** y SIM-only.
2. **Traza DÍA-D extremo a extremo:** señal → ciclo → cierre → **P&L conciliado**, sin pasos `unknown` silenciosos.
3. **Aislamiento de ejecución:** confirmar de nuevo que **ninguna** ruta alcanza dinero real de XTB con los **defaults** (`broker_venue="paper"`, doble barrera OFF, `live_auto` dry-run).
4. **Auditoría de UI:** olas 2..6 de [`auditoria-ui-6-x-global-2026-10-08.md`](./auditoria-ui-6-x-global-2026-10-08.md).
5. **P3-2/P3-3 PAPER longitudinal:** sólo cierra con la **ventana PAPER real** (≥4 días / ≥2 episodios / ≥32 ciclos, ADR-046); la evidencia de replay/OOS **no** sustituye la ventana.

---

## 6. Límites declarados

- La re-verificación se hizo **sobre el árbol local**; la verificación **externa** (tag/commit/run resueltos en GitHub) queda para la cita POST-TAG del sello.
- El sello **no** demuestra **rentabilidad** ni cierra la operativa AUTO/DÍA-D ni la auditoría de UI.
- Sigue sin existir un **procedimiento estadístico real**: `statisticalConfidence` sólo verifica la **procedencia declarada**.
- El tag es **anotado sin firmar** (`unsigned`): la identidad del objeto se verifica en GitHub, pero no hay firma criptográfica del firmante.
