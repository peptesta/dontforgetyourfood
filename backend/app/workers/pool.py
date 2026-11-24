import os
from concurrent.futures import ProcessPoolExecutor
from typing import Literal

_engine = None
_pool: ProcessPoolExecutor | None = None


def _init_worker() -> None:
    """Eseguito una sola volta per processo worker: carica il modello OCR
    in memoria (costa qualche secondo), non per ogni immagine."""
    global _engine
    from app.services.ocr.engine import OcrEngine

    _engine = OcrEngine()


def process_image_task(raw_bytes: bytes, mode: Literal["titolo", "data", "scontrino"], correct_orientation: bool = False) -> dict:
    """Eseguita nel worker process. Ritorna un dict semplice (picklable).
    `mode` seleziona quale metà della cattura a due foto è raw_bytes (titolo o data,
    vedi services/ocr/pipeline.py) e quindi quale estrazione eseguire;
    "scontrino" è una foto della colonna prodotti di uno scontrino: ritorna le righe OCR
    grezze con i box, il parsing in righe prodotto avviene fuori dal worker
    (services/receipt)."""
    global _engine
    if _engine is None:
        _init_worker()
    try:
        if mode == "scontrino":
            from app.services.ocr.pipeline import run_receipt_pipeline

            return {"ok": True, "lines": run_receipt_pipeline(_engine, raw_bytes, correct_orientation)}

        if mode == "titolo":
            from app.services.ocr.pipeline import run_title_pipeline

            result = run_title_pipeline(_engine, raw_bytes, correct_orientation=correct_orientation)
            return {
                "ok": True,
                "nome_candidato": result.nome_candidato,
                "nome_suggerito": result.nome_suggerito,
                "ocr_raw_text": result.ocr_raw_text,
                "confidence": result.confidence,
            }

        from app.services.ocr.pipeline import run_date_pipeline

        result = run_date_pipeline(_engine, raw_bytes, correct_orientation=correct_orientation)
        return {
            "ok": True,
            "data_candidata": result.data_candidata,
            "data_candidati_alternativi": result.data_candidati_alternativi,
            "ocr_raw_text": result.ocr_raw_text,
            "confidence": result.confidence,
        }
    except Exception as exc:  # noqa: BLE001 - un errore per lato non deve far fallire il batch
        return {"ok": False, "errore": str(exc)}


def create_pool() -> ProcessPoolExecutor:
    global _pool
    workers = int(os.getenv("OCR_WORKERS", "2"))
    _pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)
    return _pool


def get_pool() -> ProcessPoolExecutor:
    if _pool is None:
        raise RuntimeError("Pool OCR non inizializzato: create_pool() va chiamato nel lifespan di FastAPI")
    return _pool


def shutdown_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=True)
        _pool = None
