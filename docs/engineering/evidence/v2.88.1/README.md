# Evidencia cruda — Corrección fail-OPEN del cierre de turno (`v2.88.1`, 2026-09-29)

Resumen **verificable** del RE-SELLO que sustituye a `v2.88-beta`. Incluye el **rojo original** (no se
borra: es parte de la evidencia) y la corrección con su prueba de causalidad. Las cifras están
transcritas de las corridas, sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-16` (`v2.88.1`) — corrección fail-OPEN del cierre de turno |
| Versión de paquete | `2.11.0-beta` → **`2.11.1-beta`** |
| Tag (lo crea el propietario) | **`v2.88.1-beta`** (anotado) |
| Tag SUPERADO | **`v2.88-beta`** (público, `Release tag CI` **rojo**, ver §1) |
| Base del diff | **`3483b6b5`** (mismo punto de partida; `v2.88-beta` = `564240d2`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Diff de la corrección | **4 ficheros, +128 / −16** |

## 1. El rojo que motiva el RE-SELLO (`v2.88-beta` = `564240d2`)

| Workflow | Resultado |
| --- | --- |
| Gitleaks | success |
| Python CI | success |
| Fase 2 scientific | success |
| Frontend CI | success |
| Optimize lab | success |
| **Release tag CI** | **failure** |

`Release tag CI` run `36544461660` (`https://github.com/jvelasca/Bolsa_V1/actions/runs/36544461660`):

| Job | Resultado |
| --- | --- |
| decision-spine | success |
| shared | success |
| frontend | success |
| **python (ruff/imports/mypy/pytest offline)** | **success** ← el `mypy` que no se pudo medir en local queda medido aquí |
| playwright (mock E2E) | success |
| dr-verify | success |
| a7-gate | success |
| security (gitleaks) | success |
| **lifecycle-pg (Alembic + auth + golden restart)** | **failure** |
| **certify (aggregate + artifact)** | **failure** (agrega el anterior) |

Aserto exacto del fallo:

```
Pytest Crash/Recovery Day (proceso scheduler matado en sucio + PG, fail if skipped)
E AssertionError: la muerte debe ocurrir con el fill PARCIAL durable (cola de reserva viva);
                  reservas vivas: []
1 failed in 122.54s (0:02:02)
```

## 2. Prueba de causalidad

| Experimento (árbol local, mismo PG de desarrollo) | Resultado |
| --- | --- |
| `git checkout HEAD~1 -- …/auto_simulation_worker.py` (revierte SOLO el cierre de turno) + el test | **1 passed in 8.87s** |
| Con el cierre de turno activo + el mismo test | **1 failed** |
| CI sobre **Postgres 16 nuevo + `alembic upgrade head`** | **falla idéntico** ⇒ no es estado de BD local |

Comando del test:

```
uv run --no-sync python -m pytest \
  "apps/api-python/tests/test_crash_recovery_day_process_pg.py::test_crash_recovery_day_real_process_survives_dirty_kill_pg"
```

**Nota de honestidad:** en la corrida local completa de `apps/api-python/tests` (7 failed, 754 passed)
se atribuyeron los 7 fallos a estado obsoleto de la BD local. **Uno de ellos era esta regresión real.**
Los otros seis: contenido sembrado (`assert 17 == 26`), `403` de auth y `test_workspaces_crud`
(dependiente de orden: pasa en aislado).

## 3. Validación tras la corrección

| Medición | Comando | Resultado |
| --- | --- | --- |
| Crash/recovery PG | `pytest apps/api-python/tests/test_crash_recovery_day_process_pg.py` | **1 passed** (8,32 s) |
| Batería motor + instrumento | `pytest` sobre 7 ficheros (crash PG, durable cycle, partial fills, worker integration, cli renderers, replay_oos, replay_oos_durable_cycle) | **105 passed** (9,76 s) |
| Estilo | `ruff check --config pyproject.toml` | limpio |
| Mutaciones `M245`–`M248` | `python apps/api-python/scripts/v2_44_mutation_audit.py M245 M246 M247 M248` | **4/4 detectadas**, `medidas: 4/4`, árbol intacto |

Salida del arnés de mutaciones (transcrita):

