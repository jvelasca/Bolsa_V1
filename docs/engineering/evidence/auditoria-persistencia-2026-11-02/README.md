# Evidencia reproducible — auditoría de persistencia del workspace (2026-11-02)

Cierre de la auditoría de persistencia descrita en `docs/WORKSPACE_PERSISTENCE.md` §8.

Objetivo de este expediente: que cada afirmación del informe quede atada a **comandos
ejecutables** y a su **resultado medido** sobre el árbol que publica este commit, no a
fragmentos citados de una sesión. Lo que aquí se certifica es el árbol; la publicación
(commit, CI, tag y despliegue) se anota al final con su estado real.

- Rama: `fix/059-060-proveedores`
- Árbol auditado: el que publica este commit (el HEAD en el momento de la auditoría era
  `5012361f`, que es **solo documentación** y no contiene ninguna corrección)
- Entorno: Windows 10.0.26200, PostgreSQL local `localhost:5432`, Node 22 / pnpm 10.12.1,
  `ruff 0.16.2` (pin del `uv.lock`)

---

## 1. Aislamiento de datos

| Comprobación | Valor medido |
|--------------|--------------|
| BD usada por las pruebas | `bolsa_v1_audit` (y `bolsa_v1_gate`, creada para el gate, migrada a `062`) |
| `bolsa_v1` (desarrollo) antes y después | 1 workspace `7e503dd5` · 214 pestañas · `updated_at 2026-11-02 16:10:57.976+00` (idéntico antes y después) |
| API de desarrollo `:8000` | Nunca parada ni reiniciada (seguía escuchando al terminar) |
| Instancia de auditoría `:8010` | Levantada para la sonda, reiniciada a propósito, **detenida** al terminar; puerto libre |
| Fixture de la sonda | Borrado con `204`; `%TEMP%/bolsa_audit_fixture.json` eliminado |

Nota operativa: `conftest.py` de `apps/api-python/tests` purga residuos de test en el
teardown de sesión contra el `DATABASE_URL` vigente. Por eso **todas** las órdenes de esta
página se ejecutaron con `DATABASE_URL` apuntando a una BD de auditoría, nunca a `bolsa_v1`.

---

## 2. Gate de calidad

Ejecutado sobre el árbol completo (frontend, backend y documentación).

| Comando | Resultado |
|---------|-----------|
| `pnpm --filter @bolsa/shared build` | OK |
| `pnpm --filter @bolsa/shared typecheck` | OK |
| `pnpm --filter @bolsa/shared test` | **101 ficheros / 883 tests** + 1 todo |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | 0 errores, 23 warnings (deuda `react-hooks` previa) |
| `pnpm --filter @bolsa/web test` | **364 ficheros / 2728 tests** |
| `pnpm --filter @bolsa/web build` | OK |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | OK |
| `uv run lint-imports --config packages/py/.importlinter` | 4 contratos, 0 rotos |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **582 ficheros, 0 errores** |
| `uv run pytest` (misma selección y `--ignore` que el job `quality`) | **5966 passed, 1 failed, 1 skipped** |

La línea de Ruff no estaba en verde al empezar el gate: dos `I001` (orden de imports) en
`apps/api-python/src/bolsa_api/api/v1/routes/workspaces.py` y
`apps/api-python/tests/test_workspace_persistence.py` se corrigieron con `ruff --fix`. Con
eso el paso de Ruff de CI queda reproducido sin trampas.

### 2.1 La única prueba en rojo

`apps/api-python/tests/test_investor_profiles_assign.py::test_ensure_defaults_creates_one_shared_owned_profile`
falla **dentro de la suite completa** y pasa **en aislamiento** (`4 passed`). Se reprodujo
idéntico sobre dos bases distintas (`bolsa_v1_audit` y `bolsa_v1_gate` recién migrada), así
que no depende del estado previo de la BD. No la toca este cambio: el diff no modifica
perfiles de inversor ni cuentas. Ya estaba documentada como debilidad de restauración de
estado del propio test (AUD-06 en
`docs/engineering/evidence/cuentas-perfil-2026-10-30/diff-audit.md`): `_restore` cae a
`ensure-defaults` y deja de ser exacto cuando otra suite ha tocado la cuenta semilla.

No se ha «arreglado» aquí: es de otra área y el dictamen de esta incidencia no la cubre.

---

## 3. Pruebas de persistencia contra PostgreSQL real

```
DATABASE_URL=postgresql://bolsa:***@localhost:5432/bolsa_v1_gate
uv run pytest apps/api-python/tests/test_workspace_persistence.py -q --tb=short
9 passed in 7.50s
```

```
DATABASE_URL=postgresql://bolsa:***@localhost:5432/bolsa_v1_audit
uv run pytest apps/api-python/tests/test_workspace_persistence.py apps/api-python/tests/test_batch_caps.py -q --tb=short
14 passed in 5.93s
```

