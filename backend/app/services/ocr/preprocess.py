import io
from typing import Literal

import cv2
import numpy as np
import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

# Con la cattura a due foto dedicate (titolo / data, vedi NEXT_SESSION.md) il testo
# occupa proporzionalmente più frame rispetto a una foto dell'intera confezione, quindi
# meno pixel bastano: soglia più bassa di prima (era 1600 fisso) per detection e
# recognition più veloci.
MAX_SIDE = 1200

# La foto della data è il caso storicamente più debole (stampe piccole, a basso
# contrasto o in rilievo/embossed): un CLAHE più aggressivo aiuta lì senza rischiare
# di rovinare la foto del titolo, dove il testo è già grande e ben stampato.
_CLAHE_CLIP_LIMIT = {"titolo": 2.0, "data": 3.0, "scontrino": 2.0}

# Lo scontrino è una colonna alta e stretta con testo termico piccolo: serve più
# risoluzione sul lato lungo che per titolo/data, altrimenti le righe si impastano.
_MAX_SIDE_BY_MODE = {"scontrino": 2000}

# La F. Cad. è sempre stampata in nero: valori di partenza scelti perché testo nero
# dopo CLAHE misura tipicamente blackness ~0.6-0.85 (ben sopra midpoint), mentre uno
# sfondo scuro ma colorato (es. bordeaux, blu petrolio) misura ~0.25-0.35 (sotto). Da
# validare/tarare con foto reali quando disponibili.
_DARK_TEXT_PARAMS = {
    "sigmoid_midpoint": 0.45,
    "sigmoid_steepness": 10.0,
}


def preprocess_image(raw_bytes: bytes, mode: Literal["titolo", "data", "scontrino"] = "titolo") -> np.ndarray:
    """Da byte grezzi (JPEG/PNG/HEIC) a un array numpy BGR pronto per PaddleOCR.

    Tutto in memoria: nessun file temporaneo scritto su disco.
    """
    img = _decode_and_resize(raw_bytes, _MAX_SIDE_BY_MODE.get(mode, MAX_SIDE))

    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    bgr = _apply_clahe(bgr, _CLAHE_CLIP_LIMIT[mode])
    if mode == "data":
        bgr = _emphasize_dark_text(bgr)
    return bgr


def _decode_and_resize(raw_bytes: bytes, max_side: int) -> Image.Image:
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)  # va fatto PRIMA del resize
    return _resize(img.convert("RGB"), max_side)


def receipt_gray(raw_bytes: bytes) -> np.ndarray:
    """Scala di grigi della foto di scontrino SENZA CLAHE, pixel per pixel allineata
    all'immagine di preprocess_image(mode="scontrino"): serve a misurare quanto è scuro
    l'inchiostro di ogni box (il CLAHE amplifica il contrasto e renderebbe scuro anche
    il testo fantasma del retro, falsando la misura)."""
    img = _decode_and_resize(raw_bytes, _MAX_SIDE_BY_MODE["scontrino"])
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


def _resize(img: Image.Image, max_side: int) -> Image.Image:
    width, height = img.size
    longest = max(width, height)
    if longest <= max_side:
        return img
    scale = max_side / longest
    return img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)


def _apply_clahe(bgr: np.ndarray, clip_limit: float) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _emphasize_dark_text(bgr: np.ndarray) -> np.ndarray:
    """Schiarisce tutto ciò che non è nero/grigio scuro, per isolare la F. Cad.

    La F. Cad. è sempre stampata in nero: bassa luminosità E bassa saturazione.
    Uno sfondo scuro ma colorato ha luminosità simile al testo ma saturazione
    alta, quindi il solo canale L non separa le due cose - serve combinare L e S.
    La sigmoide (invece di una soglia dura) preserva la texture del tratto per il
    recognizer, allenato su immagini a tono continuo, non binarizzate.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0].astype(np.float32) / 255.0

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:, :, 1].astype(np.float32) / 255.0

    blackness = (1.0 - l_channel) * (1.0 - s_channel)

    midpoint = _DARK_TEXT_PARAMS["sigmoid_midpoint"]
    steepness = _DARK_TEXT_PARAMS["sigmoid_steepness"]
    emphasis = 1.0 / (1.0 + np.exp(-steepness * (blackness - midpoint)))

    out_gray = l_channel * 255.0 * emphasis + 255.0 * (1.0 - emphasis)
    return cv2.cvtColor(out_gray.astype(np.uint8), cv2.COLOR_GRAY2BGR)


# --- varianti per la foto della data -------------------------------------------------
# La data di scadenza è quasi sempre grigia, nera o bianca (inchiostro su plastica,
# rilievo su metallo, stampa chiara su fondo scuro). Una sola elaborazione (testo scuro
# enfatizzato) perde i casi chiaro-su-scuro e quelli in cui il testo è la zona più
# contrastata ma non la più scura: si provano più letture, dalla più economica.

_REGION_MIN_SIDE = 640  # il ritaglio del testo ad alto contrasto viene ingrandito fino a qui
_REGION_PAD = 0.15


def _gray_resized(raw_bytes: bytes) -> np.ndarray:
    img = _decode_and_resize(raw_bytes, MAX_SIDE)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


def find_max_contrast_region(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Riquadro (x0, y0, x1, y1) del testo con più contrasto locale della foto.

    Il contrasto locale (gradiente morfologico) è alto sui bordi dei caratteri sia
    scuri su chiaro sia chiari su scuro, quindi non dipende dal colore. I tratti vicini
    vengono fusi in blocchi di testo; vince il blocco con più energia di contrasto."""
    if gray.size == 0:
        return None
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(cv2.GaussianBlur(gray, (3, 3), 0), cv2.MORPH_GRADIENT, kernel)
    high = float(np.percentile(grad, 99))
    if high < 20:  # foto praticamente piatta: niente testo da isolare
        return None
    strong = (grad >= 0.5 * high).astype(np.uint8)
    h, w = gray.shape
    merge = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 10), max(5, h // 60)))
    blocks = cv2.morphologyEx(strong, cv2.MORPH_CLOSE, merge)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(blocks, connectivity=8)
    best, best_energy = None, 0.0
    for i in range(1, count):
        x, y, bw, bh, _area = stats[i]
        if bw < 12 or bh < 6:
            continue
        energy = float(grad[labels == i].sum()) * strong[labels == i].mean()
        if energy > best_energy:
            best, best_energy = (x, y, bw, bh), energy
    if best is None:
        return None
    x, y, bw, bh = best
    px, py = int(bw * _REGION_PAD) + 4, int(bh * _REGION_PAD) + 4
    return max(0, x - px), max(0, y - py), min(w, x + bw + px), min(h, y + bh + py)


def _region_crop(raw_bytes: bytes) -> np.ndarray | None:
    gray = _gray_resized(raw_bytes)
    box = find_max_contrast_region(gray)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    scale = _REGION_MIN_SIDE / max(crop.shape)
    if scale > 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(crop)
    return cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR)


