import re
from typing import TypedDict

BARCODE_RE = re.compile(r"^\d{8,14}$")
DATE_LIKE_RE = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")


class OcrLine(TypedDict):
    text: str
    confidence: float
    box: list[list[float]]  # 4 punti [x, y]


class NameExtractionResult(TypedDict):
    name: str | None
    raw_text: str


def _looks_like_date_or_code(text: str) -> bool:
    stripped = text.strip()
    return bool(BARCODE_RE.match(stripped) or DATE_LIKE_RE.search(stripped))


def _bbox(line: OcrLine) -> tuple[float, float, float, float]:
    xs = [pt[0] for pt in line["box"]]
    ys = [pt[1] for pt in line["box"]]
    return min(xs), min(ys), max(xs), max(ys)


def _merge_adjacent_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """Unisce righe vicine (es. nomi prodotto su più parole/righe) in due passi:

    1. Raggruppa i box che condividono la stessa riga (y_center vicini) e li ordina
       da sinistra a destra — necessario perché due box sulla stessa riga possono
       avere y0 leggermente diversi (rumore del detector di 1-2px) e un ordinamento
       ingenuo per solo y0 può invertirne l'ordine di lettura.
    2. Unisce righe consecutive verticalmente vicine e di altezza simile (nomi su
       più righe, es. "BARILLA" / "PASTA INTEGRALE").
    """
    if not lines:
        return []

    enriched = []
    for line in lines:
        x0, y0, x1, y1 = _bbox(line)
        enriched.append({"text": line["text"], "confidence": line["confidence"], "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    enriched.sort(key=lambda l: (l["y0"] + l["y1"]) / 2)

    rows: list[list[dict]] = []
    for line in enriched:
        y_center = (line["y0"] + line["y1"]) / 2
        height = line["y1"] - line["y0"]
        if rows:
            last_row = rows[-1]
            last_y_center = sum((l["y0"] + l["y1"]) / 2 for l in last_row) / len(last_row)
            last_height = sum(l["y1"] - l["y0"] for l in last_row) / len(last_row)
            if abs(y_center - last_y_center) <= 0.5 * max(height, last_height):
                last_row.append(line)
                continue
        rows.append([line])

    row_blocks = []
    for row in rows:
        row.sort(key=lambda l: l["x0"])
        row_blocks.append(
            {
                "text": " ".join(l["text"] for l in row),
                "confidence": min(l["confidence"] for l in row),
                "x0": min(l["x0"] for l in row),
                "y0": min(l["y0"] for l in row),
                "x1": max(l["x1"] for l in row),
                "y1": max(l["y1"] for l in row),
            }
        )

    merged = [row_blocks[0]]
    for block in row_blocks[1:]:
        current = merged[-1]
        gap = block["y0"] - current["y1"]
        height_a, height_b = current["y1"] - current["y0"], block["y1"] - block["y0"]
        max_height = max(height_a, height_b) or 1
        height_ratio = min(height_a, height_b) / max_height
        x_overlap = min(current["x1"], block["x1"]) - max(current["x0"], block["x0"])
        horizontally_close = x_overlap > -max_height  # tollera un piccolo disallineamento

        if gap <= max_height * 0.6 and height_ratio >= 0.5 and horizontally_close:
            current["text"] = f"{current['text']} {block['text']}"
            current["confidence"] = min(current["confidence"], block["confidence"])
            current["x0"] = min(current["x0"], block["x0"])
            current["y0"] = min(current["y0"], block["y0"])
            current["x1"] = max(current["x1"], block["x1"])
            current["y1"] = max(current["y1"], block["y1"])
        else:
            merged.append(block)

    return [
        {
            "text": m["text"],
            "confidence": m["confidence"],
            "box": [[m["x0"], m["y0"]], [m["x1"], m["y0"]], [m["x1"], m["y1"]], [m["x0"], m["y1"]]],
        }
        for m in merged
    ]


def extract_product_name(ocr_lines: list[OcrLine]) -> NameExtractionResult:
    if not ocr_lines:
        return {"name": None, "raw_text": ""}

    raw_text = "\n".join(line["text"] for line in ocr_lines)

    candidates = [
        line
        for line in ocr_lines
        if len(line["text"].strip()) > 2 and not _looks_like_date_or_code(line["text"])
    ]
    if not candidates:
        return {"name": None, "raw_text": raw_text}

    merged = _merge_adjacent_lines(candidates)

    all_y = [pt[1] for line in ocr_lines for pt in line["box"]]
    img_height = max(all_y) if all_y else 1

    scored = []
    for line in merged:
        x0, y0, x1, y1 = _bbox(line)
        area = (x1 - x0) * (y1 - y0)
        y_center = (y0 + y1) / 2
        scored.append({"text": line["text"].strip(), "confidence": line["confidence"], "area": area, "y_norm": y_center / img_height})

    max_area = max(c["area"] for c in scored) or 1
    for c in scored:
        area_norm = c["area"] / max_area
        c["score"] = 0.6 * area_norm + 0.3 * c["confidence"] + 0.1 * (1 - c["y_norm"])

    scored.sort(key=lambda c: c["score"], reverse=True)
    return {"name": scored[0]["text"], "raw_text": raw_text}


def extract_product_name_from_title_photo(ocr_lines: list[OcrLine]) -> NameExtractionResult:
    """Variante per una foto dedicata SOLO al titolo (cattura a due foto): non serve
    più disambiguare tra il nome e il resto del packaging (logo, ingredienti, promo),
    quindi invece di scegliere la riga con punteggio più alto si concatenano in ordine
    di lettura tutti i blocchi di testo rimasti dopo il filtro data/codice a barre."""
    if not ocr_lines:
        return {"name": None, "raw_text": ""}

    raw_text = "\n".join(line["text"] for line in ocr_lines)

    candidates = [
        line
        for line in ocr_lines
        if len(line["text"].strip()) > 2 and not _looks_like_date_or_code(line["text"])
    ]
    if not candidates:
        return {"name": None, "raw_text": raw_text}

    merged = _merge_adjacent_lines(candidates)  # già in ordine di lettura top-to-bottom
    name = " ".join(block["text"].strip() for block in merged if block["text"].strip())
    return {"name": name or None, "raw_text": raw_text}
