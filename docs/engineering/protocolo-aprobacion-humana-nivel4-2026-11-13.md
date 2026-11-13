# Protocolo de aprobación humana — Nivel 4

**Fecha:** 2026-11-13 · **Estado:** protocolo **abierto**, ninguna condición cumplida hoy.
**Ámbito:** decidir, con firma humana, si el sistema pasa de **medición** a **operación con capital**.
`activationAllowed` sigue y seguirá `false` mientras este protocolo no se complete con un acta firmada.
El protocolo **no** enciende el flag, no lo automatiza y no lo deja a un job.

## 1 · Qué decide este protocolo (y qué no)

- **Sí:** qué evidencia mínima debe existir, quién la revisa y quién firma el paso a operación.
- **No:** no cambia umbrales, no declara rentabilidad, no sustituye a la auditoría externa y no convierte un
  PASS técnico en permiso de operar.

Un veredicto en verde en las rutas de gobierno (`ai_governance`) sólo habilita **esta** conversación humana; la
respuesta de esas rutas publica `activationAllowed: false` siempre.

## 2 · Condiciones exigidas (todas, sin excepciones)

| # | Condición | Evidencia mínima exigida | Fuente en el repo |
| --- | --- | --- | --- |
| C1 | **LAB verde** | Los 5 gates pre-registrados evaluados con muestra suficiente: `minNetReturnPct ≥ 0`, `maxDrawdownPct ≤ 15`, `minPositiveWindowPct ≥ 60`, `minExcessVsBuyHoldPct ≥ 0`, `minRoundTripCostBps ≥ 22` | `baseline_arms.BASELINE_THRESHOLDS`, `adaptation_validation.validate_lab_gates` |
| C2 | **DÍA-D as-run certificado** | Cohorte con `verdict = certified` y `samples ≥ 12`, artefactos con `artifact_integrity`, `temporal_freeze`, `initial_state`, `sequential_replay`, `real_market_data`, `realistic_execution`, `benchmarks` y `audit` en PASS | `dia_d_certification.certify_cohort` |
| C3 | **Robustez OOS medida** | Replay OOS con ciclos **cerrados** (no `realizedCount = 0`), R realizado, acierto de signo y distribución publicados; latch de parada dura **no enganchado** (`0 governor_halted` sin `drawdown_band` medido); banda (K sorteos) cuando el punto tenga muestra | `v2_86_replay_oos_viability.py`, `v2_94_dia_d_multi_band.py` |
| C4 | **Rentabilidad neta ajustada al riesgo** | Retorno neto de costes, drawdown y exceso frente a buy & hold, con la muestra declarada y sin huecos rellenados | Resultado de C1 y C3, no una estimación |
| C5 | **Completitud de datos declarada** | Cobertura `1d` suficiente para el universo operado; cada hueco declarado con su motivo, sin sembrar datos | `ohlcv_bars`, informes de cohorte |
| C6 | **Sin flags ni rutas encendidas por defecto** | `activationAllowed = false` en todas las rutas; ningún job lo cambia | `apps/api-python/src/bolsa_api/api/v1/routes/ai_governance.py` |

**Regla de honestidad:** si una condición no se puede medir, se declara `NOT_EVALUATED` o `n/d`. No se
convierte en PASS, no se rellena con `0` y no se compensa con otra condición mejor.

## 3 · Estado real a 2026-11-13

