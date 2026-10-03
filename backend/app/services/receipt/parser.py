import re
from dataclasses import dataclass

from app.services.ocr.name_extractor import OcrLine

# prezzo a fine riga, opzionalmente negativo, con eventuale simbolo € e lettera IVA
# finale (es. "1,09 B" negli scontrini Lidl)
_TRAILING_PRICE_RE = re.compile(r"(-?\d{1,4}[.,]\d{2})\s*(?:€|EUR)?\s*(?:[A-D])?\s*$")
_ANY_PRICE_RE = re.compile(r"-?\d{1,4}[.,]\d{2}")
# riga di dettaglio: "2 x 1,25", "0,350 kg 3,99 €/kg", "2 UD"
_DETAIL_RE = re.compile(r"^\s*(\d+\s*[xX]\s*\d|\d+[.,]\d{3}\s*KG|\d+\s*UD\b)", re.IGNORECASE)
_LEADING_QTY_RE = re.compile(r"^\d{1,2}\s+(?=[A-Za-zÀ-ÿ])")
_BARCODE_RE = re.compile(r"\b\d{8,14}\b")
_DATE_RE = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")

_SKIP_WORDS = (
    "TOTAL", "TOTALE", "SUBTOTAL", "IVA", "I.V.A", "TARJETA", "EFECTIVO", "CAMBIO", "ENTREGADO",
    "ENTREGA", "ARTICULOS", "ARTÍCULOS", "CIF", "NIF", "TEL", "TELEFONO", "TELÉFONO", "FACTURA",
    "SIMPLIFICADA", "TICKET", "GRACIAS", "DESCRIPCION", "DESCRIPCIÓN", "IMPORTE", "P. UNIT",
    "VISA", "MASTERCARD", "MAESTRO", "AUTORIZACION", "AUTORIZACIÓN", "OPERACION", "OPERACIÓN",
    "BASE IMPONIBLE", "CUOTA", "FECHA", "HORA", "CAJA", "TIENDA", "CAJERO", "DEVOLUCION",
    "DEVOLUCIÓN", "PAGO", "BIZUM", "DTO", "DESCUENTO", "OFERTA", "PROMOCION", "PROMOCIÓN",
    "CONTANTI", "RESTO", "SCONTRINO", "CARTA", "PAGAMENTO", "DOCUMENTO", "COMMERCIALE",
)
_SKIP_RE = re.compile(r"(?<![A-Za-zÀ-ÿ])(?:" + "|".join(re.escape(w) for w in _SKIP_WORDS) + r")(?![A-Za-zÀ-ÿ])", re.IGNORECASE)


@dataclass
class ReceiptLine:
    nome: str
    prezzo: float | None
    confidence: float
    foto: int = 0
    possibile_doppione: bool = False


def _group_rows(lines: list[OcrLine]) -> list[dict]:
    """Raggruppa i box OCR che stanno sulla stessa riga (stesso y centrale) e li ordina
    da sinistra a destra. Come in name_extractor._merge_adjacent_lines, ma senza il
    secondo passo di unione verticale: sullo scontrino due righe consecutive sono due
    prodotti diversi, non un nome spezzato."""
    enriched = []
    for line in lines:
        xs = [pt[0] for pt in line["box"]]
        ys = [pt[1] for pt in line["box"]]
        enriched.append(
            {"text": line["text"].strip(), "confidence": line["confidence"], "x0": min(xs), "y0": min(ys), "y1": max(ys)}
        )
    enriched.sort(key=lambda l: (l["y0"] + l["y1"]) / 2)

    rows: list[list[dict]] = []
    for item in enriched:
        y_center = (item["y0"] + item["y1"]) / 2
        height = item["y1"] - item["y0"]
        if rows:
            last = rows[-1]
            last_center = sum((l["y0"] + l["y1"]) / 2 for l in last) / len(last)
            last_height = sum(l["y1"] - l["y0"] for l in last) / len(last)
            if abs(y_center - last_center) <= 0.5 * max(height, last_height):
                last.append(item)
                continue
        rows.append([item])

    result = []
    for row in rows:
        row.sort(key=lambda l: l["x0"])
        result.append(
            {
                "text": " ".join(l["text"] for l in row if l["text"]),
                "confidence": min(l["confidence"] for l in row),
            }
        )
    return result


def _parse_price(text: str) -> float:
    return float(text.replace(",", "."))


def _clean_name(text: str) -> str:
    text = _ANY_PRICE_RE.sub(" ", text)
    text = _LEADING_QTY_RE.sub("", text.strip())
    text = re.sub(r"[^\w\s/%.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -./")
    return text.upper()


def _is_name(name: str) -> bool:
    return sum(c.isalpha() for c in name) >= 3


def parse_receipt_photo(ocr_lines: list[OcrLine], foto: int = 0) -> list[ReceiptLine]:
    """Da righe OCR grezze di una foto a righe prodotto (nome, prezzo).

    Una riga è un prodotto se ha un nome con almeno 3 lettere e un prezzo a destra;
    totali, IVA, pagamento, intestazione, righe quantità/peso e barcode sono scartati.
    Caso Mercadona a peso: il nome sta su una riga senza prezzo e il prezzo sulla riga
    di dettaglio successiva ("0,350 kg 3,99 €/kg 1,40"), che vengono riunite.
    Se in tutta la foto non c'è nessun prezzo (l'utente ha inquadrato solo i nomi) si
    ricade su "ogni riga con testo è un prodotto", con prezzo None."""
    rows = _group_rows(ocr_lines)
    any_price = any(_TRAILING_PRICE_RE.search(r["text"]) for r in rows)

    products: list[ReceiptLine] = []
    pending: tuple[str, float] | None = None  # nome senza prezzo in attesa di una riga dettaglio

    for row in rows:
        text = row["text"]
        if not text or _SKIP_RE.search(text) or _DATE_RE.search(text) or _BARCODE_RE.search(text):
            pending = None
            continue

        price_match = _TRAILING_PRICE_RE.search(text)
        price = _parse_price(price_match.group(1)) if price_match else None

        if _DETAIL_RE.match(text):
            if pending and price is not None and price > 0:
                products.append(ReceiptLine(nome=pending[0], prezzo=price, confidence=min(pending[1], row["confidence"]), foto=foto))
            pending = None
            continue

        if price is not None and price <= 0:
            pending = None
            continue

        # il nome è solo ciò che precede il prezzo (taglia anche la lettera IVA finale)
        name = _clean_name(text[: price_match.start()] if price_match else text)
        if not _is_name(name):
            pending = None
            continue

        if price is not None:
            products.append(ReceiptLine(nome=name, prezzo=price, confidence=row["confidence"], foto=foto))
            pending = None
        elif any_price:
            pending = (name, row["confidence"])
        else:
            products.append(ReceiptLine(nome=name, prezzo=None, confidence=row["confidence"], foto=foto))

    return products
