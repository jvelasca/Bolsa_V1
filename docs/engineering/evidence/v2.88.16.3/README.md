# Evidencia del sello `v2.88.16.3-beta` — `GRANULARIDAD-OPERATIVA` · **W3.3** (robustez del instrumento OOS)

> **Objeto:** tag anotado **`v2.88.16.3-beta`** · **Versión:** `2.11.16.3-beta` · **Alembic head:**
> `046_fill_reference_mid` (**sin migración**).
> **Naturaleza:** **instrumento**, no motor. **CERO `src` de producto** (el desplazamiento del
> sorteo se inyecta y **se restaura byte a byte**: `Δ src = 0` al terminar la sonda).
> **Base del diff:** `v2.88.16.2-beta`.
> **AsOf:** 2026-10-01.
> **Padre:** [`evidence/v2.88.16.2/README.md`](../v2.88.16.2/README.md)

---

## 1. Qué es este sello, en una frase

Sella el **instrumento que mide cuánto del resultado OOS es estrategia y cuánto es sorteo del
venue** — y su primera medición dice que **casi todo es sorteo**.

`W3.2` probó que el artefacto OOS **es reproducible**. Este sello mide lo que faltaba: **de qué
depende ese artefacto**. Se midió, y la respuesta obliga a cambiar cómo se cita el OOS.

---

## 2. El mecanismo: el sorteo pasa a ser una ENTRADA DECLARADA

El ruido del venue no es aleatorio: es **determinista** y cuelga de **una línea** del motor.

```
seed = fill_seed(bar_tick_now, symbol)        # auto_simulation_worker.py — ÚNICA fuente
fill_seed(t, id) = t * 100_003 + sum(ord(id)) % 9999
```

Y de ese `seed` salen **todas** las decisiones del book SIM (`sim_rand(seed, …)`):
`draw_queue_noise` (rechazo/timeout/mercado cerrado), el corte de las parciales
(`partialcut`), el slippage (`slip`) y las latencias (`delay`).

⇒ El re-sorteo se hace **desplazando el ancla temporal**: el sorteo `k` usa
`fill_seed(bar_tick + k, symbol)`. Es **un solo** desplazamiento, inyectado en el árbol y
restaurado byte a byte; **no** se toca la señal, ni el régimen, ni el riesgo, ni la liquidación,
ni el `base_mid`.

**Autochequeo del instrumento (en la misma corrida, no en un test aparte):** `k = 0` **es** la
realización de producción y **no se parchea** ⇒ tiene que reproducir el sello del tag **byte a
byte**. Y lo hace:

```
k00   79    -15.53352380521819    923 fills    1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7
```

Ése es el `sha256` LF del sello de `v2.88.16.2`. Si `k00` no fuera el sello, la sonda estaría
midiendo otra cosa.

---

## 3. La medición (K = 12 sorteos: mismo dato, misma estrategia, **distinto sorteo del venue**)

| sorteo | ciclos | R total | signo + | fills | orders | días con fills | por año |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `k00` (**sello**) | 79 | −15.5335 | 43.0 % | 923 | 247 | 163 | 2022:53 · 2023:6 · 2024:5 · 2025:8 · 2026:7 |
| `k01` | 84 | −8.7052 | 46.4 % | 992 | 267 | 179 | 2022:48 · 2023:12 · 2024:5 · 2025:6 · 2026:13 |
| `k02` | 66 | −4.4820 | 48.5 % | 817 | 220 | 148 | 2022:45 · 2023:9 · 2024:3 · 2025:6 · 2026:3 |
| `k03` | 70 | −9.9392 | 44.3 % | 855 | 233 | 156 | 2022:49 · 2023:12 · 2024:4 · 2025:5 |
| `k04` | 59 | −15.1183 | 42.4 % | 720 | 197 | 130 | 2022:46 · 2023:8 · 2024:3 · 2025:2 |
| `k05` | 107 | −17.2655 | 42.1 % | 1252 | 336 | 208 | 2022:64 · 2023:17 · 2024:9 · 2025:9 · 2026:8 |
| `k06` | 47 | −10.2142 | 40.4 % | 601 | 164 | 100 | 2022:42 · 2023:4 · 2024:1 |
| `k07` | 53 | −1.3902 | 43.4 % | 680 | 189 | 121 | 2022:34 · 2023:8 · 2024:3 · 2025:5 · 2026:3 |
| `k08` | 73 | **−37.7244** | 28.8 % | 806 | 218 | 143 | 2022:56 · 2023:8 · 2024:3 · 2025:3 · 2026:3 |
| `k09` | 82 | **+0.8182** | 47.6 % | 1034 | 283 | 190 | 2022:54 · 2023:14 · 2024:5 · 2025:5 · 2026:4 |
| `k10` | 43 | −25.3750 | 27.9 % | 516 | 141 | 76 | 2022:43 |
| `k11` | 88 | −15.7999 | 45.5 % | 980 | 270 | 169 | 2022:51 · 2023:11 · 2024:5 · 2025:9 · 2026:12 |

