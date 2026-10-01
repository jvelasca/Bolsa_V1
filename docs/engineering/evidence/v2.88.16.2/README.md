# Evidencia del sello `v2.88.16.2-beta` — `GRANULARIDAD-OPERATIVA` · **W3.2** (re-sello del artefacto OOS al ancla de barra)

> **Objeto:** tag anotado **`v2.88.16.2-beta`** · **Versión:** `2.11.16.2-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** cierre del rojo que dejó `W3` en el job `replay-repro`. **CERO `src` de producto**:
> el motor de `W3` **ya era correcto**; lo que faltaba era **re-apuntar el artefacto congelado** a
> ese motor **y declarar** el delta con su **banda**.
> **Base del diff:** `v2.88.16.1-beta` (padre del árbol sellado).
> **AsOf:** 2026-10-01.
> **Supersede a:** `v2.88.16.1-beta` (rojo `replay-repro`) y `v2.88.16-beta` (rojo `lifecycle-pg`).
> **Padre:** [`evidence/v2.88.16/README.md`](../v2.88.16/README.md) · [`evidence/v2.88.16.1/README.md`](../v2.88.16.1/README.md)

---

## 1. Qué es este sello

El job **`replay-repro`** del `Release tag CI` **congela byte a byte** un artefacto del replay OOS
(`artifacts/replay-oos-durable-v2.88.7.json`): lo **regenera** desde una entrada congelada y **asserta**
su SHA-256 y su tamaño. Ese artefacto es la **prueba de que el instrumento de investigación es
reproducible** — y su referencia nació en **`v2.88.7`**, es decir **antes** de `W3`.

`W3` movió el ancla temporal del motor (`simulated_broker.fill_seed(bar_tick, símbolo)`) y el replay
**no usa un simulador aparte**: conduce el **`AutoSimulationWorker` real**
(`v2_87_replay_oos_durable_cycle.py:272`). ⇒ El artefacto **tenía** que cambiar. El trabajo de este
sello es (a) **probar** que esa es la causa y no otra, (b) **re-apuntar** la referencia, y (c) **declarar**
lo que el delta **enseña sobre el instrumento** —que es lo importante y lo que `W3` no declaró.

**NO** enmienda el ADR 010 y **NO** toca `TOP_N`/`REGIME`/`RISK`/`SIGNALS`/A-B. **NO** toca el motor.

---

## 2. Por qué se sella (rojo declarado, no heredado)

`Release tag CI` del tag **`v2.88.16.1-beta`**, run **`36785738058`**: **10 jobs verdes**, 1 *skip* y
**2 rojos**:

| Job | Veredicto | Lectura |
| --- | --- | --- |
| `lifecycle-pg` | **success** | **el hotfix `W3.1` funcionó**: el certificador A9 del día AUTO ya no revienta |
| `python` | **success** | **`3166 passed, 38 skipped`** (`Δ = 0` vs `v2.88.16`) |
| `frontend` · `shared` · `decision-spine` · `a7-gate` · `security` · `playwright (mock)` · `dr-verify` | **success** | sin regresión |
| **`replay-repro`** | **failure** | el artefacto congelado **dejó de reproducirse** |
| **`certify`** | **failure** | agrega el rojo anterior |

El rojo del `replay-repro` **no era de plataforma**: su propio `Determinismo del runner (2ª corrida)`
dio **`VEREDICTO 2ª corrida IDÉNTICA`** y `DIGEST igual en las dos corridas` ⇒ **la divergencia es de
código**, y la sección que difiere es **`replay`** (el MOTOR), no **`census`** (la ENTRADA, que sale
**idéntica** al sello: `1 237 098` / `45e4cc80cfba6e5c`).

---

## 3. La frontera compartida es una **equivalencia medida**, no una sola definición

`W3` afirma en su dossier que «el **MOTOR AUTO** y el **instrumento de investigación** (`replay_oos`)
comparten la **misma** frontera». **La medición dice otra cosa, y hay que corregirlo** (§6).

El replay **inyecta** sus fuentes sobre `cursor.as_of` (`v2_87_replay_oos_durable_cycle.py:298`),
no sobre `last_closed_bar_day`. Y `ReplayCursor.as_of()` **ya era `B-1`** antes de `W3`:

```python
def as_of(self) -> str:
    """Día anterior: la última barra COMPLETA que la decisión puede ver."""
    return self._days[self._index - 1] if self._index > 0 else ""
