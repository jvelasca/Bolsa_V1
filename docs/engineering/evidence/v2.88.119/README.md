# Evidencia `v2.88.119-beta` — `R-ev`: regeneración del artefacto OOS `K=12` en el esquema `oos-finance-band-v4`

> **Sello:** `v2.88.119-beta` (base `v2.88.118-beta`).
> **Bump:** `2.11.118-beta` → **`2.11.119-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
> **Naturaleza:** sello **de evidencia/servicio** · **`Δ motor = 0`** (el único cambio en `src` es la **etiqueta** `meta.bump` de los CLIs; **no** cambia lógica de decisión/ejecución) · **`Δ decisión = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP SIN cambio** (las bandas son **ficheros**, no endpoints) · **SIN cambio de forma de artefacto** (`SCHEMA_VERSION` **NO** se toca; el generador ya emitía `oos-finance-band-v4` desde `v2.88.117`).
> **Cierra:** residuo **`R-ev`** (regenerar `finance-band-w32-k12.json` con el esquema nuevo).
> **Fecha:** 2026-10-13.

---

## 1. Qué cambia (servicio de evidencia, Δ motor = 0)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Artefacto regenerado** | [`finance-band-w32-k12.json`](./finance-band-w32-k12.json) | Banda OOS `K = 12` **remedida** y publicada en el esquema vigente **`oos-finance-band-v4`** (antes sólo existía el artefacto sellado de `v2.88.114` en **`oos-finance-band-v1`**). `meta.bump = 2.11.119-beta`. |
| **Log de la corrida** | [`finance-band-w32-k12.log`](./finance-band-w32-k12.log) | Salida cruda de los 12 sorteos + agregado (autochequeo del sello y hashes `LF` por sorteo). |
| **Bump** | [`package.json`](../../../../package.json) + 10 CLIs | `2.11.118-beta` → `2.11.119-beta`. El **único** cambio de código es la cadena `meta.bump`; ninguna rama de lógica se modifica. |

Los artefactos sellados anteriores (`v2.88.114/finance-band-w32-k12.json`, esquema `v1`) **no se tocan**:
la regeneración se publica como artefacto **nuevo** bajo este sello, para que la evidencia histórica siga siendo inmutable.

---

## 2. El residuo `R-ev` y su cierre (corrección de una premisa ambiental)

**Qué era `R-ev`.** Los sellos `115`, `116`, `117` y `118` endurecieron la banda OOS
(`oos-finance-band-v1` → `v2` → `v3` → `v4`), pero el **artefacto de evidencia sellado** de `v2.88.114`
seguía en `v1`. `R-ev` es «**regenerar** `finance-band-w32-k12.json` con el esquema nuevo».

**La premisa que se corrige.** Las evidencias `115`/`116`/`117`/`118` declaraban que regenerarlo
«exige PostgreSQL sembrado ⇒ **no reproducible sin PG**». Esa afirmación era cierta **sólo como
suposición del entorno** (no había PostgreSQL levantado en la máquina de esos sellos), **no** como
imposibilidad del instrumento. En este entorno **sí** hay PG (`bolsa-postgres`, `healthy`, `5432`) y la
base `bolsa_v1_replay_w32` **ya estaba sembrada** con el fixture `v2.88.7` ⇒ `R-ev` **es reproducible y
se ha ejecutado**. La distinción importa: *«no reproducido en este entorno»* ≠ *«no reproducible»*.

---

## 3. Procedimiento reproducible (comando EXACTO)

Orquestador opt-in `v2_87_replay_oos_durable_cycle.py` con `--finance-band 12`
(re-sorteo del ancla `seed=fill_seed(bar_tick_now + k, symbol)` sobre el **mismo** dato histórico),
apuntando `DATABASE_URL` a la base sembrada y pasando el **sello del sorteo 0** como autochequeo:

```powershell
$env:DATABASE_URL = "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_replay_w32"
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py `
  --watch "0a5dc12fd5a24f0a89a91d36a,0cf0907837fc422db221b0149,240a4ae01a944d3bba1cf1b24,31f9a597d03249319ea0c9345,381dd3b0699a44e8b9d13ac13,49596ff25acb4294b265f321b,4d24ea029283461cb9304421a,54283bcb54674ec1b70b4db72,5a130eea1ad54dcaaa50b67b9,5c34aaec1448406ebec94b20f,615d243eb830473ab009c8997,6655c5faff8a458186dcd8adc,67c117a7d88f4c75a7174e998,6db46176cc2d4845845b6ee6e,6f6215d935c04e0f9ac7bfef7,74c66a856dde4cbaad4888908,7721cde9af0c49d29576786d5,840a307d2b074e2db4dfc3373,856510e40dda4c758f4d4df89,8601a0c3f8d248b0b8052b963" `
  --account-id 1484e253d2d54645945a6b1d7 --version-a v283-window-a --venue paper `
  --finance-band 12 `
  --finance-band-out operability_runs/oos-finance-band-r-ev-119/w32-band.json `
  --finance-band-seal 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7
