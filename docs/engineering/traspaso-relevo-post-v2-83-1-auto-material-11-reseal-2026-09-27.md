# Traspaso / relevo — post `v2.83.1` / `AUTO-MATERIAL-11` (RE-SELLO del objeto auditado)

> **AsOf:** 2026-09-27 · **Estado:** re-sello **CERRADO** (`2.08.1-beta`, tag anotado **`v2.83.1-beta`**),
> pendiente de **auditoría externa** (objeto = `v2.83.1-beta`). **Alembic head:** `046_fill_reference_mid`
> (**SIN migración**).

## 1. Resumen de una línea

`v2.83.1` **no cambia código**: **re-entrega** el instrumento read-only de `v2.83` en un tag que lleva
**dentro** la cita real del CI de `v2.83` (`Release tag CI` `36329460515`, **SUCCESS**), de modo que el
auditor que clone el objeto **no** lea el placeholder «PENDIENTE DE TAG» ni concluya «CI no acreditado».

## 2. Por qué existe (el patrón `OBS-3`/`OBS-4`)

`Release tag CI` **solo corre al empujar** el tag ⇒ la cita de su resultado **no puede** estar dentro de
ese mismo tag. En `v2.83-beta` el fichero de evidencia quedó como **placeholder** y la cita se escribió en
el commit **post-tag** `80b18061` (en `main`). Eso produjo un **falso positivo** de auditoría (leído el
placeholder, declarado «CI no acreditado»). Este re-sello elimina el problema **para la fase auditada**.

## 3. Ficheros entregados

| Fichero | Qué |
|---|---|
| `package.json` | `2.08.0-beta → 2.08.1-beta` (**único** cambio no-doc) |
| `docs/engineering/arranque-auditor-v2-83-1-…md` (**nuevo**) | punto de entrada del auditor: objeto, diff acotado, **cita del CI de `v2.83`** (dentro del tag) y límites |
| `docs/engineering/traspaso-relevo-post-v2-83-1-…md` (**nuevo**) | este relevo |
| `docs/engineering/evidencia-ci-tag-v2.83.1-2026-09-27.txt` (**nuevo**) | evidencia del CI del tag `v2.83.1` (post-tag) |
| `CHANGELOG.md` · `docs/engineering/PROJECT_STATE.md` · `docs/engineering/engineering-index-2026-08-03.md` · `docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md` | registro del re-sello |

**No se toca** ningún módulo de motor, gobernador ni del instrumento (`operability_audit.py`,
`v2_83_window_audit.py`, `test_operability_audit.py` quedan **idénticos**).

## 4. Qué comprobar en 5 minutos

```powershell
# 1) El diff es SOLO package.json + docs (sin codigo de producto ni instrumento)
git diff v2.83-beta..v2.83.1-beta --stat

# 2) Compuertas (identicas a v2.83: no cambia codigo)
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 16 passed
uv run --no-sync pytest packages/py/application/tests -q                             # 2087 passed
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml      # All checks passed!
uv run --no-sync lint-imports --config packages/py/.importlinter                     # 4 kept, 0 broken

# 3) La cita del CI de v2.83 esta DENTRO de este tag
git show v2.83.1-beta:docs/engineering/evidencia-ci-tag-v2.83-2026-09-27.txt
```

## 5. Cita del CI del tag `v2.83.1-beta`

Vive en `evidencia-ci-tag-v2.83.1-2026-09-27.txt` (**commit POST-TAG**, patrón declarado). Esperado
(código idéntico a `v2.83`): job `python` del tag `3020 passed / 37 skipped` y `quality`
`3009 passed / 40 skipped`. **No se hereda**: se cita el run cuando exista.

## 6. Deuda y próximo paso

- **`P3-2`/`P3-3` ABIERTAS:** solo se cierran con la **ventana PAPER ≥4 días** real (`AUTO-22`/`AUTO-23`).
- **`H-4` (LOW) ABIERTO:** esta entrega lo hace **visible** (`warnings: reason_contract`), no lo cierra.
- **`P3-5`** y **`OBS-5`**: siguen declaradas. `OBS-3`/`OBS-4`: **materializadas** ya **dentro** de un tag.
- **Siguiente (operación, tiempo real):** preflight → forward diario ≥4 días →
  `v2_80_market_window.py` → **`v2_83_window_audit.py`** → gate `--level evidence` → `AUTO-22`/`AUTO-23`
  → cierre de `P3-2`/`P3-3`. Comandos exactos en el
  [runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) (§2.1 cuenta fija, §2.2 pin,
  §3.1 PowerShell, §3.2 checklist).

## 7. Reglas duras (no negociables)

Freeze del worker y del gobernador intactos; `TOP_N=5` y umbrales `32/3/8/4/2` intactos; **sin migración**
(`046_fill_reference_mid`); reparto `auto18-v1`/`auto15-v1`; `ALLOCATION = none`; **forward, no replay**;
capturador y auditor **read-only**; veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si la ventana está
degenerada; **no** se cierra deuda por documentación: primero datos, después evidencia.
