# Evidencia `v2.88.143-beta` — el día **sin sesión** deja de parecer un día de ventana vetado (`NON_MARKET_DAY`)

> **Bump:** `2.11.142-beta` → **`2.11.143-beta`** (`package.json` + `meta.bump` de los **13** CLIs de [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **en verde**).
>
> **Naturaleza:** incremento **de operación + observabilidad + documentación** sobre el **runner de la ventana** — **no** toca el motor de decisión, umbrales, pesos A/B, contrato HTTP ni esquema: **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** · **SIN migración** (head `055_dia_d_identity_nullable`). Vive en `scripts/` ⇒ **freeze-neutral**. Tag **unsigned**.
>
> **Base:** `v2.88.142-beta`.

## 1. El defecto (medido el sábado 17/10/2026, no supuesto)

La tarea `BolsaV1_WindowForward` corre `schtasks /sc daily` ⇒ **también sábados y domingos**. Al ejecutarse el **17/10 a las 18:00:00.885**, escribió:

```json
{"day":"20261017","status":"NO_MEDIDO_REGIMEN","veto":true,"reason":"regime_invalid",
 "regime":{"operationalRegime":"BEAR_TREND",...}, "steps":{"preflight":{"exit":2,...}}}
```

**Por qué está mal (dos lecturas, las dos falsas):**

1. Un **sábado no hay sesión**: no hubo «régimen que vetara la ventana», no hubo preflight legítimo. El registro dice «día de ventana intentado y vetado», que es **falso**.
2. `window:status` pasaba a `veto=4` (14/15/16/17) contando un día que **no era de mercado** ⇒ el veto de régimen —que es una medida de **MERCADO**— quedaba **diluido** con un artefacto de calendario.

**No es cosmético:** el gate de la ventana se lee de este ledger (`days`/`episodes`/`cycles`), y la estadística de veto es la que decide si el bloqueo es «régimen» o «operación».

## 2. El cambio

- **`isMarketDay(date)`** (**puro**, [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs)): descarta **sábado/domingo**. Misma regla que el vigía Python (`weekday() >= 5`) ⇒ los dos instrumentos **no pueden discrepar** sobre si el día era de mercado.
- **`recordNonMarketDay(...)`** ([`window-forward-runner.mjs`](../../../../scripts/window-forward-runner.mjs)): si no es día de mercado, escribe `manifest.json` y anexa al ledger con **`status: NON_MARKET_DAY`**, `veto: false`, `reason: non_market_day`, `regime: null`, `freeze: null` ⇒ **no se ejecuta el preflight ni se abre el motor**. `--force` **no** convierte un sábado en día de mercado (la condición es del calendario, no del operador).
- **`NON_MARKET_DAY` es terminal**: una re-ejecución del mismo día se **omite** (idempotencia, sin spam en el ledger).
- **`summarizeLedger`** cuenta aparte: **`total` = días DE VENTANA** (excluye `NON_MARKET_DAY`), más `rows`, `nonMarket` y `nonMarketDays`. `window:status` lo publica: `dias_de_ventana=3 medidos=0 veto=3 declarados=0 duros=0 no_mercado=1`.
- **`--dry-run` en fin de semana** ya no lista la cadena de preflight (sería un plan falso): avisa de que sólo se registraría `NON_MARKET_DAY`.
- **`finishDay`** reutilizado ⇒ mismo formato de `manifest.json` y de fila de ledger (nada nuevo que parsear).

## 3. Verificación (medida)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Tests JS | `pnpm window:test` | **40 passed** (34 + **6 nuevos**: `isMarketDay` sábado/domingo, laborables 14/15/16/19, terminalidad, `summarizeLedger` con y sin día no mercado, y el caso `--force` con dos filas del mismo día) |
| Guardián de bump + vigía | `pytest tests/test_dia_d_bump_guard.py tests/test_window_day_watch.py -q` | **38 passed** |
| Ruff (paridad CI) | `pnpm lint:py` | **`All checks passed!`** |
| Corrida real del día corregido | `pnpm window:run-day --force` | `dia 20261017 (2026-10-17) sin sesion de mercado: se registra NON_MARKET_DAY y NO se ejecuta preflight` → exit **0** |
| Estado resultante | `pnpm window:status` | `20261017 NON_MARKET_DAY regimen=n/d` · `dias_de_ventana=3 medidos=0 veto=3 declarados=0 duros=0 no_mercado=1` · `gate: NO_MEDIDO` |
| Idempotencia | `pnpm window:run-day` | `dia 20261017 ya registrado como NON_MARKET_DAY — se omite (usa --force para repetir)` |
| Vigía | `pnpm window:watch` | `NON_MARKET_DAY` · `sin aviso` (latido escrito) |
| Congelación | `pnpm window:freeze` | **OK** (`apps` `446f198b` / `packages` `6377a7a2` **sin cambio**: el fix vive en `scripts/`) |

## 4. Límites declarados (sin fabricar)

- **No cubre festivos.** `isMarketDay` sólo descarta fin de semana. Un festivo de bolsa (p. ej. 1/5, 25/12) seguirá generando fila de régimen. **Declarado**, no arreglado: exige un calendario de festivos (tabla `MarketCalendar`, ADR-005) y no se inventa aquí.
- **La fila vieja del 17/10 sigue en el ledger** (append-only): el ledger tiene **dos** filas de `20261017` y `latestByDay` toma la **última** ⇒ el estado es `NON_MARKET_DAY`. Es el patrón de `--force` ya usado, no una reescritura de historia.
- **La ventana PAPER real sigue `0/4` días · `0/2` regímenes · `0/32` ciclos ⇒ `INCONCLUSIVE`** (`20261014/15/16` = `NO_MEDIDO_REGIMEN`, veto **`BEAR_TREND`**). Corregir el calendario **no** desbloquea la ventana: falta **OPERACIÓN**. **No demuestra rentabilidad.**
- Tag **unsigned**; la ventana avanza **un día de pared por corrida**.

## 5. Reproducción

```powershell
pnpm window:test                     # 40 (incluye los 6 del día sin sesión)
pnpm window:run-day -- --dry-run     # fin de semana: avisa de NON_MARKET_DAY, no lista preflight
pnpm window:run-day -- --force       # registra NON_MARKET_DAY (sábado) y sale 0
pnpm window:status                   # dias_de_ventana / no_mercado separados
pnpm window:freeze                   # freeze OK (scripts/ está fuera del árbol pinado)
```

## 6. Cita POST-TAG

Pendiente: se monitoriza el `Release tag CI` de `v2.88.143-beta` y su run **se cita aquí** (con `conclusion`). Si algún job queda rojo, el sello **no** se da por bueno.
