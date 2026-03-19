from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.db import Database
from app.schemas import ConnectionResponse, ConnectionUpsert, Marketplace
from app.security import CredentialVault


class ConnectionService:
    def __init__(self, database: Database, vault: CredentialVault) -> None:
        self.database = database
        self.vault = vault

    def upsert_connection(self, user_id: int, payload: ConnectionUpsert) -> ConnectionResponse:
        if payload.marketplace == Marketplace.WB:
            credentials = {"token": payload.token}
        elif payload.marketplace == Marketplace.OZON:
            credentials = {"client_id": payload.client_id, "api_key": payload.api_key}
        else:
            credentials = {
                "token": payload.token,
                "business_id": payload.business_id,
                "campaign_id": payload.campaign_id,
            }
        row = self.database.upsert_connection(
            user_id=user_id,
            marketplace=payload.marketplace.value,
            credentials_encrypted=self.vault.encrypt_json(credentials),
            now=datetime.now(UTC).isoformat(),
        )
        return self._to_response(row, credentials)

    def list_connections(self, user_id: int) -> list[ConnectionResponse]:
        rows = self.database.list_connections(user_id)
        configured = {row["marketplace"]: row for row in rows}
        responses: list[ConnectionResponse] = []
        for marketplace in Marketplace:
            row = configured.get(marketplace.value)
            if row is None:
                responses.append(
                    ConnectionResponse(
                        marketplace=marketplace,
                        is_configured=False,
                        masked_fields={},
                        updated_at=None,
                    )
                )
                continue
            credentials = self.vault.decrypt_json(row["credentials_encrypted"])
            responses.append(self._to_response(row, credentials))
        return responses

    def get_credentials(self, user_id: int, marketplace: Marketplace) -> dict:
        row = self.database.get_connection(user_id, marketplace.value)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Подключение {marketplace.value} не настроено.",
            )
        return self.vault.decrypt_json(row["credentials_encrypted"])

    def _to_response(self, row: dict, credentials: dict) -> ConnectionResponse:
        return ConnectionResponse(
            marketplace=Marketplace(row["marketplace"]),
            is_configured=True,
            masked_fields={key: self._mask_value(value) for key, value in credentials.items()},
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _mask_value(value: str | int | None) -> str:
        if value in {None, ""}:
            return ""
        value = str(value)
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
