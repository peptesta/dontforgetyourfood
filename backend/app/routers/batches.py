import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import CurrentUser, get_current_user
from app.db.models import Batch, BatchItem, Product
from app.db.session import async_session, get_db
from app.schemas.batch import (
    BatchConfirmRequest,
    BatchConfirmResponse,
    BatchConfirmResponseItem,
    BatchItemRead,
    BatchRead,
)
from app.services.batch_processor import create_batch, process_batch
from app.workers.pool import get_pool

router = APIRouter(prefix="/batches", tags=["batches"])


async def _load_owned_batch(db: AsyncSession, batch_id: uuid.UUID, household_id: uuid.UUID) -> Batch:
    batch = await db.get(Batch, batch_id)
    if batch is None or batch.household_id != household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch non trovato")
    return batch


async def _load_items(db: AsyncSession, batch_id: uuid.UUID) -> list[BatchItem]:
    result = await db.execute(
        select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.ordine_upload)
    )
    return list(result.scalars().all())


def _batch_read(batch: Batch, items: list[BatchItem]) -> BatchRead:
    return BatchRead(
        id=batch.id,
        stato=batch.stato,
        creato_il=batch.creato_il,
        totale_prodotti=batch.totale_prodotti,
        completate=batch.completate,
        items=[BatchItemRead.model_validate(i) for i in items],
    )


@router.post("", response_model=BatchRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    title_files: list[UploadFile] = File(...),
    date_files: list[UploadFile] = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not title_files or not date_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nessuna foto caricata")
    if len(title_files) != len(date_files):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Numero di foto titolo/data non corrispondente")

    batch, raw_pairs = await create_batch(db, current.household_id, current.user_id, title_files, date_files)
    asyncio.create_task(process_batch(batch.id, raw_pairs, get_pool()))

    items = await _load_items(db, batch.id)
    return _batch_read(batch, items)


@router.get("/{batch_id}", response_model=BatchRead)
async def get_batch(
    batch_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    batch = await _load_owned_batch(db, batch_id, current.household_id)
    items = await _load_items(db, batch_id)
    return _batch_read(batch, items)


@router.get("/{batch_id}/stream")
async def stream_batch(
    batch_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # verifica l'ownership prima di aprire lo stream, con la sessione della request
    await _load_owned_batch(db, batch_id, current.household_id)

    async def event_generator():
        last_snapshot = None
        while True:
            async with async_session() as session:
                batch = await session.get(Batch, batch_id)
                items = await _load_items(session, batch_id)

            snapshot = (batch.stato, batch.completate, tuple((i.id, i.stato) for i in items))
            if snapshot != last_snapshot:
                payload = _batch_read(batch, items)
                yield {"event": "update", "data": payload.model_dump_json()}
                last_snapshot = snapshot

            if batch.stato == "completato":
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.post("/{batch_id}/confirm", response_model=BatchConfirmResponse)
async def confirm_batch(
    batch_id: uuid.UUID,
    body: BatchConfirmRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _load_owned_batch(db, batch_id, current.household_id)
    items = await _load_items(db, batch_id)
    items_by_id = {item.id: item for item in items}

    created: list[BatchConfirmResponseItem] = []
    for confirmed in body.items:
        item = items_by_id.get(confirmed.batch_item_id)
        if item is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"batch_item {confirmed.batch_item_id} non appartiene a questo batch",
            )

        combined_raw_text = "\n".join(
            part
            for part in [
                f"[TITOLO]\n{item.ocr_raw_text_titolo}" if item.ocr_raw_text_titolo else None,
                f"[DATA]\n{item.ocr_raw_text_data}" if item.ocr_raw_text_data else None,
            ]
            if part
        ) or None
        confidences = [c for c in (item.confidence_titolo, item.confidence_data) if c is not None]
        combined_confidence = min(confidences) if confidences else None

        product = Product(
            household_id=current.household_id,
            added_by_user_id=current.user_id,
            nome=confirmed.nome,
            data_scadenza=confirmed.data_scadenza,
            ocr_raw_text=combined_raw_text,
            ocr_confidence=combined_confidence,
            batch_item_id=item.id,
            foto_titolo_key=item.foto_titolo_key,
        )
        db.add(product)
        await db.flush()

        item.confermato = True
        item.product_id = product.id
        created.append(BatchConfirmResponseItem(batch_item_id=item.id, product_id=product.id))

    await db.commit()
    return BatchConfirmResponse(products=created)
