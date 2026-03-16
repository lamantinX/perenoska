from __future__ import annotations

from app.schemas import CategoryAttribute, CategoryNode, Marketplace, ProductDetails, ProductSummary
from app.services.connections import ConnectionService
from app.services.container import MarketplaceClientFactory


class CatalogService:
    def __init__(self, connection_service: ConnectionService, client_factory: MarketplaceClientFactory) -> None:
        self.connection_service = connection_service
        self.client_factory = client_factory

    async def list_products(self, user_id: int, marketplace: Marketplace, limit: int = 50) -> list[ProductSummary]:
        credentials = self.connection_service.get_credentials(user_id, marketplace)
        client = self.client_factory.get_client(marketplace)
        return await client.list_products(credentials, limit=limit)

    async def get_product_details(self, user_id: int, marketplace: Marketplace, product_id: str) -> ProductDetails:
        credentials = self.connection_service.get_credentials(user_id, marketplace)
        client = self.client_factory.get_client(marketplace)
        return await client.get_product_details(credentials, product_id)

    async def list_categories(
        self,
        user_id: int,
        marketplace: Marketplace,
        parent_id: int | None = None,
    ) -> list[CategoryNode]:
        credentials = self.connection_service.get_credentials(user_id, marketplace)
        client = self.client_factory.get_client(marketplace)
        return await client.list_categories(credentials, parent_id=parent_id)

    async def get_category_attributes(
        self,
        user_id: int,
        marketplace: Marketplace,
        category_id: int,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        credentials = self.connection_service.get_credentials(user_id, marketplace)
        client = self.client_factory.get_client(marketplace)
        return await client.get_category_attributes(credentials, category_id, required_only=required_only)

    async def get_category_attributes_for_category(
        self,
        user_id: int,
        marketplace: Marketplace,
        category: CategoryNode,
        *,
        source_product: ProductDetails | None = None,
        required_only: bool = False,
    ) -> list[CategoryAttribute]:
        credentials = self.connection_service.get_credentials(user_id, marketplace)
        client = self.client_factory.get_client(marketplace)
        method = getattr(client, "get_category_attributes_for_node", None)
        if callable(method):
            return await method(
                credentials,
                category,
                source_product=source_product,
                required_only=required_only,
            )
        return await client.get_category_attributes(credentials, category.id, required_only=required_only)
