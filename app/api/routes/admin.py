from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_admin_user, get_container
from app.schemas import (
    AddPaymentEntry,
    AdminJobLogEntry,
    AdminStatsResponse,
    AdminTransferResponse,
    AdminUpdateUser,
    AdminUserDetailResponse,
    AdminUserResponse,
    PaymentHistoryEntry,
    SystemSettings,
    TopUserEntry,
    TransfersByDayEntry,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserResponse])
def admin_list_users(
    search: str | None = Query(default=None),
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> list[AdminUserResponse]:
    db = container.database
    users = db.admin_list_users(search=search)
    result: list[AdminUserResponse] = []
    for u in users:
        user_id = int(u["id"])
        transfer_count = db.admin_count_transfers_for_user(user_id)
        connections = db.admin_list_connections_for_user(user_id)
        result.append(
            AdminUserResponse(
                id=user_id,
                email=str(u["email"]),
                phone=u.get("phone"),
                is_blocked=bool(u.get("is_blocked", 0)),
                created_at=str(u["created_at"]),
                plan_expires_at=u.get("plan_expires_at"),
                transfer_limit=u.get("transfer_limit"),
                transfer_count=transfer_count,
                connections=connections,
            )
        )
    return result


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def admin_get_user(
    user_id: int,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> AdminUserDetailResponse:
    db = container.database
    u = db.admin_get_user(user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    transfer_count = db.admin_count_transfers_for_user(user_id)
    connections = db.admin_list_connections_for_user(user_id)
    payment_rows = db.admin_list_payment_history(user_id)
    payments = [
        PaymentHistoryEntry(
            id=int(p["id"]),
            plan_name=str(p["plan_name"]),
            amount=float(p["amount"]),
            currency=str(p["currency"]),
            created_at=str(p["created_at"]),
        )
        for p in payment_rows
    ]
    return AdminUserDetailResponse(
        id=int(u["id"]),
        email=str(u["email"]),
        phone=u.get("phone"),
        is_blocked=bool(u.get("is_blocked", 0)),
        created_at=str(u["created_at"]),
        plan_expires_at=u.get("plan_expires_at"),
        transfer_limit=u.get("transfer_limit"),
        transfer_count=transfer_count,
        connections=connections,
        payment_history=payments,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(
    user_id: int,
    payload: AdminUpdateUser,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> AdminUserResponse:
    db = container.database
    data = payload.model_dump()
    is_blocked_val: int | None = None
    if data.get("is_blocked") is not None:
        is_blocked_val = 1 if data["is_blocked"] else 0

    # Detect explicit None for nullable fields to allow clearing them
    # pydantic passes None when the field is omitted OR set to null;
    # we distinguish "not provided" vs "explicitly null" via model_fields_set
    unset_transfer_limit = (
        "transfer_limit" in payload.model_fields_set and payload.transfer_limit is None
    )
    unset_plan_expires_at = (
        "plan_expires_at" in payload.model_fields_set and payload.plan_expires_at is None
    )

    updated = db.admin_update_user(
        user_id=user_id,
        phone=payload.phone,
        is_blocked=is_blocked_val,
        plan_expires_at=payload.plan_expires_at,
        transfer_limit=payload.transfer_limit,
        _unset_transfer_limit=unset_transfer_limit,
        _unset_plan_expires_at=unset_plan_expires_at,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    transfer_count = db.admin_count_transfers_for_user(user_id)
    connections = db.admin_list_connections_for_user(user_id)
    return AdminUserResponse(
        id=int(updated["id"]),
        email=str(updated["email"]),
        phone=updated.get("phone"),
        is_blocked=bool(updated.get("is_blocked", 0)),
        created_at=str(updated["created_at"]),
        plan_expires_at=updated.get("plan_expires_at"),
        transfer_limit=updated.get("transfer_limit"),
        transfer_count=transfer_count,
        connections=connections,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> None:
    db = container.database
    deleted = db.admin_delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("/users/{user_id}/payment", response_model=PaymentHistoryEntry, status_code=status.HTTP_201_CREATED)
def admin_add_payment(
    user_id: int,
    payload: AddPaymentEntry,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> PaymentHistoryEntry:
    db = container.database
    u = db.admin_get_user(user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    now = datetime.now(UTC).isoformat()
    entry = db.admin_add_payment(
        user_id=user_id,
        plan_name=payload.plan_name,
        amount=payload.amount,
        currency=payload.currency,
        created_at=now,
    )
    return PaymentHistoryEntry(
        id=int(entry["id"]),
        plan_name=str(entry["plan_name"]),
        amount=float(entry["amount"]),
        currency=str(entry["currency"]),
        created_at=str(entry["created_at"]),
    )


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------


@router.get("/transfers", response_model=list[AdminTransferResponse])
def admin_list_transfers(
    user_id: int | None = Query(default=None),
    transfer_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> list[AdminTransferResponse]:
    db = container.database
    rows = db.admin_list_transfers(
        user_id=user_id,
        status=transfer_status,
        limit=limit,
        offset=offset,
    )
    return [
        AdminTransferResponse(
            id=int(r["id"]),
            user_id=int(r["user_id"]),
            user_email=str(r["user_email"]),
            source_marketplace=str(r["source_marketplace"]),
            target_marketplace=str(r["target_marketplace"]),
            status=str(r["status"]),
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
            error_message=r.get("error_message"),
            base_token=r.get("base_token"),
            external_task_id=r.get("external_task_id"),
        )
        for r in rows
    ]


@router.post("/transfers/{job_id}/cancel", response_model=dict)
def admin_cancel_transfer(
    job_id: int,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> dict:
    db = container.database
    now = datetime.now(UTC).isoformat()
    cancelled = db.admin_cancel_transfer(job_id, now)
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer job not found")
    return {"ok": True, "job_id": job_id}


@router.get("/transfers/{job_id}/logs", response_model=list[AdminJobLogEntry])
def admin_get_transfer_logs(
    job_id: int,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> list[AdminJobLogEntry]:
    db = container.database
    rows = db.admin_list_job_logs(job_id)
    return [
        AdminJobLogEntry(
            id=int(r["id"]),
            token=str(r["token"]),
            base_token=str(r["base_token"]),
            sequence_no=int(r["sequence_no"]),
            event_type=str(r["event_type"]),
            operation=str(r["operation"]),
            request_url=str(r["request_url"]),
            status_code=r.get("status_code"),
            duration_ms=r.get("duration_ms"),
            error_text=r.get("error_text"),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AdminStatsResponse)
def admin_get_stats(
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> AdminStatsResponse:
    db = container.database
    raw = db.admin_get_stats()
    return AdminStatsResponse(
        total_users=raw["total_users"],
        total_transfers=raw["total_transfers"],
        today_transfers=raw["today_transfers"],
        successful_transfers=raw["successful_transfers"],
        failed_transfers=raw["failed_transfers"],
        top_users=[TopUserEntry(**u) for u in raw["top_users"]],
        transfers_by_day=[TransfersByDayEntry(**d) for d in raw["transfers_by_day"]],
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=SystemSettings)
def admin_get_settings(
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> SystemSettings:
    db = container.database
    raw = db.get_all_settings()
    return SystemSettings(
        registration_enabled=raw.get("registration_enabled", "true").lower() == "true",
        banner_text=raw.get("banner_text", ""),
        default_transfer_limit=int(raw.get("default_transfer_limit", "100")),
    )


@router.put("/settings", response_model=SystemSettings)
def admin_update_settings(
    payload: SystemSettings,
    _admin=Depends(get_admin_user),
    container=Depends(get_container),
) -> SystemSettings:
    db = container.database
    db.set_setting("registration_enabled", "true" if payload.registration_enabled else "false")
    db.set_setting("banner_text", payload.banner_text)
    db.set_setting("default_transfer_limit", str(payload.default_transfer_limit))
    return payload
