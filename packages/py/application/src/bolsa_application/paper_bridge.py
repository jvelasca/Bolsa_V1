"""Puente paper / broker D (gated)."""

from bolsa_application.paper_lab_evidence import (
    LAB_EVIDENCE_SETTINGS_KEY,
    lab_evidence_snapshot_from_blocks,
    merge_lab_evidence_snapshots,
)
from bolsa_domain.entities.account import InvestmentAccount
from bolsa_domain.repositories.research_trial_repository import ResearchTrialRepository
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.backtest_repository import (
    SqlAlchemyBacktestRepository,
)
from bolsa_infrastructure.database.repositories.strategy_definition_repository import (
    SqlAlchemyStrategyDefinitionRepository,
)


class DeployStrategyToPaperAccount:
    """BT-7 — crea cuenta paper vinculada a una StrategyDefinition ejecutable."""

    def __init__(
        self,
        account_repo: SqlAlchemyAccountRepository,
        strategy_repo: SqlAlchemyStrategyDefinitionRepository,
        backtest_repo: SqlAlchemyBacktestRepository,
        trial_repo: ResearchTrialRepository | None = None,
    ) -> None:
        self._account_repo = account_repo
        self._strategy_repo = strategy_repo
        self._backtest_repo = backtest_repo
        self._trial_repo = trial_repo

    async def execute(
        self,
        *,
        strategy_definition_id: str,
        initial_deposit: float | None = None,
        source_backtest_run_id: str | None = None,
        account_name: str | None = None,
        lab_evidence_hint: dict | None = None,
    ) -> InvestmentAccount:
        strategy = await self._strategy_repo.get_definition(strategy_definition_id)
        if strategy is None:
            raise ValueError("Estrategia no encontrada")
        if strategy.preset_key is None:
            raise ValueError(
                "Solo estrategias con preset ejecutable pueden desplegarse en paper (H0)",
            )

        deposit = initial_deposit
        if source_backtest_run_id:
            run = await self._backtest_repo.get_run(source_backtest_run_id)
            if run is None:
                raise ValueError("Backtest no encontrado")
            if run.strategy_definition_id != strategy_definition_id:
                raise ValueError("El backtest no corresponde a esta estrategia")
            if deposit is None:
                deposit = run.initial_cash

        if deposit is None:
            deposit = 10_000.0
        if deposit <= 0:
            raise ValueError("El depósito inicial debe ser mayor que cero")

        execution = strategy.definition.get("execution") or {}
        commission_bps = int(execution.get("commissionBps", 0))
        slippage_bps = int(execution.get("slippageBps", 0))
        name = account_name or f"Paper · {strategy.name}"
        description = (
            f"Forward-test paper (BT-7) · estrategia {strategy.id} · "
            f"preset {strategy.preset_key} · comisión ref. {commission_bps} bps · "
            f"slippage ref. {slippage_bps} bps"
        )
        if source_backtest_run_id:
            description += f" · origen backtest {source_backtest_run_id}"

        scope = await self._account_repo.create_paper_account(
            name=name,
            description=description,
            initial_deposit=deposit,
            portfolio_name=f"{strategy.name} — paper",
            portfolio_description="Cartera paper vinculada a estrategia",
            strategy_tag=f"preset:{strategy.preset_key}",
            strategy_definition_id=strategy_definition_id,
            source_backtest_run_id=source_backtest_run_id,
        )
        account = scope.account
        from_blocks = await self._resolve_lab_evidence_from_ledger(source_backtest_run_id)
        snapshot = merge_lab_evidence_snapshots(from_blocks, lab_evidence_hint)
        await self._account_repo.merge_settings_json(
            account.id,
            {LAB_EVIDENCE_SETTINGS_KEY: snapshot},
        )
        return await self._account_repo.get_account(account.id)

    async def _resolve_lab_evidence_from_ledger(
        self,
        source_backtest_run_id: str | None,
    ) -> dict:
        if not source_backtest_run_id or self._trial_repo is None:
            return lab_evidence_snapshot_from_blocks(
                None,
                source_backtest_run_id=source_backtest_run_id,
            )

        trials, _ = await self._trial_repo.list_trials(
            backtest_run_id=source_backtest_run_id,
            limit=1,
            offset=0,
        )
        trial = trials[0] if trials else None
        return lab_evidence_snapshot_from_blocks(
            trial.blocks if trial else None,
            trial_id=trial.id if trial else None,
            source_backtest_run_id=source_backtest_run_id,
        )
