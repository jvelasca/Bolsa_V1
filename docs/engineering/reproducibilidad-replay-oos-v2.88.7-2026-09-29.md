# Reproducibilidad del artefacto del replay OOS durable — `v2.88.7-beta` (POST-SELLO)

**Fecha:** 2026-09-29 · **Fase:** POST-SELLO de `AUTO-MATERIAL-20` / `V2.88.7`
**Objeto:** cerrar el hueco de auditoría del artefacto de 3,39 MB del replay OOS durable.
**Motor:** **NO** se toca. **Esquema:** **NO** hay migración (Alembic head `046_fill_reference_mid`).

---

## 1. Origen: la pregunta que destapó el hueco

Al preguntar *«¿puedo auditar `v2.88.7-beta` desde GitHub?»* la respuesta honesta era **sí para todo
menos para el artefacto del replay**, y el motivo no era cosmético:

| Pieza del sello | ¿Auditable hoy desde GitHub? |
| --- | --- |
| Tag anotado → commit `5cbe84b0`, diff del motor | **Sí** (repo `PUBLIC`) |
| `Release tag CI` `36614230366` (11 jobs, logs) | **Sí** |
| 4 ficheros de evidencia versionados | **Sí** |
| **Artefacto del replay (3 393 187 B)** | **NO** |

El fichero vive en `operability_runs/`, que está en `.gitignore` (línea 102), y el CI **no podía
regenerarlo**: `v2_87_replay_oos_durable_cycle.py` **no es hermético** (hace `ensure_migrated`, lee
barras D1 reales con `SqlAlchemyOhlcvRepository` y sectores del catálogo), mientras que el
`db:seed` del repo **solo siembra instrumentos** (`packages/database/prisma/seed.ts` upserta 1
instrumento): las barras OHLCV vienen de un **sync externo** al proveedor.

**Medido, no supuesto:** un runner arranca con `ohlcv_bars` **vacía** → `census_operable_days` da
**0 días operables** → el script toma la rama `census_gate: 0 dias operables` y **no produce
artefacto**. No es que salga otro artefacto: **no sale ninguno**. El hash declarado en el README era,
por tanto, **una promesa sin forma de verificarla**.

## 2. Volumen real de la entrada (medido en la BD de desarrollo)

| Medida | Valor |
| --- | --- |
| Watch de la corrida sellada | **20** instrumentos (XETRA), en el orden que publica el artefacto |
| Ventana | `2021-12-07` → `2026-09-29`, **1 225** ticks |
| Barras D1 que exige la entrada | **25 700** (**1 285** por símbolo, `2021-09-14` → `2026-09-29`) |
| Ese subconjunto en la tabla | `source = yahoo`, `adj_close` **sin nulos**, todo `timeframe = 1d` |
| Catálogo entero (contexto) | **96 020** barras / **76** instrumentos / tabla de **44 MB** |

## 3. Qué se ha construido

1. **`apps/api-python/scripts/replay_oos_input_fixture.py`** (nuevo; CLI con `export`, `seed`,
   `verify`, `watch`, `assert-artifact`).
2. **`docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson`** — la **entrada congelada**:
   NDJSON con línea de **manifiesto** autodescriptiva + 20 instrumentos + 25 700 barras.
   `7 482 624` B, SHA-256
   `683A08DAF87999E30EFAAB6E111FA5B10EDA53DD7CC2D26FD9E20FF95603AC44`.
3. **Job `replay-repro`** en `.github/workflows/release-tag-ci.yml`: PostgreSQL de servicio →
   siembra el fixture → **regenera el artefacto con el MISMO script del sello** → **ASSERTA**
   SHA-256 y tamaño → sube el artefacto (`replay-oos-durable-v2.88.7`, 90 días) y su log.
   Cableado en `certify` (`needs` + guard `fail-if-any` + `summary`): **un rojo aquí no-GREENea el tag**.

**Fidelidad numérica.** Los valores viajan como el **TEXTO CANÓNICO de PostgreSQL** (`open::text`,
`numeric(18,6)`) y se re-insertan con `CAST(… AS numeric)`; los `timestamptz` van en ISO-8601 UTC con
microsegundos y los enums con su tipo (`"Timeframe"`, `"DataProvider"`, `"InstrumentType"`). **Sin
`float` intermedio**: un redondeo de 1e-6 cambiaría el artefacto. Se **omiten solo** `ohlcv_bars.id` y
`ohlcv_bars.created_at` (el replay **no lee ninguna**: `get_bars` no las selecciona) y queda declarado
en el manifiesto.

