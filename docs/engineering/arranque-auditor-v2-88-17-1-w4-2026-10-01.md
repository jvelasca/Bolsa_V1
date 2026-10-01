# Arranque del auditor — `v2.88.17.1-beta` / `GRANULARIDAD-OPERATIVA`: proveedor de precio REAL del motor AUTO (tras interruptor) + bundle direccional del OOS + robustez del instrumento OOS

> **Objeto auditado:** tag anotado **`v2.88.17.1-beta`** → **`6221700c`** · **Versión:** `2.11.17.1-beta`
> (**bump** `2.11.16.3-beta → 2.11.17-beta → 2.11.17.1-beta`) · **Base (diff):** **`v2.88.16.2-beta`**
> · **AsOf:** 2026-10-01 · **Alembic head:** **`046_fill_reference_mid`** (**SIN migración**).
> **Remote:** `github.com/jvelasca/Bolsa_V1.git` (**PÚBLICO** — clon anónimo).
> **Naturaleza:** **`src` de producto SÍ cambia** (8 ficheros, `+728 / −90`) pero **todo el
> comportamiento nuevo está tras un interruptor apagado por defecto** (`AUTO_ENGINE_SIM_REAL_PRICE`).
> **Audit-pack (tesis falsables + compuertas):** [`audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md`](./audit-pack-v2.88.17-w4-bundle-direccional-2026-10-01.md).
> **Entrega (preguntas concretas + prompt):** [`entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md`](./entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md).

---

## 0.0 Cómo se lee esta entrega (hazlo antes que nada)

Los documentos de auditoría viajan **POST-TAG en `main`**, **no** dentro del tag. Es la **misma razón
estructural** que la cita del CI (§1.1, límite `OBS-3`/`OBS-4`): el tag `v2.88.17.1-beta`
(`6221700c`) es **inmutable** y se selló **antes** de que existiera esta entrega. Reescribir el tag para
meter los `docs` lo invalidaría — no se hace.

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1

# (A) LEER la entrega  -> rama main (default tras el clon)
ls docs/engineering/arranque-auditor-v2-88-17-1-w4-2026-10-01.md

# (B) VERIFICAR el producto -> el tag
git checkout v2.88.17.1-beta
```

Consecuencia esperada y **no** un error: dentro del tag **no** existen
`docs/engineering/arranque-auditor-*`, `audit-pack-*`, `entrega-auditoria-*` ni
`criterio-salida-beta-*`. Están en `main`, un commit **después** del tag.

---

## 0. Qué se audita (y qué no)

Se auditan **tres objetos dentro de un mismo tag**, más un **hotfix de arnés**:

1. **`W3.3`** — el replay OOS es un **sorteo del venue** y su banda `K = 12` **cruza el cero**. Es
   **instrumento** (cero `src` de producto).
2. **El bundle direccional** — `replay_oos._realized_r` era **long-only** y la regla direccional estaba
   duplicada en cuatro módulos; ahora hay **una sola casa**.
3. **`W4`** — el **seam de precio** que puede decir «**no hay precio**» y el **proveedor real** sobre la
   frontera de barras cerradas de `W3`. **Apagado por defecto.**
4. **`W4.1`** — hotfix **test-only** del sorteo del arnés del certifier `A11` que puso rojo el tag
   `v2.88.17-beta`.

**NO se audita** (declarado, ver audit-pack §5): `W5` (el `ProtectionClock` sigue en el minuto), `W6`,
`OBS-19` (causa estructural), la convergencia de la regla direccional en los otros 4 módulos, ni la
ventana PAPER real (`P3-2`, sin arrancar).

**La pregunta de fondo para el auditor:** ¿se puede sostener que **encender** `AUTO_ENGINE_SIM_REAL_PRICE`
en un despliegue PAPER es seguro y honesto **con lo que hay sellado**, o falta algo que este sello no
dice que falte?

---

## 1. Cita del CI (lo primero que hay que comprobar)

### 1.1 CI del tag — **POST-TAG** (límite estructural `OBS-3`/`OBS-4`)

`Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado **no puede** preexistir dentro del
propio tag: la cita del run **verde** viaja en `main`, en un commit **POST-TAG**. Comprobación:

```bash
git log --format=%h:%s -5 --grep "cita POST-TAG del CI del tag v2.88.17.1-beta"
gh run view 36848732534          # o: gh run list --workflow "Release tag CI" --limit 5
gh run view 36848732534 --json conclusion,jobs -q '.conclusion, (.jobs[] | "\(.name): \(.conclusion)")'
```

**Esperado:** `conclusion=success` con **11 jobs `success` + 1 `skipped`** (`playwright (integrated E2E,
opt-in)`, por diseño) y `certify` **GREEN**.

### 1.2 Cadena de tags de este tramo (dos tags, uno de ellos ROJO)