Cubren: dos PUT con la misma revisión no pueden ganar ambos (`[200, 409]`), 409 de revisión
obsoleta, 400 de revisión malformada (no fail-open), cierre compacto que poda `charts`,
`chartStateByListInstrument`, `list.visualizationEntries` y `chartListContext` huérfano,
cierre idempotente con revisión obsoleta que sigue dando 409, y persistencia del estado
podado tras reiniciar la aplicación.

### 3.1 Sonda de integración (proceso real + reinicio)

`probe_integration.py`, contra una instancia levantada para esta pasada:

```
DATABASE_URL=.../bolsa_v1_audit API_PYTHON_PORT=8010 uv run bolsa-api   # :8010
uv run --no-sync python docs/engineering/evidence/auditoria-persistencia-2026-11-02/probe_integration.py setup
```

```
[PASS] crear workspace fixture -> 201
workspace fixture: cf7bd31d9aa343cf8f87119d0
[PASS] PUT con revision vigente -> 200
[PASS] PUT con revision obsoleta devuelve 409 -> (409, {'code': 'workspace_conflict', ...})
[PASS] revision malformada devuelve 400 (no fail-open) -> (400, {'code': 'workspace_invalid_revision', ...})
[PASS] dos PUT concurrentes: exactamente uno gana -> [200, 409]
[PASS] cierre compacto de 2 de 3 pestanas -> 200
[PASS] respuesta del cierre: charts podado -> ['SAN']
[PASS] respuesta del cierre: visualizationEntries podado -> ['SAN']
[PASS] respuesta del cierre: snapshots podados -> ['estudio::SAN']
[PASS] respuesta del cierre: chartListContext huerfano eliminado
[PASS] respuesta del cierre: pestana activa recalculada
[PASS] cierre idempotente con revision obsoleta da 409 -> 409
```

Reinicio del proceso de API (kill + arranque nuevo), y entonces:

```
... probe_integration.py verify
```

```
[PASS] releer tras reiniciar la API -> 200
[PASS] la revision sobrevive al reinicio -> ('2026-11-02T16:28:57.500969+00:00', '2026-11-02T16:28:57.500969+00:00')
[PASS] post-reinicio: charts podado -> ['SAN']
[PASS] post-reinicio: visualizationEntries podado -> ['SAN']
[PASS] post-reinicio: snapshots podados -> ['estudio::SAN']
[PASS] post-reinicio: chartListContext huerfano eliminado
[PASS] post-reinicio: pestana activa recalculada
```

```
... probe_integration.py cleanup
[PASS] borrar fixture -> 204
```

---

## 4. Cambio de cableado en CI (necesario para que el commit sea verde)

`apps/api-python/tests/test_workspace_persistence.py` necesita PostgreSQL real y **no** lleva
guarda de skip (sin PG falla, que es lo correcto). El job `quality` no tiene PostgreSQL y
recolecta `apps/api-python/tests` entero, así que sin tocarlo el commit habría quedado en
rojo. En este árbol:

- `quality`: se añade `--ignore=apps/api-python/tests/test_workspace_persistence.py`
  (con el motivo en el bloque de comentarios, **fuera** del `run: >`).
- `lifecycle-pg`: paso nuevo «Pytest persistencia del workspace PG», tras `alembic upgrade
  head`, que ejecuta el fichero contra PostgreSQL real en cada push/PR.

`test_batch_caps.py` es hermético (solo valida topes de esquema Pydantic) y corre en
`quality` por el pase de directorio.

---

## 5. E2E

Los E2E `GP-V170-02` / `GP-V170-04` en verde con Chromium pertenecen al trabajo de
**columnas y panel de listas** (`apps/web/e2e/gp-v170-list-mercado-mock.spec.ts`), que viaja
en otro commit. `GP-V170-04` mide pistas de columna, `minWidth` compartido y scroll
horizontal del panel: no ejerce persistencia y no se usa como evidencia de esta sección.

---

## 6. Límites de este expediente

- **No** se ha creado tag ni release, ni se ha desplegado nada en `:8000`: la instancia de
  desarrollo sigue ejecutando el código anterior a estas correcciones.
- El workflow `gitleaks.yml` no se dispara con push a esta rama (solo `main`, `master`,
  `stage/**` y PR). El escaneo de secretos del commit se hizo a mano sobre el diff: sin
  credenciales, sin rutas absolutas y sin artefactos temporales.
- `ruff format` no está en verde en el repositorio (este árbol reformatearía 843 ficheros),
  y CI no lo ejecuta; no se reformateó nada para no meter ruido ajeno a la auditoría.
- La única prueba roja del punto 2.1 es preexistente y de otra área; queda fuera del
  alcance de esta incidencia.
