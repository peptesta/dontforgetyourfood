import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ProductRead(BaseModel):
    id: uuid.UUID
    nome: str
    data_scadenza: date
    data_aggiunta: datetime
    stato: str
    added_by_user_id: uuid.UUID | None
    ocr_confidence: float | None
    foto_titolo_key: str | None

    model_config = {"from_attributes": True}


class ProductUpdate(BaseModel):
    nome: str | None = None
    data_scadenza: date | None = None
