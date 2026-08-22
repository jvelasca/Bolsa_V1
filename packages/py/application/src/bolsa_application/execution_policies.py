"""Use-cases de políticas de ejecución."""

from typing import Any

from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.platform_kernel import DEFAULT_SIGNAL_KINDS, validate_execution_mode
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_infrastructure.alerts.alert_channels import (
    normalize_alert_channels,
    validate_alert_channel_config,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)


def build_execution_policy_definition(
    *,
    policy_id: str,
    name: str,
    mode: str,
    account_id: str | None,
    strategy_definition_id: str | None,
    signal_kinds: list[str],
    channels: list[str] | None,
    webhook_url: str | None,
    email_to: str | None,
    require_validated_backtest: bool,
    origin: str,
    enabled: bool,
    created_at: str,
    updated_at: str,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "id": policy_id,
        "name": name,
        "mode": mode,
        "accountId": account_id,
        "strategyDefinitionId": strategy_definition_id,
        "signalKinds": signal_kinds,
        "requireValidatedBacktest": require_validated_backtest,
        "origin": origin,
        "enabled": enabled,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }
    if channels is not None:
        definition["channels"] = channels
    if webhook_url is not None:
        definition["webhookUrl"] = webhook_url
    if email_to is not None:
        definition["emailTo"] = email_to
    return definition


class ListExecutionPolicies:
    """Lista Execution Policies."""
    def __init__(self, repository: ExecutionPolicyRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        limit: int = 50,
        enabled_only: bool = False,
        owner_user_id: str | None = None,
    ) -> list[ExecutionPolicyRecord]:
        return await self._repository.list_policies(
            limit=limit,
            enabled_only=enabled_only,
            owner_user_id=owner_user_id,
        )


class GetExecutionPolicy:
    """Obtiene Execution Policy."""
    def __init__(self, repository: ExecutionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, policy_id: str) -> ExecutionPolicyRecord | None:
        return await self._repository.get_policy(policy_id)


