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

## 4. Cita del CI (POST-TAG)

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede vivir dentro del propio tag. El run **verde** se cita en `main` como commit **POST-TAG** (patrón de
la casa). Buscarlo con:

```
gh run list --workflow "Release tag CI" --limit 10
```

---

## 5. Deuda que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-14.b`, `OBS-15`, `OBS-16`, `OBS-22`,
`OBS-19`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` quedó **cerrada** en
`v2.88.11-beta`.