```

y su `price_script` **ya ignoraba** el contador privado del worker («Ignorar el `tick` es deliberado:
acoplar el precio al contador PRIVADO `_minute` … haría que un cambio interno del worker desalineara
precio y fecha sin que ningún test lo notara», `replay_oos.py:241`).

⇒ Son **dos implementaciones equivalentes por medición**, no una sola. `W3` **convergió** el motor al
contrato que el instrumento **ya cumplía**; no unificó nada.

---

## 4. La ablación — la causa, aislada (no narrada)

Herramienta **nueva**: [`v2_88_16_2_oos_anchor_ablation.py`](../../../apps/api-python/scripts/v2_88_16_2_oos_anchor_ablation.py).
Corre **cuatro variantes del MISMO replay**, reutilizando los fragmentos **ya auditados** de la matriz
de mutaciones (`M280` seed por minuto · `M279` frontera lookahead) más un **control de vivacidad**
propio (`M279b`, frontera devolviendo un día de `2099`), y **restaura el árbol byte a byte**.

Salida literal:

```
== ablación del ancla temporal sobre el artefacto OOS ==
variante                    ciclos     R total  signo +  fills orders  días  LF sha256 (12)  por año
------------------------------------------------------------------------------------------------
SELLO v2.88.7                   62    -18.3660      n/d    752    210   141  a4da036c9ac1    (no publicado)
w3                              79    -15.5335    43.0%    923    247   163  1e3adac26543    {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7}
m280_seed_minuto                62    -18.3660    37.1%    752    210   141  a4da036c9ac1    {"2022": 50, "2023": 7, "2024": 2, "2025": 3}
m279_frontera_lookahead         79    -15.5335    43.0%    923    247   163  1e3adac26543    {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7}
m279b_frontera_futuro           79    -15.5335    43.0%    923    247   163  1e3adac26543    {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7}