```

- `--finance-band-seal` es el SHA-256 (LF) del **payload del sorteo 0 sin parchear**; si no reproduce,
  la sonda sale con **código 2** (autochequeo del instrumento). Aquí salió **código 0** ⇒ el motor
  **no se movió** entre `v2.88.114` y `v2.88.119`.
- Salida: `w32-band.json` (esquema `oos-finance-band-v4`), copiada a esta carpeta.

---

## 4. Resultado (`Δ medición = 0`, sólo cambia la forma)

- **Esquema:** `oos-finance-band-v1` → **`oos-finance-band-v4`**; `draws = 12`, `design = "venue_draw"`,
  `statisticalConfidence = NOT_MEASURED` (la banda mide **sensibilidad al sorteo del venue**, no
  incertidumbre estadística), `sensitivityBand.crossesZeroNetReturn = true`, `pointCitable = false`.
- **Delta de forma `v1` → `v4`** (claves): top-level gana `design`; por grupo gana
  `strategyPresetKeys`/`strategyPresetKeyAmbiguous`; `validity` se reestructura en
  `sensitivityBand` (`crossesZeroNetReturn`, `pointCitable`, …) + `statisticalConfidence`
  (con `design`, `status`, `reason`, `provenance`, `missingProvenance`) y añade `crossesKey`.
- **La medición es IDÉNTICA a la de `v2.88.114`** (por diseño, mismo motor + mismo dato + mismo fixture):

| Nivel | `v2.88.114` (`v1`) | `v2.88.119` (`v4`) | ¿Igual? |
| --- | --- | --- | --- |
| Agregado `netReturnPct` | `{n:12, min:-3.398126, median:-0.7028965, max:0.515323, mean:-0.8613163, stdev:1.0195998}` | *idéntico* | ✅ |
| Bandas por grupo (10 grupos) | 10 grupos | *idénticos* | ✅ |
| `drawsWithCell` por grupo | `[12]*10` | `[12]*10` | ✅ |
| `crossesZeroNetReturn` / `pointCitable` | `True` / `False` | `True` / `False` | ✅ |

- **Sellos de los 12 sorteos** (SHA-256 LF, idénticos a los de `v2.88.114` ⇒ el autochequeo `k=0`
  coincide con `_SEALED_ARTIFACT_SHA256_LF`):

| `k` | SHA-256 (LF) | Reporte |
| --- | --- | --- |
| 0 | `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` | `draw-00.finance.json` |
| 1 | `CD59FEB83D64BDDF499CBF69DF58A9C44383CB3ED6CACEFA38E2789F41537D6A` | `draw-01.finance.json` |
| 2 | `7891A0327F9DD93C205172C44854BEF7C456FAF39A72279C2879ECD3E1D595AF` | `draw-02.finance.json` |
| 3 | `1001E0D1D0DA84A4AF03F974964CAEFD5A7AE7A898EF2D889E346B7231715751` | `draw-03.finance.json` |
| 4 | `F6F65AFC8A43C7D88C32F8317A339DBBEF57B4262D2E5E5EBDDCBE5BEC1EC2D8` | `draw-04.finance.json` |
| 5 | `C034436454884824238E9A2C41C9E07466DABC67E047D0D37F874752FE3B460D` | `draw-05.finance.json` |
| 6 | `5B4C7A29FE9CF5409F5E1AAC6F1A9F4EBDC08E39849A252727E43842F22942D8` | `draw-06.finance.json` |
| 7 | `E44D86B63B1A4C845F08D0EA12FD57462E8F5344E56004FBA967316FE1D2DF59` | `draw-07.finance.json` |
| 8 | `314980A17C936E4A11D9F71363D423DD4D1237D2D369C9FD8DF2EFF560D7C5B9` | `draw-08.finance.json` |
| 9 | `DC7B128CF264CFD8573A8D34B5F865BACC7D4AC0CC57D02135E22F80207A5529` | `draw-09.finance.json` |
| 10 | `522EE3DDF7686D70EEC3A56E6FEB411FEA68E5C5D331658DB27E06E4A41F7CA6` | `draw-10.finance.json` |
| 11 | `D9C97343717BF0467B38C1B22791A1BA369FDDB209B765B50966235173E49C9A` | `draw-11.finance.json` |

- **Sello del artefacto publicado** (`finance-band-w32-k12.json`, 48 026 B):
  `sha256 (LF)` = `21d7159e2afaf2f49ad0fe56747b7917ae3aacea24bfe11ab8288dd05927a71d`
  · `sha256 (raw CRLF)` = `dc70cbde34d13ff9294a4cb12227b7388d487dfdc46f1660d2e54ec03eec1f38`.

---

## 5. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy packages/py/application/src --follow-imports=silent` | ✅ `Success: no issues found in 263 source files` |
| `pytest packages/py/application/tests -q` | ✅ **2706 passed** (175.42 s) — **sin cambio** respecto a `v2.88.118` (este sello no añade pruebas: no añade lógica) |
| focales (`test_dia_d_multi_uncertainty` + `test_oos_finance_band` + `test_replay_oos_cli_renderers`) | ✅ **49 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | ✅ **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |
| **Autochequeo del instrumento** (`--finance-band-seal`, 2 corridas) | ✅ **exit 0** ⇒ sorteo 0 reproduce `1E3ADAC2…929A37E7`; los 12 `LF` coinciden con `v2.88.114` |

