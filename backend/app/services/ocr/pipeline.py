from dataclasses import dataclass, field

import cv2
import numpy as np

from app.services.ocr.date_extractor import extract_date_candidates
from app.services.ocr.engine import OcrEngine
from app.services.ocr.name_extractor import extract_product_name_from_title_photo
from app.services.ocr.preprocess import preprocess_image, receipt_gray
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


# Lo scontrino ha molte righe fitte a basso contrasto (carta termica): con le soglie di
# default il detector salta alcune righe intere (verificato su uno scontrino reale
# Lidl: PATATA GRANEL, PATE DE CERDO). Soglie più basse le recuperano; un frammento
# spurio in più costa poco perché il parser scarta le righe senza nome+prezzo.
_RECEIPT_DET_PARAMS = {"text_det_thresh": 0.2, "text_det_box_thresh": 0.4}


# seconda lettura dei box deboli: sotto questa confidenza (e senza cifre: i prezzi si
# gestiscono altrove) si ritaglia il solo box e lo si rilegge. Un box isolato spesso
# viene letto bene anche se nella foto intera no: tipicamente quando dietro passa la
# stampa del retro (es. un QR che traspare dietro "CESTA": "IE EE RR" 0.38 -> "KIWI
# VERDE CESTA" 1.0). Si accetta il risultato solo se è affidabile.
_RECHECK_BELOW = 0.6
_RECHECK_ACCEPT_AT = 0.8
_RECHECK_MAX_BOXES = 8
_RECHECK_PAD_X, _RECHECK_PAD_Y = 10, 8


def _recheck_weak_boxes(engine: OcrEngine, image, lines: list[dict]) -> list[dict]:
    height, width = image.shape[:2]
    weak = [
        (i, line)
        for i, line in enumerate(lines)
        if line["confidence"] < _RECHECK_BELOW
        and len(line["text"].strip()) >= 2
        and not any(ch.isdigit() for ch in line["text"])
    ]
    weak.sort(key=lambda item: item[1]["confidence"])  # prima i più dubbi, entro il limite
    result = list(lines)
    for i, line in weak[:_RECHECK_MAX_BOXES]:
        xs = [pt[0] for pt in line["box"]]
        ys = [pt[1] for pt in line["box"]]
        x0, x1 = int(max(0, min(xs) - _RECHECK_PAD_X)), int(min(width, max(xs) + _RECHECK_PAD_X))
        y0, y1 = int(max(0, min(ys) - _RECHECK_PAD_Y)), int(min(height, max(ys) + _RECHECK_PAD_Y))
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        reread = engine.run(image[y0:y1, x0:x1])
        if not reread:
            continue
        reread.sort(key=lambda l: min(pt[0] for pt in l["box"]))
        text = " ".join(l["text"].strip() for l in reread)
        confidence = min(l["confidence"] for l in reread)
        if confidence >= _RECHECK_ACCEPT_AT:
            result[i] = {"text": text, "confidence": confidence, "box": line["box"]}
    return result


# Il testo dei prodotti sullo scontrino è nero; la stampa del retro che traspare e i QR
# sono grigio chiaro. Per ogni box si misura il contrasto inchiostro/carta (5° percentile
# dei pixel del box = inchiostro, 95° = carta) e si scartano quelli molto più pallidi
# della norma della foto. Soglia relativa al contrasto mediano (regge anche scontrini
# sbiaditi) con un minimo assoluto. Misurato su uno scontrino Lidl: testo vero 145-199,
# fantasmi 4-16.
_FAINT_CONTRAST_RATIO = 0.4
_FAINT_CONTRAST_MIN = 25
_MIN_PIXELS_FOR_INK = 20


def _drop_faint_boxes(gray: np.ndarray, lines: list[dict]) -> list[dict]:
    measured: list[tuple[dict, float | None]] = []
    for line in lines:
        mask = np.zeros(gray.shape, np.uint8)
        cv2.fillPoly(mask, [np.array(line["box"], dtype=np.int32)], 1)
        pixels = gray[mask == 1]
        if pixels.size < _MIN_PIXELS_FOR_INK:
            measured.append((line, None))
            continue
        measured.append((line, float(np.percentile(pixels, 95) - np.percentile(pixels, 5))))

    contrasts = [c for _, c in measured if c is not None]
    if not contrasts:
        return lines
    threshold = max(_FAINT_CONTRAST_MIN, _FAINT_CONTRAST_RATIO * float(np.median(contrasts)))
    # i box troppo piccoli per misurare restano: li filtrano gli altri controlli
    return [line for line, contrast in measured if contrast is None or contrast >= threshold]


def run_receipt_pipeline(engine: OcrEngine, raw_bytes: bytes, correct_orientation: bool = False) -> list[dict]:
    """Foto di una colonna di scontrino: ritorna le righe OCR grezze (testo, confidenza,
    box) — il raggruppamento in righe prodotto/prezzo è in services/receipt/parser.py."""
    image = preprocess_image(raw_bytes, mode="scontrino")
    lines = engine.run(image, correct_orientation=correct_orientation, det_params=_RECEIPT_DET_PARAMS)
    lines = _drop_faint_boxes(receipt_gray(raw_bytes), lines)
    return _recheck_weak_boxes(engine, image, lines)
