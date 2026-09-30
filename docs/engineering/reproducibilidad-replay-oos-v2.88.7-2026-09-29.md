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
   `7 482 989` B, SHA-256
   `857C9F7D3F2CD43713080736B2C20E7CAE5C94E590A1B4626201D159A1C8279C`.
   *(Ese hash es el **posterior** al hallazgo de §6: el manifiesto declara ahora los **dos
   renders** del artefacto, lo que añade **365 B** al fichero. Su hash previo era
   `683A08DA…5603AC44` / `7 482 624` B; las 25 720 líneas de datos son idénticas.)*
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
render           CRLF (modo texto de Windows)
bytes            3393187  (sello 3393187 · mismo contenido en LF 3290062)
sha256           7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
sello (render)   7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
sha256 LF        A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB
sello (contenido)A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB
VEREDICTO        REPRODUCIDO (render del sello, byte a byte)
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

## 6. Hallazgo: el `sha256` del sello hasheaba **el render de Windows**, no la evidencia

La primera corrida del job (`workflow_dispatch` **`36627838819`**, `main`) puso `replay-repro` en
**rojo** con un número que no cuadraba con ninguna de las hipótesis de entorno:

```
bytes            3290062  (esperado 3393187)
sha256           A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB
esperado         7D998E4D7BCBA9DC2028D6274175C9A2C3099FAF3FE90B4DEFFBE47C804A0461
```

Antes de tocar nada se **descartó por medición** la lista de sospechosos habituales:

| Hipótesis | Cómo se probó | Resultado |
| --- | --- | --- |
| El `.env` local entra en el motor | replay con `load_dotenv` **neutralizado** | **no**: reproduce el sello (`7D998E4D…`) |
| Deriva de dependencias (`uv.lock` vs `.venv`) | entorno **limpio** creado desde el lock | **no**: mismas versiones (Python 3.12.13, SQLAlchemy 2.0.51, Pydantic 2.13.4) y mismo sello |
| Versión/imagen de PostgreSQL | `docker ps` + `docker-compose.yml` | **no**: `postgres:16-alpine` en ambos lados |
| Reloj/zona horaria | el artefacto **no contiene** ni un timestamp | **no**: 0 `ISO`-stamps, 0 `engine_id`, 0 `ULID` |

Para no depender de reproducir el runner a mano, el job se instrumentó (mismo commit) con un
**digest por secciones** (`replay_artifact_digest.py`, nuevo) y una **2ª corrida idéntica**. La
segunda corrida (`36636706369`) publicó esto:

| Sección | Runner (Linux) | Sello (Windows) | |
| --- | --- | --- | --- |
| `census` | `1237098` `45E4CC80CFBA6E5C` | `1237098` `45E4CC80CFBA6E5C` | **igual** |
| `replay` | `891272` `EE81E76CEE0995AA` | `891272` `EE81E76CEE0995AA` | **igual** |
| `score` | `24112` `96B3D601BAE8B99C` | `24112` `96B3D601BAE8B99C` | **igual** |
| `totals` | `{"decided":24500,"fills":752,"orders":210,"proposals":238,"vetoes":24303}` | idem | **igual** |
| `watch` (20 ids, orden) | `561` `40230635349BF2A0` | `561` `40230635349BF2A0` | **igual** |
| 2ª corrida del runner | idéntica a la 1ª (`cmp` = igual) | — | determinista |

Todas las **secciones** coincidían byte a byte y el runner era determinista consigo mismo, pero el
**fichero entero** no: luego lo que difería no era el contenido, era **cómo se escribía**. Medido
sobre los dos ficheros reales:

| | bytes | `LF` | `CRLF` |
| --- | --- | --- | --- |
| Sello (Windows) | `3 393 187` | **103 125** | **103 125** |
| Runner (Linux) | `3 290 062` | **103 125** | **0** |
| Diferencia | **103 125** | 0 | 103 125 |

`103 125` = **exactamente el número de líneas del JSON**: un `\r` por línea. Y la comprobación
cruzada cierra el caso:

- `sha256( sello con CRLF→LF )` = `A4DA036C…13CB` = **el hash del runner**;
- `sha256( artefacto del runner con LF→CRLF )` = `7D998E4D…0461` = **el hash del sello**.

**Conclusión.** El artefacto se escribe con `json.dumps(..., indent=2)` y el fichero se abría en
**modo texto**: en Windows el SO tradujo cada `\n` a `\r\n`. El `sha256` declarado
(`7D998E4D…`) no identificaba la **evidencia**, identificaba **su render en Windows**. La
evidencia es reproducible (ahora está probado sección a sección, y desde el runner), pero un
contraste por bytes del fichero **no podía pasar nunca** en Linux. No era un fallo del motor ni
del fixture: era el **contraste** el que medía la cosa equivocada.

### 6.1 El arreglo (el contraste pasa a medir el CONTENIDO)

`assert-artifact` declara ahora **los dos renders** y acepta ambos, diciendo cuál ha visto:

- `_SEALED_ARTIFACT_SHA256` / `_SEALED_ARTIFACT_BYTES` → `7D998E4D…` / `3 393 187` (render del sello);
- `_SEALED_ARTIFACT_SHA256_LF` / `_SEALED_ARTIFACT_BYTES_LF` → `A4DA036C…` / `3 290 062` (mismo contenido en `LF`).

