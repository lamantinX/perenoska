from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_transfer_service
from app.schemas import TransferJobResponse, TransferLaunchRequest, TransferPreviewRequest, TransferPreviewResponse

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.get("", response_model=list[TransferJobResponse])
def list_transfers(
    user=Depends(get_current_user),
    transfer_service=Depends(get_transfer_service),
) -> list[TransferJobResponse]:
    return transfer_service.list_jobs(user["id"])


@router.post("/preview", response_model=TransferPreviewResponse)
async def preview_transfer(
    payload: TransferPreviewRequest,
    user=Depends(get_current_user),
    transfer_service=Depends(get_transfer_service),
) -> TransferPreviewResponse:
    return await transfer_service.preview(user["id"], payload)


@router.post("", response_model=TransferJobResponse)
async def launch_transfer(
    payload: TransferLaunchRequest,
    user=Depends(get_current_user),
    transfer_service=Depends(get_transfer_service),
) -> TransferJobResponse:
    return await transfer_service.launch(user["id"], payload)


@router.get("/{job_id}", response_model=TransferJobResponse)
def get_transfer(
    job_id: int,
    user=Depends(get_current_user),
    transfer_service=Depends(get_transfer_service),
) -> TransferJobResponse:
    return transfer_service.get_job(user["id"], job_id)


@router.post("/{job_id}/sync", response_model=TransferJobResponse)
async def sync_transfer(
    job_id: int,
    user=Depends(get_current_user),
    transfer_service=Depends(get_transfer_service),
) -> TransferJobResponse:
    return await transfer_service.sync_status(user["id"], job_id)