| Condición | Estado | Evidencia |
| --- | --- | --- |
| C1 · LAB verde | **No verificado en este acto** | No se ha corrido el LAB con muestra suficiente; no se declara verde |
| C2 · Cohorte as-run | **No cumplida** | `insufficient_sample:4/12`, 2 días certificados (`2026-11-05`, `2026-11-09`) — [cohorte](cohorte-dia-d-as-run-2026-11-13.md) |
| C3 · Robustez OOS | **No cumplida** | `realizedCount = 0`, `meanR = null`: sin ciclo cerrado. Causa diagnosticada: el replay **no mide al motor**, mide el latch de parada dura enganchado por falta de `exit_order_store` — [robustez OOS](robustez-oos-nivel4-2026-11-13.md), [diagnóstico](diagnostico-gobernador-oos-2026-11-13.md) |
| C4 · Rentabilidad neta | **No medida** | Depende de C1 y C3; hoy no hay muestra |
| C5 · Completitud de datos | **No cumplida** | 16 de 197 instrumentos del catálogo sin barras `1d`; además 46 posiciones de residuo de test apuntan a instrumentos inexistentes (no son cobertura de mercado, son basura de tablas sin FK) |
| C6 · Flags apagados | **Cumplida** | `activationAllowed: false` en todas las rutas y tests que lo pinzan |

**Conclusión:** 1 de 6 condiciones cumplida (la que exige no encender nada). `activationAllowed` permanece
`false`.

## 4 · Quién firma

| Rol | Responsabilidad | Quórum |
| --- | --- | --- |
| **Responsable de riesgo** | Valida C1, C3 y C4: que la muestra sea la declarada y que el drawdown/exceso no se hayan maquillado | Obligatorio |
| **Responsable técnico** | Valida C2, C5 y C6: artefactos, hashes, cobertura y que ningún flag se haya encendido | Obligatorio |
| **Revisor externo** | Contrasta artefactos y CI contra un commit concreto; no firma viabilidad, firma **reproducibilidad** | Recomendado, no sustituible por un dictamen sin acceso al repo |

Reglas de firma:

- Ninguna firma vale sobre un árbol sucio ni sobre un SHA distinto al del CI verde que se cita.
- El acta **cita hashes** (artefactos, cohorte, contrato) y el SHA de `main`.
- Una firma puede ser **rechazo**: el acta registra quién rechazó y por qué.

## 5 · Plantilla de acta

```text
ACTA DE APROBACIÓN — NIVEL 4

Fecha: <AAAA-MM-DD>
SHA de main: <40 hex>
Bump declarado: <2.11.x-beta>
Cohorte as-run: <verdict> · samples <n>/<min> · hash <hash>
Robustez OOS: <verdict> · realizedCount <n> · meanR <valor|n/d> · hash <hash>
LAB: <verdict> · gates <PASS/FAIL/NOT_EVALUATED por gate> · hash <hash>

Condiciones:
  C1 LAB verde ............ <CUMPLIDA|NO CUMPLIDA|NO MEDIDA> — evidencia: <ruta/hash>
  C2 Cohorte certificada .. <...>
  C3 Robustez OOS ......... <...>
  C4 Rentabilidad neta .... <...>
  C5 Datos completos ...... <...>
  C6 Flags apagados ....... <...>

Decisión: <SE MANTIENE MEDICIÓN | SE ABRE OPERACIÓN>
Condiciones adicionales impuestas por los firmantes: <texto>
Lo que esta acta NO acredita: <rentabilidad futura, robustez fuera de la muestra, etc.>

Firmas:
  Responsable de riesgo: <nombre> — <fecha> — <decisión>
  Responsable técnico:   <nombre> — <fecha> — <decisión>
  Revisor externo:       <nombre> — <fecha> — <alcance revisado>
```

## 6 · Lo que queda fuera

- Cambiar `activationAllowed` desde código, job, script o migración: el flag sólo lo cambia un humano, y sólo
  después de un acta firmada.
- Ajustar umbrales, semilla o ventana para que una condición pase.
- Presentar PASS técnico, dictamen externo sin acceso al repo o una cohorte insuficiente como aptitud operativa.
- Sustituir datos ausentes por datos sembrados.

## 7 · Vigencia

El acta caduca si cambia cualquiera de estas cosas y hay que rehacer la parte afectada: el SHA de `main`, los
umbrales pre-registrados, el motor de decisión, el esquema de artefactos o la fuente de datos. Una caducidad
no se renueva por silencio: se re-firma.