class CreateExecutionPolicy:
    """Crea Execution Policy."""
    def __init__(
        self,
        repository: ExecutionPolicyRepository,
        strategy_repository: StrategyDefinitionRepository,
        account_repository: SqlAlchemyAccountRepository,
    ) -> None:
        self._repository = repository
        self._strategies = strategy_repository
        self._accounts = account_repository

    async def execute(
        self,
        *,
        name: str,
        mode: str,
        account_id: str | None = None,
        strategy_definition_id: str | None = None,
        signal_kinds: list[str] | None = None,
        channels: list[str] | None = None,
        webhook_url: str | None = None,
        email_to: str | None = None,
        require_validated_backtest: bool = False,
        origin: str = "manual",
        enabled: bool = True,
        user_id: str | None = None,
    ) -> ExecutionPolicyRecord:
        mode = validate_execution_mode(mode)
        kinds = list(signal_kinds or DEFAULT_SIGNAL_KINDS)
        if not kinds:
            raise ValueError("signalKinds no puede estar vacío")

        if strategy_definition_id:
            strategy = await self._strategies.get_definition(strategy_definition_id)
            if strategy is None:
                raise ValueError("Estrategia no encontrada")

        if account_id:
            await self._accounts.resolve_scope(account_id)

        normalized_channels = normalize_alert_channels(channels) if mode == "alert" else None
        if mode == "alert" and normalized_channels:
            validate_alert_channel_config(normalized_channels, webhook_url=webhook_url, email_to=email_to)

        if mode == "paper_auto" and not account_id:
            raise ValueError("accountId es obligatorio para mode=paper_auto")

        record = await self._repository.create_policy(
            name=name,
            definition={},
            mode=mode,
            account_id=account_id,
            strategy_definition_id=strategy_definition_id,
            origin=origin,
            enabled=enabled,
            user_id=user_id,
        )
        definition = build_execution_policy_definition(
            policy_id=record.id,
            name=name,
            mode=mode,
            account_id=account_id,
            strategy_definition_id=strategy_definition_id,
            signal_kinds=kinds,
            channels=normalized_channels,
            webhook_url=webhook_url,
            email_to=email_to,
            require_validated_backtest=require_validated_backtest,
            origin=origin,
            enabled=enabled,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        updated = await self._repository.update_policy(record.id, definition=definition, name=name)
        return updated or record


class UpdateExecutionPolicy:
    """Actualiza Execution Policy."""
    def __init__(
        self,
        repository: ExecutionPolicyRepository,
        strategy_repository: StrategyDefinitionRepository,
        account_repository: SqlAlchemyAccountRepository,
    ) -> None:
        self._repository = repository
        self._strategies = strategy_repository
        self._accounts = account_repository

    async def execute(
        self,
        policy_id: str,
        *,
        name: str | None = None,
        mode: str | None = None,
        account_id: str | None = None,
        strategy_definition_id: str | None = None,
        signal_kinds: list[str] | None = None,
        channels: list[str] | None = None,
        webhook_url: str | None = None,
        email_to: str | None = None,
        require_validated_backtest: bool | None = None,
        enabled: bool | None = None,
    ) -> ExecutionPolicyRecord | None:
        existing = await self._repository.get_policy(policy_id)
        if existing is None:
            return None

        current = dict(existing.definition)
        resolved_name = name if name is not None else existing.name
        resolved_mode = validate_execution_mode(mode or existing.mode)
        resolved_account_id = account_id if account_id is not None else existing.account_id
        resolved_strategy_id = (
            strategy_definition_id if strategy_definition_id is not None else existing.strategy_definition_id
        )
        resolved_kinds = signal_kinds if signal_kinds is not None else list(current.get("signalKinds") or DEFAULT_SIGNAL_KINDS)
        resolved_require = (
            require_validated_backtest
            if require_validated_backtest is not None
            else bool(current.get("requireValidatedBacktest", False))
        )
        resolved_enabled = enabled if enabled is not None else existing.enabled
        resolved_channels = channels if channels is not None else current.get("channels")
        resolved_webhook = webhook_url if webhook_url is not None else current.get("webhookUrl")
        resolved_email = email_to if email_to is not None else current.get("emailTo")

        if strategy_definition_id is not None and strategy_definition_id:
            strategy = await self._strategies.get_definition(strategy_definition_id)
            if strategy is None:
                raise ValueError("Estrategia no encontrada")

        if resolved_account_id:
            await self._accounts.resolve_scope(resolved_account_id)

        normalized_channels = None
        if resolved_mode == "alert":
            normalized_channels = normalize_alert_channels(resolved_channels)
            validate_alert_channel_config(
                normalized_channels,
                webhook_url=str(resolved_webhook) if resolved_webhook else None,
                email_to=str(resolved_email) if resolved_email else None,
            )

        if resolved_mode == "paper_auto" and not resolved_account_id:
            raise ValueError("accountId es obligatorio para mode=paper_auto")

        definition = build_execution_policy_definition(
            policy_id=policy_id,
            name=resolved_name,
            mode=resolved_mode,
            account_id=resolved_account_id,
            strategy_definition_id=resolved_strategy_id,
            signal_kinds=[str(k) for k in resolved_kinds],
            channels=normalized_channels if resolved_mode == "alert" else None,
            webhook_url=str(resolved_webhook) if resolved_webhook else None,
            email_to=str(resolved_email) if resolved_email else None,
            require_validated_backtest=resolved_require,
            origin=existing.origin,
            enabled=resolved_enabled,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        return await self._repository.update_policy(
            policy_id,
            name=resolved_name,
            definition=definition,
            mode=resolved_mode,
            account_id=account_id,
            strategy_definition_id=strategy_definition_id,
            enabled=enabled,
        )


class DeleteExecutionPolicy:
    """Elimina Execution Policy."""
    def __init__(self, repository: ExecutionPolicyRepository) -> None:
        self._repository = repository

    async def execute(self, policy_id: str) -> bool:
        return await self._repository.delete_policy(policy_id)
