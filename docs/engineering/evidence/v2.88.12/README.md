# Evidencia del sello `v2.88.12-beta` — `GRANULARIDAD-OPERATIVA` (diseño)

> **Objeto:** tag anotado **`v2.88.12-beta`** · **Versión:** `2.11.12-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** **`docs`-only** — el **motor NO cambia** (`git diff` de `packages/py` y
> `apps/api-python/src` = **vacío**).
> **AsOf:** 2026-09-30.

---

## 1. Qué es este sello

Un **diseño** (`config-driven`) que repiensa la cadencia del motor AUTO frente a la **granularidad real de
los datos**: la *granularidad del dato* es **diaria** (`ohlcv_bars.timeframe` default `1d`,
`KERNEL_TIMEFRAMES = {1d, 1wk}`) pero la *cadencia del bucle* es de **60 s**
(`AUTO_ENGINE_SIM_INTERVAL_SECONDS`) ⇒ ~**1.440 ticks/día** para **~1 decisión real** por barra diaria.

**NO** es una implementación, **NO** enmienda el ADR 010 y **NO** cierra deuda (`P3-2`/`P3-3` y el resto
siguen **ABIERTAS**).

---

## 2. Contenido del tag

| Documento | Rol |
| --- | --- |
| [`rethink-granularidad-operativa-auto-2026-09-30.md`](../rethink-granularidad-operativa-auto-2026-09-30.md) | **el diseño** (diagnóstico con citas + modelo `OperativeGranularity` + 3 opciones de cadencia + config/ADR + `P3` + roadmap F1–F4) |
| [`arranque-auditor-v2-88-12-granularidad-operativa-2026-09-30.md`](../arranque-auditor-v2-88-12-granularidad-operativa-2026-09-30.md) | **punto de entrada del auditor** |
| [`entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md`](../entrega-auditoria-externa-mia-v2.88.12-2026-09-30.md) | **entrega a auditoría externa MIA** (trampas declaradas + 7 preguntas + prompt) |
| `CHANGELOG.md` + `package.json` | entrada de changelog + **bump** `2.11.11-beta → 2.11.12-beta` |
| `docs/engineering/PROJECT_STATE.md` + `engineering-index-2026-08-03.md` + `docs/adr/010-...md` | registros (enlace **no normativo** en el ADR; **sin** enmienda) |

---

## 3. Firma de estado (verificable por el auditor)

```
git cat-file -t v2.88.12-beta                                   # tag  (anotado)
git show v2.88.12-beta:package.json                             # 2.11.12-beta
git diff --name-only v2.88.11-beta v2.88.12-beta -- packages/py apps/api-python/src   # VACÍO
git diff --name-only v2.88.11-beta v2.88.12-beta -- .github pyproject.toml            # ninguno
```

---

## 4. Cita del CI (POST-TAG) — **ROJO attempt 1 + VERDE attempt 2**

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**.

**`Release tag CI` [`36715434260`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36715434260)** — ref
`v2.88.12-beta`, HEAD `c0c0b89e`, evento `push`, `2026-09-30T12:32:47Z`.

| Intento | Resultado | Detalle |
| --- | --- | --- |
| **attempt 1** | **FAILURE** | único rojo: `lifecycle-pg` → `test_simulated_finance_pg.py::test_permanent_rejection_materializes_failed_not_retry` (`1 failed, 165 passed`). **NO es el motor** (sello docs-only; código idéntico al verde `v2.88.11`): es un **test flaky** (`OBS-23`). |
| **attempt 2** (rerun de jobs fallidos) | **SUCCESS** | `certify` **GREEN** (10 jobs requeridos verdes + `playwright (integrated)` `skipped` por diseño); `python` **`3118 passed, 38 skipped`** (Ruff `All checks passed!`); `lifecycle-pg` **`166 passed`** (0 fallos, 0 skips). |

Los **dos intentos** se citan; ningún rojo se oculta. Buscar la cita con:

```
gh run view 36715434260 --json status,conclusion   # success (attempt 2)
gh run list --workflow "Release tag CI" --limit 10
```

---

## 5. Hallazgo nuevo `OBS-23` y deuda que este sello NO cierra

### `OBS-23` (MEDIUM, proceso/test) — **ABIERTA**, declarada por el CI de este sello

El test `apps/api-python/tests/test_simulated_finance_pg.py::test_permanent_rejection_materializes_failed_not_retry`
(**añadido en `v2.88.11`** para certificar `OBS-21`) es **flaky por construcción**: genera un
`instrument_id` **aleatorio** por corrida (`inst-fin-{uuid4[:10]}`) y `simulated_fill_schedule` →
`draw_queue_noise(seed, side, instrument_id)` cae en una **cola TERMINAL sin fill**
(`noise_reject`/`noise_timeout`/`noise_market_closed`/`noise_unavailable`/`noise_unknown`) con probabilidad
**`0.010 + 0.025 + 0.005 + 0.012 + 0.004 = 5,6 %`** ⇒ `result.fills == ()` ⇒ `1 failed`. **No es una
regresión del motor**: el test del motor de `OBS-21` es correcto; lo que oscila es su **entrada**. Arreglo
posible (**no** implementado): fijar el `instrument_id`/semilla del caso o forzar un `queue_event` de
llenado. Fue la causa del **attempt 1 ROJO** del CI del sello (§4).

### Deuda previa que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-14.b`, `OBS-15`, `OBS-16`, `OBS-22`,
`OBS-19`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` quedó **cerrada** en
`v2.88.11-beta`.

---

## 6. Pre-auditoría interna (NO externa)

[`preauditoria-interna-granularidad-operativa-v2.88.12-2026-09-30.md`](../preauditoria-interna-granularidad-operativa-v2.88.12-2026-09-30.md)
— autocrítica **del autor** (sin independencia) con verificación reproducible de las citas de §2 del diseño
y 4 hallazgos menores (deriva de línea en algunas citas; el *seam* `_v2_consumed_bar` ya existente; cifras
`NO MEDIDO`; §10 sin comando de verificación). **No** sustituye el veredicto del auditor externo.
