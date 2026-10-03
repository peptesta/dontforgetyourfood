import os

import numpy as np

from app.services.ocr.name_extractor import OcrLine

# Necessario PRIMA di importare paddleocr: su alcune CPU (verificato empiricamente,
# non solo da changelog) il path di inferenza accelerato oneDNN di paddlepaddle 3.x
# crasha con "NotImplementedError: ConvertPirAttribute2RuntimeAttribute" sul detector
# PP-OCRv5/v6. Disabilitare oneDNN evita il crash; il costo in velocità è accettabile
# per il volume di questa app (batch occasionali, non un servizio ad alto traffico).
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")


class OcrEngine:
    """Wrapper su PaddleOCR (PP-OCRv5 mobile det + rec latino, CPU-only).

    Il caricamento dei modelli (qualche secondo) avviene una sola volta qui in
    __init__: nel batch processor viene istanziato una volta per processo worker,
    mai per immagine (v. workers/pool.py).
    """

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        # use_doc_orientation_classify=True qui carica il modello di classificazione
        # orientamento (necessario farlo in costruzione: PaddleOCR non lo inizializza
        # affatto se parte da False, e a quel punto un override a True in predict()
        # fallisce). Il costo/beneficio è deciso per-richiesta in run(), non qui:
        # una volta caricato il modello, disattivarlo per singola chiamata è gratis.
        self._ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )

    def run(
        self,
        image_bgr: np.ndarray,
        correct_orientation: bool = False,
        det_params: dict | None = None,
    ) -> list[OcrLine]:
        """`det_params`: override per-chiamata delle soglie del detector (es.
        text_det_thresh, text_det_box_thresh) — chi non le passa mantiene i default."""
        results = self._ocr.predict(
            image_bgr, use_doc_orientation_classify=correct_orientation, **(det_params or {})
        )
        if not results:
            return []
        result = results[0]
        texts = result.get("rec_texts", [])
        scores = result.get("rec_scores", [])
        polys = result.get("rec_polys", [])

        lines: list[OcrLine] = []
        for text, score, poly in zip(texts, scores, polys):
            if not text.strip():
                continue
            lines.append({"text": text, "confidence": float(score), "box": poly.tolist()})
        return lines
