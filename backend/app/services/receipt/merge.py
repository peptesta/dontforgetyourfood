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
    both_priced = a.prezzo is not None and b.prezzo is not None
    if both_priced and abs(a.prezzo - b.prezzo) > 0.001:
        return False
    # se uno dei due prezzi manca (non letto dall'OCR) il prezzo non può confermare
    # l'identità: si chiede un nome molto più simile
    threshold = _SAME_NAME_THRESHOLD if both_priced else _SAME_NAME_THRESHOLD_NO_PRICE
    return fuzz.token_sort_ratio(a.nome, b.nome) >= threshold


# quante righe a fine/inizio foto considerare quando si cerca la sovrapposizione
_SEARCH_WINDOW = 15
# la prima riga in comune deve stare vicino all'inizio della foto successiva
_MAX_FIRST_ANCHOR_INDEX = 2
# soglia più morbida per riconoscere la riga tagliata dal bordo ("DATE DE. CERDO")
_CUT_LINE_NAME_THRESHOLD = 75


def _find_anchors(prev: list[ReceiptLine], nxt: list[ReceiptLine]) -> list[tuple[int, int]]:
    """Coppie (i, j) di righe in comune tra la coda di `prev` e la testa di `nxt`, in
    ordine crescente su entrambe (catena monotona, greedy). Non richiede che le righe
    siano contigue: l'OCR salta o legge male qualche riga proprio nella zona comune, e
    un allineamento che le pretende tutte fallirebbe al primo errore."""
    anchors: list[tuple[int, int]] = []
    last_i = max(0, len(prev) - _SEARCH_WINDOW) - 1
    for j, line in enumerate(nxt[:_SEARCH_WINDOW]):
        for i in range(last_i + 1, len(prev)):
            if same_line(prev[i], line):
                anchors.append((i, j))
                last_i = i
                break
    return anchors


def _overlap(prev: list[ReceiptLine], nxt: list[ReceiptLine]) -> tuple[int, int] | None:
    """(i, j) dell'ultima riga in comune (indice in prev, indice in nxt), o None se le due
    foto non risultano sovrapposte. Con un solo punto di contatto serve che entrambe le
    righe abbiano un prezzo (conferma indipendente dal nome); altrimenti bastano due."""
    anchors = _find_anchors(prev, nxt)
    if not anchors or anchors[0][1] > _MAX_FIRST_ANCHOR_INDEX:
        return None
    if len(anchors) == 1:
        i, j = anchors[0]
        if prev[i].prezzo is None or nxt[j].prezzo is None:
            return None
    return anchors[-1]


def _is_cut_version(partial: ReceiptLine, full: ReceiptLine) -> bool:
    """`partial` è la stessa riga di `full` letta male perché tagliata dal bordo foto:
    senza prezzo e con nome comunque simile."""
    if partial.prezzo is not None:
        return False
    # ratio (sensibile all'ordine) oltre a token_sort: con una parola mutilata ("DATE"
    # per "PATE") il riordino dei token peggiora il confronto invece di migliorarlo
    a, b = partial.nome.replace(".", ""), full.nome.replace(".", "")
    return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b)) >= _CUT_LINE_NAME_THRESHOLD


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
        overlap = _overlap(prev, lines) if prev and lines else None
        if overlap is None:
            if prev and lines:
                junctions.append(k - 1)
            merged.extend(lines)
            continue

        _, j_last = overlap
        kept = lines[j_last + 1 :]
        # l'ultima riga tenuta della foto precedente può essere una riga tagliata dal
        # bordo: se la prima nuova è la sua versione completa, si sostituisce
        if kept and merged and _is_cut_version(merged[-1], kept[0]):
            merged.pop()
        merged.extend(kept)

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
