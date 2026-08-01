# Perfil ↔ Coach / Lab (CORE-P)

> Binding cuenta activa → política Coach/Lab. Complementa
> [`assistant-play-funnel-design-2026-07-29.md`](./assistant-play-funnel-design-2026-07-29.md) §3
> e [`ISSUES.md`](../../research/observations/ISSUES.md) · CORE-P.

## Contrato

```text
Cuenta activa → InvestorProfile (declared)
            → resolveCoachProfilePolicy()
            → CoachProfilePolicy
```

| Campo | Uso |
|-------|-----|
| `allowLabIfWeak` | Fallback del gate Coach¹→Lab si el check Asistente no manda |
| `maxDrawdownSoftPct` | Lab: no adoptar Mejor si \|DD\| > techo |
| `suggestedFutureWeight` | Hint (UI puede seguir el pref del rail) |
| `policyVersion` + `profileId` | Stamp en `coachFacts` + fingerprint frescura |

**Check Asistente `labEvenIfWeak` manda** sobre `allowLabIfWeak` del perfil.

## Techos DD (v1)

| riskTolerance | soft DD % |
|---------------|-----------|
| low | 18 |
| (ausente) | 25 |
| moderate | 28 |
| high | 40 |

## Código

- `apps/web/src/features/backtests/coach-profile-policy.ts`
- Stamp Finalistas: `backtest-explore-panel` → `buildCoachProfileBindingFacts`
- Lab: `BacktestOptimizePanel.maxDrawdownSoftPct` + `labImprovedRespectingProfileDd`
- Soft-bias: `labSpaceWidthFactorForRisk` + `scaleSearchSpace`
- Rail: `formatCoachProfileRailLabel`
- Invalidación ciclo: cambio `accountId` / `profileId` aborta Play / Lista AUTO

## Hecho (iteración deep-dive)

- Familias preferidas por horizonte → hint + orden en Lab (`preferredLabFamiliesForHorizon`)
- Familia Lab por defecto sin semilla: `resolveDefaultLabFamily` (adopción → horizonte → SMA) · CORE-B v0.2
- Soft-bias espacio Lab por `riskTolerance` (`labSpaceWidthFactorForRisk` · low ×0.75 / high ×1.35)
- Aviso UI si Finalistas `active`/`semifinal` tienen `coachFacts.profileId` ≠ perfil activo
  (`activeTopProfileMismatch`) — no pisa ni borra el TOP

## Pendiente (iteraciones)

- BETA1: vigilar simulaciones multi-perfil en uso real
- (Cerrado) E2E live: `pnpm test:coach:smoke` · `verify_core_p_api_smoke.py`
