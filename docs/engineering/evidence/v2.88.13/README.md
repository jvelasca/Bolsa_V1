# Evidencia del sello `v2.88.13-beta` — `GRANULARIDAD-OPERATIVA` (revisión de diseño v2)

> **Objeto:** tag anotado **`v2.88.13-beta`** · **Versión:** `2.11.13-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** **`docs`-only** — el **motor NO cambia** (`git diff` de `packages/py` y
> `apps/api-python/src` = **vacío**).
> **Base del diff:** `v2.88.12-beta`.
> **AsOf:** 2026-09-30.

---

## 1. Qué es este sello

Una **revisión de diseño** sobre el rethink de granularidad operativa de `v2.88.12-beta`. **Conserva el
diagnóstico** (el dato es **diario**, el bucle es de **60 s**; precio plano; `seed = minute`) y **cambia el
modelo** que se deriva de él:

- **clocks separados** (decisión / protección / ejecución / evidencia) con el **heartbeat de infraestructura
  fuera** del value object;
- contratos **explícitos** de **protección D1** (OHLC vs feed intradía, fail-closed) y de **fill**
  (`signal D → OPEN(D+1)`, sin `seed = minute`);
- **contrato de `record_tick`** antes de reducir su frecuencia;
- separación **Fase A** (optimización semánticamente neutra, golden de equivalencia) / **Fase B**
  (corrección deliberada del modelo temporal, nuevo golden);
- **`1wk`** declarada pero **no habilitada**; corrección del estado de **`OBS-21`** (está **CERRADA** en
  `v2.88.11-beta`).

**NO** es una implementación, **NO** enmienda el ADR 010 y **NO** cierra deuda. `P3-2`/`P3-3` y el resto
siguen **ABIERTAS**.

---

## 2. Contenido del tag

| Documento | Rol |
| --- | --- |
| [`rethink-granularidad-operativa-auto-v2-2026-09-30.md`](../../rethink-granularidad-operativa-auto-v2-2026-09-30.md) | **la revisión de diseño v2** (relojes separados + contratos + Fase A/B + roadmap) |
| [`rethink-granularidad-operativa-auto-2026-09-30.md`](../../rethink-granularidad-operativa-auto-2026-09-30.md) | diseño v1 (`v2.88.12`), **anotado [SUPERSEDED]** en lo arquitectónico; texto **verbatim** |
| `CHANGELOG.md` + `package.json` | entrada de changelog + **bump** `2.11.12-beta → 2.11.13-beta` |
| `docs/engineering/PROJECT_STATE.md` + `engineering-index-2026-08-03.md` | registros |

---

## 3. Firma de estado (verificable)

```
git cat-file -t v2.88.13-beta                                    # tag  (anotado)
git show v2.88.13-beta:package.json                              # 2.11.13-beta
git diff --name-only v2.88.12-beta v2.88.13-beta -- packages/py apps/api-python/src   # VACÍO
git diff --name-only v2.88.12-beta v2.88.13-beta -- .github pyproject.toml            # ninguno
git diff --name-status v2.88.12-beta v2.88.13-beta                                    # solo docs + CHANGELOG + package.json
```

---

## 4. Cita del CI (POST-TAG) — `(pendiente)`

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado no
puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**. Al ser `docs`-only, **no** hay
matriz de mutaciones nueva ni test nuevo (no procede). La verificación local del autor coincide con el CI
porque no hay `src` que pueda derivar.

---

## 5. Deuda que este sello NO cierra

`P3-2`/`P3-3` (ventana PAPER real ≥4 días con material), `OBS-23` (flake del test PG de `OBS-21`),
`OBS-22`, `OBS-19`, `OBS-15`, `OBS-16`, `OBS-14.b`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`.
**`OBS-21` sigue CERRADA** (desde `v2.88.11-beta`; este sello **no** la reabre).

---

## 6. Revisión

- **Revisa** (no sustituye) el diseño de [`v2.88.12-beta`](../../rethink-granularidad-operativa-auto-2026-09-30.md).
- **No** sustituye la ventana PAPER real ni el veredicto de la auditoría externa.
- **Próximo incremento propuesto:** modelo puro `OperativeGranularity` + seam de relojes, **inerte**
  (sin cambio de comportamiento), según §11 del diseño v2.
