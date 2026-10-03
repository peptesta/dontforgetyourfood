import numpy as np

from app.services.ocr.pipeline import _drop_faint_boxes


def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_scarta_box_pallidi_e_tiene_quelli_neri():
    gray = np.full((200, 400), 200, np.uint8)  # carta
    gray[20:40, 10:200:3] = 10  # testo nero (a tratti, come inchiostro)
    gray[100:120, 10:200:3] = 170  # testo fantasma grigio chiaro
    lines = [
        {"text": "LECHE ENTERA", "confidence": 0.99, "box": _box(10, 15, 200, 45)},
        {"text": "ultsnuor fislo", "confidence": 0.9, "box": _box(10, 95, 200, 125)},
    ]
    kept = _drop_faint_boxes(gray, lines)
    assert [l["text"] for l in kept] == ["LECHE ENTERA"]


def test_scontrino_sbiadito_non_viene_scartato():
    # tutto il testo è grigio medio (carta termica sbiadita): il contrasto mediano è
    # basso, quindi la soglia relativa non deve eliminare le righe vere
    gray = np.full((200, 400), 200, np.uint8)
    gray[20:40, 10:200:3] = 110
    gray[60:80, 10:200:3] = 110
    lines = [
        {"text": "PAN", "confidence": 0.9, "box": _box(10, 15, 200, 45)},
        {"text": "ATUN", "confidence": 0.9, "box": _box(10, 55, 200, 85)},
    ]
    assert len(_drop_faint_boxes(gray, lines)) == 2


def test_box_troppo_piccolo_per_misurare_resta():
    gray = np.full((50, 50), 200, np.uint8)
    lines = [{"text": "A", "confidence": 0.9, "box": _box(1, 1, 3, 3)}]
    assert _drop_faint_boxes(gray, lines) == lines