---

## 6. Límites declarados

- **Es un sello de SERVICIO de evidencia, no de motor.** `Δ motor = 0`: el único cambio en `src` es la
  etiqueta `meta.bump`; no se toca lógica de banda, decisión, ejecución, umbrales, `TOP_N`, régimen ni reparto.
- **La banda NO es rentabilidad demostrada.** `K = 12` mide la **sensibilidad al sorteo del venue** sobre el
  **mismo** dato histórico; `statisticalConfidence = NOT_MEASURED` y `pointCitable = false`. Regenerar el
  artefacto **no** añade evidencia de rentabilidad: sólo pone la evidencia anterior en el esquema vigente.
- **`Δ medición = 0` (por diseño), no `Δ medición` nuevo.** Al ser mismo motor + mismo fixture + mismo dato, el
  resultado **debía** coincidir con `v2.88.114`; la coincidencia (agregado, bandas por grupo y los 12 `LF`) es
  a la vez **prueba de reproducibilidad** y **autochequeo** de que el motor no se movió.
- **Reproducibilidad supeditada al entorno.** `R-ev` se reproduce **con PostgreSQL sembrado** (`bolsa_v1_replay_w32`
  + fixture `v2.88.7`). Sin ese entorno, el instrumento **no** fabrica el artefacto: el autochequeo de frescura
  abortará en lugar de plegar reportes viejos (`H3`).
- **Tag `unsigned`:** el tag anotado **no** está firmado.

---

## 7. Cita POST-TAG

Tag anotado **`v2.88.119-beta`** (objeto `b9e62316` → commit `3b069ce4`) sellado y publicado en `origin`
(`git ls-remote origin refs/tags/v2.88.119-beta*` resuelve objeto + `^{}`); `origin/main` == `HEAD` == `3b069ce4`.
Tag **anotado sin firmar** (`unsigned`) — declarado, no disimulado.

- `Release tag CI` [**38364511593**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364511593) → **`success`** (`12m28s`): **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado). **`replay-repro`** → **`success`** (`3m9s`): regenera el artefacto congelado del sello desde el fixture ⇒ este sello (bump + documentación + artefacto de banda) **no** toca el payload del replay (`Δ decisión = 0`).
- `Python CI` [**38364511626**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364511626) `success` (`2m0s`) · `Frontend CI` [**38364511628**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364511628) `success` (`3m26s`) · `Fase 2 scientific` [**38364511673**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364511673) `success` (`1m25s`) · `Optimize lab` [**38364511669**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364511669) `success` (`1m31s`).
- CI de **rama** (`main`, `3b069ce4`): `Python CI` [**38364509509**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364509509) `success` (`3m7s`) · `Frontend CI` [**38364509505**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364509505) `success` (`4m12s`) · `Optimize lab` [**38364509474**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364509474) `success` (`1m33s`) · `Gitleaks` [**38364509494**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38364509494) `success` (`17s`).
- **Anotaciones del run:** solo avisos **preexistentes** y ajenos al diff (deprecación de Node 20 en `actions/*`, migración `ubuntu-latest`→26, `react-hooks/exhaustive-deps` en `apps/web`). **Ninguna** referida a la banda OOS.
- **Distinción:** *estado comunicado* (artefacto regenerado y verificado localmente, autochequeo `exit 0`) vs *verificación externa* (tag/commit/run resueltos en GitHub) — aquí **ambos** confirmados. El sello **no** demuestra rentabilidad.

**Cierre POST-TAG en `main`:** commit de documentación `39e43070` (`origin/main` == `HEAD` en el momento del cierre); CI de rama → solo `Gitleaks` [`38366721591`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38366721591) `success` (`14s`), porque los workflows de código **no** disparan en commits `docs`-only (mismo patrón que los cierres de `116`/`117`/`118`).
