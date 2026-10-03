import io

import numpy as np
from PIL import Image, ImageDraw

from app.services.ocr.preprocess import MAX_SIDE, _apply_clahe, _emphasize_dark_text, preprocess_image

TEXT_BOX = (20, 20, 60, 60)
BG_BOX_OUTSIDE_TEXT = (80, 80, 120, 120)


def _synthetic_bgr(bg_color: tuple[int, int, int], overlay_box: tuple[int, int, int, int] | None = None,
                    overlay_color: tuple[int, int, int] | None = None) -> np.ndarray:
    img = Image.new("RGB", (140, 140), bg_color)
    draw = ImageDraw.Draw(img)
    draw.rectangle(TEXT_BOX, fill=(0, 0, 0))
    if overlay_box is not None:
        draw.rectangle(overlay_box, fill=overlay_color)
    import cv2

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _mean_luma(bgr: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = box
    region = bgr[y0:y1, x0:x1]
    return float(region.mean())


def test_testo_nero_su_sfondo_colorato_scuro_aumenta_contrasto():
    bgr = _synthetic_bgr(bg_color=(120, 20, 20))  # rosso scuro saturo

    before_gap = _mean_luma(bgr, BG_BOX_OUTSIDE_TEXT) - _mean_luma(bgr, TEXT_BOX)
    filtered = _emphasize_dark_text(bgr)
    after_gap = _mean_luma(filtered, BG_BOX_OUTSIDE_TEXT) - _mean_luma(filtered, TEXT_BOX)

    assert after_gap > before_gap


def test_testo_nero_su_sfondo_grigio_scuro_basso_contrasto():
    bgr = _synthetic_bgr(bg_color=(70, 70, 70))  # grigio scuro desaturato

    filtered = _emphasize_dark_text(bgr)

    assert _mean_luma(filtered, TEXT_BOX) < _mean_luma(filtered, BG_BOX_OUTSIDE_TEXT)


def test_rettangolo_colorato_sovrapposto_viene_schiarito():
    overlay_box = (25, 25, 55, 55)  # dentro TEXT_BOX
    bgr = _synthetic_bgr(bg_color=(255, 255, 255), overlay_box=overlay_box, overlay_color=(200, 30, 30))

    before = _mean_luma(bgr, overlay_box)
    filtered = _emphasize_dark_text(bgr)
    after = _mean_luma(filtered, overlay_box)

    black_margin_box = (20, 20, 24, 60)  # striscia di TEXT_BOX non coperta dall'overlay, resta nera
    assert after > before
    assert _mean_luma(filtered, black_margin_box) < after


def test_modalita_titolo_non_modificata():
    img = Image.new("RGB", (200, 150), (100, 150, 200))
    ImageDraw.Draw(img).rectangle((10, 10, 50, 50), fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    import cv2

    resized = img.copy()
    longest = max(resized.size)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        resized = resized.resize((int(resized.width * scale), int(resized.height * scale)), Image.LANCZOS)
    expected_bgr = cv2.cvtColor(np.array(resized), cv2.COLOR_RGB2BGR)
    expected = _apply_clahe(expected_bgr, 2.0)

    result = preprocess_image(raw_bytes, mode="titolo")

    assert np.array_equal(result, expected)


def test_output_bgr_uint8_tre_canali():
    img = Image.new("RGB", (200, 150), (100, 150, 200))
    ImageDraw.Draw(img).rectangle((10, 10, 50, 50), fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    result = preprocess_image(raw_bytes, mode="data")

    assert result.dtype == np.uint8
    assert result.ndim == 3
    assert result.shape[2] == 3