**Nada de esto es ruido de medición**: cada fila es un artefacto **reproducible byte a byte**
(se declara su `sha256_lf` en la sonda). El `decided` es **24 500 en las doce** — la estrategia
evalúa lo mismo; lo que cambia es el **desenlace del venue**.

---

## 4. La BANDA, su potencia y su validez

```
ciclos     media  70.9 ± 17.8   · min  43 · mediana  71.5 · max 107   (dispersión 64)
R total    media -13.3941 ± 10.1381 · min -37.7244 · mediana -12.6662 · max +0.8182 (dispersión 38.54)
fills      media 848.0 ± 195.8  · min 516 · max 1252
signo +    media  41.7% ± 6.4%  · min 27.9% · max 48.5%
```

**POTENCIA:** con `K = 12`, la media de R solo se conoce con **`SE = 2.9266`** (IC 95 % **±5.7362**).
Y la **banda de R cruza el cero** (`min = −37.72 < 0 < max = +0.82`).

**VALIDEZ (criterio evaluado, no narrado):**

```
crosses_zero_r   = True
point_citable    = False
```

⇒ **El OOS, tal como está, no tiene potencia para citar un punto.** Con `K = 1` —lo que hace el
`replay-repro` de cada tag, y lo que se citó— el instrumento **no distingue la estrategia del
ruido del simulador**.

---

## 5. Corrección de `W3.2` (autocorrección, medida)

`W3.2` declaró una banda **`[62, 79]` ciclos / `[−18.37, −15.53] R`** derivada de **dos puntos**
(el sello por-minuto y el árbol `W3`). **Esa banda era falsa por defecto**: dos puntos de **dos
familias de seed distintas** no acotan una distribución. La medición de `K = 12` sobre la
**misma** familia muestra:

| | `W3.2` declaró | `W3.3` midió (K = 12) | Subestimación |
| --- | --- | --- | --- |
| ciclos | `[62, 79]` (dispersión 17) | `[43, 107]` (dispersión 64) | **≈ 3,8×** |
| R total | `[−18.37, −15.53]` (dispersión 2,83) | `[−37.72, +0.82]` (dispersión 38,54) | **≈ 13,6×** |

Y con ello cae también la lectura que `W3.2` hizo del delta de `W3`: el «efecto» medido
(`ΔR = 2,83`) es **`0,28 σ`** del instrumento ⇒ **no es separable del sorteo**. Que el número
subiera **no** autoriza a decir que `W3` mejoró nada; `W3` sigue siendo correcto **por diseño**
(quitar lookahead, idempotencia intra-barra), **no** por el R que produjo.

> **Nota de honestidad sobre `W3.2`:** su §5 llamaba «banda honesta» a lo que era un intervalo
> de dos puntos. La corrección se hace aquí, con la medición delante, y la referencia viva pasa
> a ser la de este dossier.

---

## 6. Qué NO invalida este sello

* **La reproducibilidad byte a byte** del artefacto: sigue siendo cierta y sigue siendo un
  contrato (`replay-repro`). El instrumento es **determinista**; lo que no es determinista es el
  **resultado** frente al sorteo.
* **La ablación de `W3.2`**: el `seed` **era** la causa del rojo, y `M280` lo demuestra. Nada de
  eso cambia.