```
### M245 (render contra el dataclass): …
  rojo en: test_both_renderers_agree_on_the_same_payload, test_v86_census_renderer_accepts_the_dict_that_main_passes, test_v86_census_renderer_declares_an_empty_sample
### M246 (cierre de turno revertido): …
  rojo en: test_closing_reconcile_keeps_captured_unapplied_capital_in_flight, test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn, test_two_real_turns_do_not_drip_the_book_between_them
### M247 (cierre re-atribuye fills): …
  rojo en: test_closing_reconcile_keeps_the_live_tail_of_a_partially_filled_order
### M248 (costura re-atribuye fills): …
  rojo en: test_close_tick_does_not_re_attribute_fills
  medidas: 4/4 (ninguna se quedo sin fragmento)
```

`M247` (nueva) reproduce la regresión exacta: con `attribute_fills=True` en el cierre de turno, la
reserva parcialmente llenada pasa de `remaining_qty = 10.0` a `6.0` (`assert 6.0 == 10.0`). `M248`
(nueva) fija el mismo contrato en la costura del replay. `M246` se **re-ancló**: su fragmento anterior
(`startup=False)` sin parámetro) ya no existía en el fuente y el arnés declara y falla los fragmentos
desaparecidos, en vez de fingir cobertura.

## 4. Contenido del diff de la corrección (4 ficheros, +128 / −16)

| Fichero | Cambio |
| --- | --- |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `attribute_fills` en la firma + guarda `if attribute_fills and fill_qty > 0` + cierre de turno con `attribute_fills=False` + docstring de la regla |
| `packages/py/application/src/bolsa_application/replay_oos.py` | `close_tick` cierra con `attribute_fills=False` + docstring de la no idempotencia |
| `apps/api-python/tests/test_auto_v2_durable_cycle.py` | `test_closing_reconcile_keeps_the_live_tail_of_a_partially_filled_order` + `test_close_tick_does_not_re_attribute_fills` + dobles actualizados a la firma nueva |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M247` + `M248` (matriz `246` → `248`) + re-anclaje de `M246` |

## 5. Límite declarado (no se maquilla)

- El artefacto multianual del instrumento `v2.87` se midió con la costura **previa** a esta guarda, es
  decir con un libro que drenaba la cola viva de las órdenes parcialmente llenadas. **Sus cifras no son
  reproducibles con el código sellado** y **exigen re-ejecución**; no se usan como evidencia de
  estrategia ni para mover `P3-2`/`P3-3`.
- `mypy` **NO MEDIDO en local** (Windows Application Control bloquea `mypy.main` y `uvx`): se cita el
  resultado de CI del tag, que sí lo ejecuta en el job `python (ruff/imports/mypy/pytest offline)`.

## 6. CI del objeto de este sello (`v2.88.1-beta`) — **ROJO, citado POST-TAG**

> **[SUPERADO por `v2.88.2-beta` y, después, por `v2.88.3-beta`.]** El objeto de auditoría vigente es
> **`v2.88.3-beta`**: ver [`evidence/v2.88.3/README.md`](../v2.88.3/README.md). Esta evidencia se conserva
> **verbatim** (su rojo es parte de ella).

`Release tag CI` run [`36548125321`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548125321)
(8m58s): `shared`, `frontend`, `playwright (mock)`, `decision-spine`, `security`, `dr-verify` y
**`python (ruff/imports/mypy/pytest offline)`** = **success**; cae **`lifecycle-pg`** en el paso
`Pytest Concurrent AUTO` (`test_concurrent_auto_pg.py`, **`FFF`**):

```
AssertionError: lo liberado por fill debe ser exactamente lo materializado:
              released=200.000000 materializado=147.000000
```

Los cinco workflows de `main` del **mismo commit** fueron **todos verdes**: Python CI
[`36548121882`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548121882) · Frontend CI
[`36548121855`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548121855) · Optimize lab
[`36548121901`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548121901) · Fase 2 scientific
[`36548121839`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548121839) · Gitleaks
[`36548121852`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36548121852).

Es decir: **la guarda `attribute_fills` de este sello funcionó** (el crash/recovery pasó) y dejó a la vista
el **segundo** defecto fail-OPEN, la **carrera entre sesiones**, corregida en `v2.88.2`. Traza y prueba de
causalidad: [`evidence/v2.88.2/README.md`](../v2.88.2/README.md) §1–§3.
