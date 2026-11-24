import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.receipt import CatalogMatchOut, ReceiptLineOut, ReceiptParseResponse
from app.services.receipt.foods import is_non_food
from app.services.receipt.matching import CatalogMatch, is_reliable, match_catalog
from app.services.receipt.merge import merge_photos
from app.services.receipt.parser import parse_receipt_photo
from app.workers.pool import get_pool, process_image_task

router = APIRouter(prefix="/receipts", tags=["receipts"])

MAX_PHOTOS = 12


def _match_out(match: CatalogMatch) -> CatalogMatchOut:
    return CatalogMatchOut(
        label=match.label, brand=match.brand, name=match.name, score=match.score, fresco=match.fresco
    )


@router.post("/parse", response_model=ReceiptParseResponse)
async def parse_receipt(
    files: list[UploadFile] = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legge i prodotti da una o più foto (in ordine di scatto) della colonna prodotti
    di uno scontrino: OCR per foto, parsing in righe (nome, prezzo), rimozione della
    sovrapposizione tra foto consecutive e abbinamento al catalogo. Stateless: non
    salva né foto né righe — Step 1 del flusso "Carica scontrino"."""
    if not files:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nessuna foto")
    if len(files) > MAX_PHOTOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Massimo {MAX_PHOTOS} foto")

    raw_photos = [await f.read() for f in files]

    loop = asyncio.get_running_loop()
    outcomes = await asyncio.gather(
        *(
            loop.run_in_executor(get_pool(), process_image_task, raw, "scontrino")
            for raw in raw_photos
        )
    )

    photos = []
    failed: list[int] = []
    for index, outcome in enumerate(outcomes):
        if not outcome["ok"]:
            failed.append(index)
            photos.append([])
            continue
        photos.append(parse_receipt_photo(outcome["lines"], foto=index))

    merged = merge_photos(photos)
    empty = [i for i, p in enumerate(photos) if not p and i not in failed]

    food_lines = [line for line in merged.lines if not is_non_food(line.nome)]
    discarded = [line.nome for line in merged.lines if is_non_food(line.nome)]

    def build_rows() -> list[ReceiptLineOut]:
        rows = []
        for ordine, line in enumerate(food_lines):
            candidates = match_catalog(line.nome)
            best = candidates[0] if candidates and is_reliable(candidates[0]) else None
            rows.append(
                ReceiptLineOut(
                    ordine=ordine,
                    nome=line.nome,
                    prezzo=line.prezzo,
                    confidence=line.confidence,
                    foto=line.foto,
                    occorrenze=line.occorrenze,
                    match=_match_out(best) if best else None,
                    candidati=[_match_out(c) for c in candidates],
                    incerto=best is None,
                )
            )
        return rows

    rows = await loop.run_in_executor(None, build_rows)
    return ReceiptParseResponse(
        righe=rows,
        giunture_senza_sovrapposizione=merged.giunture_senza_sovrapposizione,
        foto_senza_righe=empty,
        foto_con_errore=failed,
        non_alimentari_scartati=discarded,
    )
