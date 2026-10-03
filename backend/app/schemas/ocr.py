from pydantic import BaseModel


class DatePreviewResponse(BaseModel):
    data_candidata: str | None
    confidence: float | None
    data_candidati_alternativi: list[str] | None = None
    errore: str | None = None