def _achromatic_gray(raw_bytes: bytes) -> np.ndarray:
    """Tiene solo i pixel poco saturati (nero, grigio, bianco) e appiattisce a grigio
    medio quelli colorati: lo sfondo colorato sparisce, il testo neutro resta."""
    img = _decode_and_resize(raw_bytes, MAX_SIDE)
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    neutral = sat < 60
    flat = gray.copy()
    flat[~neutral] = int(np.median(gray[~neutral])) if (~neutral).any() else 128
    flat = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(flat)
    return cv2.cvtColor(flat, cv2.COLOR_GRAY2BGR)


def date_variants(raw_bytes: bytes):
    """Genera (nome, immagine BGR) in ordine di costo/probabilità. Pigro: chi trova la
    data alla prima non paga le successive."""
    yield "scuro", preprocess_image(raw_bytes, mode="data")
    region = _region_crop(raw_bytes)
    if region is not None:
        yield "contrasto", region
        yield "contrasto_inverso", 255 - region
    yield "neutro", _achromatic_gray(raw_bytes)
    yield "chiaro_su_scuro", 255 - _apply_clahe(
        cv2.cvtColor(np.array(_decode_and_resize(raw_bytes, MAX_SIDE)), cv2.COLOR_RGB2BGR),
        _CLAHE_CLIP_LIMIT["data"],
    )


# --- stampa puntinata (inkjet su cartone/lattine) --------------------------------------
# La data è fatta di puntini separati: il riconoscitore non li legge come caratteri.
# Un'erosione sul grigio (min filter) allarga i punti scuri fino a fondere i tratti.
# Verificato su foto reali: con il lato lungo a 3000 px e kernel 7 "19.11.2026" viene
# letta, mentre la foto semplice no. Il kernel dipende dalla dimensione dei caratteri,
# quindi il ritaglio viene portato a un'altezza di riga nota (_DOT_TARGET_TEXT_HEIGHT).
DOT_ANALYSIS_SIDE = 3000
_DOT_TARGET_TEXT_HEIGHT = 45
_DOT_KERNELS = (7, 5, 9)


def gray_for_dot_analysis(raw_bytes: bytes) -> np.ndarray:
    img = _decode_and_resize(raw_bytes, DOT_ANALYSIS_SIDE)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)


def anchor_region(gray: np.ndarray, boxes: list[list[list[float]]], box_scale: float = 1.0) -> tuple[np.ndarray, float] | None:
    """Ritaglia attorno ai box-àncora (testi già letti con sicurezza: lotto, "consumir
    preferentemente"…). La data sta sempre vicino: si allarga di due altezze di riga in
    verticale. Ritorna (ritaglio ridimensionato, fattore di scala) o None."""
    if not boxes:
        return None
    # i box vengono da un'immagine a risoluzione diversa da `gray`: si portano in scala
    boxes = [[[x * box_scale, y * box_scale] for x, y in box] for box in boxes]
    heights = []
    for box in boxes:
        (_, _), (bw, bh), _ = cv2.minAreaRect(np.array(box, dtype=np.float32))
        heights.append(max(1.0, min(bw, bh)))
    text_h = float(np.median(heights))
    pts = np.array([pt for box in boxes for pt in box], dtype=np.float32)
    h, w = gray.shape
    x0 = int(max(0, pts[:, 0].min() - 0.5 * text_h))
    x1 = int(min(w, pts[:, 0].max() + 0.5 * text_h))
    y0 = int(max(0, pts[:, 1].min() - 2.5 * text_h))
    y1 = int(min(h, pts[:, 1].max() + 2.5 * text_h))
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    crop = gray[y0:y1, x0:x1]
    scale = min(3.0, max(0.5, _DOT_TARGET_TEXT_HEIGHT / text_h))
    if abs(scale - 1.0) > 0.05:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    return crop, scale


def merge_dots(gray: np.ndarray, kernel: int) -> np.ndarray:
    base = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
    eroded = cv2.erode(base, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel)))
    blurred = cv2.GaussianBlur(eroded, (0, 0), 1.2)
    return cv2.cvtColor(blurred, cv2.COLOR_GRAY2BGR)