VEREDICTO  DEFINIDO=MEDIDO (la ablación aísla la causa declarada)
```

### 4.1 La causa es UNA línea: el ancla del fill

**`M280` reproduce el sello BYTE A BYTE.** No sólo las cifras: el **digest por secciones** sale idéntico:

| Sección | `w3` (árbol tal cual) | `M280` (seed al minuto) = **sello** |
| --- | --- | --- |
| `replay` | `919208` / `98ac89372f49822c` | **`891272` / `ee81e76cee0995aa`** |
| `score` | `29229` / `f78863a8c7c169f8` | **`24112` / `96b3d601bae8b99c`** |
| `totals` | `fills 923` · `orders 247` | **`fills 752` · `orders 210`** |
| LF `sha256` | `1E3ADAC2…` / `3 340 728` B | **`A4DA036C…` / `3 290 062` B** |

⇒ **El rojo de `replay-repro` era el SEED, y sólo el seed.** El diff de `replay_oos.py` es **refactor
puro** (`make_closed_bar_loader` es el viejo `make_as_of_bar_loader`, línea a línea) y la frontera no
participa (§4.2).

### 4.2 La frontera cerrada es **INERTE** en el replay — y está probado con un control

`M279` (lookahead) **no cambia nada**. Un *«no cambia nada»* puede ser «inofensivo» o «inerte», así que
se añadió el **control de vivacidad** `M279b`: si la frontera estuviera de verdad en el camino, devolver
**`2099`** metería **años de barras futuras** en la señal, el régimen y el ATR. El artefacto sale
**idéntico** ⇒ `last_closed_bar_day` **no se consulta** en esta configuración.

> **Esto NO es un fallo.** Es la consecuencia de §3: el replay ya aplicaba su propia frontera `B-1`
> vía `cursor.as_of`. El *lookahead* de `M279` es un defecto **real** del helper `closed_bars`, pero el
> camino del replay no lo ejerce.

### 4.3 El journal no se duplica: el ESTADO evoluciona distinto

El journal cambia (`journalReasons` `142` / `040d5c2ff14549aa` → `143` / `9486800379e2b086`;
`regime_invalid` `878 → 2027`, `concentration_exceeded` `33 → 91`) **con las mismas 24 500 decisiones**.
La ablación lo cierra: con el seed revertido el journal **vuelve al del sello** ⇒ el cambio es
**downstream del conjunto de fills**, no una duplicación. Mecanismo coherente con lo medido: más
posiciones vivas simultáneas (79 vs 62 ciclos) ⇒ más evaluaciones por tick y más
`concentration_exceeded`. Se declara como **consecuencia medida de la trayectoria de estado**; **no** se
ha corrido un experimento separado que aísle cada familia.

### 4.4 El árbol queda intacto

La sonda restaura **byte a byte** y lo comprueba (`git status --porcelain` limpio sobre
`packages/py/application/src` y `apps/api-python/src` tras la corrida).

---

## 5. El delta OOS y su **BANDA** — el hallazgo que importa

`W3` **ensancha** la muestra del replay y **mejora** el R. Quitar lookahead **no puede** mejorar nada
—no cambia **ninguna** decisión (§4.2)—, así que la pregunta correcta no es «¿mejoró?» sino
**«¿de qué depende este número?»**. La ablación contesta: **de la realización del ruido del simulador**.

| Métrica | Sello `v2.88.7` | `W3` (ancla de barra) |
| --- | --- | --- |
| decided | 24 500 | 24 500 (**idéntico**) |
| proposals / orders | 238 / 210 | 285 / 247 |
| fills / daysWithFills | 752 / 141 | 923 / 163 |
| **ciclos (`realizedCount`)** | **62** | **79** |
| **R total** | **−18.36598** | **−15.53352** |
| meanR / medianR | −0.296225 / −1.053446 | −0.196627 / −0.892411 |
| signo positivo | **37.1 %** | **43.0 %** |
| reparto por año | 50 / 7 / 2 / 3 | 53 / 6 / 5 / 8 / 7 |

**La banda honesta del instrumento (sello del ancla de barra) es:**

```
ciclos  ∈ [62, 79]        R total ∈ [-18.37, -15.53]        signo + ∈ [37.1 %, 43.0 %]
```

porque **el replay es un sorteo del venue**: cambiar el ancla del `seed` (y nada más) mueve el
resultado de un extremo al otro de la banda, **byte a byte reproducible**.

**Consecuencia dura, y es la que hay que oír:** el R que se citó al sellar (`−18.3660`) **no es una
propiedad del motor**; es **un sorteo concreto**. Citar un punto sin su banda es citar un dado como si
fuera una constante. ⇒ **Trabajo de instrumento abierto:** medir **K sorteos** (anclas/semillas
declaradas) y publicar la banda como el resultado del instrumento, en vez de un punto.

---

## 6. Correcciones al dossier de `W3` (medidas, no cosméticas)

| # | Afirmación de `evidence/v2.88.16` | Medición de `W3.2` |
| --- | --- | --- |
| **F2** | «el MOTOR y el instrumento comparten la **misma** frontera» (§1) | **Inexacto.** Son **dos** implementaciones **equivalentes por medición**: el replay usa `cursor.as_of`, que ya era `B-1`. `W3` convergió el motor al contrato del instrumento. |
| **F4** | «la muestra es de **13 ciclos**, de un **único episodio** (`2022-02 → 2022-05`)» (§7) | **Inexacto para el SELLO.** Esa frase describe los `13` ciclos de `v2.86`, no el sello de `62`. Con la misma sonda, **el sello** reparte `2022: 50 · 2023: 7 · 2024: 2 · 2025: 3` y su signo positivo es **37.1 %**. |
| **Nuevo** | (no se declaraba) | **El delta del artefacto OOS no se documentó en `W3`.** Su §4 mide el delta del **golden de AUTO** —correcto— pero guarda silencio sobre el artefacto que `certify` congela, y ese es el que rompió el tag. |

---

## 7. Re-sello, verificación y valores

**Valores nuevos** (dos renders declarados, como desde `v2.88.8`):

| Render | Bytes | SHA-256 |
| --- | --- | --- |
| CRLF (sello en modo texto de Windows) | `3 445 622` | `240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0` |
| LF (runner) | `3 340 728` | `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` |

**Manifiesto del fixture:** `857C9F7D3F2CD43713080736B2C20E7CAE5C94E590A1B4626201D159A1C8279C` →
**`DAA3958C1D1EEAFE009DAD72E973F97612000E8B77C22CDB8E12CBB7957A877D`**. Las **25 720** líneas de
**datos** quedan **intactas** (25 700 barras + 20 instrumentos): sólo cambia la **cabecera** del
manifiesto, que publica los dos pares de referencia.

**Veredicto local — el paso EXACTO del job** (`assert-artifact`), sobre artefacto regenerado desde la
entrada congelada y una BD **fresca** (`bolsa_v1_replay_w321`, creada y migrada desde cero):

```
bytes            3445622  (sello 3445622 · mismo contenido en LF 3340728)
sha256           240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0
sha256 LF        1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7
VEREDICTO        REPRODUCIDO (render del sello, byte a byte)
```

Digest por secciones **idéntico** al del runner del CI (misma corrida del tag rojo):
`census 1237098/45e4cc80cfba6e5c` · `replay 919208/98ac89372f49822c` ·
`score 29229/f78863a8c7c169f8` · `watch 561/40230635349bf2a0` ·
`totals {"decided":24500,"fills":923,"orders":247,"proposals":285,"vetoes":24264}`.

---

## 8. Cita POST-TAG (y cita huérfana cerrada)

Límite estructural (`OBS-3`/`OBS-4`): `Release tag CI` **sólo corre al empujar** el tag ⇒ su resultado
no puede vivir dentro del propio tag; se cita en `main` como commit **POST-TAG**.

**Predicción declarada (`ESPERADO = OBSERVADO`):**

| Job | Esperado |
| --- | --- |
| `python` | **`3166 passed, 38 skipped`** (`Δ = 0` vs `v2.88.16`: este sello no toca `src`) |
| `lifecycle-pg` | **VERDE** (ya lo estaba en `v2.88.16.1`) |
| **`replay-repro`** | **VERDE** — `REPRODUCIDO` contra los valores de §7 |
| `certify` | **VERDE** |

> **CITA REAL (POST-TAG, 2026-10-01) — TAG `v2.88.16.2-beta` **TODO VERDE**.** `Release tag CI` run
> **`36821946619`** (`ref=refs/tags/v2.88.16.2-beta`, HEAD `683990ff`): **11 jobs `success`** + **1
> skipped** (`playwright (integrated E2E, opt-in)`). **Encaje `ESPERADO = OBSERVADO`:**
>
> - job `python`: **`3166 passed, 38 skipped, 6 warnings in 72.95s`** ⇒ **`Δ = 0`** vs `v2.88.16`
>   (este sello **no** toca `src` de producto).
> - job **`replay-repro` VERDE** (era el rojo que este sello cierra): veredicto del runner
>   **`REPRODUCIDO (mismo CONTENIDO; el sello está en CRLF y este fichero en LF)`**, LF
>   `1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` / `3 340 728` B,
>   **2ª corrida IDÉNTICA** y digest por secciones **idéntico al local**: `replay` `919208`/
>   `98ac89372f49822c`, `score` `29229`/`f78863a8c7c169f8`, `totals`
>   `{"decided":24500,"fills":923,"orders":247,"proposals":285,"vetoes":24264}`.
> - job **`lifecycle-pg` VERDE** (ya lo estaba en `v2.88.16.1`) y **`certify` VERDE**.
>
> ⇒ **La cadena queda cerrada:** `v2.88.16-beta` (rojo `lifecycle-pg`) → `v2.88.16.1-beta` (rojo
> `replay-repro`) → **`v2.88.16.2-beta` TODO VERDE**.

**Cita huérfana que se cierra aquí:** el sello `W2` (**`v2.88.15-beta`**) dejó su cita POST-TAG sin
cerrar. Queda citada: `Release tag CI` run **`36761134323`**, **`certify` success**.

---

## 9. Deuda que este sello NO cierra (y un cambio de ORDEN del plan)

- **NO cierra** `P3-2`/`P3-3` (ventana PAPER real; la **habilita** `W4`), `OBS-19` (**causa
  estructural**: listas manuales), `OBS-16`, `OBS-15`, `OBS-22`, `OBS-14.b`, `OBS-13`, `OBS-11`,
  `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21` y `OBS-23` siguen **CERRADAS**.
- **Deuda NUEVA (la importante):** **robustez del instrumento OOS** — el replay es un sorteo del
  venue (§5) y hoy se cita un **punto**, no una **banda**. Medir **K sorteos** con semilla declarada.
- **Cambio de orden del plan (declarado, decisión del propietario):** la **robustez del instrumento**
  pasa **antes** de `W4`. Sin banda, el OOS no es un instrumento válido y `W4` (precio real) no tendría
  contra qué medirse.

---

## 10. Firma de estado (verificable)

```
git cat-file -t v2.88.16.2-beta                                   # tag (anotado)
git show v2.88.16.2-beta:package.json                             # 2.11.16.2-beta
git diff --stat v2.88.16.1-beta v2.88.16.2-beta
# Alembic: sin migración nueva (head sigue 046_fill_reference_mid)
# Árbol de producto: CERO src (sólo fixture, constante de referencia, sonda nueva y docs)
uv run --no-sync python apps/api-python/scripts/v2_88_16_2_oos_anchor_ablation.py --reuse
#   -> VEREDICTO  DEFINIDO=MEDIDO (la ablación aísla la causa declarada)
```

---

## 11. Revisión

- **Cierra** el rojo `replay-repro` de `v2.88.16.1-beta` **con la causa medida** (el seed del fill),
  no con una re-baseline ciega: revertir sólo esa línea reproduce el artefacto del sello **byte a byte**.
- **Corrige** dos afirmaciones del dossier `W3` que la medición no sostiene (§6) y **documenta** el
  delta del artefacto OOS que `W3` no declaró.
- **Publica la banda** `[62, 79] ciclos · [−18.37, −15.53] R` y **declara** que el OOS es sensible al
  sorteo del simulador ⇒ cambia el orden del plan: **robustez del instrumento antes de `W4`**.
- **Siguiente incremento:** robustez del instrumento OOS (K sorteos, banda declarada) y después
  **`W4`** (`v2.88.17-beta`) — proveedor de **precio real** (`flat_price_script` sobre `100.0` muere).
