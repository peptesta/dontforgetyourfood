"""Script di debug per la pipeline OCR: data una foto reale, salva le immagini
intermedie di preprocessing (quello che l'IA "vede" prima del riconoscimento) e
stampa il ragionamento passo-passo che porta al candidato finale (nome prodotto o
data di scadenza) — per diagnosticare foto problematiche offline, senza toccare il
DB o il server in esecuzione.

Uso:
  cd backend && .venv/bin/python scripts/debug_ocr.py
      (senza argomenti: processa tutte le foto in scripts/debug_input/, mode=data)
  cd backend && .venv/bin/python scripts/debug_ocr.py foto.jpg --mode data
  cd backend && .venv/bin/python scripts/debug_ocr.py debug_input/ --mode titolo --correggi-orientamento

Le immagini (una per stadio di preprocessing + una con i box OCR annotati) vengono
salvate in scripts/debug_output/<nome_foto>_<mode>/.
"""
import argparse
import io
import sys
from datetime import date
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ocr import date_extractor  # noqa: E402
from app.services.ocr.engine import OcrEngine  # noqa: E402
from app.services.ocr.name_extractor import (  # noqa: E402
    OcrLine,
    _looks_like_date_or_code,
    _merge_adjacent_lines,
    extract_product_name_from_title_photo,
)
from app.services.ocr.preprocess import (  # noqa: E402
    _CLAHE_CLIP_LIMIT,
    MAX_SIDE,
    _apply_clahe,
    _emphasize_dark_text,
    _resize,
)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_DIR / "debug_output"
DEFAULT_INPUT_DIR = SCRIPT_DIR / "debug_input"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


def _preprocess_stages(raw_bytes: bytes, mode: str) -> dict[str, np.ndarray]:
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img = _resize(img, MAX_SIDE)
    resized_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    stages = {"01_resize": resized_bgr, "02_clahe": _apply_clahe(resized_bgr, _CLAHE_CLIP_LIMIT[mode])}
    if mode == "data":
        stages["03_dark_text_filter"] = _emphasize_dark_text(stages["02_clahe"])
    return stages


def _draw_ocr_boxes(bgr: np.ndarray, ocr_lines: list[OcrLine]) -> np.ndarray:
    annotated = bgr.copy()
    for i, line in enumerate(ocr_lines):
        pts = np.array(line["box"], dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(annotated, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
        x, y = pts[0][0]
        cv2.putText(
            annotated, f"{i}:{line['confidence']:.2f}", (int(x), max(int(y) - 5, 10)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA,
        )
    return annotated


def _print_ocr_lines(ocr_lines: list[OcrLine]) -> None:
    print(f"\n--- OCR: {len(ocr_lines)} righe rilevate ---")
    for i, line in enumerate(ocr_lines):
        print(f'  [{i}] "{line["text"]}" (confidenza {line["confidence"]:.2f})')


def _print_title_decision(ocr_lines: list[OcrLine]) -> None:
    print("\n--- Decisione TITOLO ---")
    for line in ocr_lines:
        text = line["text"].strip()
        if len(text) <= 2:
            print(f'  scartata (troppo corta): "{text}"')
        elif _looks_like_date_or_code(text):
            print(f'  scartata (sembra data/codice a barre): "{text}"')
        else:
            print(f'  tenuta: "{text}"')

    candidates = [line for line in ocr_lines if len(line["text"].strip()) > 2 and not _looks_like_date_or_code(line["text"])]
    merged = _merge_adjacent_lines(candidates)
    print(f"\n  Blocchi dopo la fusione righe adiacenti ({len(merged)}):")
    for block in merged:
        print(f'    "{block["text"]}"')

    result = extract_product_name_from_title_photo(ocr_lines)
    print(f'\n  ==> Nome candidato finale: "{result["name"]}"')


def _print_date_decision(ocr_lines: list[OcrLine], today: date | None) -> None:
    lines = [line["text"] for line in ocr_lines]
    keyword_candidates, other_candidates = date_extractor._collect_candidates(lines)
    resolved_today = today or date.today()

    print("\n--- Decisione DATA ---")
    print(f"  Data di riferimento ('oggi') usata per la plausibilità: {resolved_today.isoformat()}")
    for i, line in enumerate(lines):
        has_keyword = any(kw in line.upper() for kw in date_extractor.EXPIRY_KEYWORDS)
        print(f'  [{i}] "{line}"' + ("  [keyword scadenza]" if has_keyword else ""))

    def _dump(label: str, candidates: list[date_extractor.DateCandidate]) -> None:
        print(f"\n  Candidati {label} ({len(candidates)}):")
        for c in candidates:
            plausible = date_extractor._plausible_expiry(c.value, resolved_today)
            print(f'    {c.value.isoformat()} (da "{c.source_text}") — plausibile: {plausible}')

    _dump("con keyword vicina", keyword_candidates)
    _dump("senza keyword", other_candidates)

    result = date_extractor.extract_date_candidates(lines, today=today)
    print(f"\n  ==> Data candidata finale: {result.best}")
    if result.alternatives:
        print(f"      Alternative: {result.alternatives}")


def _process_image(image_path: Path, mode: str, correggi_orientamento: bool, today: date | None,
                    out_dir: Path, engine: OcrEngine) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_bytes = image_path.read_bytes()

    stages = _preprocess_stages(raw_bytes, mode)
    for name, bgr in stages.items():
        path = out_dir / f"{name}.png"
        cv2.imwrite(str(path), bgr)
        print(f"salvata {path}")
    final_bgr = list(stages.values())[-1]

    ocr_lines = engine.run(final_bgr, correct_orientation=correggi_orientamento)

    boxes_path = out_dir / "04_ocr_boxes.png"
    cv2.imwrite(str(boxes_path), _draw_ocr_boxes(final_bgr, ocr_lines))
    print(f"salvata {boxes_path}")

    _print_ocr_lines(ocr_lines)

    if mode == "titolo":
        _print_title_decision(ocr_lines)
    else:
        _print_date_decision(ocr_lines, today)


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug della pipeline OCR su foto reali")
    parser.add_argument(
        "image_path", type=Path, nargs="?", default=DEFAULT_INPUT_DIR,
        help=f"Foto singola o cartella (default: {DEFAULT_INPUT_DIR.relative_to(SCRIPT_DIR.parent)})",
    )
    parser.add_argument("--mode", choices=["titolo", "data"], default="data")
    parser.add_argument("--correggi-orientamento", action="store_true")
    parser.add_argument(
        "--today", type=date.fromisoformat, default=None,
        help="Data di 'oggi' da usare per la plausibilità (YYYY-MM-DD), default: oggi reale",
    )
    parser.add_argument("--out-dir", type=Path, default=None, help="Solo con una foto singola")
    args = parser.parse_args()

    if args.image_path.is_dir():
        image_files = sorted(p for p in args.image_path.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        if not image_files:
            print(f"Nessuna immagine trovata in {args.image_path}")
            return
    else:
        image_files = [args.image_path]

    print("Caricamento modello OCR...")
    engine = OcrEngine()

    for image_path in image_files:
        print(f"\n{'=' * 60}\n{image_path.name}\n{'=' * 60}")
        out_dir = args.out_dir or OUTPUT_ROOT / f"{image_path.stem}_{args.mode}"
        _process_image(image_path, args.mode, args.correggi_orientamento, args.today, out_dir, engine)


if __name__ == "__main__":
    main()