| Tag | Estado | Por qué |
| --- | --- | --- |
| `v2.88.17-beta` (`cfd13f54`) | **ROJO** en `lifecycle-pg` (run `36845274700`) | **sorteo del arnés** del certifier `A11` (`uuid4()`) + `seed` del venue anclado a la barra desde `W3`; en ese mismo run `python` (`3 219 passed`) y `replay-repro` fueron **VERDES** ⇒ el producto **no** estaba rojo |
| `v2.88.17.1-beta` (`6221700c`) | **VERDE** (run `36848732534`) | **reemplaza** al anterior; el tag rojo **no se reescribe** (se conserva como evidencia) |

**Ambos fueron públicos.** El rojo está conservado y declarado
([`evidence/v2.88.17/README.md`](./evidence/v2.88.17/README.md) cabecera,
[`evidence/v2.88.17.1/README.md`](./evidence/v2.88.17.1/README.md)).

---

## 2. Firma de estado verificada **antes** de auditar

| # | Comprobación | Comando | Resultado esperado |
| --- | --- | --- | --- |
| 1 | Clon anónimo (repo público) | `git clone https://github.com/jvelasca/Bolsa_V1` | OK |
| 2 | Tag **anotado** | `git cat-file -t v2.88.17.1-beta` | `tag` |
| 3 | Versión | `git show v2.88.17.1-beta:package.json` | `2.11.17.1-beta` |
| 4 | Árbol limpio | `git status --porcelain` | vacío |
| 5 | **SIN migración** | `git diff --name-only v2.88.16.2-beta v2.88.17.1-beta -- "*alembic*" "*versions*"` | **vacío** (head `046_fill_reference_mid`) |
| 6 | **Umbrales intactos** | `git diff v2.88.16.2-beta v2.88.17.1-beta \| rg "TOP_N\|REGIME\|RISK\|SIGNALS"` | **0** coincidencias |
| 7 | **El hotfix es test-only** | `git diff --name-only v2.88.17-beta v2.88.17.1-beta -- packages/py apps/api-python/src` | **vacío** |
| 8 | **No** se borran tests | `git diff --diff-filter=DR --name-status v2.88.16.2-beta v2.88.17.1-beta` | **0** |
| 9 | El interruptor es **default OFF** | `git show v2.88.17.1-beta:.env.example` | `# AUTO_ENGINE_SIM_REAL_PRICE=1` **comentado** |
| 10 | CI del tag | `Release tag CI` (cita **POST-TAG** en `main`) | **SUCCESS** (11 + 1 skipped) |

---

## 3. Alcance sugerido de la auditoría

1. **T1–T8 del audit-pack §3.** Cada tesis trae su **modo de falsación**; el objetivo no es leerlas, es
   **intentar romperlas**.
2. **La simetría de fronteras (§`1` del audit-pack y `auto_price_provider.py`):** ¿es correcto que
   `mid(...)` lea la última barra **cerrada** y `execution(...)` la **corriente**? ¿Hay algún consumidor
   del precio que esté leyendo la frontera equivocada?
3. **El fail-closed:** ¿existe **algún** camino en el que la ausencia de precio se degrade a una
   constante? Buscar rescates silenciosos (`100.0`, `or 0.0`, `default=...`).
4. **El paso `2b`:** cinco lecturas pasan a `self._v2_bar_tick()`; la **sexta** (protección legacy) se
   queda en `self._minute` **a propósito**. ¿Es defendible dejarla, o crea una **incoherencia** entre
   decisión/fill y protección que el incremento `W5` deba pagar más caro?
5. **`Δ = 0` del bundle:** ¿de verdad `direction="long"` y precios positivos reproducen la aritmética
   anterior **sin** mover un decimal? La delegación conserva `_round4` en cada llamante ⇒ verificar que
   **ningún** llamante perdió su redondeo.
6. **`point_citable = False`:** ¿se sostiene el argumento de `W3.3`, o hay una lectura legítima del OOS
   que sí sea citable (p. ej. comparando **dos** políticas con el mismo sorteo)?
7. **La deuda declarada (§5 del audit-pack):** lo importante no es que exista, sino que **esté
   declarada** y que su clasificación (bloqueante / no bloqueante) sea razonable.

Las **7 preguntas concretas** y el **prompt listo para pegar** están en
[`entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md`](./entrega-auditoria-externa-mia-v2.88.17.1-2026-10-01.md) §4 y §7.

---

## 4. Reproducción (bash / PowerShell)

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.88.17.1-beta

# 1) Firma de estado (§2)
git cat-file -t v2.88.17.1-beta
git show v2.88.17.1-beta:package.json | rg '"version"'
git diff --name-only v2.88.16.2-beta v2.88.17.1-beta -- "*alembic*" "*versions*"   # vacío
git diff --name-only v2.88.17-beta v2.88.17.1-beta -- packages/py apps/api-python/src  # vacío

