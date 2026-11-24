import asyncio

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.ocr import DatePreviewResponse
from app.workers.pool import get_pool, process_image_task

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/date-preview", response_model=DatePreviewResponse)
async def preview_date_photo(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Anteprima OCR in tempo reale sulla sola foto della data, chiamata dal frontend
    subito dopo lo scatto (prima della conferma del prodotto): serve solo a dare un
    feedback immediato in UI ("data letta" / "rifai la foto"), non persiste nulla —
    la lettura definitiva della data avviene comunque nella pipeline batch a
    `POST /batches`, come per il titolo."""
    raw_bytes = await file.read()

    loop = asyncio.get_running_loop()
    outcome = await loop.run_in_executor(get_pool(), process_image_task, raw_bytes, "data")
    if not outcome["ok"]:
        return DatePreviewResponse(data_candidata=None, confidence=None, errore=outcome["errore"])
    return DatePreviewResponse(
        data_candidata=outcome["data_candidata"],
        confidence=outcome["confidence"],
        data_candidati_alternativi=outcome["data_candidati_alternativi"],
    )
