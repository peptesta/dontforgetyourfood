import math
import re
import statistics
from dataclasses import dataclass

from app.services.ocr.name_extractor import OcrLine

# prezzo a fine riga, opzionalmente negativo, con eventuale simbolo € e lettera IVA
# finale (es. "1,09 B" negli scontrini Lidl)
_TRAILING_PRICE_RE = re.compile(r"(-?\d{1,4}[.,]\d{2})\s*(?:€|EUR)?(?:\s*[A-D])*\s*$")
# box che è solo un prezzo (con eventuale lettera IVA): serve a riconoscere i prezzi duplicati
_PRICE_ONLY_RE = re.compile(r"^-?\d{1,4}[.,]\d{2}\s*(?:€|EUR)?(?:\s*[A-D])?$")
_ANY_PRICE_RE = re.compile(r"-?\d{1,4}[.,]\d{2}")
# riga di dettaglio: "2 x 1,25", "0,350 kg 3,99 €/kg", "2 UD"
_DETAIL_RE = re.compile(r"^\s*(\d+\s*[xX]\s*\d|\d+[.,]\d{3}\s*KG|\d+\s*UD\b)", re.IGNORECASE)
_LEADING_QTY_RE = re.compile(r"^\d{1,2}\s+(?=[A-Za-zÀ-ÿ])")
_BARCODE_RE = re.compile(r"\b\d{8,14}\b")
_DATE_RE = re.compile(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}")

# sotto questa confidenza un frammento di testo senza prezzo è quasi sempre rumore
_MIN_FRAGMENT_CONFIDENCE = 0.5

