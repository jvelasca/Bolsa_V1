# RELEVO — Phase C2 · dev-stack F3.7 ECONNRESET (2026-09-01)

> **Alcance:** diagnóstico residual · Opción C · deuda transversal.  
> **Padre:** [`dev-continuation-plan-2026-08-09.md`](./dev-continuation-plan-2026-08-09.md) §2 · §4b · §4c · [`traspaso-relevo-cierre-v155-apertura-siguiente-2026-09-01.md`](./traspaso-relevo-cierre-v155-apertura-siguiente-2026-09-01.md) §5 Opción C.  
> **AsOf:** 2026-09-01.  
> **Regla:** **no** tocar scheduler productivo · **no** LIVE · **no** bump package.

---

## 0. Veredicto

| Campo               | Valor                                                           |
| ------------------- | --------------------------------------------------------------- |
| **Estado**          | **RESIDUAL ACCEPTED**                                           |
| **Código cambiado** | **No** — mitigaciones P3 + a2 ya cubren la vía proxy→pnpm→stack |
| **Gap proxy→stack** | **Ninguno material** en operación normal (Vite ya `ready`)      |

---

## 1. Síntoma histórico (F3.7)

Bajo carga de `POST /api/instruments/{id}/sync` vía proxy Vite:

```text
[vite] http proxy error: /api/instruments/{id}/sync
Error: read ECONNRESET
ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL
Deteniendo stack (exit=1)
```

Causa raíz documentada: la API cierra la conexión TCP a medias en syncs pesados; `http-proxy` emite `error`; antes Vite/pnpm salían con código ≠ 0 y `run-dev` derribaba todo el stack.

---

## 2. Mitigaciones en repo (verificadas 2026-09-01)

### 2.1 P3 — `apps/web/vite.config.ts`

```24:31:apps/web/vite.config.ts
        configure: (proxy) => {
          proxy.on("error", (err) => {
            // El proxy error se loguea a consola pero NO debe tumbar Vite.
            console.warn(
              `[dev-proxy] error reenviando a la API (se reintentará): ${err.code ?? err.message}`,
            );
          });
        },
```

**Evidencia Vite 6.3.5 (`node_modules/vite`):**

- `opts.configure(proxy)` se ejecuta **antes** del handler interno de Vite (`proxyMiddleware`, ~L34821–34857).
- El handler interno de Vite ante `proxy.on("error")` solo **loguea** y responde 500 si procede; **no** llama a `process.exit`.
- El dev server también ignora `ECONNRESET` en errores de socket (~L25147: `if (err.code === "ECONNRESET" || !socket.writable) return`).

→ Un `ECONNRESET` en el proxy **no debería** matar el proceso Vite.

### 2.2 a2 — `scripts/run-dev.mjs`

Arquitectura actual:

- Raíz: `pnpm dev` → `node scripts/run-dev.mjs` (sin `pnpm -r`).
- Web: `spawnPnpm(['--filter', '@bolsa/web', 'dev'])` — hijo aislado.
- API arranca **primero**; Vite solo después de `waitForApi` OK.

Manejo de exit de Vite (`startWebChild`):

| Condición                                               | Acción                            |
| ------------------------------------------------------- | --------------------------------- |
| Vite sale **antes** de `webReadyMarked`                 | `shutdown()` — boot fallido       |
| Vite sale **después** de ready                          | Reinicio en 1 s; API sigue viva   |
| > `MAX_WEB_QUICK_RESTARTS` (=3) consecutivos tras ready | `shutdown()` — guardia anti-bucle |
| API sale con código ≠ 0                                 | `shutdown()`                      |

Mensaje `ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL`: es la salida de **pnpm del hijo filtrado** cuando `vite` termina con exit ≠ 0; **no** implica `pnpm -r` en el padre. Tras ready, ese exit **no** derriba el stack salvo anti-bucle.

---

## 3. Gaps analizados — por qué no hay fix adicional mínimo

| Hipótesis                                          | Resultado                                                                                                                                                                                                             |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Proxy error sigue matando Vite → pnpm exit → stack | **Cerrado** por P3 + handler Vite interno (no fatal)                                                                                                                                                                  |
| pnpm recursive mata `run-dev` padre                | **No aplica** — padre es `node run-dev.mjs`, no recursive                                                                                                                                                             |
| Exit de hijo web mata stack tras ready             | **Cerrado** — autoreinicio a2                                                                                                                                                                                         |
| Exit de hijo web **antes** de ready por proxy      | **Teórico / bajo** — Vite arranca tras API healthy; sync pesado ocurre en caliente. Derribar stack aquí es **intencional** (boot roto). Ampliar autoreinicio a pre-ready enmascararía fallos reales (puerto, config). |
| ≥4 crashes seguidos (con o sin proxy)              | **Intencional** — guardia anti-bucle; no es gap de proxy                                                                                                                                                              |
| Crash silencioso de Vite sin `proxy error`         | **Residual distinto** (§4c plan 2026-08-09) — no es vía ECONNRESET                                                                                                                                                    |

**Conclusión:** no hay diff pequeño y seguro que cierre una vía proxy→stack no ya cubierta. Un reinicio pre-ready sería cambio de semántica con riesgo de ocultar boot failures.

---

## 4. Evidencia runtime

- Log reciente `logs/dev/dev-2026-09-01T14-47-20-915Z.log`: **0** ocurrencias de `ECONNRESET`, `proxy error`, `Deteniendo stack`, `ERR_PNPM`, `dev-proxy`, `Web (Vite) salió`.
- Plan P3 (2026-08-09): stress 10+ syncs concurrentes → stack vivo, 0 proxy error / ERR_PNPM en log.

---

## 5. Residual aceptado (fuera de alcance C2)

Queda documentado en [`dev-continuation-plan-2026-08-09.md`](./dev-continuation-plan-2026-08-09.md) §4c:

- **Crash silencioso “puro” de Vite** (exit 1 sin `proxy error` / `ECONNRESET`) — hipótesis HMR/chunk grande/Vite version.
- **Causa última** en API (cierre TCP en sync pesado) — fragilidad de red, no fatal para dev tras P3.

Opciones futuras (solo con runbook explícito; **no** mezclar LIVE):

| ID  | Acción                              | Ratio                      |
| --- | ----------------------------------- | -------------------------- |
| b   | Límite concurrencia sync en cliente | Medio · reduce carga API   |
| a1  | Subir Vite                          | Medio · crash silencioso   |
| a3  | Code-splitting chunk >500 kB        | Alto · M7                  |
| c   | API sin proxy Vite en dev           | Alto · cambio arquitectura |

---

## 6. Recomendación

1. **Aceptar F3.7 proxy→stack como RESIDUAL ACCEPTED** — P3 + a2 son suficientes para la vía ECONNRESET documentada.
2. **Operar dev con confianza** en syncs pesados; si reaparece `Deteniendo stack` **sin** `proxy error`, tratar como §4c (silent crash), no reabrir P3.
3. **No implementar** reinicio pre-ready ni tocar scheduler en este slice.
4. Si el dolor vuelve en caliente: valorar opción **(b)** límite concurrencia sync antes que re-arquitectura proxy.

Phase C2 **cierra en docs** sin cambio de código.
