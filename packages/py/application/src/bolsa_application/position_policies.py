from typing import Any

from bolsa_domain.entities.position_policy import PositionPolicyRecord
from bolsa_domain.platform_kernel import validate_position_execution_mode
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.position_policy_repository import PositionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_infrastructure.database.repositories.account_repository import SqlAlchemyAccountRepository


def build_position_policy_definition(
    *,
    policy_id: str,
    account_id: str,
    instrument_id: str,
    mode: str,
    exit_strategy_definition_id: str | None,
    execution_policy_id: str | None,
    created_at: str,
    updated_at: str,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "id": policy_id,
        "accountId": account_id,
        "instrumentId": instrument_id,
        "mode": mode,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }
    if exit_strategy_definition_id is not None:
        definition["exitStrategyDefinitionId"] = exit_strategy_definition_id
    if execution_policy_id is not None:
        definition["executionPolicyId"] = execution_policy_id
    return definition


def _validate_mode_refs(
    mode: str,
    *,
    exit_strategy_definition_id: str | None,
    execution_policy_id: str | None,
) -> None:
    if mode == "exit_strategy" and not exit_strategy_definition_id:
        raise ValueError("exitStrategyDefinitionId es obligatorio para mode=exit_strategy")
    if mode == "full_auto" and not execution_policy_id:
        raise ValueError("executionPolicyId es obligatorio para mode=full_auto")


class ListPositionPolicies:
    def __init__(self, repository: PositionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, *, account_id: str | None = None, limit: int = 100) -> list[PositionPolicyRecord]:
        return await self._repository.list_policies(account_id=account_id, limit=limit)


class GetPositionPolicy:
    def __init__(self, repository: PositionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, policy_id: str) -> PositionPolicyRecord | None:
        return await self._repository.get_policy(policy_id)


class GetPositionPolicyForHolding:
    def __init__(self, repository: PositionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, account_id: str, instrument_id: str) -> PositionPolicyRecord | None:
        return await self._repository.get_by_account_instrument(account_id, instrument_id)


class CreatePositionPolicy:
    def __init__(
        self,
        repository: PositionPolicyRepository,
        account_repository: SqlAlchemyAccountRepository,
        instrument_repository: InstrumentRepository,
        strategy_repository: StrategyDefinitionRepository,
        execution_policy_repository: ExecutionPolicyRepository,
    ) -> None:
        self._repository = repository
        self._accounts = account_repository
        self._instruments = instrument_repository
        self._strategies = strategy_repository
        self._execution_policies = execution_policy_repository

    async def execute(
        self,
        *,
        account_id: str,
        instrument_id: str,
        mode: str = "manual",
        exit_strategy_definition_id: str | None = None,
        execution_policy_id: str | None = None,
    ) -> PositionPolicyRecord:
        mode = validate_position_execution_mode(mode)
        _validate_mode_refs(
            mode,
            exit_strategy_definition_id=exit_strategy_definition_id,
            execution_policy_id=execution_policy_id,
        )

        await self._accounts.resolve_scope(account_id)
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        existing = await self._repository.get_by_account_instrument(account_id, instrument_id)
        if existing is not None:
            raise ValueError("Ya existe una política para esta cuenta e instrumento")

        if exit_strategy_definition_id:
            strategy = await self._strategies.get_definition(exit_strategy_definition_id)
            if strategy is None:
                raise ValueError("Estrategia de salida no encontrada")

        if execution_policy_id:
            policy = await self._execution_policies.get_policy(execution_policy_id)
            if policy is None:
                raise ValueError("ExecutionPolicy no encontrada")

        record = await self._repository.create_policy(
            account_id=account_id,
            instrument_id=instrument_id,
            definition={},
            mode=mode,
            exit_strategy_definition_id=exit_strategy_definition_id,
            execution_policy_id=execution_policy_id,
        )
        definition = build_position_policy_definition(
            policy_id=record.id,
            account_id=account_id,
            instrument_id=instrument_id,
            mode=mode,
            exit_strategy_definition_id=exit_strategy_definition_id,
            execution_policy_id=execution_policy_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        updated = await self._repository.update_policy(record.id, definition=definition, mode=mode)
        return updated or record


class UpdatePositionPolicy:
    def __init__(
        self,
        repository: PositionPolicyRepository,
        strategy_repository: StrategyDefinitionRepository,
        execution_policy_repository: ExecutionPolicyRepository,
    ) -> None:
        self._repository = repository
        self._strategies = strategy_repository
        self._execution_policies = execution_policy_repository

    async def execute(
        self,
        policy_id: str,
        *,
        mode: str | None = None,
        exit_strategy_definition_id: str | None = None,
        execution_policy_id: str | None = None,
    ) -> PositionPolicyRecord | None:
        existing = await self._repository.get_policy(policy_id)
        if existing is None:
            return None

        resolved_mode = validate_position_execution_mode(mode or existing.mode)
        resolved_exit = (
            exit_strategy_definition_id
            if exit_strategy_definition_id is not None
            else existing.exit_strategy_definition_id
        )
        resolved_exec = (
            execution_policy_id if execution_policy_id is not None else existing.execution_policy_id
        )
        _validate_mode_refs(
            resolved_mode,
            exit_strategy_definition_id=resolved_exit,
            execution_policy_id=resolved_exec,
        )

        if exit_strategy_definition_id is not None and exit_strategy_definition_id:
            strategy = await self._strategies.get_definition(exit_strategy_definition_id)
            if strategy is None:
                raise ValueError("Estrategia de salida no encontrada")

        if execution_policy_id is not None and execution_policy_id:
            policy = await self._execution_policies.get_policy(execution_policy_id)
            if policy is None:
                raise ValueError("ExecutionPolicy no encontrada")

        definition = build_position_policy_definition(
            policy_id=policy_id,
            account_id=existing.account_id,
            instrument_id=existing.instrument_id,
            mode=resolved_mode,
            exit_strategy_definition_id=resolved_exit,
            execution_policy_id=resolved_exec,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        return await self._repository.update_policy(
            policy_id,
            definition=definition,
            mode=resolved_mode,
            exit_strategy_definition_id=exit_strategy_definition_id,
            execution_policy_id=execution_policy_id,
        )


class DeletePositionPolicy:
    def __init__(self, repository: PositionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, policy_id: str) -> bool:
        return await self._repository.delete_policy(policy_id)
