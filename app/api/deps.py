from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings
from app.services.catalog import CatalogService
from app.services.category_mapper import CategoryMapper
from app.services.transfer import TransferService

security = HTTPBearer(auto_error=False)


def get_container(request: Request):
    return request.app.state.container


def get_config(container=Depends(get_container)) -> Settings:
    return container.settings


def get_auth_service(container=Depends(get_container)):
    return container.auth_service


def get_connection_service(container=Depends(get_container)):
    return container.connection_service


def get_catalog_service(container=Depends(get_container)) -> CatalogService:
    return CatalogService(container.connection_service, container.client_factory)


def get_transfer_service(container=Depends(get_container)) -> TransferService:
    catalog_service = CatalogService(container.connection_service, container.client_factory)
    return TransferService(
        database=container.database,
        connection_service=container.connection_service,
        catalog_service=catalog_service,
        client_factory=container.client_factory,
        mapping_service=container.mapping_service,
        category_mapper=container.category_mapper,
    )


def get_category_mapper(container=Depends(get_container)) -> CategoryMapper:
    return container.category_mapper


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service=Depends(get_auth_service),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужен Bearer token.")
    return auth_service.get_current_user(credentials.credentials)


def get_admin_user(
    current_user=Depends(get_current_user),
    config: Settings = Depends(get_config),
):
    if current_user["email"].lower() not in config.admin_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

