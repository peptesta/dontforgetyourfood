from dataclasses import dataclass, field

from app.services.ocr.date_extractor import extract_date_candidates
from app.services.ocr.engine import OcrEngine
from app.services.ocr.name_extractor import extract_product_name_from_title_photo
from app.services.ocr.preprocess import preprocess_image
from app.services.ocr.product_catalog import suggest_product_name

# sotto questa confidenza media OCR sul titolo, proviamo un suggerimento dal catalogo
# prodotti (vedi product_catalog.py) — stessa soglia già usata in Review per il warning
# di bassa confidenza.
_LOW_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class TitlePipelineResult:
    nome_candidato: str | None
    nome_suggerito: str | None
    ocr_raw_text: str
    confidence: float | None


@dataclass
class DatePipelineResult:
    data_candidata: str | None
    data_candidati_alternativi: list[str] = field(default_factory=list)
    ocr_raw_text: str = ""
    confidence: float | None = None


def _avg_confidence(ocr_lines: list[dict]) -> float | None:
    confidences = [line["confidence"] for line in ocr_lines]
    return sum(confidences) / len(confidences) if confidences else None


def run_title_pipeline(engine: OcrEngine, raw_bytes: bytes, correct_orientation: bool = False) -> TitlePipelineResult:
    image = preprocess_image(raw_bytes, mode="titolo")
    ocr_lines = engine.run(image, correct_orientation=correct_orientation)

    name_result = extract_product_name_from_title_photo(ocr_lines)
    confidence = _avg_confidence(ocr_lines)

    nome_suggerito = None
    if name_result["name"] and confidence is not None and confidence < _LOW_CONFIDENCE_THRESHOLD:
        nome_suggerito = suggest_product_name(name_result["name"], confidence)

    return TitlePipelineResult(
        nome_candidato=name_result["name"],
        nome_suggerito=nome_suggerito,
        ocr_raw_text=name_result["raw_text"],
        confidence=confidence,
    )


def run_date_pipeline(engine: OcrEngine, raw_bytes: bytes, correct_orientation: bool = False) -> DatePipelineResult:
    image = preprocess_image(raw_bytes, mode="data")
    ocr_lines = engine.run(image, correct_orientation=correct_orientation)

    date_result = extract_date_candidates([line["text"] for line in ocr_lines])

    return DatePipelineResult(
        data_candidata=date_result.best,
        data_candidati_alternativi=date_result.alternatives,
        ocr_raw_text="\n".join(line["text"] for line in ocr_lines),
        confidence=_avg_confidence(ocr_lines),
    )


def run_receipt_pipeline(engine: OcrEngine, raw_bytes: bytes, correct_orientation: bool = False) -> list[dict]:
    """Foto di una colonna di scontrino: ritorna le righe OCR grezze (testo, confidenza,
    box) — il raggruppamento in righe prodotto/prezzo è in services/receipt/parser.py."""
    image = preprocess_image(raw_bytes, mode="scontrino")
    return engine.run(image, correct_orientation=correct_orientation)
