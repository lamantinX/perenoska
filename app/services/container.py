from __future__ import annotations

from openai import AsyncOpenAI

from app.clients.base import MarketplaceClient
from app.clients.ozon import OzonClient
from app.clients.wb import WBClient
from app.config import Settings
from app.db import Database
from app.schemas import Marketplace
from app.security import CredentialVault, PasswordManager
from app.services.auth import AuthService
from app.services.connections import ConnectionService
from app.services.mapping import MappingService


class MarketplaceClientFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._overrides: dict[Marketplace, MarketplaceClient] = {}

    def register_override(self, marketplace: Marketplace, client: MarketplaceClient) -> None:
        self._overrides[marketplace] = client

    def get_client(self, marketplace: Marketplace) -> MarketplaceClient:
        if marketplace in self._overrides:
            return self._overrides[marketplace]
        if marketplace == Marketplace.WB:
            return WBClient(self.settings.wb_base_url, self.settings.http_timeout_seconds)
        return OzonClient(self.settings.ozon_base_url, self.settings.http_timeout_seconds)


class ServiceContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_path)
        self.password_manager = PasswordManager()
        self.vault = CredentialVault(settings.secret_key)
        self.client_factory = MarketplaceClientFactory(settings)
        self.connection_service = ConnectionService(self.database, self.vault)
        self.auth_service = AuthService(self.database, self.password_manager, settings.session_ttl_hours)
        self.llm_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
        self.mapping_service = MappingService(
            llm_client=self.llm_client,
            llm_model=settings.llm_model,
        )

