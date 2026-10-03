from pydantic import BaseModel


class CatalogMatchOut(BaseModel):
    label: str
    brand: str
    name: str
    score: float
    fresco: bool | None = None


class ReceiptLineOut(BaseModel):
    ordine: int
    nome: str
    prezzo: float | None
    confidence: float
    foto: int
    # quante righe dello scontrino erano questo prodotto (ripetizioni fuse in una)
    occorrenze: int
    # miglior abbinamento al catalogo se sopra soglia, altrimenti None (riga "incerta")
    match: CatalogMatchOut | None
    candidati: list[CatalogMatchOut]
    incerto: bool


class ReceiptParseResponse(BaseModel):
    righe: list[ReceiptLineOut]
    # indice k della foto dopo cui manca la sovrapposizione con la foto k+1
    giunture_senza_sovrapposizione: list[int]
    # indici delle foto da cui non è stata letta nessuna riga prodotto
    foto_senza_righe: list[int]
    # indici delle foto che l'OCR non è riuscito a elaborare
    foto_con_errore: list[int]
    # nomi delle righe escluse perché non alimentari (pulizia, igiene, abbigliamento…)
    non_alimentari_scartati: list[str]