# 2) El diff acotado (8 ficheros de src)
git diff --stat v2.88.16.2-beta v2.88.17.1-beta -- packages/py/analytics/src packages/py/application/src apps/api-python/src

# 3) La costura inerte (T1) — el default va comentado
git show v2.88.17.1-beta:.env.example | rg -A1 -B1 AUTO_ENGINE_SIM_REAL_PRICE

# 4) El objeto (leer): todo esto SÍ está dentro del tag
#    docs/engineering/evidence/v2.88.17/README.md      (§1 bundle · §2 paso 2b)
#    docs/engineering/evidence/v2.88.17.1/README.md    (el hotfix del arnés A11)
#    docs/engineering/evidence/v2.88.16.3/README.md    (la banda K=12 del instrumento)
#    docs/engineering/plan-w4-precio-real-2026-10-01.md (el plan de W4)
```

**MAPA de dónde vive cada cosa (para no perder tiempo buscando):**

| Qué | Dónde | Comando |
| --- | --- | --- |
| Producto (`src`, tests, `.env.example`, Alembic) | **dentro del tag** | `git checkout v2.88.17.1-beta` |
| Evidencia `evidence/v2.88.1*` + `plan-w4-*` | **dentro del tag** | `git show v2.88.17.1-beta:docs/engineering/evidence/v2.88.17/README.md` |
| Arranque · audit-pack · entrega · criterio de salida | **`main` (POST-TAG)** | `git checkout main` |
| `docs/CURRENT_SYSTEM.md` | **`main` (POST-TAG)** — ver aviso | `git show main:docs/CURRENT_SYSTEM.md` |

> **Aviso sobre `CURRENT_SYSTEM.md`:** dentro del tag está la **foto vieja** (`AsOf V2.15`,
> `1.44.0-beta`): el tag es inmutable y el documento se puso al día **después**, en `main`
> (`AsOf V2.88.17.1`). Si lo lees en el tag y no cuadra con la versión, **no es un defecto del
> producto**: es la antigüedad del documento en el sello. La fuente al día es `main`.

**El artefacto OOS (autoridad del `Δ = 0`).** No se cita un hash local: la autoridad es el job
`replay-repro`, que **regenera** el artefacto desde la entrada congelada y hace `assert-artifact`:

```bash
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py \
  assert-artifact --file artifacts/replay-oos-durable-v2.88.7.json
```

Par sellado (en `apps/api-python/scripts/replay_oos_input_fixture.py`): **`1E3ADAC2…929A37E7` /
`3 340 728 B`** (LF, lo que ve el runner) y **`240662250347A2AA…6D9F54F0` / `3 445 622 B`** (CRLF, el
sello original escrito en Windows). **Cualquier otro digest que aparezca en los docs es una medición
LOCAL de plataforma distinta y no debe citarse como el sello** (ver audit-pack §5.5).

---

## 5. Deuda viva que debe encontrarse declarada (no oculta)

`OBS-19` (**causa estructural**: listas de pytest a mano) · el **test PG invisible**
`test_auto_v70_auto23_evidence_validation.py` (`measuredCycles` 17 ≠ 26; el 17 es correcto;
**ningún job lo ejecuta**) · la regla direccional duplicada en `risk_allocator`/`trade_plan`/
`portfolio_decision_engine`/`exit_plan` · `W5` (ProtectionClock) · `W6` · `P3-2`/`P3-3` (ventana PAPER
real) · `P3-5` · `H-4` · `OBS-15` · `OBS-16` · `OBS-22`.

**Este sello no cierra ninguna de ellas.** `OBS-21` quedó **cerrada** en `v2.88.11-beta` (no reabrir).

---

## 6. Entregable esperado

Un informe `docs/engineering/auditoria-v2-88-17-1-w4-bundle-direccional-2026-XX-XX.md` con:

* **Veredicto** de las tres piezas por separado (**`APROBADO` / `APROBADO CON PRECISIONES` /
  `RECHAZADO`**) y, sobre todo, respuesta a la pregunta de fondo del §0 (**¿es seguro encender el
  interruptor en PAPER con lo sellado?**).
* Respuestas a las **7 preguntas** de la entrega.
* **Hallazgos nuevos** separados de la **deuda ya declarada** (la deuda declarada no es un hallazgo: es
  un dato).
* Lo que **no** se pudo medir.
* **Recomendación de siguiente trabajo** — candidatos propuestos: (a) cerrar el test PG invisible y su
  alta en CI (peaje `OBS-19`); (b) `W5` (ProtectionClock); (c) la ventana PAPER real (`P3-2`) **con el
  interruptor encendido**, que es lo único que convierte el precio real en una **medida**.
