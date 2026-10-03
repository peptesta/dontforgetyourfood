from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.services.receipt.parser import ReceiptLine

# similarità minima (0-100) tra due nomi riga per considerarli "la stessa riga" letta
# due volte; il prezzo uguale è la vera conferma, il nome tollera i piccoli errori OCR.
_SAME_NAME_THRESHOLD = 85
# senza prezzo (foto di soli nomi) la sola somiglianza del nome deve essere più alta
_SAME_NAME_THRESHOLD_NO_PRICE = 92
# quante righe indietro cercare un doppione residuo dopo il merge
_DUPLICATE_WINDOW = 2


@dataclass
class MergeResult:
    lines: list[ReceiptLine]
    # indice k della foto dopo cui manca la sovrapposizione con la foto k+1
    giunture_senza_sovrapposizione: list[int] = field(default_factory=list)


def same_line(a: ReceiptLine, b: ReceiptLine) -> bool:
    """Due righe sono la stessa se hanno lo stesso prezzo e nomi simili. Stesso nome
    ma prezzo diverso NON è lo stesso prodotto (es. offerta vs prezzo pieno)."""
    if (a.prezzo is None) != (b.prezzo is None):
        return False
    if a.prezzo is not None and abs(a.prezzo - b.prezzo) > 0.001:
        return False
    threshold = _SAME_NAME_THRESHOLD if a.prezzo is not None else _SAME_NAME_THRESHOLD_NO_PRICE
    return fuzz.token_sort_ratio(a.nome, b.nome) >= threshold


def _overlap_length(prev: list[ReceiptLine], nxt: list[ReceiptLine]) -> int:
    """Lunghezza del più lungo suffisso di `prev` che coincide con un prefisso di `nxt`.
    Con L >= 3 si tollera una riga diversa ai due estremi della sovrapposizione (la
    riga tagliata dal bordo della foto viene letta male); con L < 3 serve match esatto."""
    for length in range(min(len(prev), len(nxt)), 0, -1):
        pairs = [(prev[len(prev) - length + i], nxt[i]) for i in range(length)]
        mismatches = [i for i, (a, b) in enumerate(pairs) if not same_line(a, b)]
        if not mismatches:
            return length
        if length >= 3 and len(mismatches) == 1 and mismatches[0] in (0, length - 1):
            return length
    return 0


def merge_photos(photos: list[list[ReceiptLine]]) -> MergeResult:
    """Unisce le righe delle foto (in ordine di scatto) eliminando la sovrapposizione
    tra foto consecutive, poi segnala i doppioni rimasti vicini."""
    merged: list[ReceiptLine] = []
    junctions: list[int] = []

    for k, lines in enumerate(photos):
        for line in lines:
            line.foto = k
        if k == 0:
            merged.extend(lines)
            continue
        prev = photos[k - 1]
        overlap = _overlap_length(prev, lines) if prev and lines else 0
        if overlap == 0 and prev and lines:
            junctions.append(k - 1)
        merged.extend(lines[overlap:])

    return MergeResult(lines=_flag_nearby_duplicates(merged), giunture_senza_sovrapposizione=junctions)


def _flag_nearby_duplicates(lines: list[ReceiptLine]) -> list[ReceiptLine]:
    """Sullo scontrino lo stesso prodotto non compare due volte (cambia la quantità):
    una riga uguale a una delle precedenti vicine è con ogni probabilità la stessa riga
    letta due volte. Si tiene una sola copia e la si marca `possibile_doppione`, così
    l'utente può verificarla invece di perderla in silenzio."""
    kept: list[ReceiptLine] = []
    for line in lines:
        duplicate_of = next((k for k in kept[-_DUPLICATE_WINDOW:] if same_line(k, line)), None)
        if duplicate_of is not None:
            duplicate_of.possibile_doppione = True
            continue
        kept.append(line)
    return kept
