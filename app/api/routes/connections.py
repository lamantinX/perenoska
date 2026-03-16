from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_connection_service, get_current_user
from app.schemas import ConnectionResponse, ConnectionUpsert, Marketplace

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionResponse])
def list_connections(
    user=Depends(get_current_user),
    connection_service=Depends(get_connection_service),
) -> list[ConnectionResponse]:
    return connection_service.list_connections(user["id"])


@router.put("/{marketplace}", response_model=ConnectionResponse)
def upsert_connection(
    marketplace: Marketplace,
    payload: ConnectionUpsert,
    user=Depends(get_current_user),
    connection_service=Depends(get_connection_service),
) -> ConnectionResponse:
    if marketplace != payload.marketplace:
        payload = payload.model_copy(update={"marketplace": marketplace})
    return connection_service.upsert_connection(user["id"], payload)

