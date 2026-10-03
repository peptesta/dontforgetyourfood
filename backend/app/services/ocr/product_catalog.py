import json
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "product_catalog_es.json"

# sopra questa soglia (0-100, punteggio rapidfuzz) il suggerimento viene considerato
# abbastanza affidabile da mostrare in Review; sotto, si preferisce non suggerire nulla
# piuttosto che proporre un match rumoroso.
MATCH_SCORE_THRESHOLD = 80.0


@lru_cache(maxsize=1)
def load_catalog_products() -> list[dict]:
    """Carica una volta per processo worker (stesso pattern con cui workers/pool.py
    carica OcrEngine) le voci complete del catalogo (brand, name e, in futuro, `fresco`).
    Se il catalogo non è stato ancora generato (scripts/fetch_product_catalog.py non
    eseguito) il matching è semplicemente disattivato, non un errore fatale."""
    if not CATALOG_PATH.exists():
        return []
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [p for p in data.get("products", []) if product_label(p)]


def product_label(product: dict) -> str:
    return f"{product.get('brand', '')} {product.get('name', '')}".strip()


def _load_catalog_entries() -> list[str]:
    """Elenco "brand nome" usato come spazio di ricerca fuzzy."""
    return [product_label(p) for p in load_catalog_products()]


def suggest_product_name(
    candidate: str,
    confidence: float | None,
    threshold: float = 0.6,
    entries: list[str] | None = None,
) -> str | None:
    """Se la confidenza OCR sul titolo è sotto soglia, cerca nel catalogo prodotti
    Lidl/Mercadona (vedi scripts/fetch_product_catalog.py) la voce più simile a
    `candidate` e la ritorna come suggerimento — mai applicato automaticamente, va
    mostrato in Review come suggerimento cliccabile (vedi ReviewPage). `entries` è
    parametrizzabile per i test; nell'uso reale viene caricato dal catalogo su disco."""
    if confidence is not None and confidence >= threshold:
        return None
    if not candidate or not candidate.strip():
        return None

    if entries is None:
        entries = _load_catalog_entries()
    if not entries:
        return None

    match = process.extractOne(candidate, entries, scorer=fuzz.WRatio)
    if match is None:
        return None
    label, score, _ = match
    if score < MATCH_SCORE_THRESHOLD:
        return None
    return label
