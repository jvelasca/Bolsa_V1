# Premisas de cuenta — DEMO vs PAPER (2026-07-31)

> Premisas de producto **bloqueadas**. Complementa [DATA_MODEL](../DATA_MODEL.md), [ADR-010](../adr/010-platform-kernel-radar-execution.md), [research-radar-unification](./research-radar-unification-2026-07-31.md).

**AsOf:** 2026-07-31

---

## 1. Veredicto

Sí: **correcto y óptimo** para esta fase.

| Premisa | Decisión |
|---------|----------|
| **Una sola cuenta operativa** | La marcada como **Activa** en Cuentas (barra inferior / «Usar ahora»). Trading, ledger, perfil Coach, Checklist, Radar, Supervisado y propose usan **solo** esa. |
| **Ahora = solo DEMO** | Tipo técnico `simulated`. Capital y PnL **simulados** en ledger interno. |
| **PAPER = futuro broker real** | Tipo técnico `paper` (y/o `live` más adelante): cuentas con **API de operador bursátil**, dinero/órdenes reales. **No** es “paper trading” de simulación. |
| **Hasta brokers** | No crear ni operar cuentas `paper`. Los caminos A/B/C/D escriben en la **cuenta activa DEMO**. |

---

## 2. Glosario (evitar confusión)

| Lenguaje producto | Tipo BD (`InvestmentAccountType`) | Ahora | Futuro |
|-------------------|-------------------------------------|-------|--------|
| **Demo** | `simulated` | ✅ Operativo | Sigue existiendo para práctica |
| **Paper** | `paper` | ❌ No usar | Cuenta **real** enlazada a broker vía API |
| **Live** | `live` | ❌ Reservado | Posible sinónimo/estricto de producción (detalle al cablear brokers) |

**Importante — homonimia “paper”:**

- En inglés de mercado, *paper trading* = simulación.
- En Bolsa V1, el **tipo de cuenta Paper** = **operación real futura**.
- Los textos históricos «Desplegar en paper», `paper_auto`, «Paper D» significaban *ledger simulado / política de ejecución*. A partir de esta fecha el copy de producto dice **demo / cuenta activa**; los IDs técnicos (`paper_auto`, `PAPER_PATH_*`, `Paper D`) se mantienen por compatibilidad hasta un rename controlado.

---

## 3. Mapa caminos A/B/C/D → cuenta

```text
Cuenta ACTIVA (hoy: DEMO / simulated)
        │
        ├─ A Checklist «Desplegar en demo»  → ledger DEMO
        ├─ B Radar alarmas / (futuro auto) → misma cuenta si se ejecuta
        │     └─ Inbox Trading (campana) ← scan manual + jobs on_bar_close (B1.1–B1.2)
        │           └─ CTA F3 → Supervisado Confirm (B1.3 · origen alarm)
        ├─ C Supervisado F3 Confirm        → misma cuenta
        └─ D Paper D propose/execute       → misma cuenta DEMO (execute off-by-default)
```

Ningún camino abre una segunda cartera “en paralelo” distinta de la activa.

---

## 4. Auditoría de focos erróneos (hallazgos)

| Sitio | Qué decía / hacía | Corrección |
|-------|-------------------|------------|
| Copy «Desplegar en paper», «Lab → paper» | Sugiere tipo cuenta Paper | → **demo / cuenta activa** (`paper-paths-copy.ts`) |
| Ayuda Cuentas «demos o paper» | Paper como alternativa operativa hoy | → Paper = futuro broker |
| `PAPER_ACCOUNT_TYPES = {paper, simulated}` | Router acepta ambos para `paper_auto` | OK técnicamente (demo incluido); doc: hoy solo DEMO |
| Hub Cuentas filtro Paper | Existe UI | Etiqueta **Paper (futuro · broker)**; no crear |
| FIE / Paper D / radar docs | “auto-paper” | Aclarar = auto sobre **ledger DEMO activo**, no tipo Paper |
| Tipo `paper` en BD / deploy Lab | Historial P7 “cuenta paper” | Congelado: nuevos deploys → cuenta **activa DEMO** |

No se borran enums ni modos `paper_auto` (rompe APIs); se **reencuadra** el significado de producto.

---

## 5. Reglas de implementación (checklist)

1. UI de creación de cuenta: solo **Nueva demo** (`simulated`).
2. Selector global: una **Activa**; todo scope `accountId` = esa.
3. No ofrecer “crear Paper” hasta brokers.
4. Copy de despliegue: **demo**, no “paper account”.
5. Cuando lleguen brokers: nueva especificación (auth API, `live`/`paper`, risk gates) — fuera de esta premisa.

---

## 6. Relacionados

- Copy caminos: `apps/web/src/features/settings/paper-paths-copy.ts`
- Tipos: `packages/shared/src/accounts.ts`
- Ayuda: Ayuda → Cuentas / Overview (`app-help-menu.tsx`)
- Kernel: `PAPER_ACCOUNT_TYPES` en `bolsa_domain.platform_kernel`
