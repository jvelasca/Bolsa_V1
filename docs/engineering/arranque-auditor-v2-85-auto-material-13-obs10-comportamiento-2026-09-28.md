# Arranque del auditor — `v2.85` / `AUTO-MATERIAL-13` (cierre de `OBS-10` + etiqueta de `unresolvedRate` + endurecimiento OPS)

> Trabaja **desde un clon fresco** de la rama **`feat/v2.85-obs10-comportamiento`** (o del tag
> `v2.85-beta` **cuando exista**) y **nunca** sobre el árbol local del propietario. Deja constancia de que
> no lo alteras: `git status --porcelain` vacío antes y después de cada sonda.

## 0. Contexto

Esta fase **cierra** la única observación real de la auditoría externa de `v2.84-beta`
([`auditoria-v2-84-…`](./auditoria-v2-84-auto-material-12-instrument-funnel-contract-2026-09-28.md)):
**`OBS-10` (LOW)** —el bloque `stateCounts` de `window_totals` recorría `rows` mientras el resto del
`TOTAL` usaba `measured_rows`—. Además **etiqueta honestamente** `unresolvedRate` (**sin** renombrar la
clave) y **endurece** `ops_seed_window_pair.py` para que no pueda acuñar una cuenta nueva en silencio.

Y **declara**, sin cerrarla, una observación nueva **`OBS-11` (LOW)**: la aritmética de `unresolvedRate`
hace `numerador == denominador` (número de días **medidos** en estado `unresolved`) ⇒ **indicador**
(`1.0`/`None`), no proporción. Se etiqueta; la pregunta aritmética se registra como deuda abierta.

## 1. Identidad del objeto

> **La fase NO está mergeada a `main` y el tag `v2.85-beta` está PENDIENTE.** A diferencial de las fases
> anteriores, **no** hay tag que clonar todavía: audita la **rama** (su commit final), no un sello. El tag
> se creará en `main` **tras** cerrar la ventana PAPER.

```powershell
git branch --show-current                       # feat/v2.85-obs10-comportamiento
git log -1 --oneline                            # HEAD de la rama (docs + código, sin merge a main)
git rev-parse "HEAD:apps" "HEAD:packages"        # 980c7b6e… / ffe36fd2…  (freeze de main INTACTO)
Select-String -Path package.json -Pattern version  # 2.10.0-beta
git merge-base --is-ancestor v2.84-beta HEAD; $?   # base = fd3859e3 (2.09.0-beta)
```

## 2. Puntos a comprobar

1. **Naturaleza del objeto**: rama sobre `63696d0c`, versión `2.10.0-beta`, árbol limpio; **sin** commit
   de merge a `main`.
2. **Diff acotado**: sólo los ficheros de §2 del [audit-pack](./audit-pack-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md);
   **ninguno** de la lista prohibida (motor, gobernador, `operability_window.py`, migraciones, UI,
   `TOP_N`/umbrales/allocation/pesos).
3. **`OBS-10`**: reproduce una fila `measured=False` **con** `state` poblado (p. ej. `"unresolved"`) y
   exige que `stateCounts` **no** cree bucket; una fila **medida** sí lo crea; `daysMeasured` no cambia y
   el `TOTAL` sigue cuadrando con `counts`/`funnel`.
4. **Docstring de `window_totals`**: declara que `stateCounts` **también** respeta `measured_rows`.
5. **`unresolvedRate`**: `_RATE_SOURCES`, el docstring de `window_rates` y el render `_rate_lines` lo
   declaran **indicador** (no proporción, no tasa de propuestas). **La clave NO se renombra** y la
   aritmética **no** cambia: ningún número publicado se mueve.
6. **`OBS-11` (LOW)**: queda **registrado** en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
   como observación **ABIERTA**; **no** se cierra en esta fase (es una declaración honesta, no un cierre).
7. **Endurecimiento OPS**: `ops_seed_window_pair.py` sin `--account-id` y sin `--allow-create` ⇒
   `# uso incorrecto: …` en `stderr` y **exit 1** **antes** de abrir PostgreSQL; con `--allow-create` la
   creación sigue siendo explícita. `_resolve_account(..., allow_create=False)` levanta `ValueError`
   defensivamente.
8. **Invariantes del instrumento intactos**: `rate=None` (nunca `0.0`) sin días/denominador; `render_window_audit`
   determinista y con `n/d`; `window_rates`/`window_audit` sin cambios de contrato.
9. **Read-only**: sin `--out` el CLI no escribe; `operability_runs/`, `evidence_runs/`, `evidence_validations/`
   y el journal durable no se tocan.
10. **Tests**: `test_operability_audit.py` **19 passed** (18 → 19); intenta **refutar** el test nuevo
    (¿pasaría con el código `v2.84`? **no** debe).
11. **Mutaciones**: matriz **232 → 233** medida **233/233**; `M233` muerde **exactamente** el test nuevo;
    restauración **byte a byte**; crudo en
    [`evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt`](./evidencia-matriz-mutaciones-v2.85-233-2026-09-28.txt).
12. **Compuertas**: `ruff` `All checks passed!`, `lint-imports` **4 kept / 0 broken**, `mypy` **0 issues
    (507 files)**, `alembic heads` `046_fill_reference_mid`, suite de aplicación **2085 passed / 5 skipped**
    (**2090** recogidos, eran **2089**). **Caveat:** los shims `mypy`/`lint-imports` estuvieron bloqueados
    por **Windows Application Control** (`os error 4551`); se corrieron por `python -m mypy` e
    `importlinter.cli` (las **mismas** herramientas).
13. **Cita del CI — `(pendiente)` por diseño.** `v2.85-beta` es la **siguiente auditoría externa** y **no**
    hay re-sello intermedio, pero **no** puede existir cita de CI de un tag que **aún no se ha creado** y
    que debe nacer en `main` **tras** cerrar la ventana. **No** concluyas «CI no acreditado»: es **PENDIENTE
    declarado**. Tampoco hay `evidencia-ci-tag-v2.85…` en esta entrega.
14. **Límites declarados**: `OBS-11` (nuevo), `P3-2`/`P3-3` **ABIERTAS** (exigen ventana PAPER real ≥4 días
    / ≥2 episodios / ≥32 ciclos), `H-4` **ABIERTO** (visible vía `warnings: reason_contract`),
    `OBS-9`/`P3-5`/`OBS-5` declaradas. **No** se cierra ninguna deuda por documentación.

## 3. Qué invalida la fase

- Que el diff toque un fichero **prohibido** (motor/gobernador/`operability_window`/migración/UI) o mueva
  `TOP_N`/umbrales/allocation/pesos.
- Que `M233` **no** muerda o que la matriz deje fragmentos sin medir.
- Que se haya **renombrado** `unresolvedRate` o **movido** su aritmética (la etiqueta es honesta, **no**
  un cambio de contrato publicado).
- Que se haya cerrado `P3-2`/`P3-3`/`H-4`/`OBS-11` **por documentación** (no puede: exigen datos o barrido).
- Que `ops_seed_window_pair.py` todavía pueda **acuñar** una cuenta nueva sin `--allow-create`.

## 4. Veredicto esperado

`APROBADO` / `APROBADO CON OBSERVACIONES` / `RECHAZADO`, con la lista de puntos PASS/PARCIAL/FAIL y, si
procede, hallazgos nuevos en la [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md). Recuerda que el
**tag y su cita de CI están PENDIENTES** por una restricción dura de la ventana PAPER viva: eso **no** es un
defecto de la fase, es su forma declarada.