## 4. La prueba: reproducido **byte a byte**

La entrada **no** se verificó contra la BD de origen (eso sería circular). Se sembró en una base
**distinta** (`bolsa_v1_replay_fixture`, creada y migrada desde cero por el propio `seed` con
`ensure_migrated`) y se regeneró el artefacto con el script del sello **sin tocarlo**:

```
# 1) entrada congelada -> BD scratch
$env:DATABASE_URL='postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_replay_fixture'
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed \
    --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson
#    -> # sembrado  20 instrumentos, 25700 barras D1            (~5 s)

# 2) replay con el MISMO script y el watch del manifiesto
WATCH=$(uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py watch \
    --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py \
    --json --watch "$WATCH" --out /tmp/replay.json
#    -> 1225/1225 días · 2026-09-29 · fills=752 vetoes=24303 vivas=0 riesgo=0.00 libro=COMPLETE
#       (~82 s)

# 3) contraste con el sello
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py assert-artifact \
    --file /tmp/replay.json
```

```
artefacto        /tmp/replay.json
bytes            3393187  (esperado 3393187)
sha256           7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
esperado         7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
VEREDICTO        REPRODUCIDO
```

**`3 393 187` B y `7D998E4D…C804A0461` = el sello, desde otra base de datos.** La igualdad del hash
es lo que autoriza a **pasar el watch EXPLÍCITO** (lista sellada, mismo orden) en vez de versionar el
catálogo entero (76 instrumentos / 96 020 barras ≈ 4× más datos) para que la derivación por catálogo
volviese a elegir los mismos 20: la equivalencia **no se pide por fe, se mide**.

## 5. Hallazgo colateral (trampa latente del repo, declarada)

`packages/py/infrastructure/alembic/env.py` resuelve `DATABASE_URL` en `_resolved_url()`, pero
`run_migrations_online()` construye el engine con `engine_from_config(config.get_section(...))` —
esto es, **desde `alembic.ini`**— y **no** con `_resolved_url()`. Consecuencia medida: el **CLI de
Alembic IGNORA `DATABASE_URL`** en la ruta online (migra `bolsa_v1` y deja la BD apuntada intacta,
con salida `Running upgrade` **ausente** y **exit 0**), mientras que la ruta programática
(`ensure_migrated`, que inyecta `config.attributes["connection"]`) sí lo respeta.

Impacto: en los jobs existentes el `alembic upgrade head` apunta a `bolsa_v1`, que **es** la BD del
service, así que **acierta por coincidencia**. Aquí se evita la trampa por construcción: el job
**no usa el CLI de Alembic**; el esquema lo lleva a head el propio `seed` con `ensure_migrated`.
*(No se arregla en este cambio: tocar `env.py` afectaría a todos los workflows y merece su propio
análisis. Queda declarado.)*

## 6. Límites de esta evidencia (lo que NO acredita)

- **NO** acredita que la semántica de `OBS-20` sea correcta: reproduce **el mismo artefacto** que el
  sello; si el motor estuviera equivocado, el fixture reproduciría **el mismo error**. Es una prueba
  de **reproducibilidad**, no de **corrección**.
- **NO** acredita la corrida de `v2.88.7-beta` en su momento: el job se añade **después** del sello,
  así que ese tag se selló **sin** él. La primera certificación del job es la del **siguiente** tag
  (o la de un `workflow_dispatch`).
- **NO** cierra `OBS-15` (techo de **1000** `APPLIED`), `OBS-16`, `OBS-19` (deriva de las listas
  offline) ni `P3-2`/`P3-3`: el replay sigue usando **reloj simulado** y una sola cuenta/versión/watch
  con `pairActive=false`.
- **NO** versiona datos de mercado más allá del watch sellado (el resto del catálogo sigue sin
  congelar: si el sync cambia las barras del watch, el `export` produciría otro fixture y el job se
  pondría rojo — que es exactamente el comportamiento deseado).

## 7. Ficheros tocados

- `apps/api-python/scripts/replay_oos_input_fixture.py` (nuevo)
- `docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson` (nuevo, 7,5 MB)
- `.github/workflows/release-tag-ci.yml` (job `replay-repro` + cableado en `certify`)
- `.gitignore` (`/artifacts/`)
- este informe + `docs/engineering/evidence/v2.88.7/README.md`