* **`W1`…`W3.2` como mecánica**: frontera de barras cerradas, idempotencia intra-barra,
  short-circuit de barra, hotfix del arnés A9. Se sostienen **por diseño y por test**, no por el R.
* **El `decided = 24 500` idéntico**: la estrategia es determinista dado el estado; la varianza
  entra por el **desenlace** del venue, no por la decisión.

---

## 7. Consecuencia (decisión ABIERTA — no la toma este sello)

El OOS no puede seguir usándose como **gate de mérito** sin responder antes a una de estas
preguntas:

1. **¿Se cita como banda y se abandona el punto?** El OOS deja de certificar «mejor/peor» y pasa
   a certificar **forma** (que el instrumento corre, que la muestra existe, que el embudo cierra).
   Barato y honesto; pierde el gate cuantitativo.
2. **¿Se reduce el ruido del venue?** El simulador sortea rechazos (`≈1 %` + timeouts + mercado
   cerrado + parciales) que **eliminan o mutilan órdenes**. Con `flat_price_script` a `100.0` y
   sin datos reales (`W4`), el book es casi todo ruido: **`W4` es la palanca que más reduciría
   esta varianza**. Ordenar `W4` **antes** de cualquier lectura de mérito.
3. **¿Se sube `K` y se cita la media con su IC?** Funciona, pero exige `K` grande: para un IC 95 %
   de ±1 R haría falta `K ≈ (1,96 · 10,14 / 1)² ≈ 395` sorteos ⇒ **≈ 9 h** de replay. Con `K = 12`
   el IC es ±5,74 R, que es más ancho que cualquier efecto que `W4`/`W5` pretenda medir.
4. **¿Se retira el OOS del criterio de cierre de la serie y se sustituye por otro instrumento
   (PAPER longitudinal)?** Es la opción que el propio plan ya contempla para `P3-2`.

**Decisión del propietario. Este dossier deja las cuatro sobre la mesa y ninguna ejecutada.**

---

## 8. Verificación

```
uv run --no-sync python apps/api-python/scripts/v2_88_16_3_oos_seed_robustness.py \
    --draws 12 --reuse --out-dir operability_runs/w33-band
#   -> VEREDICTO  BANDA DEFINIDA=MEDIDA (el instrumento declara su sorteo, no lo esconde)   exit 0
```

* `ruff` **`All checks passed!`**
* El árbol del motor queda **limpio** tras los 12 sorteos (`git status` sobre
  `apps/api-python/src/.../auto_simulation_worker.py` **vacío**): cada parche se restaura byte a
  byte bajo `try…finally`, y un fallo de restauración **aborta** la sonda.
* Los `sha256_lf` de los 12 sorteos están **declarados** en la sonda ⇒ un drift en cualquiera de
  los doce artefactos sale con **exit 2**.

---

## 9. Deuda que este sello NO cierra

* **La banda no se asserta en CI.** Cuesta `K × replay` (≈ 80 s cada uno) y se decide junto con
  §7. Hoy el sello es **reproducible a mano**, no en el pipeline.
* **`K = 12` no es una elección estadística**, es un presupuesto de tiempo declarado. Con la
  `σ` medida, la cifra honesta es que **`K` tendría que ser de centenares** para citar la media.
* **NO cierra** `P3-2`/`P3-3`, `OBS-19` (causa estructural), `OBS-16`, `OBS-15`, `OBS-22`,
  `OBS-14.b`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`. `OBS-21`/`OBS-23` **CERRADAS**.

---

## 10. Revisión

* **Convierte el OOS en un instrumento que declara su sorteo** en vez de esconderlo: el re-sorteo
  es una entrada declarada, reproducible byte a byte, con `k = 0` anclado al sello del tag.
* **Mide lo que valía el número que se venía citando**: la media de R solo se conoce con **±5,74 R**
  a `K = 12`, y la banda **cruza el cero** ⇒ **`point_citable = False`**.
* **Se autocorrige**: la «banda» de `W3.2` era un intervalo de dos puntos, subestimado **≈ 13,6×**
  en R. Queda corregido con la medición delante.
* **Deja cuatro salidas** sobre la mesa (§7) y **ninguna ejecutada**: la decisión es del propietario,
  y afecta al orden de `W4`/`W5` y al criterio de cierre de la serie.
