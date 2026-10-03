import asyncio
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import date as date_type

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Batch, BatchItem, Household
from app.db.session import async_session
from app.services.image_storage import get_image_storage
from app.workers.pool import process_image_task


async def create_batch(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    title_files: list[UploadFile],
    date_files: list[UploadFile],
) -> tuple[Batch, list[tuple[bytes, bytes]]]:
    """Crea Batch + un BatchItem per coppia titolo/data (in stato in_coda) e legge
    subito i byte dei file: servono per l'inferenza ma non vengono mai scritti su
    disco né conservati — TRANNE la foto del titolo, che viene persistita subito qui
    (vedi services/image_storage.py): è l'unico momento in cui i byte grezzi sono
    disponibili, prima che vengano scartati dopo l'OCR."""
    batch = Batch(household_id=household_id, created_by_user_id=user_id, totale_prodotti=len(title_files))
    db.add(batch)
    await db.flush()

    storage = get_image_storage()
    raw_pairs: list[tuple[bytes, bytes]] = []
    for i, (title_file, date_file) in enumerate(zip(title_files, date_files)):
        title_bytes = await title_file.read()
        date_bytes = await date_file.read()
        raw_pairs.append((title_bytes, date_bytes))

        item_id = uuid.uuid4()
        foto_titolo_key = f"{household_id}/{item_id}.jpg"
        storage.save(foto_titolo_key, title_bytes)
        db.add(BatchItem(id=item_id, batch_id=batch.id, ordine_upload=i, foto_titolo_key=foto_titolo_key))

    await db.commit()
    await db.refresh(batch)
    return batch, raw_pairs


async def process_batch(batch_id: uuid.UUID, raw_pairs: list[tuple[bytes, bytes]], pool: ProcessPoolExecutor) -> None:
    """Task in background (non blocca la risposta HTTP): per ogni item lancia due job
    nel pool di processi (uno per il lato titolo, uno per il lato data), e scrive sul
    DB una sola volta per item quando entrambi i lati sono tornati."""
    async with async_session() as db:
        result = await db.execute(
            select(BatchItem).where(BatchItem.batch_id == batch_id).order_by(BatchItem.ordine_upload)
        )
        items = result.scalars().all()
        for item in items:
            item.stato = "in_elaborazione"

        batch = await db.get(Batch, batch_id)
        household = await db.get(Household, batch.household_id)
        correct_orientation = household.correggi_orientamento
        await db.commit()

    loop = asyncio.get_running_loop()

    async def _run_tagged(item_id: uuid.UUID, mode: str, raw: bytes) -> tuple[uuid.UUID, str, dict]:
        outcome = await loop.run_in_executor(pool, process_image_task, raw, mode, correct_orientation)
        return item_id, mode, outcome

    # NB: asyncio.as_completed() non restituisce gli stessi oggetti Future passati in
    # input (li avvolge internamente), quindi non si può usarli come chiave di lookup.
    # Si "tagga" ogni risultato con item_id + mode dentro la coroutine stessa.
    tagged_tasks = []
    for item in items:
        title_bytes, date_bytes = raw_pairs[item.ordine_upload]
        tagged_tasks.append(_run_tagged(item.id, "titolo", title_bytes))
        tagged_tasks.append(_run_tagged(item.id, "data", date_bytes))

    pending: dict[uuid.UUID, dict] = {}
    for coro in asyncio.as_completed(tagged_tasks):
        item_id, mode, outcome = await coro
        side = pending.setdefault(item_id, {})
        side[mode] = outcome
        if "titolo" not in side or "data" not in side:
            continue  # aspetta che anche l'altro lato torni prima di scrivere

        title_outcome, date_outcome = side["titolo"], side["data"]
        async with async_session() as db:
            item = await db.get(BatchItem, item_id)
            title_ok, date_ok = title_outcome["ok"], date_outcome["ok"]

            if title_ok:
                item.nome_candidato = title_outcome["nome_candidato"]
                item.nome_suggerito = title_outcome.get("nome_suggerito")
                item.ocr_raw_text_titolo = title_outcome["ocr_raw_text"]
                item.confidence_titolo = title_outcome["confidence"]
                item.errore_titolo = None
            else:
                item.errore_titolo = title_outcome["errore"]

            if date_ok:
                if date_outcome["data_candidata"]:
                    item.data_candidata = date_type.fromisoformat(date_outcome["data_candidata"])
                item.data_candidati_alternativi = date_outcome["data_candidati_alternativi"]
                item.ocr_raw_text_data = date_outcome["ocr_raw_text"]
                item.confidence_data = date_outcome["confidence"]
                item.errore_data = None
            else:
                item.errore_data = date_outcome["errore"]

            if title_ok and date_ok:
                item.stato = "completato"
            elif title_ok or date_ok:
                item.stato = "parziale"
            else:
                item.stato = "errore"

            batch = await db.get(Batch, batch_id)
            batch.completate += 1
            if batch.completate >= batch.totale_prodotti:
                batch.stato = "completato"
            await db.commit()
