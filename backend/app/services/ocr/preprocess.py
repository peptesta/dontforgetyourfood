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
_CLAHE_CLIP_LIMIT = {"titolo": 2.0, "data": 3.0}

# La F. Cad. è sempre stampata in nero: valori di partenza scelti perché testo nero
# dopo CLAHE misura tipicamente blackness ~0.6-0.85 (ben sopra midpoint), mentre uno
# sfondo scuro ma colorato (es. bordeaux, blu petrolio) misura ~0.25-0.35 (sotto). Da
# validare/tarare con foto reali quando disponibili.
_DARK_TEXT_PARAMS = {
    "sigmoid_midpoint": 0.45,
    "sigmoid_steepness": 10.0,
}


def preprocess_image(raw_bytes: bytes, mode: Literal["titolo", "data"] = "titolo") -> np.ndarray:
    """Da byte grezzi (JPEG/PNG/HEIC) a un array numpy BGR pronto per PaddleOCR.

    Tutto in memoria: nessun file temporaneo scritto su disco.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)  # va fatto PRIMA del resize
    img = img.convert("RGB")
    img = _resize(img, MAX_SIDE)

    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    bgr = _apply_clahe(bgr, _CLAHE_CLIP_LIMIT[mode])
    if mode == "data":
        bgr = _emphasize_dark_text(bgr)
    return bgr


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