El veredicto distingue los dos casos y **no admite trampa**: un fichero manipulado (probado
cambiando `"fills":752` por `753`) da **`NO reproducido`**, y si se pasan `--sha256`/`--bytes`
explícitos se exige **ese** render concreto (la vía normalizada solo vale contra los valores
sellados). El manifiesto del fixture publica los dos pares
(`expectedArtifactSha256(Lf)`/`expectedArtifactBytes(Lf)`).

**Deuda declarada (para el SIGUIENTE sello, no para este):** el escritor del replay debería fijar
`newline="\n"` — el del fixture ya lo hace (`replay_oos_input_fixture.py`, línea 191) — para que el
mismo contenido tenga **un solo** hash en cualquier SO. No se hace aquí a propósito: tocar el
script del sello invalidaría la cadena «el artefacto del tag lo produjo ESTE script» que este
trabajo precisamente acredita. Mientras siga así, el `sha256` del fichero **no** es portable y el
hash que identifica la evidencia es el **LF**.

### 6.2 Cierre: verificado en el CI (no en local)

Corrida **`36638231729`** (`workflow_dispatch`, `main`, commit **`4478fe89`**): **todo verde**,
`certify` incluido. Lo que dejó escrito el runner:

| Comprobación | Salida del runner |
| --- | --- |
| Sembrado | `# sembrado 20 instrumentos, 25700 barras D1` |
| Render del artefacto | `render LF 3290062 A4DA036C…13CB` |
| 2ª corrida del MISMO job | `VEREDICTO 2ª corrida IDÉNTICA (el runner es determinista consigo mismo)` |
| Digest por secciones | `census 1237098 45e4cc80cfba6e5c` · `replay 891272 ee81e76cee0995aa` · `score 24112 96b3d601bae8b99c` · `watch 561 40230635349bf2a0` · `totals {"decided":24500,"fills":752,"orders":210,"proposals":238,"vetoes":24303}` |
| Contraste con el sello | `VEREDICTO REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)` |
| Artefacto | subido (`replay-oos-durable-v2.88.7`, id `11065725850`) |

Los cinco digests de sección coinciden **exactamente** con los medidos en local sobre el sello: no es
una coincidencia de tamaño, es el mismo contenido **parte a parte**.

**Corrección de un diagnóstico previo de este informe.** El otro rojo de la primera corrida,
`lifecycle-pg`, **no** era determinista: esta corrida salió **verde** (`165 passed in 82,89 s`) tras
dos rojos con la misma firma (`AssertionError: RETRY` en
`test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once`, que es
el assert de la línea 327 leyendo `RETRY`). Es **intermitente**, y la sospecha previa —el camino de
**llenado parcial** que el repo documenta como «un chunk en `RETRY`»— quedó **refutada** en el repro local:
4 de 25 corridas directas con un lado `partial` **pasaron**, y exigir esquema **completo** no cambia nada
(`25/25`). La causa **sí** está acotada por código: ese `RETRY` solo sale de
`mark_retry(error="apply_ineffective")` cuando el applier devuelve `False`, y el applier lo devuelve o bien
si el resolver da `None` —descartado: el schedule se recomputa determinista con el MISMO
`venue_order_id`— o porque `ExecuteTrade.execute` **lanzó** y la excepción se **tragaba**. **No
reproducible en local:** 50 corridas directas del test objetivo + **9** del comando exacto de este job (BD
scratch fresca por iteración, una de ellas `165 passed, 0 skipped`) ⇒ **0 rojos** (**⚠️ CORRECCIÓN
POST-SELLO, `2026-09-30`: de esas `59` sólo `50` son válidas — la tanda de `50` murió con
`ProactorEventLoop` y las `8` del comando exacto no ejecutaron la suite; ver §3 de
[`evidence/v2.88.9/README.md`](./evidence/v2.88.9/README.md)**). **Arreglo aplicado:**
`simulated_finance._apply` registra ahora la traza (`logger.exception`) antes de devolver `False` —el
contrato no cambia: sigue fail-closed y **jamás** APPLIED por excepción— con gate
`test_applier_keeps_fail_closed_and_LOGS_the_swallowed_cause`, así que el **próximo** rojo del CI llegará
con causa. **No** afecta al sello del replay.

## 7. Límites de esta evidencia (lo que NO acredita)

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
- **NO** hace portable el `sha256` **del fichero** del sello: sigue siendo el render `CRLF` de
  Windows. Lo portable (y lo que ahora se asserta) es el **contenido** en `LF` (§6). El día que se
  re-selle con `newline="\n"` habrá **un** hash por contenido en cualquier SO.

## 8. Ficheros tocados

- `apps/api-python/scripts/replay_oos_input_fixture.py` (nuevo; `assert-artifact` por CONTENIDO, §6)
- `apps/api-python/scripts/replay_artifact_digest.py` (nuevo; digest por secciones + render)
- `docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson` (nuevo, 7,5 MB; manifiesto con los dos renders)
- `.github/workflows/release-tag-ci.yml` (job `replay-repro` + cableado en `certify`; huella del
  runner, digest por secciones y 2ª corrida, `upload-artifact` con `always()`)
- `.gitignore` (`/artifacts/`)
- este informe + `docs/engineering/evidence/v2.88.7/README.md`
