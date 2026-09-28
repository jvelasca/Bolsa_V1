# Arranque del auditor — `v2.84-beta` / `AUTO-MATERIAL-12` (INSTRUMENT FUNNEL CONTRACT)

> Trabaja **desde un clon fresco de GitHub** y **nunca** sobre el árbol local. Deja constancia de que no
> lo alteras: `git status --porcelain` vacío antes y después de cada sonda.

## 0. Contexto

Esta fase **cierra** tres hallazgos de tu predecesor ([auditoría de `v2.83.1-beta`](./auditoria-v2-83-1-auto-material-11-reseal-2026-09-27.md)):

- **`OBS-6` (MEDIUM)** — `enrich_rows_with_evidence` sobrescribía un funnel ya medido.
- **`OBS-7` (LOW)** — el funnel agregado de `window_totals` sumaba filas `measured=False`.
- **`OBS-8` (LOW)** — códigos de salida del CLI documentados inexactos.

Y **declara**, sin cerrarla, una cuarta observación **`OBS-9`** (doc-only, transversal al proyecto).

## 1. Identidad del objeto

```powershell
git cat-file -t v2.84-beta                        # tag (anotado)
git rev-parse 'v2.84-beta^{commit}'               # commit del sello
git rev-parse 'v2.83.1-beta^{commit}'             # base del diff
Select-String -Path package.json -Pattern version # 2.09.0-beta
```

## 2. Puntos a comprobar (13)

1. **Naturaleza del objeto**: tag **anotado**, versión `2.09.0-beta`, árbol del clon limpio.
2. **Diff acotado**: sólo los ficheros de §2 del [audit-pack](./audit-pack-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md); **ninguno** de la lista prohibida (motor, gobernador, `operability_window.py`, migraciones, UI, `TOP_N`/umbrales/allocation/pesos).
3. **`OBS-6`**: reproduce la sonda del predecesor (fila con `universe=8`, `orders=2`; evidencia nueva `watchSize=999`, `orders=99`) ⇒ los escalones medidos **sobreviven**; los `None` **se rellenan**.
4. **`OBS-7`**: fila `measured=False` **con** evidencia (`universe=8`) ⇒ **no** suma en `window_totals()["funnel"]`; `daysMeasured` no se contamina.
5. **`OBS-8`**: `python v2_83_window_audit.py --bogus` ⇒ `exit 2` **y** el docstring ya **no** promete `1`.
6. **Invariantes del instrumento intactos**: `rate=None` (nunca `0.0`) sin días/denominador; `render_window_audit` determinista y con `n/d`; `window_rates`/`window_audit` sin cambios de contrato.
7. **Read-only**: sin `--out` el CLI no escribe; `operability_runs/`, `evidence_runs/`, `evidence_validations/` y el journal durable no se tocan.
8. **Tests**: `test_operability_audit.py` **18 passed**; intenta **refutar** los dos tests nuevos (¿pasarían con el código `v2.83`? **no** deben).
9. **Mutaciones**: matriz **232/232** medida; `M231`/`M232` muerden **los dos tests nuevos**; restauración **byte a byte**.
10. **Compuertas**: `ruff`, `lint-imports`, `mypy` (**507** fuentes), `alembic heads` `046_fill_reference_mid`, suite de aplicación **2089 passed**.
11. **Registro en CI**: `test_operability_audit.py` sigue **explícito** en el job `quality` (`python-ci.yml`) y en el job `python` (`release-tag-ci.yml`).
12. **Cita del CI del tag `v2.84-beta` (patrón `OBS-3`/`OBS-4`) — LEER CON CUIDADO**: `Release tag CI`
    **solo corre al EMPUJAR** el tag, así que su resultado **no puede** existir dentro de ese mismo tag.
    Dentro del tag, `evidencia-ci-tag-v2.84-2026-09-27.txt` es un **PLACEHOLDER pre-tag** («PENDIENTE DE
    TAG») y, además, contiene un **ERROR ARITMÉTICO DECLARADO** en su predicción: escribe `esperado 3040`
    y `3029` porque sumó `18` sobre una base (`3022`/`3011`) que **ya** incluía los 2 tests nuevos. La
    predicción **correcta** es `3022/37` (job `python` del tag) y `3011/40` (job `quality`), y es
    **exactamente** lo que midió el CI. **No** se corrigió ninguna cifra observada: se corrigió la
    **fórmula**. La cita **acreditada** vive en los commits **POST-TAG** de `main` `1f2638aa` y
    `434f058d`; verifícala con `gh run view 36353503867` (SUCCESS, `headSha` `fd3859e3`).

    > **Aviso de instancia (auditor sobre el tag aislado):** esta misma frase, **dentro** del tag
    > `v2.84-beta`, dice «el tag lleva la cita del CI de la fase» — redacción heredada de `v2.83` que en
    > `v2.84` es **imprecisa**: en `v2.84` la cita del CI de la fase **es** la de este tag, y vive
    > POST-TAG. Usa **esta** versión (la de `main`) para el punto 12 y **no** concluyas «CI no
    > acreditado».
13. **Límites declarados**: `P3-2`/`P3-3` **ABIERTAS**, `H-4` **ABIERTO**, `P3-5`/`OBS-5`/`OBS-9`/`OBS-10` declaradas; **5 huecos locales preexistentes** de la matriz (`M117`/`M118`/`M170`/`M176`/`M197`).

## 3. Qué invalida la fase

- Que el diff toque un fichero **prohibido** (motor/gobernador/`operability_window`/migración/UI) o mueva
  `TOP_N`/umbrales/allocation/pesos.
- Que `M231`/`M232` **no** muerdan, o que la matriz deje fragmentos sin medir.
- Que se haya cerrado `P3-2`/`P3-3`/`H-4` **por documentación** (no puede: exigen material real).
- Que `enrich` siga pisando lo medido en algún camino (p. ej. si el `funnel` de la fila no es un mapping).

## 4. Veredicto esperado

`APROBADO` / `APROBADO CON OBSERVACIONES` / `RECHAZADO`, con la lista de puntos PASS/PARCIAL/FAIL y, si
procede, hallazgos nuevos en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
