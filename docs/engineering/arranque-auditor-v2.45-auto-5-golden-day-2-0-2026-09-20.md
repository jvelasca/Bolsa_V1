# Arranque del auditor — v2.45-beta (AUTO-5 · Golden Day 2.0: el día real y su embudo)

**Fecha:** 2026-09-20 · **Ref a atacar:** `v2.45-beta` (`1.70.0-beta`) · **Pack que manda:**
[`audit-pack-v2.45-auto-5-golden-day-2-0-2026-09-20.md`](./audit-pack-v2.45-auto-5-golden-day-2-0-2026-09-20.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase, con sus
**desviaciones declaradas**, es
[`plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md`](./plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md) §7.

Este documento es de **solo lectura** y existe para una cosa: que el auditor externo no gaste su
presupuesto redisculpiendo lo ya medido. Cada afirmación trae **el comando exacto** para medirla.

---

## 1. Qué se instala aquí (y por qué importa)

AUTO-5 cierra el criterio «Hermetic Golden Path» del roadmap con un **día** certificado en **dos
capas**:

1. **Por commit (hermético):** el **embudo** del día — `seen == traded + rejected + expired + missed`
   — con **motivo** en cada estado no operado y **coste de oportunidad** declarado. La disciplina que
   lo hace auditable es la del repo: lo que no se puede medir se **declara** (`UNKNOWN`/`PARTIAL` +
   `notes`), **nunca** se publica como un `0` que se leería como "coste cero".
2. **Al sellar el tag (real):** el día lo conduce el **proceso real** del scheduler sobre
   **PostgreSQL real**, sin `run_tick()` manual y con gate fail-if-skipped propio.

Dos consecuencias que el auditor debe atacar:

1. **Un `0` puede sustituir a un "no medido".** Si el embudo, el coste o el MAE/MFE publican `0`
   cuando el dato falta, el día afirma más de lo que midió y el operador lee una decisión en silencio.
2. **La partición del embudo puede dejar de ser exhaustiva.** Si un estado fuera del vocabulario o una
   oportunidad vista sin fila **no** se declaran, `seen` deja de cuadrar y el día se da por bueno con
   oportunidades sin explicar.

---

## 2. Orden de ataque recomendado (por coste/beneficio)

### A1 · El embudo deja de ser una partición (lo más caro si falla)

```bash
sed -n '474,517p' packages/py/application/src/bolsa_application/auto_daily_journal.py
uv run pytest packages/py/application/tests/test_auto_daily_journal.py -q
```

Preguntas abiertas:

- ¿Todo estado cae en **exactamente** un cajón? Un estado fuera de `OPPORTUNITY_STATUSES` ¿deja el
  embudo **abierto** (`opportunity_status_unknown`) o se cuela contado?
- Una rechazada **sin motivo** ¿se declara (`rejection_without_reason`) o cierra el embudo en silencio?
- El `seen` **declarado por el productor** ¿se compara con las filas construidas
  (`funnel_seen_mismatch`) o se ignora? ¿Puede un `seen=None` fabricar un cierre falso?
- `funnel_closed` ¿exige `COMPLETE` o cualquier cosa que no sea `UNKNOWN`?

### A2 · Un agregado no medido se publica como 0 (coste de oportunidad y MAE/MFE)

```bash
sed -n '518,584p' packages/py/application/src/bolsa_application/auto_daily_journal.py
uv run pytest packages/py/application/tests/test_auto_daily_journal.py -q -k "cost or mae"
```

Preguntas abiertas:

- Sin `reference_price`/`subsequent_price` ¿el coste queda `UNKNOWN` + `opportunity_cost_unmeasured`, o
  sale un `missed_return = 0` "medido"?
- Un `reference_price == 0` ¿se trata como no medible (división) o revienta?
- Con **unas** rechazadas medibles y otras no, ¿el agregado es `PARTIAL` (declarado) o `COMPLETE`?
- MAE/MFE con **una** pata ausente: ¿`PARTIAL`/`UNKNOWN` + `mae_mfe_unmeasured`, o se da por completo?
- `mae_mfe`/`opportunity_cost` **vacíos** ¿son `UNKNOWN` (no medir) o `COMPLETE`?

### A3 · La identidad de estrategia viaja (o se inventa)

```bash
sed -n '337,374p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
sed -n '1740,1800p' packages/py/application/src/bolsa_application/auto_v2_entry.py
uv run pytest apps/api-python/tests/test_auto_v2_golden_day_evidence.py -q
uv run pytest apps/api-python/tests/test_auto_simulation_worker.py -q -k strategy_version
```

Preguntas abiertas:

- Sin versión, ¿la clave `strategyVersion` se **omite** del `payload` (la ausencia es información) o se
  rellena con `"unversioned"`?
- La fuente `auto-2.0:<version>` del pipeline V2 ¿se reconoce además de `active-strategy:`? (Si no, el
  fill/cierre del camino V2 queda con versión NULL y la atribución del día se pierde **en silencio**).
- El cierre ¿hereda la versión de la **posición** o de la propuesta del tick (que podría no ser la
  misma)?

### A4 · El día real (capa del tag): ¿qué certifica y qué no?

```bash
sed -n '1,140p' apps/api-python/tests/test_golden_day_v2_process_pg.py
grep -n "AUTO_GOLDEN_DAY_V2_PG_REQUIRED" .github/workflows/release-tag-ci.yml
grep -n "test_golden_day_v2_process_pg" .github/workflows/python-ci.yml .github/workflows/release-tag-ci.yml
```

Preguntas abiertas:

- Los ids de instrumento se eligen por **barrida pura** en el propio test: ¿el sweep garantiza **≥2
  tranchas** en BUY y **llenado completo** en SELL en la ventana del test? (Si no, el día es una moneda
  al aire ⇒ rojo espurio.)
- La **fase 2** lleva `holdingDeadlineAt` al pasado y **reinicia**: ¿el reinicio **rehidrata** el plan
  (techo congelado) y vende por `time_exit`, o el test estaría certificando otra cosa?
- ¿Qué **NO** certifica esta capa? El **cierre por geometría** (T1/trailing/régimen) y la
  **calibración** de MAE/MFE **no** se certifican aquí (ver §4 del pack y §7 del plan).

---

## 3. Mutaciones que YA se midieron (no las redisculpas)

La matriz completa está en §4 del pack. Las ocho mutaciones **mordieron** su suite y la sonda dejó la
**huella del árbol intacta**. Si encuentras una novena forma de romper el invariante que **no** esté en
la tabla, ese sí es un hallazgo.

---

## 4. Comandos exactos de verificación

```bash
# El gobernador NO se movió: debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Cubo estático
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# Capa hermética nueva
uv run pytest packages/py/application/tests/test_auto_daily_journal.py \
  apps/api-python/tests/test_auto_v2_golden_day_evidence.py \
  apps/api-python/tests/test_auto_simulation_worker.py -q

# Matriz de mutaciones (mide y restaura; deja la huella intacta)
uv run --no-sync python apps/api-python/scripts/v2_45_mutation_audit.py

# Capa real. CON PostgreSQL alcanzable se mide YA en local (sin el gate, un skip es honesto):
#   env AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1  →  un skip pasa a ser FALLO duro.
# OJO: no la corras en paralelo con otra sesión de pytest contra la misma base (el
# purgado de residuos del conftest borra las cuentas e instrumentos de la otra sesión).
uv run pytest apps/api-python/tests/test_golden_day_v2_process_pg.py -q --tb=short -rs
```

---

## 5. Qué NO es un hallazgo (declarado de antemano)

- Que el día real **no** cierre por T1/trailing/régimen: está **declarado** (precio SIM plano y
  horizonte de 21–90 días); el cierre por geometría se certifica en la capa **hermética**, y el día real
  dispara el `time_exit` por el **seam durable** (techo congelado → pasado → reinicio).
- Que el MAE/MFE **no** se calibre: se **recoge**, no decide (`AUTO-7`).
- Que la correlación sea la de hoy y no una matriz por pares: deuda declarada del roadmap.
- Que la identidad de estrategia viva en el `payload` JSONB **sin índice**: sin migración por decisión
  de fase (head `043`).
- Que `packages/py/application/tests/test_auto_daily_journal.py` ya estuviera en las listas offline: se
  añadió en `v2.42.2`.
- Que el **día real** no cierre por geometría, no atribuya por estrategia desde la BD y no lea MAE/MFE ni
  coste de la BD: está **declarado** en §7.1 del pack, con el motivo técnico (precio SIM plano, horizonte
  21–90 d, y el bucle AUTO SIM que acumula el journal **en memoria**). Los cinco puntos que no cubre la
  capa real los certifica la capa **hermética**.
- Que el día real **sí** se midió en local (`AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1` ⇒ `1 passed` en 10,05 s,
  seis corridas en solitario): el arranque del plan decía que no había PG alcanzable y el contenedor
  `bolsa-postgres` estaba **sano**.
- Que **no** se puedan correr dos sesiones de pytest en paralelo contra la misma base: el barrido de
  residuos del conftest borra cuentas e instrumentos `inst-%` al cerrar cada sesión. Es un límite de
  **método** del arnés, medido y declarado; el gate del tag corre el fichero en paso dedicado.

---

## 6. Formato del hallazgo

```
P0/P1/P2 · afirmación · ruta:línea · comando exacto · salida · ¿ya declarado en §4/§5/§7 del pack?
```

Las cifras del **tag** (`lifecycle-pg` con el día real) citan el run de `Release tag CI` que las produjo;
las locales citan el comando y su salida (§5 del pack). Ninguna cifra se atribuye a un artefacto que no
la produjo.
