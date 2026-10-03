import uuid
from datetime import date, datetime

from pydantic import BaseModel


class BatchItemRead(BaseModel):
    id: uuid.UUID
    ordine_upload: int
    stato: str
    nome_candidato: str | None
    nome_suggerito: str | None
    data_candidata: date | None
    data_candidati_alternativi: list[str] | None
    ocr_raw_text_titolo: str | None
    ocr_raw_text_data: str | None
    confidence_titolo: float | None
    confidence_data: float | None
    errore_titolo: str | None
    errore_data: str | None
    confermato: bool

    model_config = {"from_attributes": True}


class BatchRead(BaseModel):
    id: uuid.UUID
    stato: str
    creato_il: datetime
    totale_prodotti: int
    completate: int
    items: list[BatchItemRead]

    model_config = {"from_attributes": True}


class ConfirmedItem(BaseModel):
    batch_item_id: uuid.UUID
    nome: str
    data_scadenza: date


class BatchConfirmRequest(BaseModel):
    items: list[ConfirmedItem]


class BatchConfirmResponseItem(BaseModel):
    batch_item_id: uuid.UUID
    product_id: uuid.UUID


class BatchConfirmResponse(BaseModel):
    products: list[BatchConfirmResponseItem]