_SKIP_WORDS = (
    "DESC",
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
    # quante righe dello scontrino erano questo prodotto (le ripetizioni vengono
    # fuse in una sola riga: la quantità vera si chiede all'utente nello step successivo)
    occorrenze: int = 1


def _estimate_skew(lines: list[OcrLine]) -> float:
    """Angolo (radianti) di inclinazione del testo: mediana dell'angolo del lato
    superiore di ogni box molto più largo che alto. Serve perché una foto scattata
    leggermente storta sposta i prezzi (a destra) più in alto/basso dei loro nomi
    (a sinistra), e il raggruppamento per y li assegnerebbe alla riga sbagliata."""
    angles = []
    for line in lines:
        (x0, y0), (x1, y1) = line["box"][0], line["box"][1]
        width = math.hypot(x1 - x0, y1 - y0)
        height = math.hypot(line["box"][3][0] - x0, line["box"][3][1] - y0) or 1
        if width >= 2 * height:
            angles.append(math.atan2(y1 - y0, x1 - x0))
    return statistics.median(angles) if angles else 0.0


def _group_rows(lines: list[OcrLine]) -> list[dict]:
    """Raggruppa i box OCR che stanno sulla stessa riga (stesso y centrale, dopo aver
    raddrizzato l'inclinazione) e li ordina da sinistra a destra. Come in
    name_extractor._merge_adjacent_lines, ma senza il secondo passo di unione verticale:
    sullo scontrino due righe consecutive sono due prodotti diversi, non un nome spezzato.
    I frammenti a bassa confidenza che non sono un prezzo (tipicamente la stampa del
    retro che traspare dalla carta) vengono scartati."""
    theta = _estimate_skew(lines)
    cos_t, sin_t = math.cos(-theta), math.sin(-theta)

    enriched = []
    for line in lines:
        text = line["text"].strip()
        if not text or (line["confidence"] < _MIN_FRAGMENT_CONFIDENCE and not _ANY_PRICE_RE.search(text)):
            continue
        rotated = [(x * cos_t - y * sin_t, x * sin_t + y * cos_t) for x, y in line["box"]]
        xs = [pt[0] for pt in rotated]
        ys = [pt[1] for pt in rotated]
        enriched.append({"text": text, "confidence": line["confidence"], "x0": min(xs), "y0": min(ys), "y1": max(ys)})
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
        row = _drop_lowercase_ghosts(row)
        row = _keep_best_price_box(row)
        result.append(
            {
                "text": " ".join(l["text"] for l in row),
                "confidence": min(l["confidence"] for l in row),
            }
        )
    return result


def _letters_upper_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 1.0


def _drop_lowercase_ghosts(row: list[dict]) -> list[dict]:
    """Su carta termica sottile la stampa del retro traspare specchiata e l'OCR la legge
    come testo senza senso, quasi sempre in minuscolo ("ultsnuor fislo"). Le righe
    prodotto sono in maiuscolo: se il primo box della riga lo è, si scartano i box
    successivi prevalentemente minuscoli (i prezzi e i box con cifre restano)."""
    if _letters_upper_ratio(row[0]["text"]) < 0.8:
        return row
    kept = [row[0]]
    for box in row[1:]:
        if _ANY_PRICE_RE.search(box["text"]) or _letters_upper_ratio(box["text"]) >= 0.5:
            kept.append(box)
    return kept


def _keep_best_price_box(row: list[dict]) -> list[dict]:
    """Se una riga ha più box che sono solo un prezzo, tiene quello con confidenza
    maggiore: gli altri sono di solito frammenti della riga adiacente tagliata dal bordo
    della foto (es. "2,09 D") o letture doppie. Non si applica alle righe di dettaglio
    peso/quantità, dove un secondo importo ("7,85" al kg) è legittimo."""
    if _DETAIL_RE.match(row[0]["text"]):
        return row
    price_boxes = [b for b in row if _PRICE_ONLY_RE.match(b["text"])]
    if len(price_boxes) < 2:
        return row
    best = max(price_boxes, key=lambda b: (b["confidence"], b["x0"]))
    return [b for b in row if b is best or b not in price_boxes]


def _parse_price(text: str) -> float:
    return float(text.replace(",", "."))


def _clean_name(text: str) -> str:
    text = _ANY_PRICE_RE.sub(" ", text)
    text = re.sub(r"-?\b\d{5,}\b", " ", text)  # codici articolo tipo "-0500229"
    text = re.sub(r"\b(?:EUR|EURO)\b|€", " ", text, flags=re.IGNORECASE)
    text = _LEADING_QTY_RE.sub("", text.strip())
    text = re.sub(r"[^\w\s/%.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -./")
    return text.upper()


_UNIT_SUFFIXES = {"L", "G", "KG", "ML", "CL", "GR", "UD", "UDS", "U"}


def _strip_garbled_price_tail(name: str) -> str:
    """Senza un prezzo letto, la coda può essere un prezzo mal riconosciuto ("69Z" per
    "2,69 A"): si toglie l'ultimo token cifre+lettera, salvo che sia una misura (1L, 500G)."""
    head, _, tail = name.rpartition(" ")
    match = re.fullmatch(r"\d{1,3}([A-Z])", tail)
    if head and match and match.group(1) not in _UNIT_SUFFIXES:
        return head
    return name


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
    pending: tuple[str, float] | None = None  # nome senza prezzo, in attesa di una riga dettaglio
    # le righe senza prezzo prima del primo prodotto con prezzo sono l'intestazione
    # (negozio, indirizzo, CIF) e si scartano; da lì in poi una riga con nome ma senza
    # prezzo è quasi sempre un prezzo che l'OCR non ha letto: meglio tenerla senza
    # prezzo (da verificare) che perderla in silenzio. Dalle foto successive alla prima
    # si parte già "dentro" lo scontrino.
    in_body = foto > 0 or not any_price

    def flush_pending() -> None:
        nonlocal pending
        if pending and in_body:
            products.append(ReceiptLine(nome=pending[0], prezzo=None, confidence=pending[1], foto=foto))
        pending = None

    for row in rows:
        text = row["text"]
        if not text:
            continue
        if re.search(r"(?<![A-Za-zÀ-ÿ])(?:TOTAL|TOTALE|SUBTOTAL)(?![A-Za-zÀ-ÿ])", text, re.IGNORECASE):
            flush_pending()
            break  # dal totale in poi è piè di pagina (pagamento, IVA, QR...)
        if _SKIP_RE.search(text) or _DATE_RE.search(text) or _BARCODE_RE.search(text):
            flush_pending()
            continue

        price_match = _TRAILING_PRICE_RE.search(text)
        price = _parse_price(price_match.group(1)) if price_match else None

        if _DETAIL_RE.match(text):
            if pending and price is not None and price > 0:
                products.append(ReceiptLine(nome=pending[0], prezzo=price, confidence=min(pending[1], row["confidence"]), foto=foto))
                pending = None
            # altrimenti è il dettaglio di una riga già emessa con il suo prezzo: si ignora
            continue

        if price is not None and price <= 0:
            flush_pending()
            continue

        # il nome è solo ciò che precede il prezzo (taglia anche la lettera IVA finale)
        name = _clean_name(text[: price_match.start()] if price_match else text)
        if not price_match:
            name = _strip_garbled_price_tail(name)
        if not _is_name(name):
            flush_pending()
            continue

        flush_pending()
        if price is not None:
            in_body = True
            products.append(ReceiptLine(nome=name, prezzo=price, confidence=row["confidence"], foto=foto))
        elif any_price:
            pending = (name, row["confidence"])
        else:
            products.append(ReceiptLine(nome=name, prezzo=None, confidence=row["confidence"], foto=foto))

    flush_pending()
    return products
